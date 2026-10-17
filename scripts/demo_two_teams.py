"""
Item 2: Two-Team Demo Scenario
Demonstrates:
(a) Cardio team dismisses 3 administrative alerts -> subsequent administrative alert is downranked for cardio vs onco.
(b) Fabrication alert still ranked high (>= 0.5) for both teams due to the clinical safety floor.
Reproducible from a clean reset.
"""
from scripts.reset import reset_all_graphs
from memory import TenantMemory
from ranking import RankingEngine
from agents.librarian import LibrarianHandler

def main():
    print("=== Step 1: Performing clean reset of all graphs ===")
    reset_all_graphs()

    # --- Setup Alerts ---
    # Alert A: Routine Administrative notice (low severity)
    alert_admin = {
        "review_id": "SYN-REV-ADM",
        "title": "Systematic Review of Protocol Registries",
        "reason_category": "administrative",
        "weight_share": 0.10,
        "flips": False,
        "guidelines": ["SYN-GL-001"],
    }

    # Alert B: Severe Data Fabrication notice (high severity)
    alert_fab = {
        "review_id": "SYN-REV-FAB",
        "title": "Critical Phase III Cardiology Review",
        "reason_category": "fabrication",
        "weight_share": 0.05,
        "flips": False,
        "guidelines": ["SYN-GL-001"],
    }

    all_alerts = [alert_admin, alert_fab]

    # --- Setup Tenant: Cardio (Dismisses 3 administrative alerts) ---
    print("\n=== Step 2: Configuring tenant_cardio (3 dismissals on administrative) ===")
    mem_cardio = TenantMemory("cardio")
    sess_cardio = mem_cardio.create_session()
    for i in range(3):
        mem_cardio.record_episode(
            session_id=sess_cardio,
            kind="dismiss",
            reason="administrative",
            weight_bucket="low",
            flips=False,
            ext_review=f"SYN-REV-ADM-HIST-{i+1}",
            ext_retraction=f"SYN-RET-ADM-{i+1}",
            notes="Cardio team: routine administrative formatting error dismissed",
        )
    lib_cardio = LibrarianHandler(mem_cardio)
    res_cardio = lib_cardio.consolidate()
    cardio_rules = [r["id"] for r in mem_cardio.get_active_rules()]
    print(f"tenant_cardio active consolidated rules: {cardio_rules}")

    # --- Setup Tenant: Onco (No administrative dismissals) ---
    print("\n=== Step 3: Configuring tenant_onco (Clean baseline / no administrative dismissals) ===")
    mem_onco = TenantMemory("onco")
    onco_rules = [r["id"] for r in mem_onco.get_active_rules()]
    print(f"tenant_onco active consolidated rules: {onco_rules}")

    # --- Rank Alerts for Both Teams ---
    print("\n=== Step 4: Computing Alert Ranking for Both Teams ===")
    engine_cardio = RankingEngine(mem_cardio)
    ranked_cardio, _ = engine_cardio.rank_alerts("SYN-RET-DEMO", all_alerts, persist=True)

    engine_onco = RankingEngine(mem_onco)
    ranked_onco, _ = engine_onco.rank_alerts("SYN-RET-DEMO", all_alerts, persist=True)

    cardio_by_id = {item["review_id"]: item for item in ranked_cardio}
    onco_by_id = {item["review_id"]: item for item in ranked_onco}

    print("\n" + "="*95)
    print(f"{'ALERT':<14} | {'CATEGORY':<14} | {'CARDIO SCORE':<14} | {'ONCO SCORE':<14} | {'SAFETY FLOOR ACTIVE'}")
    print("="*95)
    for alert in all_alerts:
        aid = alert["review_id"]
        cat = alert["reason_category"]
        c_item = cardio_by_id[aid]
        o_item = onco_by_id[aid]
        c_score = f"{c_item['score']:.4f} (r={c_item['rank']})"
        o_score = f"{o_item['score']:.4f} (r={o_item['rank']})"
        floor_str = str(c_item.get("safety_floor_active", False) or o_item.get("safety_floor_active", False))
        print(f"{aid:<14} | {cat:<14} | {c_score:<14} | {o_score:<14} | {floor_str}")
    print("="*95)

    print("\n--- Detailed Score Breakdown (Real Ranking Output) ---")
    for t_name, by_id in [("tenant_cardio", cardio_by_id), ("tenant_onco", onco_by_id)]:
        print(f"\n[{t_name}]")
        for aid in ["SYN-REV-FAB", "SYN-REV-ADM"]:
            item = by_id[aid]
            rules_applied = [r["id"] for r in item["applied_rules"]]
            print(f"  Alert: {item['review_id']} ({item['reason_category']})")
            print(f"    base_score          = {item['base']:.4f}")
            print(f"    applied_rules       = {rules_applied}")
            print(f"    raw_rule_delta_sum  = {item['raw_delta']:.4f}")
            print(f"    capped_delta        = {item['delta']:.4f}")
            print(f"    safety_floor_active = {item['safety_floor_active']}")
            print(f"    final_score         = {item['score']:.4f} (Rank #{item['rank']})")

    # --- Assertions for Item 2 Acceptance Criteria ---
    # (a) Similar administrative alert is ranked lower for cardio than onco
    adm_c = cardio_by_id["SYN-REV-ADM"]
    adm_o = onco_by_id["SYN-REV-ADM"]
    assert adm_c["score"] < adm_o["score"], f"Administrative alert should score lower for cardio ({adm_c['score']}) than onco ({adm_o['score']})!"
    assert any("administrative" in r["id"] for r in adm_c["applied_rules"]), "Cardio should have applied administrative downranking rule!"
    print(f"\n[PROOF (a)] Administrative alert SYN-REV-ADM: Cardio score = {adm_c['score']:.4f} < Onco score = {adm_o['score']:.4f}")

    # (b) Fabrication alert still ranked high (>= 0.5) for both teams because of safety floor
    fab_c = cardio_by_id["SYN-REV-FAB"]
    fab_o = onco_by_id["SYN-REV-FAB"]
    assert fab_c["score"] >= 0.5, f"Cardio fabrication score {fab_c['score']} fell below safety floor 0.5!"
    assert fab_o["score"] >= 0.5, f"Onco fabrication score {fab_o['score']} fell below safety floor 0.5!"
    assert fab_c["score"] == 0.5, f"Expected cardio score clamped to floor 0.5, got {fab_c['score']}"
    assert fab_o["score"] == 0.5, f"Expected onco score clamped to floor 0.5, got {fab_o['score']}"
    print(f"[PROOF (b)] Fabrication alert SYN-REV-FAB: Cardio score = {fab_c['score']:.4f} >= 0.5, Onco score = {fab_o['score']:.4f} >= 0.5 (Safety Floor Active)")

    print("\n[SUCCESS] Two-Team Demo verified: (a) Personalized administrative down-ranking and (b) Clinical safety floor both functioning perfectly!")

if __name__ == "__main__":
    main()
