"""
Watcher Agent: ingests retraction notices into the knowledge graph
and spawns downstream trace tasks.
"""
from typing import Any, Dict
from knowledge import KnowledgeEngine
from coord import CoordEngine

from ranking import normalize_reason_text

def classify_reason_category(reason: str, category: str = "unknown") -> str:
    return normalize_reason_text(text=reason, category=category)

class WatcherHandler:
    def __init__(self, knowledge: KnowledgeEngine, coord: CoordEngine):
        self.knowledge = knowledge
        self.coord = coord

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ret_id = payload.get("retraction_id") or payload.get("id")
        trial_id = payload.get("trial_id")
        reason = payload.get("reason", "Retraction notice published")
        category = classify_reason_category(reason, payload.get("reason_category", "unknown"))
        notice_url = payload.get("notice_url", "")
        synthetic = payload.get("synthetic", True)

        if not ret_id or not trial_id:
            raise ValueError(f"Watcher requires 'retraction_id' and 'trial_id', got: {payload}")

        # Ingest in knowledge graph
        res = self.knowledge.ingest_retraction(
            retraction_id=ret_id,
            trial_id=trial_id,
            reason=reason,
            reason_category=category,
            notice_url=notice_url,
            synthetic=synthetic,
        )

        # Spawn downstream trace task in coord graph
        trace_key = f"trace:{ret_id}"
        ingest_key = f"ingest:{ret_id}"
        trace_task_id = self.coord.spawn_task(
            task_type="trace",
            payload={"retraction_id": ret_id, "trial_id": trial_id, "reason_category": category},
            key=trace_key,
            priority=payload.get("priority", 1),
            parent_key=ingest_key,
        )

        return {
            "retraction_id": ret_id,
            "trial_id": trial_id,
            "trace_task_id": trace_task_id,
            "status": "ingested",
        }
