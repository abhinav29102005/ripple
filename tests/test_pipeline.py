"""
End-to-end pipeline test for Milestone M2:
Submitting a retraction runs ingest -> trace -> quantify -> brief
through FalkorDB-coordinated workers and stores Impact nodes.
"""
import pytest
from graph import graph_manager
from coord import CoordEngine
from knowledge import KnowledgeEngine
from scripts.seed_synthetic import seed_synthetic_data
from agents.watcher import WatcherHandler
from agents.tracer import TracerHandler
from agents.statistician import StatisticianHandler
from agents.briefer import BrieferHandler

@pytest.fixture(scope="module", autouse=True)
def setup_graphs():
    graph_manager.delete_graph("knowledge")
    graph_manager.delete_graph("coord")
    graph_manager.init_knowledge_schema()
    graph_manager.init_coord_schema()
    seed_synthetic_data(scale="standard", seed=42)
    yield

def test_full_retraction_pipeline():
    coord = CoordEngine(graph_manager.get_graph("coord"))
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))

    watcher = WatcherHandler(knowledge, coord)
    tracer = TracerHandler(knowledge, coord)
    statistician = StatisticianHandler(knowledge)
    briefer = BrieferHandler(knowledge)

    # 1. Trigger pipeline with an ingest task
    target_ret_id = "SYN-RET-001"
    target_trial_id = "SYN-TR-0001"
    ingest_key = f"ingest:{target_ret_id}"

    ingest_task_id = coord.spawn_task(
        task_type="ingest",
        payload={
            "retraction_id": target_ret_id,
            "trial_id": target_trial_id,
            "reason": "Data fabrication in baseline characteristic tables",
            "reason_category": "fabrication",
            "notice_url": "https://example.org/retractions/syn-ret-001",
        },
        key=ingest_key,
    )

    # 2. Watcher claims and handles ingest
    task = coord.claim_task("worker_watcher", task_type="ingest")
    assert task is not None
    assert task["id"] == ingest_task_id
    res = watcher.handle(task["payload"])
    assert coord.complete_task(task["id"], "worker_watcher", res)

    # 3. Tracer claims and handles trace
    task = coord.claim_task("worker_tracer", task_type="trace")
    assert task is not None
    assert task["key"] == f"trace:{target_ret_id}"
    res = tracer.handle(task["payload"])
    affected_reviews = res["affected_reviews"]
    assert len(affected_reviews) > 0, "Expected at least one review affected by the trial"
    assert coord.complete_task(task["id"], "worker_tracer", res)

    # 4. Briefer should NOT be claimable yet because quantify tasks are pending!
    brief_premature = coord.claim_task("worker_briefer", task_type="brief")
    assert brief_premature is None, "Briefer task claimed before all quantify tasks finished!"

    # 5. Statistician processes each quantify task
    quantify_processed = 0
    while True:
        task = coord.claim_task("worker_stat", task_type="quantify")
        if not task:
            break
        res = statistician.handle(task["payload"])
        assert "pct_change" in res
        assert coord.complete_task(task["id"], "worker_stat", res)
        quantify_processed += 1

    assert quantify_processed == len(affected_reviews)

    # 6. Now Briefer must be claimable and complete successfully
    brief_task = coord.claim_task("worker_briefer", task_type="brief")
    assert brief_task is not None
    assert brief_task["key"] == f"brief:{target_ret_id}"
    brief_res = briefer.handle(brief_task["payload"])
    assert brief_res["total_reviews_affected"] == len(affected_reviews)
    assert coord.complete_task(brief_task["id"], "worker_briefer", brief_res)

    # 7. Verify Impact nodes in FalkorDB knowledge graph
    impacts = knowledge.get_impacts_for_retraction(target_ret_id)
    assert len(impacts) == len(affected_reviews)
    for imp in impacts:
        assert imp["review_id"] in affected_reviews
        assert isinstance(imp["pct_change"], float)
        assert isinstance(imp["flips"], bool)
        assert imp["before"] != 0.0
