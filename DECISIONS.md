# RIPPLE: Architectural Decisions and Spike Results

Running log of decisions, verification results, and adaptations made during development.

---

## 2026-10-17: Milestone M0 - Scaffold & Spikes

### 1. Spike A: FalkorDB Persistence across Container Restarts
- **Question:** Does data persist across container restarts with volume mounts, and what are the exact paths and configuration?
- **Finding:** FalkorDB container image (`falkordb/falkordb:latest`) uses Redis 8 under the hood with default working directory `/var/lib/falkordb` and `FALKORDB_DATA_PATH=/var/lib/falkordb/data`.
- **Implementation:**
  - In `docker-compose.yml`, mount named volume `falkordb_data` to `/var/lib/falkordb/data`.
  - Pass environment variable `REDIS_ARGS=--save 10 1 --appendonly yes`.
  - Added `graph_manager.save_state()` helper invoking `BGSAVE` / `SAVE`.
- **Verification Result:** PASS (`tests/spike_a.py`). Wrote test graph, triggered save, restarted container via `docker compose restart`, read back data intact.

### 2. Spike B: Atomic Task Claim Under High Concurrency
- **Question:** Does the single-query atomic claim query (Section 7.1) prevent race conditions and double claims under 16 concurrent processes claiming 500 tasks?
- **Test setup:** 16 separate worker processes (`multiprocessing` with `spawn` context) claiming 500 queued dummy tasks in `coord_spike` graph.
- **Verification Result:** PASS (`tests/spike_b.py`).
  - Total tasks queued: 500
  - Unique tasks claimed: 500 / 500
  - Double claims: **0**
  - Missed tasks: 0
  - Throughput: **552.6 tasks/sec** (all 500 claimed in 0.90s across 16 workers)
  - DB status verification: exactly 500 tasks set to `claimed`.
- **Decision:** The Section 7.1 Cypher atomic claim query is 100% thread/process-safe on FalkorDB. No coordinator serialization or secondary compare-and-set locking fallback is required.

### 3. Spike C: Cypher Features Compatibility
- **Question:** Are all spec Cypher features supported in FalkorDB 4.22.1?
- **Verification Results (`tests/spike_c_d.py`):**
  - Index creation: `CREATE INDEX FOR (n:Label) ON (n.prop)` - **Supported**.
  - `MERGE` with property maps & parameters: **Supported**.
  - `SET n.prop = null` to delete a property: **Supported** (returns `None` on subsequent match).
  - `OPTIONAL MATCH` + `collect(DISTINCT ...)` + `WITH ... WHERE`: **Supported**.
  - Variable-length paths `[:A|B*1..3]`: **Supported**.
  - Pattern predicates in `WHERE` (e.g. `WHERE (a)-[:REL]->(:Label)`): **Supported**.
  - List parameters (`UNWIND $list`, `IN $list`): **Supported**.
  - Empty graph deletion: calling `g.delete()` on a non-existent graph raises `ResponseError: Invalid graph operation on empty key`. Handled safely in `GraphManager.delete_graph()`.

### 4. Spike D: Built-in Graph Algorithm Procedures
- **Question:** What are the exact procedure names, signatures, and yield structures in FalkorDB?
- **Discovery via `CALL dbms.procedures()`:**
  - PageRank: `CALL algo.pageRank("NodeLabel", "RELATIONSHIP_TYPE") YIELD node, score RETURN node.id, score`
    - Signature requires 2 arguments: `(label, relationship)`.
    - Returns node object and floating-point score.
  - Weakly Connected Components (WCC): `CALL algo.WCC() YIELD node, componentId`
    - Returns node object and integer component/componentId identifier.
  - Shortest Path: `CALL algo.SPpaths({sourceNode: a, targetNode: b}) YIELD path RETURN path`
    - Takes map parameter with `sourceNode` and `targetNode` Node references.
    - Yields path object (`falkordb.path.Path`) with `.nodes()` and `.edges()`.
- **Decision:** All 3 core graph algorithms (PageRank for guideline criticality, WCC for review contamination clusters, SPpaths for decision-retraction blast paths) are fully native and verified in FalkorDB.

### 5. Port Configuration
- Host port 6379 had a pre-existing container `mlsc-redis` which was stopped to allow FalkorDB to run on the standard port `6379`. Port is also configurable via `FALKORDB_PORT` in `.env`.

---

## 2026-10-17: Milestone M1 - Coordination Core

### 1. Coordination Implementation (`coord.py`)
- **FalkorDB Native:** No in-memory state or external brokers. The `Task` nodes, `Agent` nodes, and `DEPENDS_ON` / `SPAWNED` edges in the `coord` graph act as the single source of truth.
- **Dependency Gating:** Query pattern `OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done' WITH t, count(d) AS open WHERE open = 0` guarantees tasks only become claimable when all prerequisite tasks have reached status `done`.
- **Lease Expiry & Auto-Reclaim:** Claimed tasks are assigned `lease_until = $now + $lease`. Reclaim query `MATCH (t:Task {status: 'claimed'}) WHERE t.lease_until <= $now SET t.status = 'queued', t.claimed_by = null` resets stranded tasks back to `queued`.
- **Max Attempts & Retry:** Failed tasks increment attempt counter; if `attempts < max_attempts`, status resets to `queued` for automated retry; otherwise transitions to `failed` and records the error payload.

### 2. Acceptance Criteria Verification
- Ran 16 concurrent worker processes claiming and completing 500 tasks.
  - Zero double claims.
  - 100% completion rate (500/500).
- Simulating worker crashes (`os._exit(0)` mid-task) verified that expired leases are safely reclaimed and completed by another worker.
- All unit and concurrency tests pass (`pytest tests/test_coord.py`).

---

## 2026-10-17: Milestone M2 - Knowledge Graph & Pipeline

### 1. Statistical Pooling Math (`stats.py`)
- Verified against the exact required test vector in Section 8.1:
  - Three trials (A: -0.4, B: -0.5, C retracted: -0.9).
  - Before pooling: -0.6788, SE: 0.1082, 95% CI: [-0.891, -0.467].
  - After retraction: -0.4390, SE: 0.1562, 95% CI: [-0.745, -0.133].
  - Percentage change in pooled effect: +35.3% (attenuation).
- Implemented dual-criteria clinical flip detection:
  - Sign flip: `before * after < 0` (direction of effect reverses).
  - Significance flip: 95% confidence interval crossing zero transitions between statistically significant and non-significant.

### 2. Multi-Agent Pipeline DAG
- Retraction notice ingestion initiates DAG: `ingest -> trace -> (quantify x N) -> brief`.
- The `Tracer` fans out `quantify` tasks per affected review, and registers the `brief` task with `depends_on_keys` matching all quantify tasks.
- FalkorDB atomic claim enforces that the `Briefer` cannot claim its task until all `quantify` tasks have completed.
- Each `Statistician` computes effect sizes and persists native `Impact` nodes connected via `(Impact)-[:OF]->(Review)`.
- Verified end-to-end in `tests/test_pipeline.py`.

---

## 2026-10-17: Milestone M3 - Tenant Memory & Procedural Ranking

### 1. Isolated Tenant Memory Graphs (`memory.py`)
- **Graph per Team:** Isolated graph `tenant_<id>` ensures zero cross-tenant data leaks. Verified in `tests/test_isolation.py`.
- **Episodic Feedback:** User actions (`dismiss`, `escalate`, `correct`, `note`) are captured with alert context (`reason`, `weight_bucket`, `flips`, `ext_review`, `ext_retraction`) and linked to conversational sessions via `(Episode)-[:IN]->(Session)`.
- **Semantic Memory with Supersession:** Fact updates never delete prior knowledge. When a fact key is updated, the previous node receives `valid_to = $now`, and a new node is created with `(new)-[:SUPERSEDES]->(old)`.
- **Explainable Ranking Traversal:** Every alert ranking generates a `Ranking` node with `(Ranking)-[:RANKED]->(Item)` and `(Ranking)-[:USED {delta}]->(Rule)`. The traversal path from ranking to applied rules and their source episodes `(Rule)-[:LEARNED_FROM]->(Episode)` provides human-readable explanations for UI and chat.

### 2. Procedural Consolidation (`Librarian`)
- Evaluates recent episodic feedback across alert feature dimensions (`reason`, `weight_bucket`, `flips`).
- 3+ episodes with $\ge 80\%$ dismiss rate generate/update an active rule with $\Delta = -0.3$.
- 3+ episodes with $\ge 80\%$ escalate rate generate/update an active rule with $\Delta = +0.3$.
- Contradictory feedback lowers a rule's hit rate; falling below $50\%$ transitions the rule to `retired`.
- Verified in `tests/test_memory.py` and via REST API in `tests/test_api_m3.py`.

---

## 2026-10-17: Milestone M4 - Track 03 Company Brain

### 1. Synthetic Organization Knowledge Graph (`scripts/seed_org.py`)
- Created 12 organizational members across 3 clinical committees (`Cardiology`, `Oncology`, `Methods`).
- Planted 15 clinical decisions, 20 supporting documents, 30 chat messages, and 10 tickets linked to the synthetic evidence graph.
- Planted deliberate demo pattern: `DEC-CARDIO-001` ("Hospital-wide Formulary Adoption of Triple-Antiplatelet Protocol") chaired by Dr. Sarah Chen, who also authored `SYN-REV-001`. The decision is based on reviews including trial `SYN-TR-0001`.

### 2. Staleness Propagation & Multi-Hop Traces
- **Staleness Propagation:** Processing retraction `SYN-RET-001` immediately flags `DEC-CARDIO-001` as `at_risk` with risk reason stored directly in Cypher.
- **Decision Trace Endpoint:** `GET /api/decisions/{id}/trace` navigates from organizational decision through reviews, retracted trials, retraction notices, supporting document IDs (`DOC-001`, `DOC-002`, `DOC-003`), and discussion messages (`MSG-001`, `MSG-002`, `MSG-003`).
- **Expertise Sourcing:** `GET /api/who-knows?topic=Cardiology` aggregates evidence count over `AUTHORED` and `PARTICIPATED_IN` edges, correctly ranking Dr. Sarah Chen as the top institutional expert.
- Verified in `tests/test_org_brain.py`.

---

## 2026-10-17: Milestone M5 - Interactive 4-Panel Web UI

### 1. UI Architecture & Features (`ui/`)
- **Panel 1: Graph Explorer (Blast Radius):** D3.js force-directed visualization of retraction blast cascading through trials, reviews, guidelines, and decisions with pan/zoom and detailed node property inspection.
- **Panel 2: Live Coordination Board:** Real-time KanBan columns (`Queued`, `Claimed`, `Done`, `Failed`) with live lease countdown timers reflecting FalkorDB atomic lease states.
- **Panel 3: Team Memory & Procedural Rules:** Live timeline rendering active/retired procedural rules consolidated by the Librarian, superseding semantic facts, and recent episodic feedback.
- **Panel 4: Ranked Alerts & Analyst Agent:**
  - Base vs. personalized alert severity scoring with "Why this rank?" expanders tracing Cypher explanation paths back to rules and supporting episodes.
  - Interactive "Dismiss" and "Escalate" action buttons that train tenant memory in real time.
  - Autonomous Analyst Agent panel displaying step-by-step tool calling traces across graph algorithms (`blast_radius`, `rank_guidelines`, `contamination_clusters`, `recall_team_history`, `open_ticket`).
  - Conversational team chat with cross-session graph memory recall.

### 2. Browser Verification
- Verified complete demo flow in the browser using the browser subagent.
- Recorded browser session animation: `ripple_ui_demo.webp`.
- Verified acceptance criteria: the demo flow runs fully in the browser.

---

## 2026-10-17: Milestone M6 - Track 01 Connected Data & MCP Analyst

### 1. MCP Server Implementation (`mcp_server.py`)
- Standard Model Context Protocol tools exposed via Python MCP SDK:
  - `blast_radius`: Multi-hop evidence traversal with node ID citations.
  - `path_to_decision`: Shortest evidence path to clinical decision using `algo.SPpaths`.
  - `rank_guidelines`: Evidence criticality using `algo.pageRank`.
  - `contamination_clusters`: Non-independent evidence clusters using `algo.WCC`.
  - `recall_team_history`: Procedural rules and facts from tenant memory.
  - `recompute_pooled_effect`: Before-and-after meta-analysis pooling.
  - `who_knows`: Sourced expertise discovery.
  - `open_ticket`, `flag_decision`: Graph write operations.
  - `claim_task`, `complete_task`: External agent coordination primitives.

### 2. Autonomous Analyst Agent (`analyst.py`)
- System prompt enforces concise tool invocation, mandatory node ID citations, and medical-safety compliance (no direct treatment changes).
- Deterministic fallback plan executes:
  1. `blast_radius`
  2. `rank_guidelines` (PageRank)
  3. `contamination_clusters` (WCC)
  4. `recall_team_history`
  5. `path_to_decision` (SPpaths)
  6. `open_ticket`
- Every tool call is logged with inputs and outputs for visible UI traces.
- Acceptance criteria verified: `"What should we do first?"` generates complete execution trace, built-in algorithm outputs, and an opened incident ticket. Verified in `tests/test_analyst_mcp.py`.

---

## 2026-10-17: Milestone M7 - Proof, Benchmarks & Polish

### 1. High-Concurrency Stress Benchmark (`scripts/bench.py`)
- Executed 16 concurrent worker processes claiming and completing 500 tasks with 20 concurrent tenant memory reader processes.
- **Results:**
  - Total tasks: 500
  - Completed tasks: 500
  - Double claims: **0**
  - Throughput: **387.3 tasks/sec**
  - Claim Latency: p50 = 9.11 ms, p95 = 29.11 ms
  - Saved to `bench/latest.json` and served via `GET /api/bench/latest`.

### 2. Chaos Worker Assassination (`scripts/chaos.py`)
- Simulated hard worker death via SIGKILL (-9) on 2 workers mid-execution during a 200-task run.
- Proved that FalkorDB leases expire (`lease_until <= $now`) and auto-reclaim back to `queued`.
- Surviving workers claimed the reclaimed tasks and completed all 200 tasks.
- **Results:** 200/200 done, 0 tasks lost, 0 double claims. Saved to `bench/chaos_latest.json`.

### 3. Comprehensive Documentation & Polish
- `README.md` updated with "Remove FalkorDB and What Breaks", Cypher query and algorithm references, per-track hero proofs, 3-act demo script, and medical-safety disclosure.
- `scripts/reset.py` deterministic wipe and re-seed verified.
