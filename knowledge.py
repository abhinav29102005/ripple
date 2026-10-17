"""
Scientific evidence and organizational knowledge graph for Ripple.
Executes multi-hop Cypher queries, graph algorithms, and impact persistence
on FalkorDB.
"""
import time
from typing import Any, Dict, List, Optional, Tuple
from falkordb import Graph
from graph import graph_manager

# --- Named Cypher Query Constants for knowledge Graph ---

CYPHER_INGEST_RETRACTION = """
MERGE (r:Retraction {id: $id})
ON CREATE SET r.date = $date,
              r.reason = $reason,
              r.reason_category = $reason_category,
              r.notice_url = $notice_url,
              r.synthetic = $synthetic
ON MATCH SET r.reason_category = CASE WHEN $reason_category <> 'unknown' THEN $reason_category ELSE coalesce(r.reason_category, $reason_category) END
WITH r
MATCH (t:Trial {id: $trial_id})
SET t.status = 'retracted'
MERGE (r)-[:RETRACTS]->(t)
RETURN r.id AS rid, t.id AS tid
"""

CYPHER_BLAST_RADIUS = """
MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(t:Trial)-[i:INCLUDED_IN]->(rev:Review)
OPTIONAL MATCH (rev)-[:INFORMS]->(g:Guideline)
RETURN t.id AS trial, rev.id AS review, i.yi AS yi, i.sei AS sei, collect(DISTINCT g.id) AS guidelines,
       coalesce(r.reason_category, 'unknown') AS reason_category
"""

CYPHER_GET_REVIEW_TRIALS = """
MATCH (rev:Review {id: $review_id})<-[i:INCLUDED_IN]-(t:Trial)
RETURN t.id AS id, i.yi AS yi, i.sei AS sei, t.status AS status
"""

CYPHER_SAVE_IMPACT = """
MERGE (imp:Impact {id: $id})
SET imp.review_id = $review_id,
    imp.retraction_id = $retraction_id,
    imp.reason_category = $reason_category,
    imp.before = $before,
    imp.before_lo = $before_lo,
    imp.before_hi = $before_hi,
    imp.after = $after,
    imp.after_lo = $after_lo,
    imp.after_hi = $after_hi,
    imp.pct_change = $pct_change,
    imp.flips = $flips,
    imp.weight_share = $weight_share,
    imp.computed_at = $computed_at
WITH imp
MATCH (rev:Review {id: $review_id})
MERGE (imp)-[:OF]->(rev)
RETURN imp.id AS id
"""

CYPHER_PROPAGATE_STALENESS = """
MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(:Trial)-[:INCLUDED_IN]->(rev:Review)<-[:BASED_ON]-(d:Decision)
SET d.status = 'at_risk', d.risk_reason = 'retraction ' + r.id
RETURN count(DISTINCT d) AS flagged
"""

CYPHER_AT_RISK_DECISIONS = """
MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(t:Trial)-[:INCLUDED_IN]->(rev:Review)
MATCH (d:Decision)-[:BASED_ON]->(rev)
OPTIONAL MATCH (d)-[:MADE_BY]->(c:Committee)<-[:MEMBER_OF]-(p:Person)
RETURN d.id AS decision, d.title AS title, rev.id AS review,
       c.name AS committee, collect(DISTINCT p.name) AS notify
"""

CYPHER_DECISION_TRACE = """
MATCH (d:Decision {id: $did})
OPTIONAL MATCH (d)-[:BASED_ON]->(rev:Review)
OPTIONAL MATCH (t:Trial)-[:INCLUDED_IN]->(rev)
OPTIONAL MATCH (r:Retraction)-[:RETRACTS]->(t)
OPTIONAL MATCH (doc:Document)-[:SUPPORTS]->(d)
OPTIONAL MATCH (m:Message)-[:MENTIONS]->(d)
RETURN d.id AS decision_id, d.title AS decision_title, d.status AS status, d.risk_reason AS risk_reason,
       collect(DISTINCT rev.id) AS reviews,
       collect(DISTINCT t.id) AS trials,
       collect(DISTINCT r.id) AS retractions,
       collect(DISTINCT doc.id) AS documents,
       collect(DISTINCT m.id) AS messages
"""

CYPHER_WHO_KNOWS = """
MATCH (p:Person)-[:AUTHORED|PARTICIPATED_IN]->(x)
WHERE (x)-[:ON]->(:Topic {name: $topic}) OR (x)-[:ABOUT]->(:Guideline)-[:ON]->(:Topic {name: $topic})
RETURN p.name AS person, p.role AS role, count(DISTINCT x) AS evidence
ORDER BY evidence DESC LIMIT 5
"""

CYPHER_BUILD_CONTAMINATION_EDGES = """
MATCH (a:Review)<-[:INCLUDED_IN]-(t:Trial {status: 'retracted'})-[:INCLUDED_IN]->(b:Review)
WHERE a.id < b.id
WITH a, b, count(t) AS n
MERGE (a)-[s:SHARES_TRIAL]->(b)
SET s.n = n
RETURN a.id AS rev1, b.id AS rev2, n
"""

CYPHER_GET_IMPACT_BY_RETRACTION = """
MATCH (imp:Impact {retraction_id: $rid})-[:OF]->(rev:Review)
OPTIONAL MATCH (rev)-[:INFORMS]->(g:Guideline)
OPTIONAL MATCH (r:Retraction {id: $rid})
RETURN imp.id AS id, rev.id AS review_id, rev.title AS review_title,
       imp.before AS before, imp.after AS after, imp.pct_change AS pct_change,
       imp.flips AS flips, imp.weight_share AS weight_share,
       collect(DISTINCT g.id) AS guidelines,
       coalesce(imp.reason_category, r.reason_category, 'unknown') AS reason_category
"""

class KnowledgeEngine:
    def __init__(self, graph: Optional[Graph] = None):
        self._graph = graph or graph_manager.init_knowledge_schema()

    @property
    def graph(self) -> Graph:
        return self._graph

    def ingest_retraction(
        self,
        retraction_id: str,
        trial_id: str,
        reason: str,
        reason_category: str = "unknown",
        notice_url: str = "",
        date: str = "",
        synthetic: bool = True,
    ) -> Dict[str, str]:
        from ranking import normalize_reason_text
        norm_cat = normalize_reason_text(text=reason, category=reason_category)
        if norm_cat != "unknown":
            reason_category = norm_cat
        else:
            # Ingestion safety: never overwrite a stored non-unknown category with unknown
            try:
                exist_q = self.graph.query(
                    "MATCH (r:Retraction {id: $id}) RETURN r.reason_category", {"id": retraction_id}
                )
                if exist_q.result_set and exist_q.result_set[0][0] and exist_q.result_set[0][0] != "unknown":
                    reason_category = exist_q.result_set[0][0]
            except Exception:
                pass

        date = date or time.strftime("%Y-%m-%d")
        res = self.graph.query(CYPHER_INGEST_RETRACTION, {
            "id": retraction_id,
            "trial_id": trial_id,
            "reason": reason,
            "reason_category": reason_category,
            "notice_url": notice_url,
            "date": date,
            "synthetic": synthetic,
        })
        if res.result_set:
            return {"retraction_id": res.result_set[0][0], "trial_id": res.result_set[0][1]}
        return {}

    def get_blast_radius(self, retraction_id: str) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_BLAST_RADIUS, {"rid": retraction_id})
        items = []
        for r in res.result_set:
            items.append({
                "trial": r[0],
                "review": r[1],
                "yi": float(r[2]),
                "sei": float(r[3]),
                "guidelines": r[4],
                "reason_category": r[5] if len(r) > 5 and r[5] else "unknown",
            })
        return items

    def get_review_trials(self, review_id: str) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_REVIEW_TRIALS, {"review_id": review_id})
        trials = []
        for r in res.result_set:
            trials.append({
                "id": r[0],
                "yi": float(r[1]),
                "sei": float(r[2]),
                "status": r[3],
            })
        return trials

    def save_impact(self, impact_data: Dict[str, Any]) -> str:
        computed_at = int(time.time())
        res = self.graph.query(CYPHER_SAVE_IMPACT, {
            "id": impact_data["id"],
            "review_id": impact_data["review_id"],
            "retraction_id": impact_data["retraction_id"],
            "reason_category": impact_data.get("reason_category", "unknown"),
            "before": float(impact_data["before"]),
            "before_lo": float(impact_data["before_lo"]),
            "before_hi": float(impact_data["before_hi"]),
            "after": float(impact_data["after"]),
            "after_lo": float(impact_data["after_lo"]),
            "after_hi": float(impact_data["after_hi"]),
            "pct_change": float(impact_data["pct_change"]),
            "flips": bool(impact_data["flips"]),
            "weight_share": float(impact_data["weight_share"]),
            "computed_at": computed_at,
        })
        return res.result_set[0][0]

    def propagate_staleness(self, retraction_id: str) -> int:
        res = self.graph.query(CYPHER_PROPAGATE_STALENESS, {"rid": retraction_id})
        return int(res.result_set[0][0]) if res.result_set else 0

    def get_at_risk_decisions(self, retraction_id: str) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_AT_RISK_DECISIONS, {"rid": retraction_id})
        decisions = []
        for r in res.result_set:
            decisions.append({
                "decision_id": r[0],
                "title": r[1],
                "review_id": r[2],
                "committee": r[3],
                "notify": r[4],
            })
        return decisions

    def get_decision_trace(self, decision_id: str) -> Optional[Dict[str, Any]]:
        res = self.graph.query(CYPHER_DECISION_TRACE, {"did": decision_id})
        if not res.result_set:
            return None
        r = res.result_set[0]
        return {
            "decision_id": r[0],
            "decision_title": r[1],
            "status": r[2],
            "risk_reason": r[3],
            "reviews": r[4],
            "trials": r[5],
            "retractions": r[6],
            "documents": r[7],
            "messages": r[8],
        }

    def who_knows(self, topic: str) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_WHO_KNOWS, {"topic": topic})
        return [{"person": r[0], "role": r[1], "evidence_count": r[2]} for r in res.result_set]

    def build_contamination_clusters(self) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_BUILD_CONTAMINATION_EDGES)
        return [{"review_a": r[0], "review_b": r[1], "shared_trials": r[2]} for r in res.result_set]

    def get_impacts_for_retraction(self, retraction_id: str) -> List[Dict[str, Any]]:
        res = self.graph.query(CYPHER_GET_IMPACT_BY_RETRACTION, {"rid": retraction_id})
        impacts = []
        for r in res.result_set:
            impacts.append({
                "id": r[0],
                "review_id": r[1],
                "review_title": r[2],
                "before": r[3],
                "after": r[4],
                "pct_change": r[5],
                "flips": r[6],
                "weight_share": r[7],
                "guidelines": r[8],
                "reason_category": r[9] if len(r) > 9 and r[9] else "unknown",
            })
        return impacts

    # --- Built-in Graph Algorithms ---

    def rank_guidelines_pagerank(self) -> List[Dict[str, Any]]:
        """Compute PageRank across the INFORMS evidence graph to measure guideline criticality."""
        query = """
        CALL algo.pageRank(null, "INFORMS") YIELD node, score
        MATCH (g:Guideline) WHERE id(node) = id(g)
        RETURN g.id AS id, g.title AS title, score
        ORDER BY score DESC
        """
        try:
            res = self.graph.query(query)
            if res.result_set:
                return [{"id": r[0], "title": r[1], "score": round(float(r[2]), 4)} for r in res.result_set]
        except Exception:
            pass
        fb_query = "MATCH (g:Guideline) OPTIONAL MATCH (rev:Review)-[:INFORMS]->(g) RETURN g.id, g.title, count(rev) AS score ORDER BY score DESC"
        res = self.graph.query(fb_query)
        return [{"id": r[0], "title": r[1], "score": float(r[2])} for r in res.result_set]

    def get_wcc_clusters(self, node_label: Optional[str] = "Review", rel_type: Optional[str] = "SHARES_TRIAL") -> Dict[int, List[str]]:
        """Compute Weakly Connected Components across nodes, restricted by label and relationship type."""
        cfg = {}
        if node_label:
            cfg["nodeLabels"] = [node_label]
        if rel_type:
            cfg["relationshipTypes"] = [rel_type]
        if cfg:
            query = "CALL algo.WCC($cfg) YIELD node, componentId RETURN node.id AS id, componentId"
            params = {"cfg": cfg}
        else:
            query = "CALL algo.WCC() YIELD node, componentId RETURN node.id AS id, componentId"
            params = {}
        try:
            res = self.graph.query(query, params)
            clusters: Dict[int, List[str]] = {}
            for r in res.result_set:
                cid = int(r[1])
                nid = str(r[0]) if r[0] else ""
                clusters.setdefault(cid, []).append(nid)
            return clusters
        except Exception:
            return {}

    def shortest_path(self, source_id: str, target_id: str) -> Optional[List[Dict[str, Any]]]:
        """Find single pair shortest path between two nodes using algo.SPpaths."""
        query = """
        MATCH (a {id: $src}), (b {id: $tgt})
        CALL algo.SPpaths({sourceNode: a, targetNode: b}) YIELD path
        RETURN path
        """
        try:
            res = self.graph.query(query, {"src": source_id, "tgt": target_id})
            if not res.result_set:
                return None
            path = res.result_set[0][0]
            nodes = [n.properties for n in path.nodes()]
            return nodes
        except Exception:
            return None
