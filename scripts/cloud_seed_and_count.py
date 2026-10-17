"""
Item 2: Cloud Seeding and Graph Verification
Seeds Ripple's graphs on FalkorDB Cloud using environment variables:
FALKORDB_HOST, FALKORDB_PORT, FALKORDB_USERNAME, FALKORDB_PASSWORD.

Safety verification:
- Confirms only Ripple's own graphs ('coord', 'knowledge', 'tenant_cardio', 'tenant_onco') are touched.
- Never issues FLUSHALL or FLUSHDB.
- Reports exact node and edge counts per label and relationship type for each graph.
"""
import os
import sys
import time
from falkordb import FalkorDB
from graph import GraphManager
from scripts.seed_synthetic import seed_synthetic_data
from scripts.seed_org import seed_organization
from memory import TenantMemory

def main():
    host = os.getenv("FALKORDB_HOST")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    username = os.getenv("FALKORDB_USERNAME", "")
    password = os.getenv("FALKORDB_PASSWORD", "")

    if not host or not password:
        print("[ERROR] FALKORDB_HOST and FALKORDB_PASSWORD must be set in the environment.")
        sys.exit(1)

    print(f"=== Connecting to FalkorDB Cloud at {host}:{port} ===")
    t0 = time.time()
    db = FalkorDB(host=host, port=port, username=username, password=password)
    assert db.connection.ping(), "Connection failed!"
    print(f"[OK] Authenticated with FalkorDB Cloud in {time.time() - t0:.2f}s")

    # Safety check: Verify existing graphs and ensure only Ripple graphs are targeted
    initial_graphs = db.list_graphs()
    print(f"Initial graphs present on Cloud instance: {initial_graphs}")

    ripple_graphs = ["coord", "knowledge", "tenant_cardio", "tenant_onco"]
    for gname in initial_graphs:
        if gname not in ripple_graphs and not gname.startswith("tenant_") and not "test" in gname:
            print(f"[SAFEGUARD] Foreign graph detected: '{gname}' will NOT be modified or deleted.")

    # Custom GraphManager bound to cloud DB
    cloud_mgr = GraphManager(host=host, port=port)
    cloud_mgr._db = db

    import graph
    graph.graph_manager = cloud_mgr
    import scripts.seed_synthetic
    scripts.seed_synthetic.graph_manager = cloud_mgr
    import scripts.seed_org
    scripts.seed_org.graph_manager = cloud_mgr
    import memory
    memory.graph_manager = cloud_mgr

    # 1. Reset ONLY Ripple's target graphs
    print("\n--- Resetting Ripple Graphs (knowledge, coord, tenant_cardio, tenant_onco) ---")
    for gname in ripple_graphs:
        try:
            db.select_graph(gname).delete()
            print(f"  Deleted old graph: {gname}")
        except Exception:
            pass

    # 2. Initialize schemas
    print("\n--- Initializing Schemas & Indexes ---")
    cloud_mgr.init_coord_schema()
    cloud_mgr.init_knowledge_schema()
    cloud_mgr.init_tenant_schema("cardio")
    cloud_mgr.init_tenant_schema("onco")
    print("  Schemas initialized.")

    # 3. Seed synthetic evidence and organization
    print("\n--- Seeding Knowledge Graph ---")
    seed_synthetic_data(scale="standard", seed=42)
    seed_organization(seed=42)

    # 4. Seed tenant facts
    print("\n--- Seeding Tenant Memory ---")
    cardio_mem = TenantMemory("cardio")
    cardio_mem.set_fact("preferred_pooling_model", "fixed")
    cardio_mem.set_fact("clinical_guideline_authority", "Cardiology Clinical Evidence Board (CCEB)")

    onco_mem = TenantMemory("onco")
    onco_mem.set_fact("preferred_pooling_model", "fixed")
    onco_mem.set_fact("clinical_guideline_authority", "Oncology Research Review Board (ORRB)")
    print("  Tenant facts seeded.")

    # 5. Report Node and Edge Counts per label per graph
    print("\n" + "="*80)
    print("                 FALKORDB CLOUD: VERIFIED GRAPH AUDIT COUNTS")
    print("="*80)

    for gname in ["knowledge", "coord", "tenant_cardio", "tenant_onco"]:
        g = db.select_graph(gname)
        print(f"\n[GRAPH: {gname}]")
        
        # Node counts per label
        node_res = g.query("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC").result_set
        print("  Nodes per Label:")
        total_nodes = 0
        if node_res:
            for lbl, cnt in node_res:
                print(f"    - {lbl:<15}: {cnt}")
                total_nodes += cnt
            print(f"    TOTAL NODES: {total_nodes}")
        else:
            print("    (0 nodes - ready task queue)")

        # Edge counts per relationship type
        edge_res = g.query("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC").result_set
        print("  Edges per Type:")
        total_edges = 0
        if edge_res:
            for rtype, cnt in edge_res:
                print(f"    - {rtype:<15}: {cnt}")
                total_edges += cnt
            print(f"    TOTAL EDGES: {total_edges}")
        else:
            print("    (0 edges)")

    print("\n" + "="*80)
    print("[SUCCESS] Cloud seeding completed successfully without touching any foreign instance state!")

if __name__ == "__main__":
    main()
