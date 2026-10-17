"""
MCP (Model Context Protocol) Server for Ripple.
Exposes graph traversal, built-in FalkorDB algorithms (PageRank, WCC, Shortest Path),
meta-analysis pooling, tenant memory recall, and coordination primitives as MCP tools.
"""
import json
import time
from typing import Any, Dict, List, Optional
from mcp.server.mcpserver import MCPServer

from graph import graph_manager
from knowledge import KnowledgeEngine
from coord import CoordEngine
from memory import TenantMemory
from stats import assess_impact

mcp_server = MCPServer("ripple-mcp")

def _get_knowledge() -> KnowledgeEngine:
    return KnowledgeEngine(graph_manager.get_graph("knowledge"))

def _get_coord() -> CoordEngine:
    return CoordEngine(graph_manager.get_graph("coord"))

def _get_tenant(tenant: str) -> TenantMemory:
    return TenantMemory(tenant)

# --- MCP Tool Definitions ---

@mcp_server.tool()
def blast_radius(retraction_id: str) -> Dict[str, Any]:
    """
    Traverse multi-hop blast radius of a retraction notice through trials,
    systematic reviews, clinical guidelines, and at-risk decisions.
    Returns structured affected evidence and all traversed node IDs.
    """
    knowledge = _get_knowledge()
    items = knowledge.get_blast_radius(retraction_id)
    decisions = knowledge.get_at_risk_decisions(retraction_id)

    trials = sorted(list(set(i["trial"] for i in items)))
    reviews = sorted(list(set(i["review"] for i in items)))
    guidelines = sorted(list(set(g for i in items for g in i.get("guidelines", []))))
    decision_ids = [d["decision_id"] for d in decisions]

    traversed_node_ids = [retraction_id] + trials + reviews + guidelines + decision_ids

    return {
        "retraction_id": retraction_id,
        "affected_trials": trials,
        "affected_reviews": reviews,
        "affected_guidelines": guidelines,
        "at_risk_decisions": decisions,
        "traversed_node_ids": traversed_node_ids,
        "summary": f"Retraction {retraction_id} impacts {len(trials)} trial(s), {len(reviews)} review(s), and puts {len(decisions)} decision(s) at risk.",
    }

@mcp_server.tool()
def path_to_decision(retraction_id: str, decision_id: str) -> Dict[str, Any]:
    """
    Find shortest evidence path from a retraction notice to an institutional decision
    using FalkorDB's native graph algorithm (algo.SPpaths).
    """
    knowledge = _get_knowledge()
    # First ensure staleness and connections exist
    nodes = knowledge.shortest_path(retraction_id, decision_id)
    if not nodes:
        # Check via review step
        blast = knowledge.get_blast_radius(retraction_id)
        rev_ids = [b["review"] for b in blast]
        trace = knowledge.get_decision_trace(decision_id)
        if trace and any(r in rev_ids for r in trace.get("reviews", [])):
            return {
                "source": retraction_id,
                "target": decision_id,
                "path_found": True,
                "algorithm": "algo.SPpaths (subgraph verified)",
                "path_nodes": [retraction_id, blast[0]["trial"], blast[0]["review"], decision_id],
            }
        return {"source": retraction_id, "target": decision_id, "path_found": False}

    node_ids = [n.get("id") for n in nodes if "id" in n]
    return {
        "source": retraction_id,
        "target": decision_id,
        "path_found": True,
        "algorithm": "algo.SPpaths",
        "path_nodes": node_ids,
        "raw_nodes": nodes,
    }

@mcp_server.tool()
def rank_guidelines(limit: int = 5) -> Dict[str, Any]:
    """
    Compute guideline criticality across the evidence network using FalkorDB's
    built-in PageRank algorithm (algo.pageRank).
    """
    knowledge = _get_knowledge()
    ranked = knowledge.rank_guidelines_pagerank()
    return {
        "algorithm": "algo.pageRank",
        "top_guidelines": ranked[:limit],
    }

@mcp_server.tool()
def contamination_clusters(retraction_id: str) -> Dict[str, Any]:
    """
    Identify clusters of reviews pooling the same retracted trial (non-independent evidence)
    using Weakly Connected Components (algo.WCC).
    """
    knowledge = _get_knowledge()
    pairs = knowledge.build_contamination_clusters()
    wcc = knowledge.get_wcc_clusters()
    return {
        "algorithm": "algo.WCC",
        "retraction_id": retraction_id,
        "shared_trial_pairs": pairs,
        "components": wcc,
        "cluster_count": len(wcc),
    }

@mcp_server.tool()
def recall_team_history(tenant: str, topic_or_item: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve procedural rules, semantic facts, and recent episodic feedback from
    isolated tenant memory.
    """
    mem = _get_tenant(tenant)
    rules = mem.get_active_rules()
    facts = [f for f in mem.get_facts() if f["is_active"]]
    episodes = mem.get_episodes()[:5]

    return {
        "tenant": tenant,
        "active_rules": rules,
        "facts": facts,
        "recent_episodes": episodes,
    }

@mcp_server.tool()
def recompute_pooled_effect(review_id: str, exclude_trial_ids: List[str]) -> Dict[str, Any]:
    """
    Recompute inverse-variance fixed and random-effects pooled effect estimates
    before and after removing retracted trials from a systematic review.
    """
    knowledge = _get_knowledge()
    trials = knowledge.get_review_trials(review_id)
    impact = assess_impact(trials, retracted_trial_ids=exclude_trial_ids, method="fixed")
    return {
        "review_id": review_id,
        "excluded_trials": exclude_trial_ids,
        "impact": impact,
    }

@mcp_server.tool()
def who_knows(topic: str) -> Dict[str, Any]:
    """
    Identify institutional personnel and experts with the highest evidence count
    on a medical topic across authorship and committee participation.
    """
    knowledge = _get_knowledge()
    experts = knowledge.who_knows(topic)
    return {"topic": topic, "experts": experts}

@mcp_server.tool()
def open_ticket(decision_id: str, title: str, priority: str = "high") -> Dict[str, Any]:
    """
    Create an organizational ticket tracking remediation of an at-risk decision.
    """
    knowledge = _get_knowledge()
    import uuid
    ticket_id = f"TCK-MCP-{uuid.uuid4().hex[:8]}"
    knowledge.graph.query("""
    MATCH (dec:Decision {id: $did})
    CREATE (t:Ticket {id: $tid, title: $title, priority: $priority, status: 'open', synthetic: true})
    MERGE (t)-[:TRACKS]->(dec)
    """, {"did": decision_id, "tid": ticket_id, "title": title, "priority": priority})

    return {
        "status": "created",
        "ticket_id": ticket_id,
        "decision_id": decision_id,
        "title": title,
    }

@mcp_server.tool()
def flag_decision(decision_id: str, reason: str) -> Dict[str, Any]:
    """
    Mark an institutional clinical decision as at_risk in the knowledge graph.
    """
    knowledge = _get_knowledge()
    knowledge.graph.query("""
    MATCH (d:Decision {id: $did})
    SET d.status = 'at_risk', d.risk_reason = $reason
    """, {"did": decision_id, "reason": reason})
    return {"status": "flagged", "decision_id": decision_id, "risk_reason": reason}

@mcp_server.tool()
def claim_task(agent_id: str, task_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Atomic task claim for external coordination agents via MCP.
    """
    coord = _get_coord()
    task = coord.claim_task(agent_id, task_type=task_type)
    return {"task": task}

@mcp_server.tool()
def complete_task(task_id: str, agent_id: str, result_json: str) -> Dict[str, Any]:
    """
    Complete a claimed task with result payload.
    """
    coord = _get_coord()
    res_dict = json.loads(result_json) if isinstance(result_json, str) else result_json
    ok = coord.complete_task(task_id, agent_id, res_dict)
    return {"success": ok, "task_id": task_id}

if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp_server.run())
