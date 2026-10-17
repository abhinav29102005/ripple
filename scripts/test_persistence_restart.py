"""
Verification of Item 1: Persistence of procedural rules and rankings across docker compose restart
WITHOUT issuing a manual SAVE.
"""
import time
import subprocess
import sys
from falkordb import FalkorDB
from graph import graph_manager
from memory import TenantMemory
from ranking import RankingEngine
from agents.librarian import LibrarianHandler
from config import settings

def main():
    tenant_name = "persist_verify"
    graph_name = f"tenant_{tenant_name}"
    
    print(f"[*] Step 1: Initializing test graph '{graph_name}' on port {settings.falkordb_port}...")
    graph_manager.delete_graph(graph_name)
    mem = TenantMemory(tenant_name)
    sess_id = mem.create_session()

    print("[*] Step 2: Recording 3 dismissals on administrative retractions...")
    for i in range(3):
        mem.record_episode(
            session_id=sess_id,
            kind="dismiss",
            reason="administrative",
            weight_bucket="low",
            flips=False,
            ext_review=f"SYN-REV-P{i+1}",
            ext_retraction="SYN-RET-ADM",
            notes="Administrative notice dismiss",
        )

    print("[*] Step 3: Running Librarian consolidation...")
    librarian = LibrarianHandler(mem)
    res = librarian.consolidate()
    print(f"    Librarian consolidation created rules: {res['created_rules']}")

    active_rules_pre = mem.get_active_rules()
    print(f"    Active rules before restart: {[r['id'] for r in active_rules_pre]}")
    assert any(r["id"] == "rule_reason_administrative" for r in active_rules_pre), "Rule not created!"

    alerts = [{
        "review_id": "SYN-REV-P999",
        "title": "Administrative Review P999",
        "reason_category": "administrative",
        "weight_share": 0.10,
        "flips": False,
        "guidelines": ["SYN-GL-01"],
    }]
    ranking_engine = RankingEngine(mem)
    ranked_pre, r_id_pre = ranking_engine.rank_alerts("SYN-RET-TEST", alerts, persist=True)
    score_pre = ranked_pre[0]["score"]
    base_pre = ranked_pre[0]["base"]
    print(f"    Ranking before restart: base={base_pre}, score={score_pre}, applied={ranked_pre[0]['applied_rules']}")
    assert score_pre < base_pre, "Ranking score was not reduced by rule!"

    print("\n[*] Step 4: Executing 'docker compose restart' WITHOUT MANUAL SAVE...")
    sub_res = subprocess.run(["docker", "compose", "restart", "falkordb"], capture_output=True, text=True)
    print("    Docker compose output:", sub_res.stdout.strip())
    if sub_res.returncode != 0:
        print("    Docker compose error:", sub_res.stderr.strip())
        sys.exit(1)

    # Wait for FalkorDB container to accept connections
    print("[*] Step 5: Waiting for FalkorDB to recover...")
    recovered = False
    for attempt in range(15):
        time.sleep(1.0)
        try:
            db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)
            db.connection.ping()
            recovered = True
            print(f"    FalkorDB is UP after {attempt+1} seconds.")
            break
        except Exception:
            continue

    assert recovered, "FalkorDB did not recover after restart!"

    print("[*] Step 6: Verifying rule and ranking survival AFTER restart...")
    mem_post = TenantMemory(tenant_name)
    active_rules_post = mem_post.get_active_rules()
    print(f"    Active rules after restart: {[r['id'] for r in active_rules_post]}")
    assert any(r["id"] == "rule_reason_administrative" for r in active_rules_post), "RULE WAS LOST AFTER RESTART!"

    rule_post = [r for r in active_rules_post if r["id"] == "rule_reason_administrative"][0]
    print(f"    Rule details: id={rule_post['id']}, delta={rule_post['delta']}, support={rule_post['support']}")

    ranking_engine_post = RankingEngine(mem_post)
    ranked_post, r_id_post = ranking_engine_post.rank_alerts("SYN-RET-TEST-2", alerts, persist=False)
    score_post = ranked_post[0]["score"]
    print(f"    Ranking after restart: base={ranked_post[0]['base']}, score={score_post}, applied={ranked_post[0]['applied_rules']}")
    assert score_post == score_pre, f"Ranking score mismatch! Pre: {score_pre}, Post: {score_post}"

    print("\n[SUCCESS] Verification passed: Rule and ranking shift survived docker compose restart WITHOUT manual save!")

if __name__ == "__main__":
    main()
