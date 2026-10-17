"""
Unit tests for Ranking Safety Invariants:
1. Rule adjustment cap: total delta strictly clamped to [-0.4, +0.4]
2. Safety floor: alerts with reason='fabrication' or flips=True never score below 0.5
3. Tie-breaking: when the safety floor applies, ties are broken by base score
4. Rule-stacking: multiple matching rules stack their deltas up to the cap
"""
import pytest
from graph import graph_manager
from memory import TenantMemory
from ranking import RankingEngine, compute_base_score, DELTA_CAP_MIN, DELTA_CAP_MAX, SAFETY_FLOOR_SCORE

@pytest.fixture(autouse=True)
def clean_safety_tenant():
    t_name = "test_safety_tenant"
    graph_manager.delete_graph(f"tenant_{t_name}")
    mem = TenantMemory(t_name)
    yield mem
    graph_manager.delete_graph(f"tenant_{t_name}")

def test_rule_adjustment_cap_negative_and_positive(clean_safety_tenant):
    mem = clean_safety_tenant

    # Case A: Negative cap [-0.4]
    mem.save_rule("rule_1", "reason", "error", delta=-0.3, support=5, hit_rate=1.0, description="r1")
    mem.save_rule("rule_2", "weight_bucket", "low", delta=-0.3, support=5, hit_rate=1.0, description="r2")

    engine = RankingEngine(mem)
    alert = [{
        "review_id": "REV-TEST-01",
        "reason_category": "error",
        "weight_share": 0.05,
        "flips": False,
        "guidelines": [],
    }]

    ranked, _ = engine.rank_alerts("SYN-RET-TEST", alert, persist=False)
    item = ranked[0]
    assert item["raw_delta"] == -0.6
    assert item["delta"] == DELTA_CAP_MIN  # Capped at -0.4!
    assert item["score"] == max(0.0, round(item["base"] - 0.4, 4))

    # Case B: Positive cap [+0.4]
    mem.save_rule("rule_pos_1", "reason", "administrative", delta=0.3, support=5, hit_rate=1.0, description="rp1")
    mem.save_rule("rule_pos_2", "weight_bucket", "mid", delta=0.3, support=5, hit_rate=1.0, description="rp2")

    alert_pos = [{
        "review_id": "REV-TEST-02",
        "reason_category": "administrative",
        "weight_share": 0.20,
        "flips": False,
        "guidelines": [],
    }]

    ranked_pos, _ = engine.rank_alerts("SYN-RET-TEST", alert_pos, persist=False)
    item_pos = ranked_pos[0]
    assert item_pos["raw_delta"] == 0.6
    assert item_pos["delta"] == DELTA_CAP_MAX  # Capped at +0.4!
    assert item_pos["score"] == min(1.0, round(item_pos["base"] + 0.4, 4))

def test_safety_floor_fabrication_and_flips(clean_safety_tenant):
    mem = clean_safety_tenant

    mem.save_rule("rule_down_1", "reason", "fabrication", delta=-0.3, support=5, hit_rate=1.0, description="r1")
    mem.save_rule("rule_down_2", "weight_bucket", "low", delta=-0.3, support=5, hit_rate=1.0, description="r2")

    engine = RankingEngine(mem)

    # 1. Alert with reason='fabrication' (low weight, no flips)
    alert_fab = [{
        "review_id": "REV-FAB-01",
        "reason_category": "fabrication",
        "weight_share": 0.01,
        "flips": False,
        "guidelines": [],
    }]
    ranked_fab, _ = engine.rank_alerts("SYN-RET-TEST", alert_fab, persist=False)
    item_fab = ranked_fab[0]
    assert item_fab["score"] >= SAFETY_FLOOR_SCORE
    assert item_fab["safety_floor_active"] is True

    # 2. Legacy alias 'data_falsification' normalizes to 'fabrication'
    alert_legacy = [{
        "review_id": "REV-FAB-LEGACY",
        "reason_category": "data_falsification",
        "weight_share": 0.01,
        "flips": False,
        "guidelines": [],
    }]
    ranked_legacy, _ = engine.rank_alerts("SYN-RET-TEST", alert_legacy, persist=False)
    item_legacy = ranked_legacy[0]
    assert item_legacy["reason_category"] == "fabrication"
    assert item_legacy["score"] >= SAFETY_FLOOR_SCORE

    # 3. Alert with flips=True
    mem.save_rule("rule_adm", "reason", "administrative", delta=-0.3, support=5, hit_rate=1.0, description="ra")
    alert_flip = [{
        "review_id": "REV-FLIP-01",
        "reason_category": "administrative",
        "weight_share": 0.01,
        "flips": True,
        "guidelines": [],
    }]
    ranked_flip, _ = engine.rank_alerts("SYN-RET-TEST", alert_flip, persist=False)
    item_flip = ranked_flip[0]
    assert item_flip["score"] >= SAFETY_FLOOR_SCORE
    assert item_flip["safety_floor_active"] is True

def test_safety_floor_tie_breaking_by_base_score(clean_safety_tenant):
    """
    Item 9: When safety floor applies, break ties among floored alerts
    by base score so they do not all show an identical 0.5.
    """
    mem = clean_safety_tenant
    # Force heavy negative rule to push both critical alerts below 0.5
    mem.save_rule("r_conj", "reason,weight_bucket", "fabrication,low", delta=-0.4, support=5, hit_rate=1.0, description="heavy down")

    engine = RankingEngine(mem)
    # Alert A has higher base score (higher weight share and guideline count)
    alert_a = {
        "review_id": "REV-CRIT-A",
        "reason_category": "fabrication",
        "weight_share": 0.08,  # low bucket
        "flips": False,
        "guidelines": ["GL-1"],
    }
    # Alert B has lower base score
    alert_b = {
        "review_id": "REV-CRIT-B",
        "reason_category": "fabrication",
        "weight_share": 0.01,  # low bucket
        "flips": False,
        "guidelines": [],
    }

    ranked, _ = engine.rank_alerts("SYN-RET-TEST", [alert_b, alert_a], persist=False)
    assert len(ranked) == 2

    item_a = next(x for x in ranked if x["review_id"] == "REV-CRIT-A")
    item_b = next(x for x in ranked if x["review_id"] == "REV-CRIT-B")

    assert item_a["safety_floor_active"] is True
    assert item_b["safety_floor_active"] is True

    # Both must be >= 0.5
    assert item_a["score"] >= 0.5
    assert item_b["score"] >= 0.5

    # They must NOT show identical scores
    assert item_a["score"] != item_b["score"], f"Both floored alerts show identical score {item_a['score']}"
    # Tie broken by base score
    assert item_a["base"] > item_b["base"]
    assert item_a["score"] > item_b["score"]
    assert item_a["rank"] < item_b["rank"]

def test_rule_stacking_case(clean_safety_tenant):
    mem = clean_safety_tenant

    mem.save_rule("rule_reason_error", "reason", "error", delta=-0.15, support=4, hit_rate=1.0, description="error rule")
    mem.save_rule("rule_weight_mid", "weight_bucket", "mid", delta=-0.10, support=4, hit_rate=1.0, description="mid weight rule")
    mem.save_rule("rule_flips_false", "flips", "false", delta=-0.05, support=4, hit_rate=1.0, description="flips false rule")

    engine = RankingEngine(mem)
    alert = [{
        "review_id": "REV-STACK-01",
        "reason_category": "error",
        "weight_share": 0.20,  # mid weight
        "flips": False,
        "guidelines": ["GL-1", "GL-2", "GL-3"],
    }]

    ranked, _ = engine.rank_alerts("SYN-RET-TEST", alert, persist=False)
    item = ranked[0]
    
    assert len(item["applied_rules"]) == 3
    rule_ids = {r["id"] for r in item["applied_rules"]}
    assert rule_ids == {"rule_reason_error", "rule_weight_mid", "rule_flips_false"}

    expected_delta = -0.15 + -0.10 + -0.05  # -0.30
    assert item["raw_delta"] == -0.30
    assert item["delta"] == -0.30
    expected_score = round(item["base"] - 0.30, 4)
    assert item["score"] == expected_score

def test_final_ranking_formula_clamp_and_safety_floor(clean_safety_tenant):
    mem = clean_safety_tenant
    mem.save_rule("r_admin", "reason", "administrative", delta=-0.25, support=3, hit_rate=1.0, description="desc")
    mem.save_rule("r_low", "weight_bucket", "low", delta=-0.25, support=3, hit_rate=1.0, description="desc")

    engine = RankingEngine(mem)
    test_alerts = [
        {"review_id": "TC-1", "reason_category": "administrative", "weight_share": 0.05, "flips": False, "guidelines": ["GL-1"]},
        {"review_id": "TC-2", "reason_category": "fabrication", "weight_share": 0.05, "flips": False, "guidelines": ["GL-1"]},
        {"review_id": "TC-3", "reason_category": "administrative", "weight_share": 0.05, "flips": True, "guidelines": []},
        {"review_id": "TC-4", "reason_category": "error", "weight_share": 0.50, "flips": False, "guidelines": ["GL-1", "GL-2"]},
    ]

    ranked, _ = engine.rank_alerts("SYN-RET-TEST", test_alerts, persist=False)
    assert len(ranked) == 4

    for item in ranked:
        base = item["base"]
        raw_delta = sum(r["delta"] for r in item["applied_rules"])
        capped_delta = max(-0.4, min(0.4, raw_delta))
        adjusted = round(base + capped_delta, 4)
        is_critical = (item["reason_category"] == "fabrication") or item["flips"]

        if is_critical:
            if adjusted < 0.5:
                expected = round(0.5 + (base * 0.01), 4)
            else:
                expected = min(1.0, adjusted)
        else:
            expected = max(0.0, min(1.0, adjusted))

        assert item["score"] == expected, f"Formula mismatch for {item['review_id']}: {item['score']} != {expected}"
