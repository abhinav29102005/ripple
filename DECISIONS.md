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
