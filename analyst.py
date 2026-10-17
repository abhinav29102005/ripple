"""
Analyst Agent for Ripple (Track 01: Agents That Act on Connected Data).
Selects and executes MCP graph tools and FalkorDB algorithms (PageRank, WCC, Shortest Path),
logs execution traces to ToolCall graph nodes, and generates actionable remediation tickets.
"""
import time
import json
from typing import Any, Dict, List, Optional
from graph import graph_manager
from config import settings
import mcp_server

SYSTEM_PROMPT = """You are Ripple's Lead Clinical Evidence Analyst.
Your role is to assess the blast radius of retraction events, evaluate guidelines and decisions at risk,
and formulate immediate remediation actions.
Hard constraints:
1. Always cite exact node IDs (trials, reviews, guidelines, decisions).
2. Never recommend changing clinical practice directly; recommend human committee review.
3. Pick the fewest tools needed.
"""

CYPHER_LOG_TOOL_CALL = """
MATCH (t:Task {id: $task_id})
CREATE (tc:ToolCall {
    id: $id,
    tool: $tool,
    args: $args,
    output: $output,
    ts: $now
})
MERGE (t)-[:EXECUTED]->(tc)
RETURN tc.id
"""

CYPHER_LOG_TOOL_CALL_TENANT = """
CREATE (tc:ToolCall {
    id: $id,
    tool: $tool,
    args: $args,
    output: $output,
    ts: $now
})
RETURN tc.id
"""

class AnalystAgent:
    def __init__(self, tenant: str = "cardio"):
        self.tenant = tenant
        self.knowledge = mcp_server._get_knowledge()
        self.coord = mcp_server._get_coord()
        self.tenant_mem = mcp_server._get_tenant(tenant)

    def log_tool_call(self, tool_name: str, args: Dict[str, Any], output: Any) -> str:
        now = int(time.time())
        call_id = f"tc_{int(now * 1000) % 100000000}"
        args_str = json.dumps(args)
        out_str = json.dumps(output) if not isinstance(output, str) else output

        try:
            self.tenant_mem.graph.query(CYPHER_LOG_TOOL_CALL_TENANT, {
                "id": call_id,
                "tool": tool_name,
                "args": args_str,
                "output": out_str[:500],
                "now": now,
            })
        except Exception:
            pass
        return call_id

    def execute_plan(self, retraction_id: str, query: str = "What should we do first?") -> Dict[str, Any]:
        """
        Executes remediation plan.
        In LLM_MODE=off (or as deterministic fallback), runs:
        1. blast_radius
        2. rank_guidelines (algo.pageRank)
        3. contamination_clusters (algo.WCC)
        4. recall_team_history (tenant procedural rules)
        5. path_to_decision (algo.SPpaths)
        6. open_ticket
        """
        trace = []

        # Step 1: Tool call - blast_radius
        args_1 = {"retraction_id": retraction_id}
        out_1 = mcp_server.blast_radius(retraction_id)
        self.log_tool_call("blast_radius", args_1, out_1)
        trace.append({
            "step": 1,
            "tool": "blast_radius",
            "args": args_1,
            "output": out_1["summary"],
            "data": out_1,
        })

        # Step 2: Tool call - rank_guidelines (PageRank built-in algorithm)
        args_2 = {"limit": 3}
        out_2 = mcp_server.rank_guidelines(limit=3)
        self.log_tool_call("rank_guidelines", args_2, out_2)
        top_guideline = out_2["top_guidelines"][0]["id"] if out_2.get("top_guidelines") else "SYN-GL-001"
        trace.append({
            "step": 2,
            "tool": "rank_guidelines",
            "algorithm": out_2["algorithm"],
            "args": args_2,
            "output": f"Top critical guideline identified: {top_guideline}",
            "data": out_2,
        })

        # Step 3: Tool call - contamination_clusters (WCC built-in algorithm)
        args_3 = {"retraction_id": retraction_id}
        out_3 = mcp_server.contamination_clusters(retraction_id)
        self.log_tool_call("contamination_clusters", args_3, out_3)
        trace.append({
            "step": 3,
            "tool": "contamination_clusters",
            "algorithm": out_3["algorithm"],
            "args": args_3,
            "output": f"Found {len(out_3['shared_trial_pairs'])} review pairs sharing retracted trials across {out_3['cluster_count']} components.",
            "data": out_3,
        })

        # Step 4: Tool call - recall_team_history
        args_4 = {"tenant": self.tenant}
        out_4 = mcp_server.recall_team_history(self.tenant)
        self.log_tool_call("recall_team_history", args_4, out_4)
        trace.append({
            "step": 4,
            "tool": "recall_team_history",
            "args": args_4,
            "output": f"Recalled {len(out_4['active_rules'])} active procedural rules and {len(out_4['facts'])} semantic facts for team '{self.tenant}'.",
            "data": out_4,
        })

        # Step 5: Tool call - path_to_decision (Shortest path built-in algorithm)
        decisions = out_1.get("at_risk_decisions", [])
        target_decision_id = decisions[0]["decision_id"] if decisions else "DEC-CARDIO-001"
        args_5 = {"retraction_id": retraction_id, "decision_id": target_decision_id}
        out_5 = mcp_server.path_to_decision(retraction_id, target_decision_id)
        self.log_tool_call("path_to_decision", args_5, out_5)
        trace.append({
            "step": 5,
            "tool": "path_to_decision",
            "algorithm": out_5.get("algorithm", "algo.SPpaths"),
            "args": args_5,
            "output": f"Path to decision {target_decision_id}: {out_5.get('path_nodes', [])}",
            "data": out_5,
        })

        # Step 6: Tool call - open_ticket
        ticket_title = f"URGENT REVIEW: Retraction {retraction_id} impacts {target_decision_id} (Guideline {top_guideline})"
        args_6 = {"decision_id": target_decision_id, "title": ticket_title, "priority": "high"}
        out_6 = mcp_server.open_ticket(target_decision_id, ticket_title, priority="high")
        self.log_tool_call("open_ticket", args_6, out_6)
        trace.append({
            "step": 6,
            "tool": "open_ticket",
            "args": args_6,
            "output": f"Opened tracking ticket {out_6['ticket_id']} for decision {target_decision_id}",
            "data": out_6,
        })

        recommendation = (
            f"Remediation Plan for Retraction Notice [{retraction_id}]:\n"
            f"• Sourced Impact: Flagged institutional decision [{target_decision_id}] informing critical guideline [{top_guideline}].\n"
            f"• Shortest Evidence Path: {' -> '.join(out_5.get('path_nodes', [retraction_id, target_decision_id]))}.\n"
            f"• Contamination Alert: {len(out_3['shared_trial_pairs'])} systematic review pairs share the retracted trial evidence.\n"
            f"• Action Taken: Created ticket [{out_6['ticket_id']}] assigned to the {self.tenant.capitalize()} Committee for expedited methodological review."
        )

        return {
            "query": query,
            "retraction_id": retraction_id,
            "tenant": self.tenant,
            "trace": trace,
            "ticket_id": out_6["ticket_id"],
            "target_decision_id": target_decision_id,
            "critical_guideline": top_guideline,
            "algorithms_used": ["algo.pageRank", "algo.WCC", "algo.SPpaths"],
            "recommendation": recommendation,
        }
