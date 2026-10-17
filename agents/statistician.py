"""
Statistician Agent: fetches trial effect sizes, recalculates pooled effects
before and after retraction, detects clinical flips, and stores Impact nodes.
"""
import uuid
from typing import Any, Dict
from knowledge import KnowledgeEngine
from stats import assess_impact

class StatisticianHandler:
    def __init__(self, knowledge: KnowledgeEngine):
        self.knowledge = knowledge

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ret_id = payload["retraction_id"]
        rev_id = payload["review_id"]
        category = payload.get("reason_category")
        if not category or category == "unknown":
            res = self.knowledge.graph.query(
                "MATCH (r:Retraction {id: $rid}) RETURN r.reason_category", {"rid": ret_id}
            )
            if res.result_set and res.result_set[0][0]:
                category = res.result_set[0][0]
            else:
                category = "unknown"

        trials = self.knowledge.get_review_trials(rev_id)
        retracted_ids = [t["id"] for t in trials if t.get("status") == "retracted"]

        # Run statistical pooling assessment
        impact = assess_impact(trials, retracted_trial_ids=retracted_ids, method="fixed")

        # Persist Impact node into FalkorDB knowledge graph
        impact_id = f"imp_{ret_id}_{rev_id}"
        impact_node_data = {
            "id": impact_id,
            "review_id": rev_id,
            "retraction_id": ret_id,
            "reason_category": category,
            "before": impact["before"],
            "before_lo": impact["before_lo"],
            "before_hi": impact["before_hi"],
            "after": impact["after"],
            "after_lo": impact["after_lo"],
            "after_hi": impact["after_hi"],
            "pct_change": impact["pct_change"],
            "flips": impact["flips"],
            "weight_share": impact["weight_share"],
        }
        self.knowledge.save_impact(impact_node_data)

        return {
            "impact_id": impact_id,
            "review_id": rev_id,
            "retraction_id": ret_id,
            "reason_category": category,
            "pct_change": impact["pct_change"],
            "flips": impact["flips"],
            "weight_share": impact["weight_share"],
        }
