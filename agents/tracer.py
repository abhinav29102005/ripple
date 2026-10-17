"""
Tracer Agent: navigates multi-hop blast radius in the knowledge graph,
propagates staleness to organizational decisions, builds contamination clusters,
and fans out quantify tasks to Statistician agents with a dependent brief task.
"""
from typing import Any, Dict, List
from knowledge import KnowledgeEngine
from coord import CoordEngine

class TracerHandler:
    def __init__(self, knowledge: KnowledgeEngine, coord: CoordEngine):
        self.knowledge = knowledge
        self.coord = coord

    def handle(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ret_id = payload["retraction_id"]

        # 1. Traverse blast radius
        blast_items = self.knowledge.get_blast_radius(ret_id)
        affected_review_ids = sorted(list(set(b["review"] for b in blast_items)))

        # 2. Propagate staleness to dependent organizational decisions
        flagged_decisions = self.knowledge.propagate_staleness(ret_id)

        # 3. Update contamination clusters
        self.knowledge.build_contamination_clusters()

        # 4. Fan out quantify tasks per affected review
        trace_key = f"trace:{ret_id}"
        quantify_keys: List[str] = []

        for rev_id in affected_review_ids:
            q_key = f"quantify:{ret_id}:{rev_id}"
            quantify_keys.append(q_key)
            self.coord.spawn_task(
                task_type="quantify",
                payload={"retraction_id": ret_id, "review_id": rev_id},
                key=q_key,
                priority=2,
                parent_key=trace_key,
            )

        # 5. Spawn downstream brief task that DEPENDS_ON all quantify tasks
        brief_key = f"brief:{ret_id}"
        brief_task_id = self.coord.spawn_task(
            task_type="brief",
            payload={"retraction_id": ret_id, "affected_reviews": affected_review_ids},
            key=brief_key,
            priority=1,
            depends_on_keys=quantify_keys,
            parent_key=trace_key,
        )

        return {
            "retraction_id": ret_id,
            "affected_reviews": affected_review_ids,
            "flagged_decisions": flagged_decisions,
            "quantify_tasks_spawned": len(quantify_keys),
            "brief_task_id": brief_task_id,
        }
