"""
Record live transcripts for 3 clinical analyst queries executed twice each (6 total runs)
via MCP Client with autonomous OpenAI-compatible tool selection (Groq openai/gpt-oss-120b).
Saves verbatim output to docs/analyst_transcripts_live.md without manual editing.
"""
import os
import sys
import json
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyst import AnalystAgent
from config import settings

load_dotenv()

QUERIES = [
    "what should we do first?",
    "who knows about Cardiology?",
    "which decisions are at risk?",
]

def main():
    print("=== Recording Live LLM Analyst Transcripts (2 Runs per Question) ===")
    print(f"Provider: OpenAI-Compatible ({settings.llm_base_url})")
    print(f"Model: {settings.llm_model}")
    print(f"LLM_MODE: {settings.llm_mode}")

    doc = []
    doc.append("# Live LLM Analyst Execution Transcripts")
    doc.append(f"\n**Execution Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    doc.append(f"**Endpoint:** `{settings.llm_base_url}`")
    doc.append(f"**Model ID:** `{settings.llm_model}`")
    doc.append(f"**Protocol:** Model Context Protocol (MCP) Stdio Client (`mcp.client.session.ClientSession`)")
    doc.append(f"**Temperature:** `0` | **Max Steps:** `6`")
    doc.append(f"**Fallback Status:** None (All runs autonomous model-selected tools)")
    doc.append("\n---\n")

    agent = AnalystAgent("cardio")

    for q_idx, q in enumerate(QUERIES, 1):
        doc.append(f"## Question {q_idx}: \"{q}\"\n")
        print(f"\n[Question {q_idx}/3] \"{q}\"")

        for run_idx in (1, 2):
            print(f"  -> Executing Run {run_idx}...")
            start_t = time.time()
            res = agent.execute_plan(query=q)
            dur = time.time() - start_t

            mode = res.get("mode")
            trace = res.get("trace", [])
            tools_chosen = [s["tool"] for s in trace]

            doc.append(f"### Run {run_idx}")
            doc.append(f"- **Execution Mode:** `{mode}`")
            doc.append(f"- **Duration:** {dur:.2f}s")
            doc.append(f"- **Tools Chosen ({len(tools_chosen)}):** `{'`, `'.join(tools_chosen) if tools_chosen else 'None'}`")
            doc.append(f"- **Algorithms Triggered:** `{'`, `'.join(res.get('algorithms_used', [])) if res.get('algorithms_used') else 'None'}`")
            doc.append("\n#### Execution Trace\n")
            doc.append("| Step | Tool | Arguments | Output Summary | Selected By |")
            doc.append("|---|---|---|---|---|")

            for s in trace:
                args_str = json.dumps(s.get("args", {}))
                out_str = s.get("output", "").replace("\n", " ")[:160]
                doc.append(f"| {s['step']} | `{s['tool']}` | `{args_str}` | {out_str} | `{s.get('selected_by')}` |")

            doc.append("\n#### Final Model Response\n")
            doc.append("```")
            doc.append(res.get("recommendation", "").strip())
            doc.append("```\n")

            time.sleep(2.0)  # Brief delay between runs to respect token-per-minute limits

    os.makedirs("docs", exist_ok=True)
    with open("docs/analyst_transcripts_live.md", "w") as f:
        f.write("\n".join(doc) + "\n")

    print("\n[OK] Successfully wrote docs/analyst_transcripts_live.md")

if __name__ == "__main__":
    main()
