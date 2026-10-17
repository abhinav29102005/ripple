# RIPPLE: Agent Memory & Cross-Organization Retraction Blast Engine

> **Built for Graph Hacks: Context for AI Agents (WeMakeDevs x FalkorDB)**

[![FalkorDB](https://img.shields.io/badge/Graph_Database-FalkorDB-red)](https://falkordb.com)
[![Python 3.12+](https://img.shields.io/badge/Python-3.14-blue)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)](https://docker.com)

---

## 1. Overview & Pitch

When a clinical trial or scientific publication is retracted, the blast radius does not stop at the paper—it cascades through systematic reviews, clinical guidelines, hospital procurement policies, and active patient care protocols.

**Ripple** is an autonomous multi-agent coordination system and organizational memory engine backed by **FalkorDB**. When a retraction notice appears:
1. **Coordination Engine (FalkorDB Native):** Orchestrates multi-agent tasks (`Watcher`, `Tracer`, `Statistician`, `Briefer`, `Librarian`) with zero double-claims, graph-native dependency gating, and self-healing lease reclamation.
2. **Knowledge Graph & Blast Propagation:** Traverses multi-hop dependency chains from retracted trials to affected meta-analyses, re-quantifies pooled effect sizes (fixed and random effects), flags contaminated guidelines, and identifies organizational decisions placed at risk.
3. **Tenant Memory & Procedural Rules:** Teams develop procedural memory over time: user dismissals or escalations consolidate into active graph rules that dynamically adjust future alert rankings, with full explainability paths from ranking to rules to episodic feedback.
4. **Analyst Agent & Action:** Connects directly via MCP tools and built-in graph algorithms (`algo.pageRank`, `algo.WCC`, `algo.SPpaths`) to plan remediation and auto-open tracking tickets.

---

## 2. Tracks Entered

- **Primary:** Track 02 — Agent Memory and Coordination
- Track 03 — Company Brain
- Track 01 — Agents That Act on Connected Data

---

## 3. Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.12+ (or `uv`)

### Setup
```bash
# 1. Start persistent FalkorDB container
docker compose up -d

# 2. Setup virtual environment & dependencies
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# 3. Copy environment configuration
cp .env.example .env

# 4. Run tests
pytest tests/
```

---

## 4. Graph Data Models

Ripple maintains three isolated graph namespaces in FalkorDB:
1. `coord`: Distributed agent coordination, atomic task queue, lease heartbeats, and dependency DAG.
2. `knowledge`: Scientific evidence graph (Trials, Reviews, Guidelines, Retractions, Impact nodes) interconnected with synthetic organizational nodes (Committees, Decisions, Documents, Tickets).
3. `tenant_<id>`: Isolated organizational team graphs containing episodic sessions, superseded facts, procedural rules, and explained ranking trees.

---

## 5. Medical Safety & Disclaimer

> **IMPORTANT NOTICE:**
> Ripple is an automated decision-support and evidence-tracing tool intended solely for administrative and methodological human review.
> **Ripple does not recommend changing clinical practice, making patient treatment decisions, or alleging academic misconduct.**
> All retraction categorizations reflect only the stated reasons in published retraction notices. All organizational data is synthetic.

---

## 6. AI Assistance Disclosure

This project was built with the assistance of Google DeepMind's Antigravity AI assistant. Architecture, Cypher queries, statistical models, coordination primitives, and tests were designed, pair-programmed, and verified against running FalkorDB database instances following the project specifications in `RIPPLE_PROJECT.md`.
