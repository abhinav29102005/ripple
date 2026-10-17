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
    from scripts.seed_org import seed_organization
    seed_organization(seed=42)
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
        assert imp["reason_category"] == "fabrication"

    # 8. Assert ranked alert has reason=fabrication, safety floor active, and final score >= 0.5
    from fastapi.testclient import TestClient
    from api import app
    client = TestClient(app)
    rank_resp = client.get(f"/api/tenants/cardio/rankings?retraction_id={target_ret_id}")
    assert rank_resp.status_code == 200
    alerts = rank_resp.json()["ranked_alerts"]
    assert len(alerts) > 0
    syn_alert = alerts[0]
    assert syn_alert["reason_category"] == "fabrication"
    assert syn_alert["safety_floor_active"] is True
    assert syn_alert["score"] >= 0.5

def test_api_notice_submission_with_fabrication_wording():
    """
    Submitting a retraction notice through the API with fabrication wording (LLM_MODE=off)
    correctly classifies category as fabrication, propagates through the pipeline,
    and produces a ranked alert with reason=fabrication, safety_floor_active=True, score >= 0.5.
    """
    from fastapi.testclient import TestClient
    from api import app
    client = TestClient(app)

    coord = CoordEngine(graph_manager.get_graph("coord"))
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    watcher = WatcherHandler(knowledge, coord)
    tracer = TracerHandler(knowledge, coord)
    statistician = StatisticianHandler(knowledge)
    briefer = BrieferHandler(knowledge)

    ret_id = "SYN-RET-FAB-API"
    trial_id = "SYN-TR-0001"

    # Post notice with fabrication wording without explicitly providing reason_category
    resp = client.post("/api/retractions", json={
        "retraction_id": ret_id,
        "trial_id": trial_id,
        "reason": "Institutional audit concluded severe data fabrication and falsification in clinical trial patient registries",
        "notice_url": "https://example.org/retractions/syn-ret-fab-api",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"

    # Run the worker pipeline
    # 1. Watcher claims ingest
    t_ingest = coord.claim_task("worker_watcher_api", task_type="ingest")
    assert t_ingest is not None
    res_w = watcher.handle(t_ingest["payload"])
    assert coord.complete_task(t_ingest["id"], "worker_watcher_api", res_w)

    # 2. Tracer claims trace
    t_trace = coord.claim_task("worker_tracer_api", task_type="trace")
    assert t_trace is not None
    res_t = tracer.handle(t_trace["payload"])
    assert coord.complete_task(t_trace["id"], "worker_tracer_api", res_t)

    # 3. Statistician processes quantify tasks
    while True:
        t_stat = coord.claim_task("worker_stat_api", task_type="quantify")
        if not t_stat:
            break
        res_s = statistician.handle(t_stat["payload"])
        assert coord.complete_task(t_stat["id"], "worker_stat_api", res_s)

    # 4. Briefer claims brief
    t_brief = coord.claim_task("worker_briefer_api", task_type="brief")
    assert t_brief is not None
    res_b = briefer.handle(t_brief["payload"])
    assert coord.complete_task(t_brief["id"], "worker_briefer_api", res_b)

    # 5. Verify ranked alert via GET API
    rank_resp = client.get(f"/api/tenants/cardio/rankings?retraction_id={ret_id}")
    assert rank_resp.status_code == 200
    alerts = rank_resp.json()["ranked_alerts"]
    assert len(alerts) > 0
    alert = alerts[0]
    assert alert["reason_category"] == "fabrication"
    assert alert["safety_floor_active"] is True
    assert alert["score"] >= 0.5
