"""
Deterministic reset script for Ripple.
Wipes and reseeds all FalkorDB graphs (coord, knowledge, and tenant graphs).
Run this before every demo take to ensure deterministic starting state.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph import graph_manager
from scripts.seed_synthetic import seed_synthetic_data
from scripts.seed_org import seed_organization
from memory import TenantMemory

def reset_all_graphs(seed: int = 42):
    print("=== Resetting Ripple Graphs to Clean Deterministic State ===")

    # List and delete all ripple-related graphs
    existing_graphs = graph_manager.list_graphs()
    print(f"Existing graphs in FalkorDB: {existing_graphs}")

    target_graphs = ["coord", "knowledge", "tenant_cardio", "tenant_onco"]
    for gname in existing_graphs:
        if gname in target_graphs or gname.startswith("tenant_") or "test" in gname:
            print(f"Deleting graph: {gname}")
            graph_manager.delete_graph(gname)

    # 1. Initialize schemas
    print("Initializing schemas and indexes...")
    graph_manager.init_coord_schema()
    graph_manager.init_knowledge_schema()
    graph_manager.init_tenant_schema("cardio")
    graph_manager.init_tenant_schema("onco")

    # 2. Seed synthetic evidence graph (Trials, Reviews, Guidelines, Retractions)
    seed_synthetic_data(scale="standard", seed=seed)

    # 3. Seed synthetic organization (People, Committees, Decisions, Documents, Chats, Tickets)
    seed_organization(seed=seed)

    # 4. Seed initial tenant memory facts
    cardio_mem = TenantMemory("cardio")
    cardio_mem.set_fact("preferred_pooling_model", "fixed")
    cardio_mem.set_fact("clinical_guideline_authority", "Cardiology Clinical Evidence Board (CCEB)")

    onco_mem = TenantMemory("onco")
    onco_mem.set_fact("preferred_pooling_model", "fixed")
    onco_mem.set_fact("clinical_guideline_authority", "Oncology Research Review Board (ORRB)")

    # 5. Persist snapshot
    graph_manager.save_state()
    print("=== Reset Complete: All Graphs Re-seeded Deterministically ===")

if __name__ == "__main__":
    reset_all_graphs()
