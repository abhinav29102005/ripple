"""
Seeds the live FalkorDB Cloud instance with Ripple's deterministic synthetic data:
- Initializes coord, knowledge, tenant_cardio, and tenant_onco schemas
- Seeds 40 trials, 10 systematic reviews, 5 guidelines, and 4 retractions
- Seeds institutional people, committees, decisions, documents, chats, tickets
- Seeds tenant memory facts for cardio and onco
"""
import time
from falkordb import FalkorDB
from scripts.seed_synthetic import seed_synthetic_data
from scripts.seed_org import seed_organization
from memory import TenantMemory
from graph import GraphManager

import os
HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6380"))
USERNAME = os.getenv("FALKORDB_USERNAME", "")
PASSWORD = os.getenv("FALKORDB_PASSWORD", "")

def main():
    print(f"=== Connecting to FalkorDB Cloud at {HOST}:{PORT} ===")
    t0 = time.time()
    db = FalkorDB(host=HOST, port=PORT, username=USERNAME, password=PASSWORD)
    assert db.connection.ping(), "Failed to ping FalkorDB Cloud!"
    print(f"Successfully authenticated with FalkorDB Cloud in {time.time() - t0:.2f}s!")

    # Configure custom GraphManager pointing to Cloud
    cloud_mgr = GraphManager(host=HOST, port=PORT)
    cloud_mgr._db = db

    # Overwrite the global graph_manager in modules so seeders use the cloud DB
    import graph
    graph.graph_manager = cloud_mgr
    import scripts.seed_synthetic
    scripts.seed_synthetic.graph_manager = cloud_mgr
    import scripts.seed_org
    scripts.seed_org.graph_manager = cloud_mgr
    import memory
    memory.graph_manager = cloud_mgr

    print("\n1. Initializing Cloud Graph Schemas & Indexes...")
    cloud_mgr.init_coord_schema()
    cloud_mgr.init_knowledge_schema()
    cloud_mgr.init_tenant_schema("cardio")
    cloud_mgr.init_tenant_schema("onco")
    print("   Schemas and indexes initialized successfully.")

    print("\n2. Seeding Synthetic Evidence Network (40 Trials, 10 Reviews, 5 Guidelines, 4 Retractions)...")
    seed_synthetic_data(scale="standard", seed=42)

    print("\n3. Seeding Synthetic Organization (People, Committees, Decisions, Docs, Chats)...")
    seed_organization(seed=42)

    print("\n4. Seeding Tenant Memory Facts...")
    cardio_mem = TenantMemory("cardio")
    cardio_mem.set_fact("preferred_pooling_model", "fixed_effect")
    cardio_mem.set_fact("clinical_guideline_authority", "American College of Cardiology (ACC)")

    onco_mem = TenantMemory("onco")
    onco_mem.set_fact("preferred_pooling_model", "random_effects")
    onco_mem.set_fact("clinical_guideline_authority", "American Society of Clinical Oncology (ASCO)")

    print("\n5. Verifying Seeded Cloud Graphs...")
    kg = cloud_mgr.get_graph("knowledge")
    counts = kg.query("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count").result_set
    print("   Knowledge graph node counts:")
    for lbl, cnt in counts:
        print(f"     - {lbl}: {cnt}")

    print("\n=== FalkorDB Cloud Instance Successfully Seeded & Ready for Live Production! ===")

if __name__ == "__main__":
    main()
