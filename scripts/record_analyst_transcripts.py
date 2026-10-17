"""
Generates docs/analyst_transcripts.md by running the Analyst agent over an
official MCP Client session on three distinct questions:
1. "What should we do first about retraction SYN-RET-001?"
2. "Who knows about Cardiology?"
3. "Which decisions are at risk from retraction SYN-RET-001?"
Demonstrates that distinct tool sets are chosen per question and all tool
invocations execute through the MCP server over stdio.
"""
import os
import json
import time
from analyst import AnalystAgent
from config import settings

def main():
    agent = AnalystAgent("cardio")
    questions = [
        ("What should we do first about retraction SYN-RET-001?", "SYN-RET-001"),
        ("Who knows about Cardiology?", "SYN-RET-001"),
        ("Which decisions are at risk from retraction SYN-RET-001?", "SYN-RET-001"),
    ]

    results = []
    print("=== Executing Analyst Queries over MCP Client Session ===")
    for q, ret_id in questions:
        print(f"\n[QUERY]: {q}")
        res = agent.execute_plan(query=q, retraction_id=ret_id)
        tools_called = [step["tool"] for step in res["trace"]]
        print(f" -> Tools Selected ({len(tools_called)}): {tools_called}")
        print(f" -> Algorithms: {res.get('algorithms_used', [])}")
        results.append(res)

    # Verify that different tool sets were selected
    tool_sets = [tuple(step["tool"] for step in r["trace"]) for r in results]
    assert len(set(tool_sets)) == 3, f"Expected 3 distinct tool sets, got: {tool_sets}"

    # Build Markdown document
    doc = []
    doc.append("# Ripple MCP Analyst: Execution Transcripts\n")
    doc.append(f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S IST')}")
    doc.append(f"**Mode:** `LLM_MODE={settings.llm_mode}` (with deterministic fallback & MCP client routing)")
    doc.append(f"**MCP Protocol:** Python MCP SDK `ClientSession` over `stdio` transport connecting to `mcp_server.py`\n")
    doc.append("## Overview\n")
    doc.append("This document records execution traces from Ripple's autonomous Analyst agent (Track 01). ")
    doc.append("All tool calls are dispatched through an official Model Context Protocol (MCP) client session, ")
    doc.append("leveraging FalkorDB's native graph algorithms (`algo.pageRank`, `algo.WCC`, `algo.SPpaths`), ")
    doc.append("isolated tenant memory, and organizational knowledge entities.\n")

    for i, res in enumerate(results, 1):
        doc.append(f"---\n")
        doc.append(f"### Run {i}: \"{res['query']}\"\n")
        doc.append(f"- **Target Notice:** `{res['retraction_id']}`")
        doc.append(f"- **Target Tenant:** `{res['tenant']}`")
        doc.append(f"- **Algorithms Utilized:** `{res.get('algorithms_used', [])}`")
        if res.get("ticket_id"):
            doc.append(f"- **Created Ticket:** `{res['ticket_id']}`")
        if res.get("target_decision_id"):
            doc.append(f"- **Target Decision:** `{res['target_decision_id']}`")
        doc.append(f"- **Tools Dispatched:** `{', '.join(s['tool'] for s in res['trace'])}`\n")

        doc.append("#### Tool Execution Trace\n")
        doc.append("| Step | Tool Name | Transport | Arguments | Output Summary |")
        doc.append("|:---:|:---|:---:|:---|:---|")
        for s in res["trace"]:
            args_str = json.dumps(s.get("args", {}))
            algo_badge = f"<br>*(algo: {s['algorithm']})*" if "algorithm" in s else ""
            doc.append(f"| {s['step']} | `{s['tool']}`{algo_badge} | MCP stdio | `{args_str}` | {s['output']} |")
        
        doc.append("\n#### Synthesized Recommendation\n")
        doc.append("```text")
        doc.append(res["recommendation"])
        doc.append("```\n")

    content = "\n".join(doc)
    os.makedirs("docs", exist_ok=True)
    with open("docs/analyst_transcripts.md", "w") as f:
        f.write(content)

    print("\n[SUCCESS] Saved all 3 distinct MCP execution transcripts to docs/analyst_transcripts.md!")

if __name__ == "__main__":
    main()
