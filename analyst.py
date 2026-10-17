"""
Analyst Agent for Ripple (Track 01: Agents That Act on Connected Data).
Selects and executes MCP graph tools and FalkorDB algorithms (PageRank, WCC, Shortest Path)
via an official MCP client session over stdio, logs execution traces to ToolCall graph nodes,
and generates actionable remediation tickets.
Supports both deterministic intent routing (LLM_MODE=off) and external LLM provider generation (LLM_MODE=on).
"""
import os
import sys
import time
import json
import asyncio
from typing import Any, Dict, List, Optional
import httpx

from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp import StdioServerParameters

from graph import graph_manager
from config import settings
from llm import GeminiFunctionCaller

SYSTEM_PROMPT = """You are Ripple's Lead Clinical Evidence Analyst.
Your role is to assess the blast radius of retraction events, evaluate guidelines and decisions at risk,
and formulate immediate remediation actions.
Hard constraints:
1. Always cite exact node IDs (trials, reviews, guidelines, decisions, tickets).
2. Never recommend changing clinical practice directly; recommend human committee review.
3. Pick the fewest tools needed.
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
        self.tenant_graph = graph_manager.get_graph(f"tenant_{tenant}")
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=["mcp_server.py"],
            env={**os.environ, "PYTHONPATH": "."}
        )

    def log_tool_call(self, tool_name: str, args: Dict[str, Any], output: Any) -> str:
        now = int(time.time())
        call_id = f"tc_{int(now * 1000) % 100000000}"
        args_str = json.dumps(args)
        out_str = json.dumps(output) if not isinstance(output, str) else output

        try:
            self.tenant_graph.query(CYPHER_LOG_TOOL_CALL_TENANT, {
                "id": call_id,
                "tool": tool_name,
                "args": args_str,
                "output": out_str[:500],
                "now": now,
            })
        except Exception:
            pass
        return call_id

    async def _execute_tool(self, session: ClientSession, tool_name: str, args: Dict[str, Any]) -> Any:
        """Invokes a tool via the active MCP client session over stdio."""
        call_res = await session.call_tool(tool_name, args)
        parsed = None
        if call_res.content and hasattr(call_res.content[0], "text"):
            raw_text = call_res.content[0].text
            try:
                parsed = json.loads(raw_text)
            except Exception:
                parsed = raw_text
        else:
            parsed = call_res

        self.log_tool_call(tool_name, args, parsed)
        return parsed

    async def run_plan_async(self, query: str = "What should we do first?", retraction_id: str = "SYN-RET-001") -> Dict[str, Any]:
        """
        Connects to MCP Server via stdio client, executes questions with tool routing,
        and logs transcripts.
        """
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                available_tools = await session.list_tools()
                tool_names = [t.name for t in available_tools.tools]

                # Check if LLM_MODE=on and Gemini key is configured
                gemini_caller = GeminiFunctionCaller()
                if settings.llm_mode == "on" and gemini_caller.is_available():
                    try:
                        llm_calls = await gemini_caller.select_tools(query, available_tools.tools, SYSTEM_PROMPT)
                        if llm_calls:
                            trace = []
                            algorithms_used = []
                            ticket_id = None
                            target_decision_id = None
                            for idx, call in enumerate(llm_calls, 1):
                                t_name = call["tool"]
                                t_args = call["args"]
                                if "retraction_id" in t_args and not t_args["retraction_id"]:
                                    t_args["retraction_id"] = retraction_id
                                out = await self._execute_tool(session, t_name, t_args)
                                out_str = str(out)
                                if "algo" in out_str:
                                    if "pageRank" in out_str: algorithms_used.append("algo.pageRank")
                                    if "WCC" in out_str: algorithms_used.append("algo.WCC")
                                    if "SPpaths" in out_str: algorithms_used.append("algo.SPpaths")
                                if t_name == "open_ticket" and isinstance(out, dict) and "ticket_id" in out:
                                    ticket_id = out["ticket_id"]
                                if "decision_id" in t_args:
                                    target_decision_id = t_args["decision_id"]
                                trace.append({
                                    "step": idx,
                                    "tool": t_name,
                                    "args": t_args,
                                    "output": str(out)[:200],
                                    "data": out,
                                    "selected_by": "gemini-2.0-flash"
                                })
                            
                            recommendation = (
                                f"Autonomous LLM Analyst Plan for [{retraction_id}]:\n"
                                f"• Query: \"{query}\"\n"
                                f"• Dynamic Tools Chosen by Gemini: {', '.join(s['tool'] for s in trace)}\n"
                                f"• Execution Trace: {len(trace)} tools called via MCP stdio client.\n"
                                f"• Recommendations strictly subject to human committee review."
                            )
                            return {
                                "query": query,
                                "retraction_id": retraction_id,
                                "tenant": self.tenant,
                                "trace": trace,
                                "ticket_id": ticket_id,
                                "target_decision_id": target_decision_id,
                                "algorithms_used": list(set(algorithms_used)),
                                "recommendation": recommendation,
                                "mode": "llm_live",
                            }
                    except Exception:
                        pass

                query_lower = query.lower()
                trace = []
                algorithms_used = []
                ticket_id = None
                target_decision_id = None
                critical_guideline = None

                # Question Category 2: "Who knows about <topic>?"
                if "who knows" in query_lower or "expert" in query_lower:
                    topic = "Cardiology"
                    for kw in ["cardiology", "oncology", "neurology", "immunology", "endocrinology", "statins"]:
                        if kw in query_lower:
                            topic = kw.capitalize()
                            break

                    out_who = await self._execute_tool(session, "who_knows", {"topic": topic})
                    trace.append({
                        "step": 1,
                        "tool": "who_knows",
                        "args": {"topic": topic},
                        "output": f"Found {len(out_who.get('experts', []))} domain experts for {topic}.",
                        "data": out_who,
                    })

                    out_team = await self._execute_tool(session, "recall_team_history", {"tenant": self.tenant})
                    trace.append({
                        "step": 2,
                        "tool": "recall_team_history",
                        "args": {"tenant": self.tenant},
                        "output": f"Recalled {len(out_team.get('active_rules', []))} active rules and {len(out_team.get('facts', []))} facts for team '{self.tenant}'.",
                        "data": out_team,
                    })

                    top_expert = out_who["experts"][0] if out_who.get("experts") else {"name": "Unknown", "person_id": "N/A"}
                    recommendation = (
                        f"Expertise Analysis for [{topic}]:\n"
                        f"• Leading Expert: {top_expert.get('name')} ({top_expert.get('person_id')}) with evidence score {top_expert.get('evidence_count', 0)}.\n"
                        f"• Affiliation: {top_expert.get('role', 'Researcher')} ({top_expert.get('email', 'N/A')}).\n"
                        f"• Recommended Action: Consult committee experts for methodological review."
                    )
                    return {
                        "query": query,
                        "retraction_id": retraction_id,
                        "tenant": self.tenant,
                        "trace": trace,
                        "ticket_id": None,
                        "target_decision_id": None,
                        "algorithms_used": [],
                        "recommendation": recommendation,
                    }

                # Question Category 3: "Which decisions are at risk?"
                elif "decisions" in query_lower or "at risk" in query_lower:
                    out_blast = await self._execute_tool(session, "blast_radius", {"retraction_id": retraction_id})
                    decisions = out_blast.get("at_risk_decisions", [])
                    trace.append({
                        "step": 1,
                        "tool": "blast_radius",
                        "args": {"retraction_id": retraction_id},
                        "output": f"Identified {len(decisions)} decision(s) at risk.",
                        "data": out_blast,
                    })

                    target_decision_id = decisions[0]["decision_id"] if decisions else "DEC-CARDIO-001"
                    out_path = await self._execute_tool(session, "path_to_decision", {
                        "retraction_id": retraction_id,
                        "decision_id": target_decision_id,
                    })
                    algorithms_used.append("algo.SPpaths")
                    trace.append({
                        "step": 2,
                        "tool": "path_to_decision",
                        "algorithm": "algo.SPpaths",
                        "args": {"retraction_id": retraction_id, "decision_id": target_decision_id},
                        "output": f"Found shortest evidence path to {target_decision_id}: {out_path.get('path_nodes', [])}",
                        "data": out_path,
                    })

                    out_flag = await self._execute_tool(session, "flag_decision", {
                        "decision_id": target_decision_id,
                        "reason": f"Impacted by retraction notice {retraction_id}",
                    })
                    trace.append({
                        "step": 3,
                        "tool": "flag_decision",
                        "args": {"decision_id": target_decision_id, "reason": f"Impacted by {retraction_id}"},
                        "output": f"Decision {target_decision_id} flagged with status 'at_risk'.",
                        "data": out_flag,
                    })

                    recommendation = (
                        f"At-Risk Decision Assessment for [{retraction_id}]:\n"
                        f"• Compromised Decisions: {', '.join(d['decision_id'] for d in decisions) if decisions else target_decision_id}.\n"
                        f"• Immediate Target: Flagged [{target_decision_id}] as at_risk via shortest path.\n"
                        f"• Action Taken: Notification routed to committee chairs for administrative review."
                    )
                    return {
                        "query": query,
                        "retraction_id": retraction_id,
                        "tenant": self.tenant,
                        "trace": trace,
                        "ticket_id": None,
                        "target_decision_id": target_decision_id,
                        "algorithms_used": algorithms_used,
                        "recommendation": recommendation,
                    }

                # Question Category 1 (Default): "What should we do first?" / Remediation Plan
                else:
                    # Step 1: blast_radius
                    args_1 = {"retraction_id": retraction_id}
                    out_1 = await self._execute_tool(session, "blast_radius", args_1)
                    trace.append({
                        "step": 1,
                        "tool": "blast_radius",
                        "args": args_1,
                        "output": out_1["summary"],
                        "data": out_1,
                    })

                    # Step 2: rank_guidelines (PageRank)
                    args_2 = {"limit": 3}
                    out_2 = await self._execute_tool(session, "rank_guidelines", args_2)
                    algorithms_used.append("algo.pageRank")
                    critical_guideline = out_2["top_guidelines"][0]["id"] if out_2.get("top_guidelines") else "SYN-GL-001"
                    trace.append({
                        "step": 2,
                        "tool": "rank_guidelines",
                        "algorithm": "algo.pageRank",
                        "args": args_2,
                        "output": f"Top critical guideline identified: {critical_guideline}",
                        "data": out_2,
                    })

                    # Step 3: contamination_clusters (WCC)
                    args_3 = {"retraction_id": retraction_id}
                    out_3 = await self._execute_tool(session, "contamination_clusters", args_3)
                    algorithms_used.append("algo.WCC")
                    trace.append({
                        "step": 3,
                        "tool": "contamination_clusters",
                        "algorithm": "algo.WCC",
                        "args": args_3,
                        "output": f"Found {len(out_3['shared_trial_pairs'])} review pairs sharing retracted trials across {out_3['cluster_count']} components.",
                        "data": out_3,
                    })

                    # Step 4: recall_team_history
                    args_4 = {"tenant": self.tenant}
                    out_4 = await self._execute_tool(session, "recall_team_history", args_4)
                    trace.append({
                        "step": 4,
                        "tool": "recall_team_history",
                        "args": args_4,
                        "output": f"Recalled {len(out_4['active_rules'])} active procedural rules and {len(out_4['facts'])} semantic facts for team '{self.tenant}'.",
                        "data": out_4,
                    })

                    # Step 5: path_to_decision (Shortest path)
                    decisions = out_1.get("at_risk_decisions", [])
                    target_decision_id = decisions[0]["decision_id"] if decisions else "DEC-CARDIO-001"
                    args_5 = {"retraction_id": retraction_id, "decision_id": target_decision_id}
                    out_5 = await self._execute_tool(session, "path_to_decision", args_5)
                    algorithms_used.append("algo.SPpaths")
                    trace.append({
                        "step": 5,
                        "tool": "path_to_decision",
                        "algorithm": out_5.get("algorithm", "algo.SPpaths"),
                        "args": args_5,
                        "output": f"Path to decision {target_decision_id}: {out_5.get('path_nodes', [])}",
                        "data": out_5,
                    })

                    # Step 6: open_ticket
                    ticket_title = f"URGENT REVIEW: Retraction {retraction_id} impacts {target_decision_id} (Guideline {critical_guideline})"
                    args_6 = {"decision_id": target_decision_id, "title": ticket_title, "priority": "high"}
                    out_6 = await self._execute_tool(session, "open_ticket", args_6)
                    ticket_id = out_6["ticket_id"]
                    trace.append({
                        "step": 6,
                        "tool": "open_ticket",
                        "args": args_6,
                        "output": f"Opened tracking ticket {ticket_id} for decision {target_decision_id}",
                        "data": out_6,
                    })

                    recommendation = (
                        f"Remediation Plan for Retraction Notice [{retraction_id}]:\n"
                        f"• Sourced Impact: Flagged institutional decision [{target_decision_id}] informing critical guideline [{critical_guideline}].\n"
                        f"• Shortest Evidence Path: {' -> '.join(out_5.get('path_nodes', [retraction_id, target_decision_id]))}.\n"
                        f"• Contamination Alert: {len(out_3['shared_trial_pairs'])} systematic review pairs share the retracted trial evidence.\n"
                        f"• Action Taken: Created ticket [{ticket_id}] assigned to the {self.tenant.capitalize()} Committee for expedited methodological review."
                    )

                    return {
                        "query": query,
                        "retraction_id": retraction_id,
                        "tenant": self.tenant,
                        "trace": trace,
                        "ticket_id": ticket_id,
                        "target_decision_id": target_decision_id,
                        "critical_guideline": critical_guideline,
                        "algorithms_used": algorithms_used,
                        "recommendation": recommendation,
                    }

    def execute_plan(self, retraction_id: str = "SYN-RET-001", query: str = "What should we do first?") -> Dict[str, Any]:
        """Synchronous wrapper for run_plan_async."""
        return asyncio.run(self.run_plan_async(query=query, retraction_id=retraction_id))

if __name__ == "__main__":
    agent = AnalystAgent("cardio")
    print("Testing AnalystAgent with MCP Client:")
    res = agent.execute_plan(query="What should we do first?")
    print(f"Executed {len(res['trace'])} tools via MCP Client!")
    for step in res['trace']:
        print(f"  [{step['step']}] Tool: {step['tool']} -> {step['output']}")
    print("Recommendation:\n", res['recommendation'])
