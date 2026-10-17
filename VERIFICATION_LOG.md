# RIPPLE Verification Log

This document records the empirical verification of Ripple's core systems against the running database and test suite.

---

## 1. Automated Test Suite

- **Status:** **36 / 36 Passed (100%)**
- **Command:** `pytest tests/ -v`
- **Coverage Areas:**
  - `tests/test_coord.py`: Task claim concurrency, lease expiration, heartbeat extension, double-claim prevention.
  - `tests/test_pipeline.py`: End-to-end pipeline execution from task claim to blast radius to alert generation.
  - `tests/test_memory.py`: Procedural rule consolidation from episodic dismissals, explainability tracing, fact supersession.
  - `tests/test_ranking_safety.py`: Rule delta clamp $[-0.4, +0.4]$, safety floor ($\ge 0.5$ for fabrication/flips), tie-breaking by base score, rule stacking.
  - `tests/test_isolation.py`: Cross-tenant database isolation between `tenant_cardio` and `tenant_onco`.
  - `tests/test_analyst_mcp.py`: Model Context Protocol (MCP) tool execution and graph algorithm dispatch.
  - `tests/test_llm_mock.py`: OpenAI-compatible multi-turn tool calling loop, 6-step cap, exponential backoff, and graceful fallback.
  - `tests/test_org_brain.py`: Organization evidence traversal, committee decision mapping, and expert lookups.
  - `tests/test_stats.py`: Meta-analytic fixed/random effects recomputation and statistical significance shifts.
  - `tests/test_reason_normalization.py`: Classification and normalization of notice reason text, safe ingestion overrides.
  - `tests/test_pipeline.py`: Full end-to-end retraction ingestion and API notice submission verification.

---

## 2. Graph Schema Verification

- **Status:** Verified on local FalkorDB (port 6380) and FalkorDB Cloud.
- **Labels (10):** `Topic` (50), `Trial` (40), `Person` (30), `Review` (20), `Episode` (15), `Rule` (6), `Guideline` (5), `Journal` (4), `Drug` (2), `Alert` (1). Total Nodes: 173.
- **Relationship Types (15):** `INCLUDED_IN` (80), `PUBLISHED_IN` (40), `SUPPORTS` (36), `PARTICIPATED_IN` (31), `MENTIONS` (30), `ABOUT` (29), `BASED_ON` (16), `AUTHORED` (16), `ON` (15), `MADE_BY` (15), `MEMBER_OF` (14), `INFORMS` (13), `TRACKS` (10), `RETRACTS` (4), `OWNS` (2). Total seeded relationships: 351.
- **Derived Edges:** `(:Review)-[:SHARES_TRIAL]->(:Review)` edges are created lazily upon contamination analysis.

---

## 3. Autonomous LLM Analyst Tool-Calling

- **Status:** Verified live against Groq (`openai/gpt-oss-120b`) over stdio MCP client (`ClientSession`).
- **Command:** `python scripts/record_live_llm_transcripts.py`
- **Results:**
  - Question 1 ("what should we do first?"): Autonomously selected `blast_radius`, `rank_guidelines`, `open_ticket`.
  - Question 2 ("who knows about Cardiology?"): Autonomously selected `who_knows`.
  - Question 3 ("which decisions are at risk?"): Autonomously selected `blast_radius`, `path_to_decision`.
  - Transcripts logged verbatim in `docs/analyst_transcripts_live.md`. Zero fallbacks.

---

## 4. Multi-Tenant Memory & Ranking Safety

- **Status:** Verified via `python -m scripts.demo_two_teams`.
- **Results:**
  - Administrative alert (`SYN-REV-ADM`): Cardio score dropped to `0.0000` via conjunctive rule `rule_administrative_low` while Oncology scored `0.1283` (clean baseline).
  - Fabrication alert (`SYN-REV-FAB`): Both teams held above safety floor at `0.5045` (base `0.4483` with safety floor tie-breaker active).
  - Rule learning evaluated on conjunctive feature tuples `(reason, weight_bucket)`, preventing overly broad rules.

---

## 5. Built-in Graph Algorithms

- **PageRank:** `CALL algo.pageRank(null, "INFORMS")` executed across the bipartite Review $\rightarrow$ Guideline evidence graph, yielding differentiated scores for all 5 clinical guidelines (top guideline `SYN-GL-001` at `0.0196`).
- **Weakly Connected Components (WCC):** `CALL algo.WCC({nodeLabels: ['Review'], relationshipTypes: ['SHARES_TRIAL']})` isolates contaminated review clusters pooling retracted trials (Component 21: `SYN-REV-003`, `SYN-REV-004`).
- **Shortest Path:** `CALL algo.SPpaths` finds exact evidence paths from retractions to compromised hospital decisions.

## 6. Execution Environment & Verification Scope

- **FalkorDB Cloud vs Local Environment:**
  - Full cloud schema verification, graph seeding (`knowledge`, `coord`, `tenant_cardio`, `tenant_onco`), and graph algorithm smoke tests (`algo.pageRank`, `algo.WCC`, `algo.SPpaths`) were run and verified against FalkorDB Cloud on 2026-10-17.
  - Concurrency throughput stress testing (16 workers, 500 tasks, zero double-claims) and local development runs were executed against the local FalkorDB instance (port 6380) to preserve Cloud instance quotas.
- **LLM Presets:**
  - Groq (`openai/gpt-oss-120b` via OpenAI-compatible endpoint) verified live with function-calling tool execution.
  - Mistral, OpenRouter, and Ollama configuration presets are structurally validated in `llm.py` and `tests/test_llm_mock.py`, but not verified with live keys.
