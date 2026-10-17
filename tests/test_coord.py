"""
Unit and concurrency tests for FalkorDB-native coordination engine (coord.py).
Tests:
- Dependency gating
- Failure and max_attempts retry
- Lease expiry and auto-reclaim
- 16 concurrent workers on 500 tasks with zero double-claims
- Worker crash mid-execution followed by lease reclaim and completion
"""
import time
import os
import signal
import multiprocessing as mp
from collections import Counter
import pytest
from coord import CoordEngine
from graph import graph_manager

@pytest.fixture(autouse=True)
def clean_coord_graph():
    graph_manager.delete_graph("test_coord")
    g = graph_manager.get_graph("test_coord")
    graph_manager.init_coord_schema()
    yield
    graph_manager.delete_graph("test_coord")

def test_dependency_gating():
    coord = CoordEngine(graph_manager.get_graph("test_coord"))
    
    # Spawn parent task A and dependent task B
    id_a = coord.spawn_task("ingest", {"source": "notice_1"}, key="ingest:1")
    id_b = coord.spawn_task("trace", {"source": "notice_1"}, key="trace:1", depends_on_keys=["ingest:1"])

    # Attempt to claim "trace" before "ingest" is done -> must be None
    claimed_trace = coord.claim_task("worker_trace", task_type="trace")
    assert claimed_trace is None, "Dependent task was claimed before prerequisite finished!"

    # Claim and complete parent task A
    claimed_a = coord.claim_task("worker_ingest", task_type="ingest")
    assert claimed_a is not None
    assert claimed_a["id"] == id_a
    assert coord.complete_task(id_a, "worker_ingest", {"status": "ingested"})

    # Now dependent task B must be claimable
    claimed_b = coord.claim_task("worker_trace", task_type="trace")
    assert claimed_b is not None
    assert claimed_b["id"] == id_b
    assert coord.complete_task(id_b, "worker_trace", {"status": "traced"})

def test_task_fail_and_max_attempts():
    coord = CoordEngine(graph_manager.get_graph("test_coord"))
    
    task_id = coord.spawn_task("flaky", {"count": 1}, max_attempts=2)

    # First attempt: claim and fail
    t1 = coord.claim_task("worker_1", task_type="flaky")
    assert t1 is not None
    assert t1["attempts"] == 1
    new_status = coord.fail_task(task_id, "worker_1", "Transient network error")
    assert new_status == "queued"

    # Second attempt: claim and fail
    t2 = coord.claim_task("worker_2", task_type="flaky")
    assert t2 is not None
    assert t2["attempts"] == 2
    new_status = coord.fail_task(task_id, "worker_2", "Fatal error")
    assert new_status == "failed"

    # Verify task in db
    task = coord.get_task(task_id)
    assert task["status"] == "failed"
    assert task["attempts"] == 2
    assert "Fatal error" in task["error"]

def test_lease_expiry_and_reclaim():
    coord = CoordEngine(graph_manager.get_graph("test_coord"))
    
    task_id = coord.spawn_task("slow", {"job": "render"})
    # Claim with 1-second lease
    claimed = coord.claim_task("worker_slow", task_type="slow", lease_seconds=1)
    assert claimed is not None

    # Immediate reclaim: lease has not expired yet
    reclaimed = coord.reclaim_expired_leases()
    assert reclaimed == 0

    # Wait for lease to expire
    time.sleep(2.0)
    reclaimed = coord.reclaim_expired_leases()
    assert reclaimed == 1

    # Should be back in queue and claimable again
    reclaimed_task = coord.claim_task("worker_fast", task_type="slow")
    assert reclaimed_task is not None
    assert reclaimed_task["id"] == task_id
    assert coord.complete_task(task_id, "worker_fast", {"done": True})

def _multi_worker_runner(worker_num, total_expected, out_queue):
    from falkordb import FalkorDB
    from coord import CoordEngine
    db = FalkorDB(host="localhost", port=6379)
    coord = CoordEngine(db.select_graph("test_coord"))
    agent_id = f"worker_{worker_num}"
    coord.register_agent(agent_id, "dummy_worker")
    
    processed = []
    while True:
        task = coord.claim_task(agent_id, task_type="batch_dummy", lease_seconds=20)
        if not task:
            # Check remaining
            res = coord.graph.query("MATCH (t:Task {status: 'queued', type: 'batch_dummy'}) RETURN count(t)")
            remaining = res.result_set[0][0] if res.result_set else 0
            if remaining == 0:
                break
            time.sleep(0.01)
            continue

        coord.complete_task(task["id"], agent_id, {"worker": agent_id, "idx": task["payload"]["i"]})
        processed.append(task["id"])

    out_queue.put(processed)

def test_16_workers_500_tasks_zero_double_claims():
    coord = CoordEngine(graph_manager.get_graph("test_coord"))
    total_tasks = 500

    now = int(time.time())
    batch = []
    for i in range(total_tasks):
        batch.append({
            "id": f"t_{i:04d}",
            "key": f"batch_dummy:{i:04d}",
            "type": "batch_dummy",
            "status": "queued",
            "priority": i % 4,
            "created": now + i,
            "lease_until": 0,
            "attempts": 0,
            "max_attempts": 3,
            "payload": f'{{"i": {i}}}'
        })
        if len(batch) >= 50 or i == total_tasks - 1:
            coord.graph.query("""
            UNWIND $batch AS p
            CREATE (t:Task {
                id: p.id, key: p.key, type: p.type, status: p.status,
                priority: p.priority, created: p.created, lease_until: p.lease_until,
                attempts: p.attempts, max_attempts: p.max_attempts, payload: p.payload
            })
            """, {"batch": batch})
            batch = []

    num_workers = 16
    ctx = mp.get_context("spawn")
    out_queue = ctx.Queue()
    workers = [ctx.Process(target=_multi_worker_runner, args=(w, total_tasks, out_queue)) for w in range(num_workers)]
    for w in workers:
        w.start()

    all_completed = []
    for _ in range(num_workers):
        all_completed.extend(out_queue.get())

    for w in workers:
        w.join()

    counts = Counter(all_completed)
    double_claims = [t_id for t_id, cnt in counts.items() if cnt > 1]
    assert len(double_claims) == 0, f"Double claims detected: {double_claims}"
    assert len(counts) == total_tasks, f"Expected {total_tasks} completed tasks, got {len(counts)}"

    # Check all are done in DB
    res = coord.graph.query("MATCH (t:Task {type: 'batch_dummy'}) RETURN t.status, count(t)")
    status_counts = dict(res.result_set)
    assert status_counts.get("done") == total_tasks

def _crash_worker(task_id, ready_event):
    from falkordb import FalkorDB
    from coord import CoordEngine
    db = FalkorDB(host="localhost", port=6379)
    coord = CoordEngine(db.select_graph("test_coord"))
    # Claim with a 1-second lease, signal ready, then simulate crash (exit immediately without completing)
    task = coord.claim_task("crashed_agent", task_type="crash_test", lease_seconds=1)
    if task:
        ready_event.set()
        # Worker abruptly dies here
        os._exit(0)

def test_worker_killed_leads_to_reclaim_and_completion():
    coord = CoordEngine(graph_manager.get_graph("test_coord"))
    task_id = coord.spawn_task("crash_test", {"item": 99})

    ctx = mp.get_context("spawn")
    ready_event = ctx.Event()
    p = ctx.Process(target=_crash_worker, args=(task_id, ready_event))
    p.start()
    ready_event.wait(timeout=5.0)
    p.join()

    # The task was claimed by crashed_agent
    task_status = coord.get_task(task_id)
    assert task_status["status"] == "claimed"
    assert task_status["claimed_by"] == "crashed_agent"

    # Wait for the 1-second lease to expire
    time.sleep(2.0)

    # Reclaim
    reclaimed = coord.reclaim_expired_leases()
    assert reclaimed >= 1

    # Task should be back to queued
    task_status = coord.get_task(task_id)
    assert task_status["status"] == "queued"
    assert task_status["claimed_by"] is None

    # Healthy worker claims and finishes it
    healthy = coord.claim_task("healthy_agent", task_type="crash_test")
    assert healthy is not None
    assert healthy["id"] == task_id
    assert coord.complete_task(task_id, "healthy_agent", {"result": "recovered"})

    task_status = coord.get_task(task_id)
    assert task_status["status"] == "done"
    assert task_status["result"]["result"] == "recovered"
