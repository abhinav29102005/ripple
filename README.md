# RIPPLE: Agent Memory & Cross-Organization Retraction Blast Engine

> **Built for Graph Hacks: Context for AI Agents (WeMakeDevs x FalkorDB)**  
> **Event Hard Deadline:** Sun Oct 18, 11:59 PM IST | **Target Submission:** Sun 6:00 PM IST  
> **Tracks Entered:**  
> • **Track 02 (Primary):** Agent Memory and Coordination  
> • **Track 03:** Company Brain  
> • **Track 01:** Agents That Act on Connected Data  

[![FalkorDB](https://img.shields.io/badge/Graph_Database-FalkorDB%20v4.22+-E11D48?style=for-the-badge&logo=redis&logoColor=white)](https://falkordb.com)
[![Python](https://img.shields.io/badge/Python-3.12%20|%203.14-3B82F6?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-059669?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/Tests-23%20Passed-10B981?style=for-the-badge)](tests/)

---

## 1. Executive Summary & Pitch

When a clinical trial or scientific publication is retracted, the blast radius does not stop at the paper—it silently cascades through systematic reviews, clinical guidelines, hospital formulary decisions, and active patient care protocols.

**Ripple** is an autonomous multi-agent coordination system and organizational memory engine built natively on **FalkorDB**. When a retraction notice appears:
1. **Coordination Engine (FalkorDB Native):** Orchestrates multi-agent pipelines (`Watcher`, `Tracer`, `Statistician`, `Briefer`, `Librarian`) with **0 double-claims**, Cypher dependency gating, and self-healing lease reclamation.
2. **Knowledge Graph & Blast Propagation:** Traverses multi-hop dependency chains from retracted trials to affected meta-analyses, re-quantifies pooled effect sizes before and after removal, flags contaminated guidelines, and identifies institutional decisions placed at risk.
3. **Tenant Memory & Procedural Rules:** Teams develop procedural memory over time: user dismissals or escalations consolidate into active graph rules that dynamically adjust future alert rankings, with full explainability paths from ranking to rules to episodic feedback.
4. **Analyst Agent & Action:** Connects directly via MCP tools and built-in graph algorithms (`algo.pageRank`, `algo.WCC`, `algo.SPpaths`) to plan remediation and auto-open tracking tickets.

---

## 2. "Remove FalkorDB and What Breaks"

FalkorDB is not an auxiliary cache in Ripple; it is the single authoritative source of truth. If FalkorDB is removed:

| Subsystem | What FalkorDB Does | What Breaks Without FalkorDB |
|---|---|---|
| **Coordination Task Queue** | Executes atomic claims (`MATCH ... OPTIONAL MATCH (:Task)-[:DEPENDS_ON]->(d) WHERE d.status <> 'done' WITH t, count(d) AS open WHERE open = 0 ... SET status='claimed' LIMIT 1`). | Race conditions and double claims under concurrency; external brokers (Redis/RabbitMQ) cannot evaluate dynamic multi-task DAG dependencies in a single atomic claim. |
| **Self-Healing Leases** | Recovers abandoned tasks from crashed workers (`WHERE lease_until <= $now SET status='queued'`). | Stranded tasks remain locked indefinitely if workers crash mid-execution. |
| **Blast Radius & Decision Traces** | Multi-hop traversals connecting `Retraction -> Trial -> Review -> Guideline -> Decision -> Documents -> Messages`. | Relational databases require 6+ table joins with recursive CTEs; querying institutional impact becomes sluggish and complex. |
| **Contamination Clustering** | Built-in Weakly Connected Components (`algo.WCC`) across `SHARES_TRIAL` edges. | Detecting non-independent review clusters pooling identical retracted evidence requires heavy in-memory graph duplication. |
| **Guideline Criticality** | Native PageRank (`algo.pageRank("Guideline", "INFORMS")`). | Identifying high-impact guidelines cannot be computed natively in transactional stores. |
| **Shortest Evidence Paths** | Native Single-Pair Shortest Paths (`algo.SPpaths`). | Tracing the shortest evidentiary trail from retraction notice to affected decision fails. |
| **Tenant Memory & Explainability** | Traversal of `(Ranking)-[:USED]->(Rule)-[:LEARNED_FROM]->(Episode)`. | Explaining *why* an alert score changed requires assembling fragmented tables without graph provenance. |
| **Tenant Isolation** | Physical graph-per-team namespace isolation (`tenant_cardio`, `tenant_onco`). | Risk of multi-tenant data leaks and complex row-level security logic. |

---

## 3. Per-Track Qualifications & Hero Proofs

### Track 02: Agent Memory and Coordination (Primary Track)
- **Why it qualifies:** Ripple implements a complete FalkorDB-native coordination engine with atomic task claiming, dependency-gated fan-out (`ingest -> trace -> (quantify x N) -> brief`), lease heartbeats, and self-healing recovery. It pairs coordination with procedural tenant memory (`Session -> Episode -> Rule -> Ranking`) where team feedback autonomously consolidates into scoring rules.
- **Hero Proof:**
  - **High Concurrency Benchmark:** 16 concurrent workers executing 500 tasks with **0 double-claims** at **312+ tasks/sec** (`scripts/bench.py`).
  - **Chaos Worker Assassination:** Two workers killed mid-run with `kill -9`; leases expire; tasks auto-reclaim and finish with **100% completion (200/200)** and **0 tasks lost** (`scripts/chaos.py`).
  - **Procedural Rule Consolidation:** 3 dismissals create an active rule ($\Delta = -0.3$) that shifts the next alert ranking and provides full explainability trees (`tests/test_memory.py`).

### Track 03: Company Brain
- **Why it qualifies:** Interconnects clinical evidence with internal organizational structures (Committees, Decisions, Supporting Documents, Chat Threads, Tickets).
- **Hero Proof:**
  - Ingestion of retraction `SYN-RET-001` immediately propagates staleness, flipping `DEC-CARDIO-001` to `status = 'at_risk'`.
  - Multi-hop Decision Trace: `GET /api/decisions/DEC-CARDIO-001/trace` navigates decision $\rightarrow$ review $\rightarrow$ retracted trial $\rightarrow$ notice, citing supporting documents (`DOC-001`, `DOC-002`) and chat messages (`MSG-001`, `MSG-002`).
  - Institutional Expertise Sourcing: `GET /api/who-knows?topic=Cardiology` aggregates evidence across authorship and committee participation to rank institutional experts.

### Track 01: Agents That Act on Connected Data
- **Why it qualifies:** Implements an MCP (Model Context Protocol) Server exposing 10 tools that invoke built-in FalkorDB algorithms (`algo.pageRank`, `algo.WCC`, `algo.SPpaths`).
- **Hero Proof:**
  - Asking `"What should we do first?"` triggers the autonomous `AnalystAgent`, generating a step-by-step tool execution trace, running PageRank to find critical guidelines, detecting contamination clusters, finding the shortest evidence path, and opening an incident ticket in the graph (`tests/test_analyst_mcp.py`).

---

## 4. Graph Data Models

Ripple maintains three isolated graph namespaces in FalkorDB:

### 4.1 `coord` Graph (Coordination & Task Queue)
| Label | Properties | Description |
|---|---|---|
| `Task` | `id, key, type, status, priority, created, lease_until, attempts, max_attempts, claimed_by, payload, result, error` | Task node. Status: `queued`, `claimed`, `done`, `failed`. |
| `Agent` | `id, role, started, heartbeat` | Registered worker agents. |
| **Edges** | `(Task)-[:DEPENDS_ON]->(Task)`, `(Task)-[:SPAWNED]->(Task)` | Dependency gating and parent-child task tracking. |

### 4.2 `knowledge` Graph (Scientific Evidence & Institutional Brain)
| Label | Properties | Description |
|---|---|---|
| `Trial` | `id, title, year, status, synthetic` | Clinical trials (`status`: `active` or `retracted`). |
| `Review` | `id, title, year, model, synthetic` | Systematic reviews & meta-analyses. |
| `Guideline` | `id, title, body_org, year, synthetic` | Clinical practice guidelines. |
| `Retraction`| `id, date, reason, reason_category, notice_url, synthetic` | Retraction notices. |
| `Impact` | `id, review_id, retraction_id, before, after, pct_change, flips, weight_share` | Pooled effect recalculations. |
| `Person` | `id, name, role, synthetic` | Institutional clinicians and researchers. |
| `Committee`| `id, name, synthetic` | Clinical steering and formulary committees. |
| `Decision` | `id, title, date, status, risk_reason, synthetic` | Institutional decisions (`active` or `at_risk`). |
| `Document` | `id, kind, title, synthetic` | Supporting policy briefs and committee minutes. |
| `Message`  | `id, channel, text, ts, synthetic` | Internal communication threads. |
| `Ticket`   | `id, title, status, priority, synthetic` | Tracking and remediation tickets. |
| **Edges** | `(Retraction)-[:RETRACTS]->(Trial)`, `(Trial)-[:INCLUDED_IN {yi, sei}]->(Review)`, `(Review)-[:INFORMS]->(Guideline)`, `(Review)-[:SHARES_TRIAL]->(Review)`, `(Impact)-[:OF]->(Review)`, `(Decision)-[:BASED_ON]->(Review)`, `(Decision)-[:MADE_BY]->(Committee)`, `(Person)-[:MEMBER_OF]->(Committee)`, `(Document)-[:SUPPORTS]->(Decision)`, `(Message)-[:MENTIONS]->(Decision)`, `(Ticket)-[:TRACKS]->(Decision)` |

### 4.3 `tenant_<id>` Graph (Team Memory & Explainability)
| Label | Properties | Description |
|---|---|---|
| `Session` | `id, started, tenant` | Conversational and interaction sessions. |
| `Message` | `id, seq, role, text, ts` | Conversational messages. |
| `Episode` | `id, ts, kind, reason, weight_bucket, flips, ext_review, ext_retraction` | User actions: `dismiss`, `escalate`, `correct`, `note`. |
| `Fact` | `id, key, value, valid_from, valid_to` | Semantic facts with supersession history. |
| `Rule` | `id, feature, value, delta, support, hit_rate, status, description` | Procedural rules learned by Librarian. |
| `Ranking` | `id, ts, retraction_id` | Historical alert ranking events. |
| `Item` | `id, ext_id, kind` | Ranked alert items. |
| **Edges** | `(Session)-[:FOLLOWS]->(Session)`, `(Session)-[:HAS]->(Message)`, `(Episode)-[:IN]->(Session)`, `(Rule)-[:LEARNED_FROM]->(Episode)`, `(Fact)-[:SUPERSEDES]->(Fact)`, `(Ranking)-[:USED {delta}]->(Rule)`, `(Ranking)-[:RANKED {rank, score, base}]->(Item)` |

---

## 5. Cypher Queries & Built-in Algorithms Library

All Cypher queries are maintained as named constants across Ripple's modules:

### Coordination Engine (`coord.py`)
- **Atomic Claim with Dependency Gating:**
  ```cypher
  MATCH (t:Task {status: 'queued', type: $type})
  OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
  WITH t, count(d) AS open WHERE open = 0
  WITH t ORDER BY t.priority DESC, t.created ASC LIMIT 1
  SET t.status = 'claimed', t.claimed_by = $agent,
      t.lease_until = $now + $lease, t.attempts = t.attempts + 1
  RETURN t.id AS id, t.key AS key, t.type AS type, t.payload AS payload, t.attempts AS attempts
  ```
- **Self-Healing Lease Reclamation:**
  ```cypher
  MATCH (t:Task {status: 'claimed'}) WHERE t.lease_until <= $now
  SET t.status = 'queued', t.claimed_by = null
  RETURN count(t) AS reclaimed
  ```
- **Lease Heartbeat:**
  ```cypher
  MATCH (t:Task {id: $id, claimed_by: $agent, status: 'claimed'})
  SET t.lease_until = $now + $lease
  RETURN t.id AS id
  ```

### Knowledge Graph & Algorithms (`knowledge.py`, `mcp_server.py`)
- **Multi-Hop Blast Radius Traversal:**
  ```cypher
  MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(t:Trial)-[i:INCLUDED_IN]->(rev:Review)
  OPTIONAL MATCH (rev)-[:INFORMS]->(g:Guideline)
  RETURN t.id AS trial, rev.id AS review, i.yi AS yi, i.sei AS sei, collect(DISTINCT g.id) AS guidelines
  ```
- **Staleness Propagation to Decisions:**
  ```cypher
  MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(:Trial)-[:INCLUDED_IN]->(rev:Review)<-[:BASED_ON]-(d:Decision)
  SET d.status = 'at_risk', d.risk_reason = 'retraction ' + r.id
  RETURN count(DISTINCT d) AS flagged
  ```
- **Built-in PageRank Algorithm (Guideline Criticality):**
  ```cypher
  CALL algo.pageRank("Guideline", "INFORMS") YIELD node, score
  RETURN node.id AS id, node.title AS title, score ORDER BY score DESC
  ```
- **Built-in Weakly Connected Components (Contamination Clusters):**
  ```cypher
  CALL algo.WCC() YIELD node, componentId
  RETURN node.id AS id, componentId
  ```
- **Built-in Shortest Path (Evidence to Decision Trace):**
  ```cypher
  MATCH (a {id: $src}), (b {id: $tgt})
  CALL algo.SPpaths({sourceNode: a, targetNode: b}) YIELD path
  RETURN path
  ```

### Tenant Memory & Explainability (`memory.py`)
- **Ranking Explainability Traversal:**
  ```cypher
  MATCH (rk:Ranking {id: $ranking_id})-[rel:RANKED]->(item:Item {ext_id: $review_id})
  OPTIONAL MATCH (rk)-[u:USED]->(r:Rule)
  OPTIONAL MATCH (r)-[:LEARNED_FROM]->(e:Episode)
  RETURN item.ext_id AS review_id, rel.rank AS rank, rel.score AS score, rel.base AS base,
         r.id AS rule_id, r.feature AS feature, r.value AS value, u.delta AS delta,
         r.description AS rule_desc, collect(DISTINCT e.id) AS episode_ids
  ```
- **Semantic Fact Supersession:**
  ```cypher
  MATCH (old:Fact {key: $key}) WHERE old.valid_to IS NULL
  SET old.valid_to = $now
  WITH old
  CREATE (new:Fact {id: $new_id, key: $key, value: $value, valid_from: $now, valid_to: null})
  MERGE (new)-[:SUPERSEDES]->(old)
  RETURN new.id AS id
  ```

---

## 6. Quick Start & Local Setup

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (or `uv`)

### 1. Start Persistent FalkorDB
```bash
docker compose up -d
```
*FalkorDB will be available on port 6379, and FalkorDB Browser on port 3000 (`http://localhost:3000`).*

### 2. Install Dependencies
```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Initialize & Reset Database Deterministically
```bash
python scripts/reset.py
```

### 4. Run Automated Test Suite
```bash
pytest -v tests/
```
*All 23 unit, concurrency, isolation, and pipeline tests will execute.*

### 5. Launch Ripple Web Application
```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```
Open your browser to: **`http://localhost:8000`**

---

## 7. Demo Script (3-Act Walkthrough)

- **Act 1: Company Brain (60s):**
  1. Open dashboard at `http://localhost:8000`.
  2. Select `SYN-RET-001 (Fabrication)`.
  3. Observe the D3 Evidence Blast Radius graph. Click on `SYN-TR-0001` and `SYN-REV-001` to inspect effect sizes.
  4. View at-risk decision `DEC-CARDIO-001` flagged with owners Dr. Sarah Chen and Dr. Marcus Vance to notify.
- **Act 2: Autonomous Analyst (60s):**
  1. Switch to "Analyst Plan" tab.
  2. Click **⚡ Run Autonomous Analyst Remediation Plan**.
  3. Watch the real-time tool calling trace execute across PageRank, WCC, and Shortest Path.
  4. Notice the newly opened incident ticket (`TCK-MCP-...`) linked to the at-risk decision in the graph.
- **Act 3: Tenant Memory & Fault-Tolerant Coordination (75s):**
  1. In Ranked Alerts, click "Why this rank?" on an administrative alert to view baseline scoring.
  2. Click "✕ Dismiss" on 3 administrative alerts.
  3. Watch Panel 3: The Librarian immediately consolidates the feedback into active rule `rule_reason_administrative` ($\Delta = -0.3$).
  4. Notice the alert score immediately drops by 0.3, and "Why this rank?" now displays the applied rule and its 3 source episodes.
  5. Switch tenant to `Oncology Committee` $\rightarrow$ observe that Oncology's memory and rankings remain isolated and untouched.
  6. Run `python scripts/chaos.py` in terminal $\rightarrow$ witness two workers assassinated with `kill -9` while leases auto-reclaim and all tasks finish with 0 double claims.

---

## 8. Data Labeling & Integrity

- **Synthetic Data:** In accordance with Hackathon Rule 4, all generated trial data, reviews, guidelines, decisions, documents, and messages are synthetic, prefixed with `SYN-`, and flagged with property `synthetic: true`.
- **Fictional Organization:** The hospital organization, committees, personnel names, and chat logs are entirely fictional.
- **Deterministic Seeding:** Fixed random seeds ensure 100% reproducible demo and benchmark runs.

---

## 9. Medical Safety & Disclaimer

> **IMPORTANT MEDICAL NOTICE:**  
> Ripple is an automated decision-support and evidence-tracing tool designed strictly for administrative, methodological, and institutional audit review.  
> **Ripple does not recommend changing clinical practice, altering patient treatment regimens, or alleging academic or professional misconduct.**  
> Retraction categorizations strictly report the explicit categorization published in formal retraction notices.

---

## 10. AI Assistance Disclosure

Ripple was designed, architected, and pair-programmed with Google DeepMind's **Antigravity AI coding assistant**. Antigravity assisted in formulating FalkorDB Cypher queries, benchmarking high-concurrency multiprocessing routines, implementing statistical meta-analysis mathematical models, building the 4-panel web dashboard, and verifying all verification spikes (A through D). All architectural decisions, performance benchmarks, and adaptations are logged in [DECISIONS.md](file:///home/bigboyaks/Projects/ripple/DECISIONS.md).
