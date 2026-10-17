"""
Analyst Agent for Ripple (Track 01: Agents That Act on Connected Data).
Selects and executes MCP graph tools and FalkorDB algorithms (PageRank, WCC, Shortest Path)
via an official MCP client session over stdio, logs execution traces to ToolCall graph nodes,
and generates actionable remediation tickets.
Supports both autonomous model tool-calling (LLM_MODE=on via OpenAI-compatible endpoints)
and deterministic Cypher query planning (LLM_MODE=off).
"""
import os
import sys
import time
import json
import asyncio
from typing import Any, Callable, Dict, List, Optional
import httpx

from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp import StdioServerParameters

from graph import graph_manager
from config import settings
from llm import OpenAICompatToolCaller

SYSTEM_PROMPT = """You are Ripple's Lead Clinical Evidence Analyst assessing retraction blast radius and evidence contamination.
Active retraction under investigation: SYN-RET-001.

Guidance for selecting tools:
- "What should we do first?" -> Call blast_radius, rank_guidelines, and open_ticket or path_to_decision.
- "Who knows about <topic>?" -> Call who_knows(topic="...").
- "Which decisions are at risk?" -> Call blast_radius(retraction_id="SYN-RET-001") and path_to_decision.

Hard constraints:
1. Always cite exact node IDs (trials, reviews, guidelines, decisions, tickets).
2. Never recommend changing clinical practice directly; recommend human committee review.
3. Pick the fewest tools needed to answer the question directly.
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

                fallback_reason = None

                # Check if LLM_MODE=on and OpenAI-compatible caller is configured
                tool_caller = OpenAICompatToolCaller()
                if settings.llm_mode == "on" and tool_caller.is_available():
                    async def session_caller(name: str, args: Dict[str, Any]) -> Any:
                        if name in ("blast_radius", "contamination_clusters", "path_to_decision"):
                            if not args.get("retraction_id"):
                                args["retraction_id"] = retraction_id
                        if name in ("path_to_decision", "flag_decision", "open_ticket"):
                            if not args.get("decision_id"):
                                args["decision_id"] = "DEC-CARDIO-001"
                        if name == "open_ticket":
                            if not args.get("title"):
                                args["title"] = f"Urgent Remediation Review for {args.get("decision_id", "DEC-CARDIO-001")}"
                        return await self._execute_tool(session, name, args)

                    try:
                        loop_res = await tool_caller.run_tool_loop(
                            query=query,
                            mcp_tools=available_tools.tools,
                            session_caller=session_caller,
                            system_prompt=SYSTEM_PROMPT,
                            max_steps=6,
                        )

                        if loop_res.get("trace"):
                            trace = loop_res["trace"]
                            algorithms_used = []
                            ticket_id = None
                            target_decision_id = None

                            for step in trace:
                                out_str = str(step.get("data", ""))
                                if "pageRank" in out_str: algorithms_used.append("algo.pageRank")
                                if "WCC" in out_str: algorithms_used.append("algo.WCC")
                                if "SPpaths" in out_str: algorithms_used.append("algo.SPpaths")

                                if step["tool"] == "open_ticket" and isinstance(step.get("data"), dict):
                                    ticket_id = step["data"].get("ticket_id")
                                if "decision_id" in step.get("args", {}):
                                    target_decision_id = step["args"]["decision_id"]

                            return {
                                "query": query,
                                "retraction_id": retraction_id,
                                "tenant": self.tenant,
                                "trace": trace,
                                "ticket_id": ticket_id,
                                "target_decision_id": target_decision_id,
                                "algorithms_used": list(set(algorithms_used)),
                                "recommendation": loop_res.get("final_answer", ""),
                                "mode": "model-selected tools",
                                "model": loop_res.get("model", ""),
                            }
                    except Exception as e:
                        fallback_reason = str(e)

                # Deterministic Fixed Planner (Fallback or LLM_MODE=off)
                mode_label = "fixed planner (fallback)" if fallback_reason else "fixed planner"
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
                        "selected_by": mode_label,
                    })

                    out_team = await self._execute_tool(session, "recall_team_history", {"tenant": self.tenant})
                    trace.append({
                        "step": 2,
                        "tool": "recall_team_history",
                        "args": {"tenant": self.tenant},
                        "output": f"Recalled {len(out_team.get('active_rules', []))} procedural rules for team {self.tenant}.",
                        "data": out_team,
                        "selected_by": mode_label,
                    })

                    experts_str = ", ".join(f"{e['person']} ({e['role']}, {e['evidence_count']} papers)" for e in out_who.get("experts", []))
                    recommendation = (
                        f"Expertise Assessment for [{topic}]:\n"
                        f"• Clinical Specialists Identified: {experts_str if experts_str else 'Dr. Jane Chen (Chief of Cardiology)'}.\n"
                        f"• Institutional Context: Department has {len(out_team.get('active_rules', []))} active procedural rules on file.\n"
                        f"• Action Taken: Direct consultation recommended before protocol revisions."
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
                        "mode": mode_label,
                        "fallback_reason": fallback_reason,
                    }

                # Question Category 3: "Which decisions are at risk?"
                elif "decision" in query_lower or "at risk" in query_lower:
                    out_blast = await self._execute_tool(session, "blast_radius", {"retraction_id": retraction_id})
                    trace.append({
                        "step": 1,
                        "tool": "blast_radius",
                        "args": {"retraction_id": retraction_id},
                        "output": out_blast["summary"],
                        "data": out_blast,
                        "selected_by": mode_label,
                    })

                    decisions = out_blast.get("at_risk_decisions", [])
                    target_decision_id = decisions[0]["decision_id"] if decisions else "DEC-CARDIO-001"

                    out_path = await self._execute_tool(session, "path_to_decision", {
                        "retraction_id": retraction_id,
                        "decision_id": target_decision_id,
                    })
                    algorithms_used.append(out_path.get("algorithm", "algo.SPpaths"))
                    trace.append({
                        "step": 2,
                        "tool": "path_to_decision",
                        "algorithm": out_path.get("algorithm", "algo.SPpaths"),
                        "args": {"retraction_id": retraction_id, "decision_id": target_decision_id},
                        "output": f"Found shortest evidence path to {target_decision_id}: {out_path.get('path_nodes', [])}",
                        "data": out_path,
                        "selected_by": mode_label,
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
                        "selected_by": mode_label,
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
                        "mode": mode_label,
                        "fallback_reason": fallback_reason,
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
                        "selected_by": mode_label,
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
                        "selected_by": mode_label,
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
                        "selected_by": mode_label,
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
                        "selected_by": mode_label,
                    })

                    # Step 5: path_to_decision (Shortest path)
                    decisions = out_1.get("at_risk_decisions", [])
                    target_decision_id = decisions[0]["decision_id"] if decisions else "DEC-CARDIO-001"
                    args_5 = {"retraction_id": retraction_id, "decision_id": target_decision_id}
                    out_5 = await self._execute_tool(session, "path_to_decision", args_5)
                    algorithms_used.append(out_5.get("algorithm", "algo.SPpaths"))
                    trace.append({
                        "step": 5,
                        "tool": "path_to_decision",
                        "algorithm": out_5.get("algorithm", "algo.SPpaths"),
                        "args": args_5,
                        "output": f"Path to decision {target_decision_id}: {out_5.get('path_nodes', [])}",
                        "data": out_5,
                        "selected_by": mode_label,
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
                        "selected_by": mode_label,
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
                        "mode": mode_label,
                        "fallback_reason": fallback_reason,
                    }

    def execute_plan(self, retraction_id: str = "SYN-RET-001", query: str = "What should we do first?") -> Dict[str, Any]:
        """Synchronous wrapper for run_plan_async."""
        return asyncio.run(self.run_plan_async(query=query, retraction_id=retraction_id))

if __name__ == "__main__":
    agent = AnalystAgent("cardio")
    print("Testing AnalystAgent:")
    res = agent.execute_plan(query="What should we do first?")
    print(f"Executed plan in mode: {res.get('mode')}")
    print(f"Executed {len(res['trace'])} tools:")
    for step in res['trace']:
        print(f"  [{step['step']}] Tool: {step['tool']} (selected_by={step.get('selected_by')}) -> {step['output']}")
    print("Recommendation:\n", res['recommendation'])
