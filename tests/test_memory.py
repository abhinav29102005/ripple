"""
Unit tests for Milestone M3: Tenant Memory and Procedural Rule Consolidation.
Verifies:
- 3 dismissals sharing (reason, weight_bucket) generate an active conjunctive procedural rule with delta = -0.3
- Rule application shifts ranking score and establishes USED & LEARNED_FROM explanation paths
- Rule retirement on contradictory feedback
- Fact supersession history preservation
"""
import pytest
from graph import graph_manager
from memory import TenantMemory
from ranking import RankingEngine, compute_base_score
from agents.librarian import LibrarianHandler

@pytest.fixture(autouse=True)
def clean_tenant_graph():
    tenant_name = "test_memory_tenant"
    graph_manager.delete_graph(f"tenant_{tenant_name}")
    mem = TenantMemory(tenant_name)
    yield mem
    graph_manager.delete_graph(f"tenant_{tenant_name}")

def test_three_dismissals_create_active_rule(clean_tenant_graph):
    mem = clean_tenant_graph
    sess_id = mem.create_session()

    # Record 3 dismissals on administrative retractions with low weight bucket
    ep_ids = []
    for i in range(3):
        eid = mem.record_episode(
            session_id=sess_id,
            kind="dismiss",
            reason="administrative",
            weight_bucket="low",
            flips=False,
            ext_review=f"SYN-REV-00{i+1}",
            ext_retraction="SYN-RET-ADM",
            notes="Administrative formatting notice",
        )
        ep_ids.append(eid)

    # Run Librarian consolidation
    librarian = LibrarianHandler(mem)
    res = librarian.consolidate()

    assert "rule_administrative_low" in res["created_rules"]

    active_rules = mem.get_active_rules()
    rule_map = {r["id"]: r for r in active_rules}
    assert "rule_administrative_low" in rule_map
    rule = rule_map["rule_administrative_low"]
    assert rule["delta"] == -0.3
    assert rule["support"] == 3
    assert rule["hit_rate"] == 1.0

def test_rule_modifies_next_ranking_and_explains(clean_tenant_graph):
    mem = clean_tenant_graph
    sess_id = mem.create_session()

    # 1. Base ranking before rule
    ranking_engine = RankingEngine(mem)
    alerts = [{
        "review_id": "SYN-REV-999",
        "title": "Review 999",
        "reason_category": "administrative",
        "weight_share": 0.05,  # low weight bucket
        "flips": False,
        "guidelines": ["SYN-GL-01"],
    }]

    unmodified_ranked, _ = ranking_engine.rank_alerts("SYN-RET-01", alerts, persist=False)
    base_score = unmodified_ranked[0]["base"]
    assert unmodified_ranked[0]["score"] == base_score
    assert len(unmodified_ranked[0]["applied_rules"]) == 0

    # 2. Add 3 dismissals for administrative retractions sharing weight_bucket=low
    ep_ids = [
        mem.record_episode(sess_id, "dismiss", "administrative", "low", False, "REV-0", "RET-1"),
        mem.record_episode(sess_id, "dismiss", "administrative", "low", False, "REV-1", "RET-1"),
        mem.record_episode(sess_id, "dismiss", "administrative", "low", False, "REV-2", "RET-1"),
    ]
    librarian = LibrarianHandler(mem)
    librarian.consolidate()

    # 3. New ranking after rule is active
    modified_ranked, ranking_id = ranking_engine.rank_alerts("SYN-RET-02", alerts, persist=True)
    assert ranking_id is not None
    item = modified_ranked[0]
    expected_score = max(0.0, round(base_score - 0.3, 4))
    assert item["score"] == expected_score
    assert len(item["applied_rules"]) == 1
    assert item["applied_rules"][0]["id"] == "rule_administrative_low"

    # 4. Verify explainability path
    explanation = mem.explain_ranking(ranking_id, "SYN-REV-999")
    assert explanation is not None
    assert explanation["base_score"] == base_score
    assert explanation["final_score"] == expected_score
    assert len(explanation["rules_applied"]) == 1
    rule_exp = explanation["rules_applied"][0]
    assert rule_exp["rule_id"] == "rule_administrative_low"
    assert rule_exp["delta"] == -0.3
    assert set(ep_ids).issubset(set(rule_exp["learned_from_episodes"]))

def test_rule_retirement_on_contradictory_feedback(clean_tenant_graph):
    mem = clean_tenant_graph
    sess_id = mem.create_session()
    librarian = LibrarianHandler(mem)

    # 3 dismissals create rule
    for i in range(3):
        mem.record_episode(sess_id, "dismiss", "administrative", "low", False, f"REV-{i}", "RET-1")
    librarian.consolidate()
    assert any(r["id"] == "rule_administrative_low" for r in mem.get_active_rules())

    # Add 4 escalations for administrative alerts (dismiss rate drops from 3/3=1.0 to 3/7=0.43 < 0.5)
    for i in range(4):
        mem.record_episode(sess_id, "escalate", "administrative", "low", False, f"REV-ESC-{i}", "RET-2")

    res = librarian.consolidate()
    assert "rule_administrative_low" in res["retired_rules"]
    assert not any(r["id"] == "rule_administrative_low" for r in mem.get_active_rules())

def test_semantic_fact_supersession(clean_tenant_graph):
    mem = clean_tenant_graph

    # First version of fact
    id_v1 = mem.set_fact("preferred_model", "fixed")
    facts_v1 = mem.get_facts()
    assert len(facts_v1) == 1
    assert facts_v1[0]["value"] == "fixed"
    assert facts_v1[0]["is_active"] is True

    # Superseding update
    id_v2 = mem.set_fact("preferred_model", "random_effects")
    facts_v2 = mem.get_facts()
    assert len(facts_v2) == 2

    # Check active vs retired facts
    active_facts = [f for f in facts_v2 if f["is_active"]]
    retired_facts = [f for f in facts_v2 if not f["is_active"]]
    assert len(active_facts) == 1
    assert active_facts[0]["value"] == "random_effects"
    assert active_facts[0]["supersedes_id"] == id_v1

    assert len(retired_facts) == 1
    assert retired_facts[0]["id"] == id_v1
    assert retired_facts[0]["valid_to"] is not None
