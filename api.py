import os
import json
from agents.watcher import WatcherHandler
from agents.tracer import TracerHandler
from agents.statistician import StatisticianHandler
from agents.briefer import BrieferHandler
from analyst import AnalystAgent
"""
FastAPI REST API for Ripple.
Exposes endpoints for retraction submissions, task board status,
graph exploration, tenant memory, personalized alert rankings, and feedback.
"""
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
import time
from collections import defaultdict
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings
from graph import graph_manager
from coord import CoordEngine
from knowledge import KnowledgeEngine
from memory import TenantMemory
from ranking import RankingEngine
from agents.librarian import LibrarianHandler

app = FastAPI(
    title="Ripple API",
    description="FalkorDB-Native Multi-Agent Coordination & Organizational Brain Engine",
    version="1.0.0",
)


RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10  # max requests per window in public mode
_ip_request_timestamps = defaultdict(list)

def get_client_ip(request: Request) -> str:
    trust_proxy = os.getenv("TRUST_PROXY", "0").lower() in ("1", "true", "yes")
    if trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # Last value added by the trusted proxy
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if parts:
                return parts[-1]
    return request.client.host if (request.client and request.client.host) else "127.0.0.1"

def reset_rate_limits():
    _ip_request_timestamps.clear()

def check_public_rate_limit(request: Request):
    public_mode = os.getenv("PUBLIC_MODE", "0").lower() in ("1", "true", "yes") or settings.public_mode
    if not public_mode:
        return
    client_ip = get_client_ip(request)
    now = time.time()
    _ip_request_timestamps[client_ip] = [ts for ts in _ip_request_timestamps[client_ip] if now - ts < RATE_LIMIT_WINDOW]
    if len(_ip_request_timestamps[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({RATE_LIMIT_MAX_REQUESTS} req/min). Public demo mode is active. Please wait a moment."
        )
    _ip_request_timestamps[client_ip].append(now)

class DynamicCORSMiddleware(CORSMiddleware):
    def is_allowed_origin(self, origin: str) -> bool:
        env_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
        allowed = set(self.allow_origins) | set(env_origins)
        return origin in allowed

cors_origins_raw = os.getenv("CORS_ORIGINS", "").strip()
initial_allowed_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    DynamicCORSMiddleware,
    allow_origins=initial_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# --- Request / Response Models ---

class RetractionSubmission(BaseModel):
    retraction_id: str
    trial_id: str
    reason: str
    reason_category: str = "unknown"
    notice_url: str = ""

class EpisodeSubmission(BaseModel):
    session_id: Optional[str] = None
    kind: str = Field(..., description="dismiss, escalate, correct, or note")
    reason: str
    weight_bucket: str = "low"
    flips: bool = False
    ext_review: str
    ext_retraction: str
    notes: str = ""

class FactSubmission(BaseModel):
    key: str
    value: str

# --- Endpoints ---

def classify_reason_wording(reason: str, explicit_category: Optional[str] = None) -> str:
    if explicit_category and explicit_category.lower() not in ("unknown", ""):
        cat = explicit_category.lower().strip()
        if cat in ("data_falsification", "falsification"):
            return "fabrication"
        return cat
    r_lower = (reason or "").lower()
    if any(w in r_lower for w in ("fabricat", "falsif", "fraud", "manipulat", "misconduct")):
        return "fabrication"
    elif any(w in r_lower for w in ("error", "mistake", "calculation", "coding", "software bug", "flaw")):
        return "error"
    elif any(w in r_lower for w in ("administrative", "publisher", "formatting", "duplicate", "author request")):
        return "administrative"
    return "unknown"

@app.get("/api/health")
def health_check():
    graphs = graph_manager.list_graphs()
    return {"status": "ok", "graphs": graphs, "llm_mode": settings.llm_mode}

@app.post("/api/retractions")
def submit_retraction(sub: RetractionSubmission):
    coord = CoordEngine(graph_manager.get_graph("coord"))
    category = classify_reason_wording(sub.reason, sub.reason_category)
    task_key = f"ingest:{sub.retraction_id}"
    task_id = coord.spawn_task(
        task_type="ingest",
        payload={
            "retraction_id": sub.retraction_id,
            "trial_id": sub.trial_id,
            "reason": sub.reason,
            "reason_category": category,
            "notice_url": sub.notice_url,
        },
        key=task_key,
        priority=3,
    )
    return {"status": "queued", "task_id": task_id, "task_key": task_key}

@app.get("/api/tasks")
def list_tasks():
    coord = CoordEngine(graph_manager.get_graph("coord"))
    return {"tasks": coord.list_tasks()}

@app.get("/api/agents")
def list_agents():
    coord = CoordEngine(graph_manager.get_graph("coord"))
    return {"agents": coord.list_agents()}

@app.get("/api/graph/blast/{retraction_id}")
def get_graph_blast(retraction_id: str):
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    items = knowledge.get_blast_radius(retraction_id)

    nodes_map = {}
    edges = []

    # Source retraction node (Central Nucleus of the Brain)
    nodes_map[retraction_id] = {
        "id": retraction_id,
        "label": "Retraction",
        "title": f"Retraction Notice ({retraction_id})",
        "hemisphere": "core",
    }

    for item in items:
        trial_id = item["trial"]
        rev_id = item["review"]

        if trial_id not in nodes_map:
            nodes_map[trial_id] = {
                "id": trial_id,
                "label": "Trial",
                "title": f"Retracted Trial {trial_id}",
                "status": "retracted",
                "hemisphere": "left",
            }
        if rev_id not in nodes_map:
            nodes_map[rev_id] = {
                "id": rev_id,
                "label": "Review",
                "title": f"Systematic Review {rev_id}",
                "yi": item["yi"],
                "sei": item["sei"],
                "hemisphere": "left",
            }

        edges.append({"source": retraction_id, "target": trial_id, "type": "RETRACTS"})
        edges.append({"source": trial_id, "target": rev_id, "type": "INCLUDED_IN", "yi": item["yi"], "sei": item["sei"]})

        for gid in item.get("guidelines", []):
            if gid not in nodes_map:
                nodes_map[gid] = {
                    "id": gid,
                    "label": "Guideline",
                    "title": f"Clinical Practice Guideline {gid}",
                    "hemisphere": "left",
                }
            edges.append({"source": rev_id, "target": gid, "type": "INFORMS"})

    # Primary reviews in blast
    rev_ids = [n["id"] for n in nodes_map.values() if n["label"] == "Review"]

    # Contamination neighbor reviews (cross-talk between left and right hemispheres)
    if rev_ids:
        contam_res = knowledge.graph.query(
            "MATCH (r:Review)<-[:INCLUDED_IN]-(t:Trial)-[:INCLUDED_IN]->(r2:Review) "
            "WHERE r.id IN $rev_ids AND r <> r2 "
            "OPTIONAL MATCH (r2)-[:INFORMS]->(g2:Guideline) "
            "RETURN r2.id AS r2id, t.id AS tid, g2.id AS g2id, r2.title AS r2title, g2.title AS g2title",
            {"rev_ids": rev_ids}
        )
        for row in contam_res.result_set:
            r2id, tid, g2id, r2title, g2title = row
            if r2id not in nodes_map:
                nodes_map[r2id] = {
                    "id": r2id,
                    "label": "Review",
                    "title": r2title or r2id,
                    "status": "contaminated",
                    "hemisphere": "right",
                }
            if tid not in nodes_map:
                nodes_map[tid] = {
                    "id": tid,
                    "label": "Trial",
                    "title": tid,
                    "status": "active",
                    "hemisphere": "bridge",
                }
            edges.append({"source": tid, "target": r2id, "type": "INCLUDED_IN"})
            if g2id:
                if g2id not in nodes_map:
                    nodes_map[g2id] = {
                        "id": g2id,
                        "label": "Guideline",
                        "title": g2title or g2id,
                        "hemisphere": "right",
                    }
                edges.append({"source": r2id, "target": g2id, "type": "INFORMS"})

    # Co-included evidence trials that form the evidence base of these reviews
    all_rev_ids = [n["id"] for n in nodes_map.values() if n["label"] == "Review"]
    if all_rev_ids:
        co_res = knowledge.graph.query(
            "MATCH (t:Trial)-[inc:INCLUDED_IN]->(rev:Review) "
            "WHERE rev.id IN $rev_ids "
            "RETURN t.id AS tid, t.title AS title, t.status AS status, inc.yi AS yi, inc.sei AS sei, rev.id AS rid",
            {"rev_ids": all_rev_ids}
        )
        for row in co_res.result_set:
            tid, ttitle, tstatus, yi, sei, rid = row
            if tid not in nodes_map:
                parent_hemi = nodes_map.get(rid, {}).get("hemisphere", "left")
                nodes_map[tid] = {
                    "id": tid,
                    "label": "Trial",
                    "title": ttitle or tid,
                    "status": tstatus or "active",
                    "hemisphere": parent_hemi,
                }
            edges.append({
                "source": tid,
                "target": rid,
                "type": "INCLUDED_IN",
                "yi": float(yi) if yi is not None else 0.0,
                "sei": float(sei) if sei is not None else 0.0,
            })

    # Track 03: Decision nodes and Committee / owners to notify
    decisions = knowledge.get_at_risk_decisions(retraction_id)
    for d in decisions:
        did = d["decision_id"]
        if did not in nodes_map:
            nodes_map[did] = {
                "id": did,
                "label": "Decision",
                "title": d.get("title", did),
                "status": "at_risk",
                "committee": d.get("committee", ""),
                "notify": d.get("notify", []),
                "hemisphere": "left",
            }
        rev_id = d.get("review_id")
        if rev_id and rev_id in nodes_map:
            edges.append({"source": did, "target": rev_id, "type": "BASED_ON"})

    # Extended decision & governance context across both hemispheres
    dec_res = knowledge.graph.query(
        "MATCH (dec:Decision) "
        "OPTIONAL MATCH (dec)-[:BASED_ON]->(rev:Review) "
        "OPTIONAL MATCH (dec)-[:ABOUT]->(gl:Guideline) "
        "OPTIONAL MATCH (dec)-[:MADE_BY]->(c:Committee) "
        "OPTIONAL MATCH (p:Person)-[:PARTICIPATED_IN]->(dec) "
        "RETURN dec.id, dec.title, dec.status, rev.id, gl.id, c.id, c.name, p.id, p.name, p.role"
    )
    for row in dec_res.result_set:
        did, dtitle, dstatus, rid, gid, cid, cname, pid, pname, prole = row
        if (rid and rid in nodes_map) or (gid and gid in nodes_map):
            hemi = "right" if cid == "COM-ONCO" else "left"
            if did not in nodes_map:
                nodes_map[did] = {
                    "id": did,
                    "label": "Decision",
                    "title": dtitle or did,
                    "status": dstatus or "active",
                    "committee": cname or "",
                    "hemisphere": hemi,
                }
            if rid and rid in nodes_map:
                edges.append({"source": did, "target": rid, "type": "BASED_ON"})
            if gid and gid in nodes_map:
                edges.append({"source": did, "target": gid, "type": "BASED_ON"})
            if cid and cid not in nodes_map:
                nodes_map[cid] = {"id": cid, "label": "Committee", "title": cname or cid, "hemisphere": hemi}
            if cid:
                edges.append({"source": did, "target": cid, "type": "GOVERNED_BY"})
            if pid and pid not in nodes_map:
                nodes_map[pid] = {"id": pid, "label": "Person", "title": pname or pid, "role": prole or "", "hemisphere": hemi}
            if pid:
                edges.append({"source": did, "target": pid, "type": "PARTICIPATED"})

    edge_seen = set()
    deduped_edges = []
    for e in edges:
        k = (e["source"], e["target"], e.get("type", ""))
        if k not in edge_seen:
            edge_seen.add(k)
            deduped_edges.append(e)

    return {
        "retraction_id": retraction_id,
        "nodes": list(nodes_map.values()),
        "edges": deduped_edges,
    }

@app.get("/api/tenants/{tenant}/rankings")
def get_tenant_rankings(tenant: str, retraction_id: str = "SYN-RET-001"):
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    mem = TenantMemory(tenant)
    ranking_engine = RankingEngine(mem)

    # Query retraction's stored category
    r_cat = "unknown"
    r_res = knowledge.graph.query(
        "MATCH (r:Retraction {id: $rid}) RETURN r.reason_category", {"rid": retraction_id}
    )
    if r_res.result_set and r_res.result_set[0][0]:
        r_cat = r_res.result_set[0][0]

    # Fetch impact data
    impacts = knowledge.get_impacts_for_retraction(retraction_id)
    if not impacts:
        # Fallback to blast radius
        blast = knowledge.get_blast_radius(retraction_id)
        impacts = [{
            "review_id": b["review"],
            "title": f"Review {b['review']}",
            "weight_share": 0.15,
            "flips": False,
            "guidelines": b["guidelines"],
            "reason_category": b.get("reason_category") or r_cat,
        } for b in blast]
    else:
        for imp in impacts:
            if not imp.get("reason_category") or imp.get("reason_category") == "unknown":
                imp["reason_category"] = r_cat

    ranked_items, ranking_id = ranking_engine.rank_alerts(retraction_id, impacts, persist=True)
    return {
        "tenant": tenant,
        "retraction_id": retraction_id,
        "ranking_id": ranking_id,
        "ranked_alerts": ranked_items,
    }

@app.post("/api/tenants/{tenant}/load-demo")
def load_demo_scenario(tenant: str, retraction_id: str = "SYN-RET-001"):
    if settings.public_mode:
        raise HTTPException(
            status_code=403,
            detail="Load demo scenario is disabled when PUBLIC_MODE=1."
        )

    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    coord = CoordEngine(graph_manager.get_graph("coord"))
    mem = TenantMemory(tenant)

    # 1. Run real pipeline for SYN-RET-001 (fabrication)
    watcher = WatcherHandler(knowledge, coord)
    tracer = TracerHandler(knowledge, coord)
    stat = StatisticianHandler(knowledge)
    briefer = BrieferHandler(knowledge)

    watcher.handle({
        "retraction_id": "SYN-RET-001",
        "trial_id": "SYN-TR-0001",
        "reason": "Data fabrication and falsification in clinical patient records",
        "reason_category": "fabrication",
        "synthetic": True,
    })
    t1 = tracer.handle({"retraction_id": "SYN-RET-001", "reason_category": "fabrication"})
    for r in t1["affected_reviews"]:
        stat.handle({"retraction_id": "SYN-RET-001", "review_id": r, "reason_category": "fabrication"})
    briefer.handle({"retraction_id": "SYN-RET-001"})

    # 2. Run real pipeline for 4 low-weight administrative alerts clearly labeled synthetic
    admin_items = [
        ("SYN-TR-ADM-01", "SYN-REV-ADM-01", "[SYNTHETIC] Systematic Review of Registry Reporting Protocols (ADM-01)", -0.15, 0.45),
        ("SYN-TR-ADM-02", "SYN-REV-ADM-02", "[SYNTHETIC] Clinical Guidelines Ethics Disclosure Audit (ADM-02)", 0.12, 0.40),
        ("SYN-TR-ADM-03", "SYN-REV-ADM-03", "[SYNTHETIC] Systematic Review of Duplicate Publication Logs (ADM-03)", -0.18, 0.48),
        ("SYN-TR-ADM-04", "SYN-REV-ADM-04", "[SYNTHETIC] Multicenter Trial Registry Formatting Review (ADM-04)", 0.14, 0.42),
    ]

    created_ids = []
    for tid, rid, title, yi, sei in admin_items:
        # Seed review and trial with included_in edge
        knowledge.graph.query(
            "MERGE (rev:Review {id: $rid}) SET rev.title = $title, rev.synthetic = true "
            "MERGE (t:Trial {id: $tid}) SET t.status = 'active', t.synthetic = true "
            "MERGE (t)-[:INCLUDED_IN {yi: $yi, sei: $sei}]->(rev)",
            {"rid": rid, "title": title, "tid": tid, "yi": yi, "sei": sei}
        )
        for b_idx in range(5):
            bt_id = f"SYN-TR-BASE-{rid}-{b_idx}"
            knowledge.graph.query(
                "MATCH (rev:Review {id: $rid}) "
                "MERGE (t:Trial {id: $tid}) SET t.status = 'active', t.synthetic = true "
                "MERGE (t)-[:INCLUDED_IN {yi: 0.10, sei: 0.12}]->(rev)",
                {"tid": bt_id, "rid": rid}
            )

        adm_ret_id = f"SYN-RET-{rid}"
        watcher.handle({
            "retraction_id": adm_ret_id,
            "trial_id": tid,
            "reason": "Administrative duplication and formatting error",
            "reason_category": "administrative",
            "synthetic": True,
        })
        tr = tracer.handle({"retraction_id": adm_ret_id, "reason_category": "administrative"})
        for r in tr["affected_reviews"]:
            stat.handle({"retraction_id": retraction_id, "review_id": r, "reason_category": "administrative"})
        briefer.handle({"retraction_id": adm_ret_id})
        created_ids.append(rid)

    rankings_res = get_tenant_rankings(tenant, retraction_id)
    return {
        "status": "loaded",
        "tenant": tenant,
        "retraction_id": retraction_id,
        "created_alerts": created_ids,
        "ranked_alerts_count": len(rankings_res.get("ranked_alerts", [])),
    }

@app.post("/api/tenants/{tenant}/episodes")
def record_tenant_episode(tenant: str, ep: EpisodeSubmission, background_tasks: BackgroundTasks):
    mem = TenantMemory(tenant)
    session_id = ep.session_id or mem.create_session()

    episode_id = mem.record_episode(
        session_id=session_id,
        kind=ep.kind,
        reason=ep.reason,
        weight_bucket=ep.weight_bucket,
        flips=ep.flips,
        ext_review=ep.ext_review,
        ext_retraction=ep.ext_retraction,
        notes=ep.notes,
    )

    # Consolidate in background
    librarian = LibrarianHandler(mem)
    consolidation = librarian.consolidate()

    return {
        "status": "recorded",
        "episode_id": episode_id,
        "session_id": session_id,
        "consolidation": consolidation,
    }

@app.get("/api/tenants/{tenant}/memory")
def get_tenant_memory(tenant: str):
    mem = TenantMemory(tenant)
    return {
        "tenant": tenant,
        "episodes": mem.get_episodes(),
        "active_rules": mem.get_active_rules(),
        "facts": mem.get_facts(),
    }

@app.get("/api/tenants/{tenant}/explain/{ranking_id}/{review_id}")
def explain_alert(tenant: str, ranking_id: str, review_id: str):
    mem = TenantMemory(tenant)
    exp = mem.explain_ranking(ranking_id, review_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Ranking explanation not found")
    return exp

@app.post("/api/tenants/{tenant}/facts")
def add_fact(tenant: str, fact: FactSubmission):
    mem = TenantMemory(tenant)
    fid = mem.set_fact(fact.key, fact.value)
    return {"status": "ok", "fact_id": fid}

# --- Track 03 (Company Brain) Endpoints ---

@app.get("/api/decisions/at-risk/{retraction_id}")
def get_at_risk_decisions_endpoint(retraction_id: str):
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    decisions = knowledge.get_at_risk_decisions(retraction_id)
    return {"retraction_id": retraction_id, "at_risk_decisions": decisions}

@app.get("/api/decisions/{decision_id}/trace")
def get_decision_trace_endpoint(decision_id: str):
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    trace = knowledge.get_decision_trace(decision_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Decision not found")
    return trace

@app.get("/api/who-knows")
def who_knows_endpoint(topic: str = Query(..., description="Medical topic to search expertise")):
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    experts = knowledge.who_knows(topic)
    return {"topic": topic, "experts": experts}

@app.get("/api/guidelines/criticality")
def get_guideline_criticality():
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    ranked = knowledge.rank_guidelines_pagerank()
    return {"critical_guidelines": ranked}

@app.get("/api/clusters")
def get_contamination_clusters():
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    pairs = knowledge.build_contamination_clusters()
    components = knowledge.get_wcc_clusters()
    return {"shared_trial_pairs": pairs, "components": components}

# --- Chat & Analyst Endpoints ---


@app.post("/api/reset")
def reset_database():
    if settings.public_mode:
        raise HTTPException(
            status_code=403,
            detail="Resetting the database is disabled in PUBLIC_MODE to protect public demo integrity."
        )
    from scripts.reset import reset_all_graphs
    reset_all_graphs()
    return {"status": "ok", "message": "All graphs reset deterministically."}

@app.post("/api/chaos/run")
def trigger_chaos_experiment():
    if settings.public_mode:
        raise HTTPException(
            status_code=403,
            detail="Process assassination and chaos experiments are disabled in PUBLIC_MODE."
        )
    return {"status": "ok", "message": "Chaos experiment triggered."}

class ChatRequest(BaseModel):
    tenant: str = "cardio"
    session: Optional[str] = None
    text: str

class AnalystRequest(BaseModel):
    tenant: str = "cardio"
    retraction_id: str = "SYN-RET-001"
    prompt: Optional[str] = "What should we do first about this retraction?"

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest, request: Request):
    check_public_rate_limit(request)
    mem = TenantMemory(req.tenant)
    session_id = req.session or mem.create_session()
    
    # Save user message
    mem.add_message(session_id, role="user", text=req.text)
    
    # Gather context from tenant memory
    active_rules = mem.get_active_rules()
    episodes = mem.get_episodes()
    facts = [f for f in mem.get_facts() if f["is_active"]]

    lower_text = req.text.lower()
    
    # Deterministic templated response citing graph nodes
    if "why" in lower_text or "rank" in lower_text or "rule" in lower_text:
        if active_rules:
            rule_texts = [f"• Rule {r['id']} ({r['description']}, delta: {r['delta']})" for r in active_rules]
            reply = (
                f"Alert rankings in tenant '{req.tenant}' are adjusted by active procedural memory rules:\n"
                + "\n".join(rule_texts)
                + f"\nThese rules were derived by the Librarian from {len(episodes)} team feedback episodes."
            )
        else:
            reply = (
                f"No active procedural rules are currently applied in tenant '{req.tenant}'. "
                "Alerts reflect baseline severity based on retraction reason, weight share, and clinical flips."
            )
    elif "fact" in lower_text or "guideline" in lower_text or "authority" in lower_text:
        if facts:
            fact_texts = [f"• {f['key']}: {f['value']}" for f in facts]
            reply = f"Active semantic memory facts for team '{req.tenant}':\n" + "\n".join(fact_texts)
        else:
            reply = f"No semantic facts recorded yet for team '{req.tenant}'."
    else:
        reply = (
            f"Ripple Assistant ({req.tenant} brain): Monitoring evidence cascades and multi-hop retraction blast radiuses. "
            f"Graph memory contains {len(episodes)} episodes and {len(active_rules)} active procedural rules."
        )

    # Save assistant reply
    mid = mem.add_message(session_id, role="assistant", text=reply)
    
    return {
        "session_id": session_id,
        "message_id": mid,
        "role": "assistant",
        "text": reply,
        "active_rules_count": len(active_rules),
    }

@app.post("/api/analyst")
def analyst_endpoint(req: AnalystRequest, request: Request):
    check_public_rate_limit(request)
    agent = AnalystAgent(req.tenant)
    res = agent.execute_plan(req.retraction_id, req.prompt or "What should we do first?")
    return {
        "retraction_id": req.retraction_id,
        "tenant": req.tenant,
        "tool_trace": res["trace"],
        "recommendation": res["recommendation"],
        "ticket_created": res["ticket_id"],
        "target_decision_id": res["target_decision_id"],
        "algorithms_used": res["algorithms_used"],
    }

# Static UI mounting moved to bottom of file after all API routes

# --- Benchmark & Chaos Telemetry Endpoints ---

@app.get("/api/bench/latest")
def get_bench_latest():
    path = "bench/latest.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Benchmark not run yet")
    with open(path) as f:
        return json.load(f)

@app.get("/api/bench/chaos")
def get_chaos_latest():
    path = "bench/chaos_latest.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Chaos experiment not run yet")
    with open(path) as f:
        return json.load(f)

# --- Mount Static UI (New React App at /, Legacy at /legacy) ---
from fastapi.staticfiles import StaticFiles

# Always keep legacy UI accessible at /legacy
app.mount("/legacy", StaticFiles(directory="ui", html=True), name="legacy_ui")

# Serve React production build at / if available, otherwise fallback to legacy ui
if os.path.exists("web/dist"):
    app.mount("/", StaticFiles(directory="web/dist", html=True), name="react_ui")
else:
    app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
