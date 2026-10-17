"""
Integration and acceptance tests for Milestone M4 (Track 03 Company Brain).
Verifies:
- Retraction propagates staleness to organizational decisions (flipping to at_risk with owners listed)
- Trace endpoint returns multi-hop evidence chain including documents and messages with ids
- Who-knows topic expertise discovery returns relevant personnel
"""
import pytest
from fastapi.testclient import TestClient
from api import app
from graph import graph_manager
from knowledge import KnowledgeEngine
from scripts.seed_synthetic import seed_synthetic_data
from scripts.seed_org import seed_organization

@pytest.fixture(scope="module", autouse=True)
def setup_org_knowledge():
    graph_manager.delete_graph("knowledge")
    graph_manager.init_knowledge_schema()
    seed_synthetic_data(scale="standard", seed=42)
    seed_organization(seed=42)
    yield

def test_retraction_flips_decisions_to_at_risk():
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))

    # Initial state of planted decision
    d_initial = knowledge.get_decision_trace("DEC-CARDIO-001")
    assert d_initial is not None
    assert d_initial["status"] == "active"

    # Propagate staleness from retraction SYN-RET-001
    flagged = knowledge.propagate_staleness("SYN-RET-001")
    assert flagged >= 1

    # Fetch at-risk decisions
    at_risk = knowledge.get_at_risk_decisions("SYN-RET-001")
    assert len(at_risk) >= 1
    target = next((d for d in at_risk if d["decision_id"] == "DEC-CARDIO-001"), None)
    assert target is not None, "Planted decision DEC-CARDIO-001 was not found in at_risk list"
    assert target["committee"] == "Cardiology Steering Committee"
    assert "Dr. Sarah Chen" in target["notify"]
    assert "Dr. Marcus Vance" in target["notify"]

def test_decision_trace_endpoint():
    client = TestClient(app)

    res = client.get("/api/decisions/DEC-CARDIO-001/trace")
    assert res.status_code == 200
    trace = res.json()

    assert trace["decision_id"] == "DEC-CARDIO-001"
    assert "Triple-Antiplatelet" in trace["decision_title"]
    assert trace["status"] == "at_risk"
    assert "retraction SYN-RET-001" in trace["risk_reason"]

    # Traversed evidence nodes
    assert "SYN-TR-0001" in trace["trials"]
    assert "SYN-RET-001" in trace["retractions"]

    # Associated organizational context with IDs
    docs = trace["documents"]
    assert len(docs) >= 4
    assert "DOC-001" in docs
    assert "DOC-002" in docs
    assert "DOC-003" in docs

    msgs = trace["messages"]
    assert len(msgs) >= 3
    assert "MSG-001" in msgs
    assert "MSG-002" in msgs
    assert "MSG-003" in msgs

def test_who_knows_endpoint():
    client = TestClient(app)

    res = client.get("/api/who-knows?topic=Cardiology")
    assert res.status_code == 200
    data = res.json()
    assert data["topic"] == "Cardiology"
    experts = data["experts"]
    assert len(experts) > 0
    names = [e["person"] for e in experts]
    assert "Dr. Sarah Chen" in names
