"""
FastAPI REST API for Ripple.
Exposes endpoints for retraction submissions, task board status,
graph exploration, tenant memory, personalized alert rankings, and feedback.
"""
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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

@app.get("/api/health")
def health_check():
    graphs = graph_manager.list_graphs()
    return {"status": "ok", "graphs": graphs, "llm_mode": settings.llm_mode}

@app.post("/api/retractions")
def submit_retraction(sub: RetractionSubmission):
    coord = CoordEngine(graph_manager.get_graph("coord"))
    task_key = f"ingest:{sub.retraction_id}"
    task_id = coord.spawn_task(
        task_type="ingest",
        payload={
            "retraction_id": sub.retraction_id,
            "trial_id": sub.trial_id,
            "reason": sub.reason,
            "reason_category": sub.reason_category,
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

    # Source retraction node
    nodes_map[retraction_id] = {"id": retraction_id, "label": "Retraction", "title": f"Retraction {retraction_id}"}

    for item in items:
        trial_id = item["trial"]
        rev_id = item["review"]

        if trial_id not in nodes_map:
            nodes_map[trial_id] = {"id": trial_id, "label": "Trial", "status": "retracted"}
        if rev_id not in nodes_map:
            nodes_map[rev_id] = {"id": rev_id, "label": "Review", "yi": item["yi"], "sei": item["sei"]}

        edges.append({"source": retraction_id, "target": trial_id, "type": "RETRACTS"})
        edges.append({"source": trial_id, "target": rev_id, "type": "INCLUDED_IN", "yi": item["yi"], "sei": item["sei"]})

        for gid in item.get("guidelines", []):
            if gid not in nodes_map:
                nodes_map[gid] = {"id": gid, "label": "Guideline"}
            edges.append({"source": rev_id, "target": gid, "type": "INFORMS"})

    return {
        "retraction_id": retraction_id,
        "nodes": list(nodes_map.values()),
        "edges": edges,
    }

@app.get("/api/tenants/{tenant}/rankings")
def get_tenant_rankings(tenant: str, retraction_id: str = "SYN-RET-001"):
    knowledge = KnowledgeEngine(graph_manager.get_graph("knowledge"))
    mem = TenantMemory(tenant)
    ranking_engine = RankingEngine(mem)

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
        } for b in blast]

    ranked_items, ranking_id = ranking_engine.rank_alerts(retraction_id, impacts, persist=True)
    return {
        "tenant": tenant,
        "retraction_id": retraction_id,
        "ranking_id": ranking_id,
        "ranked_alerts": ranked_items,
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
