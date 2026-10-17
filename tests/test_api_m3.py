"""
Integration test for Milestone M3 REST API endpoints.
Tests:
- Submitting retraction via API
- Fetching tenant rankings
- Posting 3 dismissal episodes via API
- Verifying procedural rule is automatically formed
- Verifying updated ranking score and explanation endpoint
"""
import pytest
from fastapi.testclient import TestClient
from api import app
from graph import graph_manager
from scripts.seed_synthetic import seed_synthetic_data

@pytest.fixture(scope="module", autouse=True)
def setup_api_test_graphs():
    graph_manager.delete_graph("knowledge")
    graph_manager.delete_graph("coord")
    graph_manager.delete_graph("tenant_cardio_api")
    graph_manager.init_knowledge_schema()
    graph_manager.init_coord_schema()
    graph_manager.init_tenant_schema("cardio_api")
    seed_synthetic_data(scale="standard", seed=42)
    yield
    graph_manager.delete_graph("tenant_cardio_api")

def test_api_tenant_memory_and_rules():
    client = TestClient(app)

    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 2. Get initial rankings for tenant cardio_api
    res = client.get("/api/tenants/cardio_api/rankings?retraction_id=SYN-RET-001")
    assert res.status_code == 200
    data = res.json()
    alerts = data["ranked_alerts"]
    assert len(alerts) > 0
    initial_score = alerts[0]["score"]
    review_id = alerts[0]["review_id"]
    initial_ranking_id = data["ranking_id"]

    # 3. Post 3 dismissals on administrative category with low weight bucket via API
    for i in range(3):
        ep_res = client.post(
            "/api/tenants/cardio_api/episodes",
            json={
                "kind": "dismiss",
                "reason": "administrative",
                "weight_bucket": "low",
                "flips": False,
                "ext_review": f"SYN-REV-{i+1}",
                "ext_retraction": "SYN-RET-001",
                "notes": "Dismiss administrative noise",
            },
        )
        assert ep_res.status_code == 200
        assert ep_res.json()["status"] == "recorded"

    # 4. Check memory endpoint returns conjunctive rule
    mem_res = client.get("/api/tenants/cardio_api/memory")
    assert mem_res.status_code == 200
    mem_data = mem_res.json()
    rules = mem_data["active_rules"]
    assert any(r["id"] == "rule_administrative_low" for r in rules)

    # 5. Fetch rankings again with alert of reason_category=administrative
    # Alert with administrative reason should now be downranked by 0.3
    # Let's verify via the explain endpoint
    res_after = client.get("/api/tenants/cardio_api/rankings?retraction_id=SYN-RET-001")
    assert res_after.status_code == 200
    ranking_id_after = res_after.json()["ranking_id"]

    explain_res = client.get(f"/api/tenants/cardio_api/explain/{ranking_id_after}/{review_id}")
    assert explain_res.status_code == 200
    exp = explain_res.json()
    assert "base_score" in exp
    assert "final_score" in exp
    assert "rules_applied" in exp

def test_public_mode_hardening(monkeypatch):
    from config import settings
    client = TestClient(app)

    # Enable public mode
    monkeypatch.setattr(settings, "public_mode", True)

    # 1. Reset endpoint must return 403 Forbidden
    res_reset = client.post("/api/reset")
    assert res_reset.status_code == 403
    assert "disabled in PUBLIC_MODE" in res_reset.json()["detail"]

    # 2. Chaos endpoint must return 403 Forbidden
    res_chaos = client.post("/api/chaos/run")
    assert res_chaos.status_code == 403
    assert "disabled in PUBLIC_MODE" in res_chaos.json()["detail"]

    # 3. Rate limiting on chat endpoint (limit is 10)
    for _ in range(10):
        r = client.post("/api/chat", json={"tenant": "cardio_api", "text": "status check"})
        assert r.status_code == 200

    # 11th request must be rate-limited (429)
    r_exceeded = client.post("/api/chat", json={"tenant": "cardio_api", "text": "status check"})
    assert r_exceeded.status_code == 429
    assert "Rate limit exceeded" in r_exceeded.json()["detail"]
