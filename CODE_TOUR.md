# Ripple: Architectural Code Tour & Judge Defense Guide

This guide is written for engineers and presenters explaining **Ripple** to hackathon judges. For each core module and each Cypher query, it documents:
1. **What it does**
2. **Why it is written that way** (architectural justification)
3. **Likely judge question with a direct, defensible answer**

---

## 1. Architectural Overview & Graph Topology

Ripple maintains three strictly decoupled graph schemas within FalkorDB:
- **`coord`**: Task queue, agent worker leases, dependency DAG, execution logs.
- **`knowledge`**: The institutional & evidence brain (Trials, Reviews, Guidelines, Retractions, Decisions, People, Committees, Documents, Tickets).
- **`tenant_<id>`** (e.g. `tenant_cardio`, `tenant_onco`): Isolated procedural rules, semantic facts, episodic user feedback, and explainability provenance chains.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          FalkorDB Instance                             │
│                                                                        │
│   ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
│   │   coord Graph    │  │ knowledge Graph  │  │ tenant_* Graphs   │    │
│   │                  │  │                  │  │                   │    │
│   │ • :Task          │  │ • :Trial, :Review│  │ • :Session        │    │
│   │ • :Agent         │  │ • :Guideline     │  │ • :Episode        │    │
│   │ • [:DEPENDS_ON]  │  │ • :Retraction    │  │ • :Rule           │    │
│   │ • [:SPAWNED]     │  │ • :Decision      │  │ • :Fact           │    │
│   │                  │  │ • :Person, :Comm │  │ • :Ranking, :Item │    │
│   │                  │  │ • :Document, :Msg│  │ • [:USED]         │    │
│   │                  │  │ • :Ticket        │  │ • [:RANKED]       │    │
│   │                  │  │ • [:INCLUDED_IN] │  │ • [:LEARNED_FROM] │    │
│   │                  │  │ • [:INFORMS, etc]│  │ • [:SUPERSEDES]   │    │
│   └────────▲─────────┘  └────────▲─────────┘  └────────▲──────────┘    │
└────────────┼─────────────────────┼─────────────────────┼───────────────┘
             │                     │                     │
   ┌─────────┴─────────┐ ┌─────────┴─────────┐ ┌─────────┴─────────┐
   │ Autonomous Worker │ │ Multi-Agent DAG   │ │ Analyst Agent     │
   │ Loop (runner.py)  │ │ (Watcher, Tracer, │ │ (Track 01 MCP &   │
   │                   │ │  Stats, Briefer)  │ │  PageRank/WCC/SP) │
   └───────────────────┘ └───────────────────┘ └───────────────────┘
```

---

## 2. Core Modules

### 2.1 Coordination Engine (`coord.py`)

#### What it does
Implements an atomic, concurrency-safe distributed task queue and multi-agent coordination system entirely inside FalkorDB Cypher queries. It supports:
- Dependency gating (`[:DEPENDS_ON]`) so downstream tasks remain unclaimable until all prerequisites reach `status = 'done'`.
- Atomic worker leasing with configurable timeouts (`lease_until`).
- Garbage collection / dead worker reclamation (`reclaim_expired_leases`).
- Worker heartbeats and agent registry.

#### Why it is written that way
External task brokers (Celery, Redis Streams, RabbitMQ) decouple coordination from the state graph. By keeping tasks in FalkorDB:
1. Task state and dependency resolution occur in a single atomic Cypher execution.
2. If a worker dies, the lease expires and is reclaimed back into the queue without orphan state.
3. Zero extra infrastructure is needed.

#### Likely Judge Question & Answer
> **Judge:** *"Why build a task queue in Cypher when Redis Streams or Celery already exist?"*  
> **Answer:** *"In complex agent workflows, task dependencies are a directed acyclic graph (DAG). Redis Streams cannot natively evaluate multi-parent graph dependency completion atomically. In FalkorDB, a single query checks `ALL(dep IN deps WHERE dep.status = 'done')` and atomically claims the task in under 10ms with zero double-claims across 16 concurrent workers."*

---

### 2.2 Worker Loop & Pipeline Hand-off (`agents/runner.py`, `agents/`)

#### What it does
Runs independent worker processes that poll the `coord` graph, claim ready tasks, invoke specialized domain agents, and record completions:
- **Watcher** (`agents/watcher.py`): Ingests retraction notices.
- **Tracer** (`agents/tracer.py`): Traverses the multi-hop evidence graph to identify affected trials, reviews, and guidelines.
- **Statistician** (`agents/statistician.py`): Recalculates pooled effect sizes via inverse-variance meta-analysis without the retracted trial.
- **Briefer** (`agents/briefer.py`): Generates structured impact briefs and persists `Impact` nodes.

#### Why it is written that way
Each agent is purely functional and stateless. Agents communicate solely by reading from and writing to FalkorDB graphs. A killed worker can be replaced by any other worker with zero in-memory session loss.

#### Likely Judge Question & Answer
> **Judge:** *"How do agents pass data between each other without in-memory state or message queues?"*  
> **Answer:** *"Agents pass data exclusively through FalkorDB nodes. Tracer writes impacted review IDs to the task payload in `coord`; Statistician claims the task, executes meta-analysis math, and writes `Impact` nodes into `knowledge`; Briefer queries the `Impact` node to formulate executive alerts. The graph is the single source of truth."*

---

### 2.3 Evidence Mathematics & Knowledge Graph (`knowledge.py`, `stats.py`)

#### What it does
- `stats.py`: Implements standard epidemiological inverse-variance fixed and DerSimonian-Laird random-effects meta-analysis pooling. Identifies if removing a retracted trial causes a statistical flip (point estimate cross-over or confidence interval crossing null $p=0.05$).
- `knowledge.py`: Traverses blast radius, propagates staleness across organizational decisions, and computes expert rankings (`who_knows`).

#### Why it is written that way
Scientific retractions cannot be evaluated through generic LLM summaries. Medical teams require verifiable effect-size deltas ($\Delta \theta$), weight share reductions ($w_i / \sum w$), and exact citation provenance.

#### Likely Judge Question & Answer
> **Judge:** *"Why do you need a graph to calculate meta-analyses?"*  
> **Answer:** *"The meta-analysis math is done on arrays of effect sizes, but discovering *which* systematic reviews and hospital guidelines are contaminated by a retracted trial requires traversing `(:Retraction)-[:RETRACTS]->(:Trial)-[:INCLUDED_IN]->(:Review)-[:INFORMS]->(:Guideline)-[:SUPPORTS]->(:Decision)`. Relational SQL requires multiple expensive joins across recursive tables; FalkorDB traverses this multi-hop path in milliseconds."*

---

### 2.4 Tenant Memory & Consolidation (`memory.py`, `agents/librarian.py`, `ranking.py`)

#### What it does
- Tracks episodic user interactions (dismiss, escalate, acknowledge).
- **Librarian Agent** analyzes interaction history and consolidates patterns into active procedural rules (e.g. "Down-rank alerts where reason is administrative by 0.3").
- Retires rules when contradictory feedback occurs.
- Tracks semantic facts with full temporal supersession (`valid_from`, `valid_to`, `supersedes_id`).
- Produces full explainability chains (`[:APPLIED]` $\rightarrow$ `[:LEARNED_FROM]`).

#### Why it is written that way
Multi-tenant isolation is enforced at the graph level (`tenant_cardio` vs `tenant_onco`). Procedural memory is stored as graph nodes rather than opaque vector embeddings, allowing deterministic inspection and full user explainability ("Why did this alert rank here?").

#### Likely Judge Question & Answer
> **Judge:** *"How does your agent memory differ from vector-based RAG?"*  
> **Answer:** *"Vector RAG stores unstructured text snippets and retrieves by cosine similarity, which cannot guarantee rule enforcement or explainability. Ripple stores procedural rules as explicit graph nodes with measurable hit rates, delta adjustments, and provenance pointers to the exact feedback episodes that generated them. When an alert score is adjusted, the user can click 'Why?' and inspect the exact rule and historical episodes."*

#### Exact Alert Base-Score Formula (`ranking.py::compute_base_score`)
Alert severity begins with an empirical baseline score computed strictly from the retracted evidence parameters:

$$\text{base} = 0.4 \times \text{reason\_w} + 0.3 \times \text{weight\_share} + 0.2 \times \text{flips} + 0.1 \times \min\left(\frac{\text{guideline\_count}}{3}, 1.0\right)$$

Where:
- **`reason_w`:** `fabrication` ($1.0$), `error` ($0.6$), `unknown` ($0.5$), `administrative` ($0.2$).
- **`weight_share`:** Percentage weight of the retracted trial inside the systematic review meta-analysis ($\in [0.0, 1.0]$).
- **`flips`:** $1.0$ if removing the retracted trial reverses effect direction or nullifies statistical significance ($p < 0.05 \rightarrow p \ge 0.05$); else $0.0$.
- **`guideline_count`:** Number of institutional guidelines citing the review, normalized over a denominator of 3 ($\le 1.0$).

**Worked Real Examples from `scripts/demo_two_teams.py`:**
- **`SYN-REV-ADM` (administrative):** $\text{base} = 0.4(0.2) + 0.3(0.05) + 0.2(0.0) + 0.1(1/3) = 0.08 + 0.015 + 0.0333 = \mathbf{0.1283}$
- **`SYN-REV-FAB` (fabrication):** $\text{base} = 0.4(1.0) + 0.3(0.05) + 0.2(0.0) + 0.1(1/3) = 0.40 + 0.015 + 0.0333 = \mathbf{0.4483}$

#### Ranking Safety Invariants & Clinical Guardrails
1. **Rule Adjustment Cap (`[-0.4, +0.4]`):** Even if an alert matches multiple consolidated down-ranking or up-ranking procedural rules, the total net adjustment is strictly capped at $\pm 0.4$. This guarantees that learned organizational heuristics can personalize prioritization but cannot overpower baseline empirical evidence weights.
2. **Clinical Safety Floor ($\ge 0.5$) with Tie-Breaking:** Medical ethics demand that severe scientific infractions (such as data fabrication) or statistical reversals that invalidate clinical conclusions must never be suppressed by user dismissals. Regardless of how many downranking rules match, alerts where `reason == "fabrication"` or `flips == True` are bound by a hard floor of $0.5$. When the safety floor applies, ties are broken by base score ($\text{final} = 0.5 + 0.01 \times \text{base}$) so that critical alerts do not show a uniform $0.5$ and the higher empirical base score alert retains higher priority.
1. **Rule Adjustment Cap (`[-0.4, +0.4]`):** Even if an alert matches multiple consolidated down-ranking or up-ranking procedural rules, the total net adjustment is strictly capped at $\pm 0.4$. This guarantees that learned organizational heuristics can personalize prioritization but cannot overpower baseline empirical evidence weights.
2. **Clinical Safety Floor ($\ge 0.5$):** Medical ethics demand that severe scientific infractions (such as data fabrication) or statistical reversals that invalidate clinical conclusions must never be suppressed by user dismissals. Regardless of how many downranking rules match, alerts where `reason == "fabrication"` or `flips == True` are bound by a hard floor of $0.5$.

#### Likely Judge Question & Answer (Ranking Safety)
> **Judge:** *"What prevents a rogue user or biased team from training the Librarian to dismiss critical safety retractions?"*  
> **Answer:** *"Ripple enforces hard graph-level safety invariants that override procedural rules. First, total adjustment is capped at $\pm 0.4$. Second, any alert involving scientific fabrication (`reason='fabrication'`) or a statistical flip (`flips=True`) is clamped by a safety floor of $\ge 0.5$. Even if a cardiology team dismisses every administrative notice, a trial retracted for data falsification will never be buried beneath the safety threshold."*

---

### 2.5 MCP Server & Autonomous Analyst (`mcp_server.py`, `analyst.py`)

#### What it does
- `mcp_server.py`: Model Context Protocol server exposing 10 tools, including FalkorDB native algorithms (`algo.pageRank`, `algo.WCC`, `algo.SPpaths`), evidence traversal, and organizational ticketing.
- `analyst.py`: Autonomous agent communicating with the MCP server over stdio via `ClientSession`. Analyzes retraction questions, selects optimal tools, logs tool execution to graph nodes, and opens remediation tickets.

#### Why it is written that way
Follows the open Anthropic Model Context Protocol specification. By communicating over standard MCP clients rather than direct Python imports, Ripple's tools can be plugged into Claude Desktop, Cursor, or any external autonomous agent framework.

#### Likely Judge Question & Answer
> **Judge:** *"Did you implement graph algorithms yourself or use FalkorDB built-ins?"*  
> **Answer:** *"We use FalkorDB's native built-in procedures: `algo.pageRank` for guideline criticality, `algo.WCC` for contamination clustering across co-pooled reviews, and `algo.SPpaths` for shortest path evidence tracing from retraction notice to hospital decision. They execute directly inside the C-engine in FalkorDB without moving graph data into Python."*

---

## 3. Cypher Query Deep Dive

All Cypher queries in Ripple are defined as exact, immutable uppercase constants across `coord.py`, `knowledge.py`, and `memory.py`:

### 3.1 Atomic Task Claim (`coord.py::CYPHER_ATOMIC_CLAIM`)

```cypher
MATCH (t:Task {status: 'queued', type: $type})
OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
WITH t, count(d) AS open WHERE open = 0
WITH t ORDER BY t.priority DESC, t.created ASC LIMIT 1
SET t.status = 'claimed',
    t.claimed_by = $agent,
    t.lease_until = $now + $lease,
    t.attempts = t.attempts + 1
RETURN t.id AS id, t.key AS key, t.type AS type, t.payload AS payload, t.attempts AS attempts
```

- **What it does:** Atomically finds the highest-priority, oldest queued task whose dependency prerequisites are completely satisfied (`open = 0`), and leases it to the worker.
- **Why it is written that way:** Combines dependency validation, priority ordering, and atomic state mutation into a single Cypher transaction. `LIMIT 1` ensures exactly one task is claimed.
- **Judge Defense:** Under 16 concurrent worker processes claiming 500 tasks, FalkorDB serializes transactions and produces **0 double-claims** at 364.2 tasks/sec.

---

### 3.2 Dead Worker Lease Reclamation (`coord.py::CYPHER_RECLAIM_EXPIRED_LEASES`)

```cypher
MATCH (t:Task {status: 'claimed'}) WHERE t.lease_until <= $now
SET t.status = 'queued', t.claimed_by = null
RETURN count(t) AS reclaimed
```

- **What it does:** Scans for tasks held by workers whose lease timestamp has elapsed, resetting them to `'queued'` and stripping the worker assignment.
- **Why it is written that way:** Prevents system deadlocks when workers are assassinated (`kill -9`) or experience hardware failure. Uses `<= $now` to avoid second-boundary race conditions.
- **Judge Defense:** In our chaos engineering benchmark (`scripts/chaos.py`), killing workers mid-task resulted in 100% task recovery (200/200) and zero dropped tasks.

---

### 3.3 Multi-Hop Evidence Blast Radius (`knowledge.py::CYPHER_BLAST_RADIUS`)

```cypher
MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(t:Trial)-[i:INCLUDED_IN]->(rev:Review)
OPTIONAL MATCH (rev)-[:INFORMS]->(g:Guideline)
RETURN t.id AS trial, rev.id AS review, i.yi AS yi, i.sei AS sei, collect(DISTINCT g.id) AS guidelines
```

- **What it does:** Traverses from the retraction notice to all affected clinical trials, systematic reviews, and published guidelines, collecting individual study effect sizes (`yi`) and standard errors (`sei`).
- **Why it is written that way:** Retrieves the entire structural blast radius and numerical input vectors required for statistical meta-analysis in a single index-accelerated query.
- **Judge Defense:** Index lookups on `Retraction(id)` and `Trial(id)` make this sub-millisecond even across hundreds of trials.

---

### 3.4 Variable-Length Staleness Propagation (`knowledge.py::CYPHER_PROPAGATE_STALENESS`)

```cypher
MATCH (r:Retraction {id: $rid})-[:RETRACTS]->(:Trial)-[:INCLUDED_IN]->(rev:Review)<-[:BASED_ON]-(d:Decision)
SET d.status = 'at_risk', d.risk_reason = 'retraction ' + r.id
RETURN count(DISTINCT d) AS flagged
```

- **What it does:** Cascades retraction impact downstream through systematic reviews to hospital committee decisions, flagging them as `status = 'at_risk'`.
- **Why it is written that way:** Directly traverses the institutional policy dependency graph to identify compromised administrative decisions.
- **Judge Defense:** Powers Track 03 (Company Brain), showing how organizational decisions become stale when foundational clinical evidence is retracted.

---

### 3.5 Organizational Expertise Discovery (`knowledge.py::CYPHER_WHO_KNOWS`)

```cypher
MATCH (p:Person)-[:AUTHORED|PARTICIPATED_IN]->(x)
WHERE (x)-[:ON]->(:Topic {name: $topic}) OR (x)-[:ABOUT]->(:Guideline)-[:ON]->(:Topic {name: $topic})
RETURN p.name AS person, p.role AS role, count(DISTINCT x) AS evidence
ORDER BY evidence DESC LIMIT 5
```

- **What it does:** Discovers who in the organization possesses the deepest documented expertise on a medical topic, aggregating authored documents, committee participation, and clinical role.
- **Why it is written that way:** When a guideline or decision is flagged as at-risk, the system must immediately identify which clinical leaders to convene for an emergency review.
- **Judge Defense:** Avoids generic broadcast emails by identifying the exact subject-matter experts with institutional authority on the topic.

---

### 3.6 Explainable Ranking Provenance Path (`memory.py::CYPHER_EXPLAIN_RANKING`)

```cypher
MATCH (rk:Ranking {id: $ranking_id})-[rel:RANKED]->(item:Item {ext_id: $review_id})
OPTIONAL MATCH (rk)-[u:USED]->(r:Rule)
OPTIONAL MATCH (r)-[:LEARNED_FROM]->(e:Episode)
RETURN item.ext_id AS review_id, rel.rank AS rank, rel.score AS score, rel.base AS base,
       r.id AS rule_id, r.feature AS feature, r.value AS value, u.delta AS delta,
       r.description AS rule_desc, collect(DISTINCT e.id) AS episode_ids
```

- **What it does:** Reconstructs the complete explanation chain for why an alert was upranked or downranked for a specific team.
- **Why it is written that way:** Provides a verifiable graph trail from the final score adjustment back to the procedural rule, and from the procedural rule back to the individual historical feedback episodes that generated it.
- **Judge Defense:** Solves the black-box AI problem. The UI displays an interactive "Why?" expander showing the exact Cypher path from ranking to human feedback episodes.

---

### 3.7 Native Graph Algorithms (`knowledge.py`, `mcp_server.py`)

#### Guideline Criticality via Bipartite PageRank
```cypher
CALL algo.pageRank(null, "INFORMS")
YIELD node, score
MATCH (g:Guideline) WHERE id(node) = id(g)
RETURN g.id AS id, g.title AS title, score
ORDER BY score DESC
```
- **Why:** Evaluates topological centrality of clinical guidelines within the evidence graph across incoming `(:Review)-[:INFORMS]->(:Guideline)` citations. Guidelines cited by multiple foundational reviews receive higher PageRank scores (`0.0196` for Cardiology Protocol 1).

#### Contamination Clusters via Weakly Connected Components (WCC)
```cypher
CALL algo.WCC({nodeLabels: ['Review'], relationshipTypes: ['SHARES_TRIAL']})
YIELD node, componentId
RETURN node.id AS id, componentId
ORDER BY componentId ASC
```
- **Why:** Detects non-independent review clusters that pool the exact same retracted trial, revealing systematic contamination across independent medical literatures.

#### Shortest Evidence Path
```cypher
MATCH (source {id: $source_id}), (target {id: $target_id})
CALL algo.SPpaths({sourceNode: source, targetNode: target})
YIELD path
RETURN path
```
- **Why:** Finds the exact shortest chain of evidence linking a newly issued retraction notice to an institutional hospital decision.
