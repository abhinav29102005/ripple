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

        # Retrieve all impacts computed by Statisticians
        impacts = self.knowledge.get_impacts_for_retraction(ret_id)
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
