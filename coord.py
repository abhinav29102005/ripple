"""
FalkorDB-native coordination engine for Ripple.
All task queues, dependency gating, atomic claims, heartbeats,
and self-healing lease reclaims run entirely via Cypher on FalkorDB.
"""
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from falkordb import Graph
from graph import graph_manager

# --- Named Cypher Query Constants for coord Graph ---

CYPHER_REGISTER_AGENT = """
MERGE (a:Agent {id: $id})
SET a.role = $role, a.started = $now, a.heartbeat = $now
RETURN a.id
"""

CYPHER_AGENT_HEARTBEAT = """
MATCH (a:Agent {id: $id})
SET a.heartbeat = $now
RETURN a.id
"""

CYPHER_SPAWN_TASK = """
MERGE (t:Task {key: $key})
ON CREATE SET t.id = $id,
              t.type = $type,
              t.status = 'queued',
              t.priority = $priority,
              t.created = $now,
              t.lease_until = 0,
              t.attempts = 0,
              t.max_attempts = $max_attempts,
              t.payload = $payload,
              t.claimed_by = null,
              t.result = null,
              t.error = null
RETURN t.id AS id, t.key AS key, t.status AS status
"""

CYPHER_LINK_DEPENDENCY = """
MATCH (t:Task {key: $key})
UNWIND $dep_keys AS dep_key
MATCH (dep:Task {key: dep_key})
MERGE (t)-[:DEPENDS_ON]->(dep)
"""

CYPHER_LINK_SPAWNED = """
MATCH (parent:Task {key: $parent_key}), (child:Task {key: $child_key})
MERGE (parent)-[:SPAWNED]->(child)
"""

CYPHER_ATOMIC_CLAIM = """
MATCH (t:Task {status: 'queued', type: $type})
OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
WITH t, count(d) AS open WHERE open = 0
WITH t ORDER BY t.priority DESC, t.created ASC LIMIT 1
SET t.status = 'claimed',
    t.claimed_by = $agent,
    t.lease_until = $now + $lease,
    t.attempts = t.attempts + 1
RETURN t.id AS id, t.key AS key, t.type AS type, t.payload AS payload, t.attempts AS attempts
"""

CYPHER_ATOMIC_CLAIM_ANY = """
MATCH (t:Task {status: 'queued'})
OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
WITH t, count(d) AS open WHERE open = 0
WITH t ORDER BY t.priority DESC, t.created ASC LIMIT 1
SET t.status = 'claimed',
    t.claimed_by = $agent,
    t.lease_until = $now + $lease,
    t.attempts = t.attempts + 1
RETURN t.id AS id, t.key AS key, t.type AS type, t.payload AS payload, t.attempts AS attempts
"""

CYPHER_TASK_HEARTBEAT = """
MATCH (t:Task {id: $id, claimed_by: $agent, status: 'claimed'})
SET t.lease_until = $now + $lease
RETURN t.id AS id
"""

CYPHER_COMPLETE_TASK = """
MATCH (t:Task {id: $id, claimed_by: $agent, status: 'claimed'})
SET t.status = 'done',
    t.result = $result,
    t.completed_at = $now
RETURN t.id AS id
"""

CYPHER_FAIL_TASK = """
MATCH (t:Task {id: $id, claimed_by: $agent, status: 'claimed'})
SET t.error = $error,
    t.status = CASE WHEN t.attempts < t.max_attempts THEN 'queued' ELSE 'failed' END,
    t.claimed_by = null
RETURN t.id AS id, t.status AS status
"""

CYPHER_RECLAIM_EXPIRED_LEASES = """
MATCH (t:Task {status: 'claimed'}) WHERE t.lease_until <= $now
SET t.status = 'queued', t.claimed_by = null
RETURN count(t) AS reclaimed
"""

CYPHER_GET_TASK_BY_ID = """
MATCH (t:Task {id: $id})
RETURN t.id AS id, t.key AS key, t.type AS type, t.status AS status,
       t.priority AS priority, t.created AS created, t.lease_until AS lease_until,
       t.attempts AS attempts, t.max_attempts AS max_attempts,
       t.claimed_by AS claimed_by, t.payload AS payload, t.result AS result, t.error AS error
"""

CYPHER_LIST_TASKS = """
MATCH (t:Task)
OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task)
RETURN t.id AS id, t.key AS key, t.type AS type, t.status AS status,
       t.priority AS priority, t.created AS created, t.lease_until AS lease_until,
       t.attempts AS attempts, t.claimed_by AS claimed_by,
       collect(DISTINCT d.id) AS dependencies
ORDER BY t.created DESC
"""

CYPHER_LIST_AGENTS = """
MATCH (a:Agent)
RETURN a.id AS id, a.role AS role, a.started AS started, a.heartbeat AS heartbeat
ORDER BY a.started ASC
"""

class CoordEngine:
    def __init__(self, graph: Optional[Graph] = None):
        self._graph = graph or graph_manager.init_coord_schema()

    @property
    def graph(self) -> Graph:
        return self._graph

    def register_agent(self, agent_id: str, role: str) -> str:
        now = int(time.time())
        self.graph.query(CYPHER_REGISTER_AGENT, {"id": agent_id, "role": role, "now": now})
        return agent_id

    def agent_heartbeat(self, agent_id: str) -> None:
        now = int(time.time())
        self.graph.query(CYPHER_AGENT_HEARTBEAT, {"id": agent_id, "now": now})

    def spawn_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        key: Optional[str] = None,
        priority: int = 0,
        max_attempts: int = 3,
        depends_on_keys: Optional[List[str]] = None,
        parent_key: Optional[str] = None,
    ) -> str:
        now = int(time.time())
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        task_key = key or f"{task_type}:{task_id}"
        payload_str = json.dumps(payload)

        res = self.graph.query(CYPHER_SPAWN_TASK, {
            "id": task_id,
            "key": task_key,
            "type": task_type,
            "priority": priority,
            "now": now,
            "max_attempts": max_attempts,
            "payload": payload_str,
        })
        actual_id = res.result_set[0][0]

        if depends_on_keys:
            self.graph.query(CYPHER_LINK_DEPENDENCY, {
                "key": task_key,
                "dep_keys": depends_on_keys,
            })

        if parent_key:
            self.graph.query(CYPHER_LINK_SPAWNED, {
                "parent_key": parent_key,
                "child_key": task_key,
            })

        return actual_id

    def claim_task(
        self,
        agent_id: str,
        task_type: Optional[str] = None,
        lease_seconds: int = 30,
    ) -> Optional[Dict[str, Any]]:
        now = int(time.time())
        if task_type:
            res = self.graph.query(CYPHER_ATOMIC_CLAIM, {
                "type": task_type,
                "agent": agent_id,
                "now": now,
                "lease": lease_seconds,
            })
        else:
            res = self.graph.query(CYPHER_ATOMIC_CLAIM_ANY, {
                "agent": agent_id,
                "now": now,
                "lease": lease_seconds,
            })

        if not res.result_set:
            return None

        row = res.result_set[0]
        payload = json.loads(row[3]) if row[3] else {}
        return {
            "id": row[0],
            "key": row[1],
            "type": row[2],
            "payload": payload,
            "attempts": row[4],
        }

    def heartbeat_task(self, task_id: str, agent_id: str, lease_seconds: int = 30) -> bool:
        now = int(time.time())
        res = self.graph.query(CYPHER_TASK_HEARTBEAT, {
            "id": task_id,
            "agent": agent_id,
            "now": now,
            "lease": lease_seconds,
        })
        return len(res.result_set) > 0

    def complete_task(self, task_id: str, agent_id: str, result: Dict[str, Any]) -> bool:
        now = int(time.time())
        result_str = json.dumps(result)
        res = self.graph.query(CYPHER_COMPLETE_TASK, {
            "id": task_id,
            "agent": agent_id,
            "result": result_str,
            "now": now,
        })
        return len(res.result_set) > 0

    def fail_task(self, task_id: str, agent_id: str, error: str) -> str:
        res = self.graph.query(CYPHER_FAIL_TASK, {
            "id": task_id,
            "agent": agent_id,
            "error": error,
        })
        if res.result_set:
            return res.result_set[0][1]
        return "not_found"

    def reclaim_expired_leases(self) -> int:
        now = int(time.time())
        res = self.graph.query(CYPHER_RECLAIM_EXPIRED_LEASES, {"now": now})
        if res.result_set:
            return int(res.result_set[0][0])
        return 0

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_TASK_BY_ID, {"id": task_id})
        if not res.result_set:
            return None
        r = res.result_set[0]
        return {
            "id": r[0],
            "key": r[1],
            "type": r[2],
            "status": r[3],
            "priority": r[4],
            "created": r[5],
            "lease_until": r[6],
            "attempts": r[7],
            "max_attempts": r[8],
            "claimed_by": r[9],
            "payload": json.loads(r[10]) if r[10] else {},
            "result": json.loads(r[11]) if r[11] else None,
            "error": r[12],
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_LIST_TASKS)
        tasks = []
        for r in res.result_set:
            tasks.append({
                "id": r[0],
                "key": r[1],
                "type": r[2],
                "status": r[3],
                "priority": r[4],
                "created": r[5],
                "lease_until": r[6],
                "attempts": r[7],
                "claimed_by": r[8],
                "dependencies": r[9],
            })
        return tasks

    def list_agents(self) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_LIST_AGENTS)
        agents = []
        for r in res.result_set:
            agents.append({
                "id": r[0],
                "role": r[1],
                "started": r[2],
                "heartbeat": r[3],
            })
        return agents
