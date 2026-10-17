"""
Librarian Agent: consolidates episodic feedback into active procedural rules
and semantic facts. Updates hit rates, delta adjustments, and retires stale rules.
Evaluates conjunctive features (reason, weight_bucket) to prevent overly broad rules.
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional
from memory import TenantMemory

class LibrarianHandler:
    def __init__(self, tenant_memory: TenantMemory):
        self.memory = tenant_memory

    def consolidate(self) -> Dict[str, Any]:
        episodes = self.memory.get_episodes()
        active_rules = {r["id"]: r for r in self.memory.get_active_rules()}

        # Group episodes by conjunctive feature tuple (reason, weight_bucket)
        # Avoid broad single-feature rules (such as flips=false) that match most alerts.
        feature_episodes: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)

        for ep in episodes:
            r_val = ep.get("reason")
            if r_val:
                r_val = str(r_val).lower()
                if r_val in ("data_falsification", "falsification"):
                    r_val = "fabrication"

            w_val = ep.get("weight_bucket")
            if w_val:
                w_val = str(w_val).lower()

            if r_val and w_val:
                feature_episodes[("reason,weight_bucket", f"{r_val},{w_val}")].append(ep)

        created_rules = []
        updated_rules = []
        retired_rules = []

        for (feat, val), eps in feature_episodes.items():
            rule_id = f"rule_{val.replace(',', '_')}"
            total = len(eps)
            if total < 3:
                continue

            dismiss_count = sum(1 for e in eps if e["kind"] in ("dismiss", "dismissal"))
            escalate_count = sum(1 for e in eps if e["kind"] in ("escalate", "escalation"))
            dismiss_rate = dismiss_count / total
            escalate_rate = escalate_count / total

            ep_ids = [e["id"] for e in eps]
            parts = val.split(",")
            r_label, w_label = parts[0], parts[1]

            if dismiss_rate >= 0.8:
                delta = -0.3
                desc = f"Down-rank alerts where reason is '{r_label}' and weight is '{w_label}' by 0.3 (based on {dismiss_count}/{total} dismissals)"
                self.memory.save_rule(
                    rule_id=rule_id,
                    feature=feat,
                    value=val,
                    delta=delta,
                    support=total,
                    hit_rate=round(dismiss_rate, 2),
                    description=desc,
                    episode_ids=ep_ids,
                    status="active",
                )
                if rule_id in active_rules:
                    updated_rules.append(rule_id)
                else:
                    created_rules.append(rule_id)

            elif escalate_rate >= 0.8:
                delta = 0.3
                desc = f"Up-rank alerts where reason is '{r_label}' and weight is '{w_label}' by 0.3 (based on {escalate_count}/{total} escalations)"
                self.memory.save_rule(
                    rule_id=rule_id,
                    feature=feat,
                    value=val,
                    delta=delta,
                    support=total,
                    hit_rate=round(escalate_rate, 2),
                    description=desc,
                    episode_ids=ep_ids,
                    status="active",
                )
                if rule_id in active_rules:
                    updated_rules.append(rule_id)
                else:
                    created_rules.append(rule_id)

            else:
                if rule_id in active_rules:
                    existing = active_rules[rule_id]
                    eff_rate = dismiss_rate if existing["delta"] < 0 else escalate_rate
                    if eff_rate < 0.5:
                        desc = f"Retired rule for {feat}='{val}' (hit rate dropped to {eff_rate:.2f})"
                        self.memory.save_rule(
                            rule_id=rule_id,
                            feature=feat,
                            value=val,
                            delta=existing["delta"],
                            support=total,
                            hit_rate=round(eff_rate, 2),
                            description=desc,
                            episode_ids=ep_ids,
                            status="retired",
                        )
                        retired_rules.append(rule_id)

        return {
            "created_rules": created_rules,
            "updated_rules": updated_rules,
            "retired_rules": retired_rules,
            "total_episodes_analyzed": len(episodes),
        }
