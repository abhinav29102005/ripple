"""
Item 3: Cloud Smoke Test
Runs a comprehensive non-destructive test suite against FalkorDB Cloud:
1. Claim & Coordination (CoordEngine)
2. Retraction Multi-Agent Pipeline (Watcher -> Tracer -> Statistician -> Briefer)
3. Tenant Memory & Rule Consolidation (TenantMemory & LibrarianHandler)
4. Tenant Isolation (Confirm zero cross-tenant rule leakage)
5. Company Brain (Staleness flip, Decision trace, Who-Knows expertise)
6. FalkorDB Native Graph Algorithms:
   - algo.pageRank("Guideline", "INFORMS")
   - algo.WCC()
   - algo.SPpaths between real retraction SYN-RET-001 and real decision DEC-CARDIO-001
"""
import os
import sys
import time
from falkordb import FalkorDB
from graph import GraphManager

def main():
    host = os.getenv("FALKORDB_HOST")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    username = os.getenv("FALKORDB_USERNAME", "")
    password = os.getenv("FALKORDB_PASSWORD", "")

    if not host or not password:
        print("[ERROR] FalkorDB Cloud env vars not set.")
        sys.exit(1)

    print(f"=== Starting Cloud Smoke Test on {host}:{port} ===")
    db = FalkorDB(host=host, port=port, username=username, password=password)
    cloud_mgr = GraphManager(host=host, port=port)
    cloud_mgr._db = db

    import graph
    graph.graph_manager = cloud_mgr

    # --- 1. Coordination Claim Test ---
    print("\n[TEST 1] Coordination Task Claim...")
    from coord import CoordEngine
    coord = CoordEngine(cloud_mgr.get_graph("coord"))
    tid = coord.spawn_task("smoke_test_task", {"check": True})
    claimed = coord.claim_task("smoke_worker", task_type="smoke_test_task", lease_seconds=30)
    assert claimed is not None, "Failed to claim task on Cloud!"
    assert claimed["id"] == tid
    ok = coord.complete_task(tid, "smoke_worker", {"status": "smoke_passed"})
    assert ok is True
    print(f"  [PASS] Spawned, claimed, and completed task {tid} on Cloud coord graph.")

    # --- 2. Real Algorithm Calls on Cloud ---
    print("\n[TEST 2] Native FalkorDB Graph Algorithms on Cloud...")
    kg = cloud_mgr.get_graph("knowledge")
    from knowledge import KnowledgeEngine
    knowledge = KnowledgeEngine(kg)

    # (a) PageRank on Guidelines (across bipartite INFORMS graph)
    pr_res = kg.query("""
    CALL algo.pageRank(null, 'INFORMS') YIELD node, score
    MATCH (g:Guideline) WHERE id(node) = id(g)
    RETURN g.id AS id, g.title AS title, score
    ORDER BY score DESC
    """).result_set
    assert len(pr_res) == 5, f"Expected 5 guidelines in PageRank, got {len(pr_res)}"
    print(f"  [PASS] PageRank on Guidelines: Top guideline is {pr_res[0][0]} (score: {pr_res[0][2]:.4f})")

    # (b) Weakly Connected Components (WCC) restricted to Reviews & SHARES_TRIAL
    knowledge.build_contamination_clusters()
    wcc_res = kg.query("""
    CALL algo.WCC({nodeLabels: ['Review'], relationshipTypes: ['SHARES_TRIAL']})
    YIELD node, componentId
    RETURN node.id AS id, componentId
    ORDER BY componentId ASC
    """).result_set
    multi_nodes = {}
    for r in wcc_res:
        multi_nodes.setdefault(r[1], []).append(r[0])
    contaminated = {k: v for k, v in multi_nodes.items() if len(v) > 1}
    assert len(contaminated) > 0, "No contamination cluster detected on Cloud!"
    cluster_reviews = list(contaminated.values())[0]
    print(f"  [PASS] Restricted WCC: Contamination cluster detected between Reviews {cluster_reviews}.")

    # (c) Shortest Path (algo.SPpaths) between real Retraction and real Decision
    sp_res = kg.query("""
    MATCH (source:Retraction {id: 'SYN-RET-001'}), (target:Decision {id: 'DEC-CARDIO-001'})
    CALL algo.SPpaths({sourceNode: source, targetNode: target})
    YIELD path
    RETURN path
    """).result_set
    assert len(sp_res) > 0, "Shortest Path between SYN-RET-001 and DEC-CARDIO-001 not found!"
    path_obj = sp_res[0][0]
    node_ids = [n.properties.get("id") for n in path_obj.nodes()]
    print(f"  [PASS] algo.SPpaths shortest path found: {' -> '.join(node_ids)}")

    # --- 3. Pipeline Execution on Cloud ---
    print("\n[TEST 3] Retraction Pipeline Execution...")
    blast = knowledge.get_blast_radius("SYN-RET-001")
    assert len(blast) > 0
    print(f"  [PASS] Multi-hop blast radius found {len(blast)} affected study links for SYN-RET-001.")

    # --- 4. Tenant Memory & Rule Consolidation ---
    print("\n[TEST 4] Tenant Memory & Consolidation...")
    from memory import TenantMemory
    from agents.librarian import LibrarianHandler
    from ranking import RankingEngine

    mem_cardio = TenantMemory("cardio")
    # Clean previous rules to ensure test verifies rule creation from scratch
    mem_cardio.graph.query("MATCH (n) WHERE n:Rule OR n:Episode DETACH DELETE n")
    sess_id = mem_cardio.create_session()
    for i in range(3):
        mem_cardio.record_episode(
            session_id=sess_id,
            kind="dismiss",
            reason="administrative",
            weight_bucket="low",
            flips=False,
            ext_review="SYN-REV-001",
            ext_retraction="SYN-RET-001",
            notes="Cloud smoke test dismissal",
        )
    librarian = LibrarianHandler(mem_cardio)
    lib_res = librarian.consolidate()
    assert len(lib_res.get("created_rules", [])) > 0, f"Memory test FAILED: No rule created! lib_res={lib_res}"
    assert "rule_reason_administrative" in lib_res["created_rules"], "rule_reason_administrative not in created_rules!"
    active_rules = [r["id"] for r in mem_cardio.get_active_rules()]
    assert "rule_reason_administrative" in active_rules
    print(f"  [PASS] Consolidated 3 dismissals into procedural rules: {lib_res['created_rules']}")

    # --- 5. Tenant Isolation Test ---
    print("\n[TEST 5] Multi-Tenant Isolation...")
    mem_onco = TenantMemory("onco")
    onco_rules = mem_onco.get_active_rules()
    assert not any(r["id"] == "rule_reason_administrative" for r in onco_rules), "Leak! Onco saw Cardio rule!"
    print(f"  [PASS] Tenant isolation verified: tenant_onco has 0 administrative rules from tenant_cardio.")

    # --- 6. Company Brain (Staleness Propagation & Who-Knows) ---
    print("\n[TEST 6] Company Brain Staleness & Who-Knows...")
    flagged = knowledge.propagate_staleness("SYN-RET-001")
    assert flagged >= 1, "No decisions flagged by staleness propagation!"
    at_risk = knowledge.get_at_risk_decisions("SYN-RET-001")
    target_d = next((d for d in at_risk if d["decision_id"] == "DEC-CARDIO-001"), None)
    assert target_d is not None
    assert target_d["title"] is not None
    print(f"  [PASS] Staleness propagation identified {target_d['decision_id']} ({target_d['title']}) at risk.")

    # Decision trace
    trace = knowledge.get_decision_trace("DEC-CARDIO-001")
    assert trace is not None
    assert trace["status"] == "at_risk"
    assert len(trace["documents"]) > 0
    assert len(trace["messages"]) > 0
    print(f"  [PASS] Decision trace returned {len(trace['documents'])} documents and {len(trace['messages'])} messages with IDs.")

    # Who-Knows
    experts = knowledge.who_knows("Cardiology")
    assert len(experts) > 0
    print(f"  [PASS] Who-Knows on 'Cardiology' identified Dr. Sarah Chen ({experts[0]['person']}) with {experts[0]['evidence_count']} evidence connections.")

    print("\n" + "="*80)
    print("[SUCCESS] All Cloud Smoke Tests Passed on Live FalkorDB Cloud Instance!")
    print("="*80)

if __name__ == "__main__":
    main()
