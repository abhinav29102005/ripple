"""
Benchmark script for Ripple (Milestone M7 / Track 02 Proof).
Spawns 16 worker processes executing 500 tasks across FalkorDB with
20 concurrent tenant memory reads.
Calculates double claims, throughput (tasks/sec), and p50/p95 claim latency.
Saves results to bench/latest.json.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import statistics
import multiprocessing as mp
from collections import Counter
from falkordb import FalkorDB
from coord import CoordEngine
from graph import graph_manager
from memory import TenantMemory

def _bench_worker(worker_id: int, total_tasks: int, out_queue: mp.Queue):
    from config import settings
    kwargs = {}
    if settings.falkordb_username:
        kwargs["username"] = settings.falkordb_username
    if settings.falkordb_password:
        kwargs["password"] = settings.falkordb_password
    db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port, **kwargs)
    coord = CoordEngine(db.select_graph("coord"))
    agent_id = f"bench_worker_{worker_id:02d}"
    coord.register_agent(agent_id, "benchmark_worker")

    claimed_ids = []
    latencies = []

    while True:
        t0 = time.perf_counter()
        task = coord.claim_task(agent_id, task_type="bench_task", lease_seconds=30)
        t1 = time.perf_counter()

        latencies.append((t1 - t0) * 1000.0) # ms

        if not task:
            # Check if any remain
            res = coord.graph.query("MATCH (t:Task {status: 'queued', type: 'bench_task'}) RETURN count(t)")
            rem = res.result_set[0][0] if res.result_set else 0
            if rem == 0:
                break
            time.sleep(0.01)
            continue

        task_id = task["id"]
        claimed_ids.append(task_id)

        # Complete task
        coord.complete_task(task_id, agent_id, {"worker": agent_id, "ts": time.time()})

    out_queue.put({
        "worker_id": worker_id,
        "claimed_ids": claimed_ids,
        "latencies": latencies,
    })

def _tenant_reader(tenant_id: int, stop_event: mp.Event):
    from config import settings
    kwargs = {}
    if settings.falkordb_username:
        kwargs["username"] = settings.falkordb_username
    if settings.falkordb_password:
        kwargs["password"] = settings.falkordb_password
    db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port, **kwargs)
    mem = TenantMemory(f"bench_tenant_{tenant_id:02d}")
    while not stop_event.is_set():
        try:
            mem.get_active_rules()
            mem.get_facts()
            time.sleep(0.05)
        except Exception:
            pass

def run_benchmark(num_tasks: int = 500, num_workers: int = 16, num_tenants: int = 20, out_file: str = "bench/latest.json") -> Dict[str, Any]:
    print(f"=== Starting Ripple Benchmark ({num_workers} workers, {num_tasks} tasks, {num_tenants} concurrent tenant graphs) ===")

    # Initialize coord schema
    coord = CoordEngine(graph_manager.get_graph("coord"))
    coord.graph.query("MATCH (t:Task {type: 'bench_task'}) DELETE t")

    # Seed 20 tenant graphs with background facts
    print(f"Seeding {num_tenants} tenant memory graphs...")
    for t in range(num_tenants):
        mem = TenantMemory(f"bench_tenant_{t:02d}")
        mem.set_fact("authority", f"Clinical Council {t}")
        mem.save_rule(f"rule_{t}", "reason", "error", -0.2, 5, 0.9, f"Test rule {t}")

    # Seed 500 bench tasks in batches
    print(f"Seeding {num_tasks} tasks into FalkorDB task queue...")
    now = int(time.time())
    batch = []
    for i in range(num_tasks):
        batch.append({
            "id": f"bench_{i:04d}",
            "key": f"bench:{i:04d}",
            "type": "bench_task",
            "status": "queued",
            "priority": i % 5,
            "created": now + i,
            "lease_until": 0,
            "attempts": 0,
            "max_attempts": 3,
            "payload": f'{{"index": {i}}}',
        })
        if len(batch) >= 50 or i == num_tasks - 1:
            coord.graph.query("""
            UNWIND $batch AS p
            CREATE (t:Task {
                id: p.id, key: p.key, type: p.type, status: p.status,
                priority: p.priority, created: p.created, lease_until: p.lease_until,
                attempts: p.attempts, max_attempts: p.max_attempts, payload: p.payload
            })
            """, {"batch": batch})
            batch = []

    # Start background tenant readers
    ctx = mp.get_context("spawn")
    stop_event = ctx.Event()
    readers = [ctx.Process(target=_tenant_reader, args=(t, stop_event)) for t in range(num_tenants)]
    for r in readers:
        r.start()

    # Launch 16 worker processes
    print(f"Launching {num_workers} concurrent worker processes...")
    out_queue = ctx.Queue()
    workers = [ctx.Process(target=_bench_worker, args=(w, num_tasks, out_queue)) for w in range(num_workers)]

    start_time = time.perf_counter()
    for w in workers:
        w.start()

    worker_results = []
    for _ in range(num_workers):
        worker_results.append(out_queue.get())

    for w in workers:
        w.join()

    total_duration = time.perf_counter() - start_time

    # Stop readers
    stop_event.set()
    for r in readers:
        r.join()

    # Aggregate metrics
    all_claimed = []
    all_latencies = []
    for r in worker_results:
        all_claimed.extend(r["claimed_ids"])
        all_latencies.extend(r["latencies"])

    counts = Counter(all_claimed)
    double_claims = sum(1 for _, c in counts.items() if c > 1)
    completed_count = len(counts)
    throughput = completed_count / total_duration if total_duration > 0 else 0.0

    all_latencies.sort()
    p50_latency = statistics.median(all_latencies) if all_latencies else 0.0
    p95_latency = all_latencies[int(len(all_latencies) * 0.95)] if all_latencies else 0.0

    # DB status check
    db_done_res = coord.graph.query("MATCH (t:Task {type: 'bench_task', status: 'done'}) RETURN count(t)")
    db_done = db_done_res.result_set[0][0] if db_done_res.result_set else 0

    results = {
        "benchmark": "Ripple FalkorDB Coordination & Memory Throughput",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tasks": num_tasks,
        "completed_tasks": completed_count,
        "db_verified_done": db_done,
        "workers": num_workers,
        "concurrent_tenant_graphs": num_tenants,
        "duration_seconds": round(total_duration, 3),
        "throughput_tasks_per_sec": round(throughput, 1),
        "double_claims": double_claims,
        "claim_latency_p50_ms": round(p50_latency, 2),
        "claim_latency_p95_ms": round(p95_latency, 2),
        "pass": double_claims == 0 and completed_count == num_tasks,
    }

    print("\n=== Benchmark Results ===")
    print(f"Total Tasks: {num_tasks}")
    print(f"Completed Tasks: {completed_count}")
    print(f"Double Claims: {double_claims} (Hard Requirement: 0)")
    print(f"Throughput: {results['throughput_tasks_per_sec']} tasks/sec")
    print(f"Claim Latency: p50={results['claim_latency_p50_ms']} ms, p95={results['claim_latency_p95_ms']} ms")
    print(f"Duration: {results['duration_seconds']}s")
    print(f"Verdict: {'PASS' if results['pass'] else 'FAIL'}")

    os.makedirs("bench", exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=500)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--tenants", type=int, default=20)
    parser.add_argument("--out", type=str, default="bench/latest.json")
    args = parser.parse_args()
    run_benchmark(num_tasks=args.tasks, num_workers=args.workers, num_tenants=args.tenants, out_file=args.out)
