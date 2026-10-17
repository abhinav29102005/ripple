"""
Tenant memory engine for Ripple.
Manages isolated tenant graphs for:
- Sessions and message chains
- Episodic feedback (dismiss, escalate, correct, note)
- Semantic memory with superseding facts
- Procedural memory (rules learned from episodes)
- Ranking history and full explainability paths
"""
import time
import uuid
import json
from typing import Any, Dict, List, Optional, Tuple
from falkordb import Graph
from graph import graph_manager

# --- Named Cypher Query Constants for tenant_<id> Graph ---

CYPHER_CREATE_SESSION = """
MERGE (s:Session {id: $id})
ON CREATE SET s.started = $now, s.tenant = $tenant
RETURN s.id
"""

CYPHER_LINK_SESSION_FOLLOWS = """
MATCH (prev:Session {id: $prev_id}), (curr:Session {id: $curr_id})
MERGE (curr)-[:FOLLOWS]->(prev)
"""

CYPHER_ADD_MESSAGE = """
MATCH (s:Session {id: $session_id})
CREATE (m:Message {id: $id, seq: $seq, role: $role, text: $text, ts: $now})
MERGE (s)-[:HAS]->(m)
RETURN m.id
"""

CYPHER_GET_SESSION_MESSAGES = """
MATCH (s:Session {id: $session_id})-[:HAS]->(m:Message)
RETURN m.id AS id, m.seq AS seq, m.role AS role, m.text AS text, m.ts AS ts
ORDER BY m.seq ASC
"""

CYPHER_RECORD_EPISODE = """
MERGE (s:Session {id: $session_id})
CREATE (e:Episode {
    id: $id,
    ts: $now,
    kind: $kind,
    reason: $reason,
    weight_bucket: $weight_bucket,
    flips: $flips,
    ext_review: $ext_review,
    ext_retraction: $ext_retraction,
    notes: $notes
})
MERGE (e)-[:IN]->(s)
RETURN e.id
"""

CYPHER_GET_EPISODES = """
MATCH (e:Episode)
OPTIONAL MATCH (e)-[:IN]->(s:Session)
RETURN e.id AS id, e.ts AS ts, e.kind AS kind, e.reason AS reason,
       e.weight_bucket AS weight_bucket, e.flips AS flips,
       e.ext_review AS ext_review, e.ext_retraction AS ext_retraction,
       s.id AS session_id
ORDER BY e.ts DESC
"""

CYPHER_CREATE_OR_UPDATE_RULE = """
MERGE (r:Rule {id: $id})
ON CREATE SET r.feature = $feature,
              r.value = $value,
              r.delta = $delta,
              r.support = $support,
              r.hit_rate = $hit_rate,
              r.status = 'active',
              r.description = $description,
              r.created = $now,
              r.updated = $now
ON MATCH SET r.delta = $delta,
             r.support = $support,
             r.hit_rate = $hit_rate,
             r.status = $status,
             r.description = $description,
             r.updated = $now
RETURN r.id
"""

CYPHER_LINK_RULE_EPISODES = """
MATCH (r:Rule {id: $rule_id})
UNWIND $episode_ids AS ep_id
MATCH (e:Episode {id: ep_id})
MERGE (r)-[:LEARNED_FROM]->(e)
"""

CYPHER_GET_ACTIVE_RULES = """
MATCH (r:Rule {status: 'active'})
RETURN r.id AS id, r.feature AS feature, r.value AS value,
       r.delta AS delta, r.support AS support, r.hit_rate AS hit_rate,
       r.description AS description
"""

CYPHER_SUPERSEDE_FACT = """
MATCH (old:Fact {key: $key}) WHERE old.valid_to IS NULL
SET old.valid_to = $now
WITH old
CREATE (new:Fact {id: $new_id, key: $key, value: $value, valid_from: $now, valid_to: null})
MERGE (new)-[:SUPERSEDES]->(old)
RETURN new.id AS id
"""

CYPHER_CREATE_INITIAL_FACT = """
CREATE (f:Fact {id: $id, key: $key, value: $value, valid_from: $now, valid_to: null})
RETURN f.id AS id
"""

CYPHER_GET_FACTS = """
MATCH (f:Fact)
OPTIONAL MATCH (f)-[:SUPERSEDES]->(prev:Fact)
RETURN f.id AS id, f.key AS key, f.value AS value,
       f.valid_from AS valid_from, f.valid_to AS valid_to,
       prev.id AS supersedes_id
ORDER BY f.valid_from DESC
"""

CYPHER_RECORD_RANKING = """
CREATE (rk:Ranking {id: $id, ts: $now, retraction_id: $retraction_id})
RETURN rk.id
"""

CYPHER_LINK_RANKING_RULE = """
MATCH (rk:Ranking {id: $ranking_id}), (r:Rule {id: $rule_id})
MERGE (rk)-[:USED {delta: $delta}]->(r)
"""

CYPHER_LINK_RANKING_ITEM = """
MATCH (rk:Ranking {id: $ranking_id})
MERGE (item:Item {id: $item_id, ext_id: $ext_id, kind: $kind})
MERGE (rk)-[:RANKED {rank: $rank, score: $score, base: $base}]->(item)
"""

CYPHER_LINK_ITEM_RULE = """
MATCH (item:Item {id: $item_id}), (r:Rule {id: $rule_id})
MERGE (item)-[:APPLIED]->(r)
"""

CYPHER_EXPLAIN_RANKING = """
MATCH (rk:Ranking {id: $ranking_id})-[rel:RANKED]->(item:Item {ext_id: $review_id})
OPTIONAL MATCH (item)-[:APPLIED]->(r:Rule)
OPTIONAL MATCH (rk)-[u:USED]->(r)
OPTIONAL MATCH (r)-[:LEARNED_FROM]->(e:Episode)
RETURN item.ext_id AS review_id, rel.rank AS rank, rel.score AS score, rel.base AS base,
       r.id AS rule_id, r.feature AS feature, r.value AS value, u.delta AS delta,
       r.description AS rule_desc, collect(DISTINCT e.id) AS episode_ids
"""

class TenantMemory:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._graph = graph_manager.init_tenant_schema(tenant_id)

    @property
    def graph(self) -> Graph:
        return self._graph

    # --- Session & Conversation Memory ---

    def create_session(self, session_id: Optional[str] = None, previous_session_id: Optional[str] = None) -> str:
        sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        now = int(time.time())
        self.graph.query(CYPHER_CREATE_SESSION, {"id": sid, "now": now, "tenant": self.tenant_id})
        if previous_session_id:
            self.graph.query(CYPHER_LINK_SESSION_FOLLOWS, {"prev_id": previous_session_id, "curr_id": sid})
        return sid

    def add_message(self, session_id: str, role: str, text: str, seq: int = 1) -> str:
        mid = f"msg_{uuid.uuid4().hex[:8]}"
        now = int(time.time())
        self.graph.query(CYPHER_ADD_MESSAGE, {
            "session_id": session_id,
            "id": mid,
            "seq": seq,
            "role": role,
            "text": text,
            "now": now,
        })
        return mid

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_SESSION_MESSAGES, {"session_id": session_id})
        return [{"id": r[0], "seq": r[1], "role": r[2], "text": r[3], "ts": r[4]} for r in res.result_set]

    # --- Episodic Memory ---

    def record_episode(
        self,
        session_id: str,
        kind: str,
        reason: str,
        weight_bucket: str,
        flips: bool,
        ext_review: str,
        ext_retraction: str,
        notes: str = "",
    ) -> str:
        eid = f"ep_{uuid.uuid4().hex[:8]}"
        now = int(time.time())
        self.graph.query(CYPHER_RECORD_EPISODE, {
            "session_id": session_id,
            "id": eid,
            "now": now,
            "kind": kind,
            "reason": reason,
            "weight_bucket": weight_bucket,
            "flips": str(flips).lower(),
            "ext_review": ext_review,
            "ext_retraction": ext_retraction,
            "notes": notes,
        })
        return eid

    def get_episodes(self) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_EPISODES)
        return [{
            "id": r[0],
            "ts": r[1],
            "kind": r[2],
            "reason": r[3],
            "weight_bucket": r[4],
            "flips": r[5] == "true" or r[5] is True,
            "ext_review": r[6],
            "ext_retraction": r[7],
            "session_id": r[8],
        } for r in res.result_set]

    # --- Semantic Facts (with Supersession) ---

    def set_fact(self, key: str, value: str) -> str:
        now = int(time.time())
        new_id = f"fact_{uuid.uuid4().hex[:8]}"
        # Check if an active fact already exists
        check = self.graph.query("MATCH (f:Fact {key: $key}) WHERE f.valid_to IS NULL RETURN f.id", {"key": key})
        if check.result_set:
            res = self.graph.query(CYPHER_SUPERSEDE_FACT, {
                "key": key,
                "value": value,
                "new_id": new_id,
                "now": now,
            })
            return res.result_set[0][0]
        else:
            res = self.graph.query(CYPHER_CREATE_INITIAL_FACT, {
                "id": new_id,
                "key": key,
                "value": value,
                "now": now,
            })
            return res.result_set[0][0]

    def get_facts(self) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_FACTS)
        return [{
            "id": r[0],
            "key": r[1],
            "value": r[2],
            "valid_from": r[3],
            "valid_to": r[4],
            "is_active": r[4] is None,
            "supersedes_id": r[5],
        } for r in res.result_set]

    # --- Procedural Rules ---

    def save_rule(
        self,
        rule_id: str,
        feature: str,
        value: str,
        delta: float,
        support: int,
        hit_rate: float,
        description: str,
        episode_ids: Optional[List[str]] = None,
        status: str = "active",
    ) -> str:
        now = int(time.time())
        self.graph.query(CYPHER_CREATE_OR_UPDATE_RULE, {
            "id": rule_id,
            "feature": feature,
            "value": value,
            "delta": delta,
            "support": support,
            "hit_rate": hit_rate,
            "description": description,
            "status": status,
            "now": now,
        })
        if episode_ids:
            self.graph.query(CYPHER_LINK_RULE_EPISODES, {
                "rule_id": rule_id,
                "episode_ids": episode_ids,
            })
        return rule_id

    def get_active_rules(self) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_ACTIVE_RULES)
        return [{
            "id": r[0],
            "feature": r[1],
            "value": r[2],
            "delta": float(r[3]),
            "support": int(r[4]),
            "hit_rate": float(r[5]),
            "description": r[6],
        } for r in res.result_set]

    # --- Rankings & Explainability ---

    def record_ranking(
        self,
        retraction_id: str,
        ranked_items: List[Dict[str, Any]],
        applied_rules: List[Dict[str, Any]],
    ) -> str:
        ranking_id = f"rk_{uuid.uuid4().hex[:8]}"
        now = int(time.time())
        self.graph.query(CYPHER_RECORD_RANKING, {
            "id": ranking_id,
            "now": now,
            "retraction_id": retraction_id,
        })

        for rule in applied_rules:
            self.graph.query(CYPHER_LINK_RANKING_RULE, {
                "ranking_id": ranking_id,
                "rule_id": rule["id"],
                "delta": float(rule["delta"]),
            })

        for item in ranked_items:
            item_id = f"item_{item['review_id']}"
            self.graph.query(CYPHER_LINK_RANKING_ITEM, {
                "ranking_id": ranking_id,
                "item_id": item_id,
                "ext_id": item["review_id"],
                "kind": "review",
                "rank": item["rank"],
                "score": float(item["score"]),
                "base": float(item["base"]),
            })
            for r in item.get("applied_rules", []):
                self.graph.query(CYPHER_LINK_ITEM_RULE, {
                    "item_id": item_id,
                    "rule_id": r["id"],
                })

        return ranking_id

    def explain_ranking(self, ranking_id: str, review_id: str) -> Optional[Dict[str, Any]]:
        res = self.graph.query(CYPHER_EXPLAIN_RANKING, {
            "ranking_id": ranking_id,
            "review_id": review_id,
        })
        if not res.result_set:
            return None

        rules = []
        base_score = 0.0
        final_score = 0.0
        rank = 0

        for r in res.result_set:
            rank = r[1]
            final_score = r[2]
            base_score = r[3]
            rule_id = r[4]
            if rule_id:
                rules.append({
                    "rule_id": rule_id,
                    "feature": r[5],
                    "value": r[6],
                    "delta": r[7],
                    "description": r[8],
                    "learned_from_episodes": r[9],
                })

        return {
            "review_id": review_id,
            "rank": rank,
            "base_score": base_score,
            "final_score": final_score,
            "rules_applied": rules,
        }
