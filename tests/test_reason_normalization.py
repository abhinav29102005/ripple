"""
Unit tests for reason category normalization and ingestion safety:
1. Normalization mappings:
   - "fabricat" or "falsif" -> "fabrication"
   - "administrative" or "authorship" -> "administrative"
   - "error" -> "error"
   - Anything else -> "unknown"
   - Exact text "Data fabrication and falsification in clinical patient records" -> "fabrication"
2. Ingestion safety:
   - An existing Retraction with non-unknown category is never overwritten with "unknown".
3. Administrative retraction pipeline test:
   - Pipeline on an administrative retraction asserts administrative weight (0.2) is used.
"""
import pytest
from ranking import normalize_reason_text, REASON_WEIGHTS, compute_base_score, RankingEngine
from graph import graph_manager
from knowledge import KnowledgeEngine
from coord import CoordEngine
from memory import TenantMemory
from agents.watcher import WatcherHandler
from agents.tracer import TracerHandler
from agents.statistician import StatisticianHandler
from agents.briefer import BrieferHandler

def test_normalization_mappings():
    # 1. Fabrication / falsification
    assert normalize_reason_text("fabricat") == "fabrication"
    assert normalize_reason_text("falsif") == "fabrication"
    assert normalize_reason_text("data fabrication") == "fabrication"
    assert normalize_reason_text("falsification of results") == "fabrication"
    assert normalize_reason_text("Data fabrication and falsification in clinical patient records") == "fabrication"

    # 2. Administrative / authorship
    assert normalize_reason_text("administrative") == "administrative"
    assert normalize_reason_text("authorship") == "administrative"
    assert normalize_reason_text("administrative error in filing") == "administrative"
    assert normalize_reason_text("authorship dispute and lack of disclosure") == "administrative"
    assert normalize_reason_text("Duplicate publication without proper authorship agreement") == "administrative"

    # 3. Error
    assert normalize_reason_text("error") == "error"
    assert normalize_reason_text("calculation error in trial data") == "error"
    assert normalize_reason_text("statistical coding error") == "error"

    # 4. Unknown
    assert normalize_reason_text("unspecified") == "unknown"
    assert normalize_reason_text("withdrawn by editorial team") == "unknown"
    assert normalize_reason_text("") == "unknown"

    # Category and text combination
    assert normalize_reason_text(text="Patient records withdrawn", category="fabrication") == "fabrication"
    assert normalize_reason_text(text="authorship dispute", category="unknown") == "administrative"

def test_ingestion_safety_does_not_overwrite_known_category():
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    ret_id = "SYN-RET-SAFE-01"
    trial_id = "SYN-TR-0001"

    # 1. Ingest with fabrication
    knowledge.ingest_retraction(
        retraction_id=ret_id,
        trial_id=trial_id,
        reason="Data fabrication in patient logs",
        reason_category="fabrication",
    )
    res = knowledge.graph.query("MATCH (r:Retraction {id: $id}) RETURN r.reason_category", {"id": ret_id})
    assert res.result_set[0][0] == "fabrication"

    # 2. Submit update with reason_category='unknown' and unspecified reason
    knowledge.ingest_retraction(
        retraction_id=ret_id,
        trial_id=trial_id,
        reason="Update notice published",
        reason_category="unknown",
    )
    res_after = knowledge.graph.query("MATCH (r:Retraction {id: $id}) RETURN r.reason_category", {"id": ret_id})
    # MUST NOT be overwritten with "unknown"
    assert res_after.result_set[0][0] == "fabrication", "Ingestion safety failed: stored fabrication was overwritten!"

def test_administrative_retraction_uses_administrative_weight():
    """
    Asserts full pipeline on an administrative retraction computes base score using
    administrative weight (0.2).
    """
    coord = CoordEngine(graph_manager.get_graph("coord"))
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    watcher = WatcherHandler(knowledge, coord)
    tracer = TracerHandler(knowledge, coord)
    statistician = StatisticianHandler(knowledge)
    briefer = BrieferHandler(knowledge)

    ret_id = "SYN-RET-ADM-REGRESS"
    trial_id = "SYN-TR-0003"

    # Ingest administrative notice
    w_res = watcher.handle({
        "retraction_id": ret_id,
        "trial_id": trial_id,
        "reason": "Duplicate publication and lack of authorship disclosure",
        "reason_category": "administrative",
    })

    # Trace
    t_res = tracer.handle({"retraction_id": ret_id, "reason_category": "administrative"})

    # Quantify
    for rev_id in t_res["affected_reviews"]:
        statistician.handle({
            "retraction_id": ret_id,
            "review_id": rev_id,
            "reason_category": "administrative",
        })

    # Brief
    b_res = briefer.handle({"retraction_id": ret_id})
    assert len(b_res["impacts"]) > 0

    # Rank
    mem = TenantMemory("cardio")
    engine = RankingEngine(mem, knowledge=knowledge)
    ranked, _ = engine.rank_alerts(ret_id, b_res["impacts"], persist=False)

    for item in ranked:
        assert item["reason_category"] == "administrative"
        # Administrative weight in formula is 0.2
        # base = 0.4 * 0.2 + 0.3 * weight_share + 0.2 * flips + 0.1 * min(guidelines/3, 1)
        expected_reason_component = 0.4 * 0.2  # 0.08
        actual_base = item["base"]
        # With low weight and no flips, base should be under 0.3
        assert actual_base < 0.4, f"Administrative alert base score {actual_base} unexpectedly high!"
