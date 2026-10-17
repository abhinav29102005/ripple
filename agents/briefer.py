"""
Briefer Agent: synthesizes completed statistical impact assessments,
guideline criticality, and organizational decision risks into an actionable brief.
"""
from typing import Any, Dict, List
from knowledge import KnowledgeEngine

class BrieferHandler:
    def __init__(self, knowledge: KnowledgeEngine):
        self.knowledge = knowledge

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ret_id = payload["retraction_id"]

        # Fetch stored category and reason from Retraction node via Cypher
        ret_cat = "unknown"
        ret_reason = ""
        try:
            res = self.knowledge.graph.query(
                "MATCH (r:Retraction {id: $rid}) RETURN coalesce(r.reason_category, 'unknown'), coalesce(r.reason, '')",
                {"rid": ret_id}
            )
            if res.result_set:
                ret_cat = res.result_set[0][0] or "unknown"
                ret_reason = res.result_set[0][1] or ""
        except Exception:
            pass

        # Retrieve all impacts computed by Statisticians and apply Retraction category
        impacts = self.knowledge.get_impacts_for_retraction(ret_id)
        for imp in impacts:
            if not imp.get("reason_category") or imp.get("reason_category") == "unknown":
                imp["reason_category"] = ret_cat
            imp["reason"] = ret_reason
        at_risk_decisions = self.knowledge.get_at_risk_decisions(ret_id)

        flipped_reviews = [imp["review_id"] for imp in impacts if imp.get("flips")]

        summary = {
            "retraction_id": ret_id,
            "total_reviews_affected": len(impacts),
            "flipped_reviews_count": len(flipped_reviews),
            "flipped_reviews": flipped_reviews,
            "at_risk_decisions_count": len(at_risk_decisions),
            "at_risk_decisions": at_risk_decisions,
            "impacts": impacts,
            "status": "briefed",
        }
        return summary
