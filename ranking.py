"""
Alert severity and tenant-personalized ranking engine for Ripple.
Calculates baseline severity and applies active procedural rules from tenant memory.
Enforces safety caps ([-0.4, +0.4]) and clinical safety floors (>= 0.5 for fabrication/flips).
"""
from typing import Any, Dict, List, Optional, Tuple
from memory import TenantMemory

REASON_WEIGHTS = {
    "fabrication": 1.0,
    "error": 0.6,
    "unknown": 0.5,
    "administrative": 0.2,
}

# Safety invariants
DELTA_CAP_MIN = -0.4
DELTA_CAP_MAX = 0.4
SAFETY_FLOOR_SCORE = 0.5

def get_weight_bucket(weight_share: float) -> str:
    if weight_share < 0.10:
        return "low"
    elif weight_share <= 0.30:
        return "mid"
    else:
        return "high"

def compute_base_score(
    reason_category: str,
    weight_share: float,
    flips: bool,
    guideline_count: int,
) -> float:
    # Normalize legacy aliases
    cat = reason_category.lower()
    if cat in ("data_falsification", "falsification"):
        cat = "fabrication"

    reason_w = REASON_WEIGHTS.get(cat, 0.5)
    w_share = max(0.0, min(1.0, weight_share))
    f_val = 1.0 if flips else 0.0
    g_val = min(guideline_count / 3.0, 1.0)

    base = 0.4 * reason_w + 0.3 * w_share + 0.2 * f_val + 0.1 * g_val
    return round(base, 4)

class RankingEngine:
    def __init__(self, tenant_memory: TenantMemory):
        self.memory = tenant_memory

    def rank_alerts(
        self,
        retraction_id: str,
        alerts: List[Dict[str, Any]],
        persist: bool = True,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Rank a collection of affected review alerts for a given retraction.
        Applies tenant-specific active rules with:
        1. Adjustment cap [-0.4, +0.4]
        2. Clinical safety floor (>= 0.5 for fabrication or flips=True)
        Persists the ranking with USED edges.
        """
        active_rules = self.memory.get_active_rules()
        ranked_items = []
        all_applied_rules = {}

        for alert in alerts:
            rev_id = alert["review_id"]
            raw_cat = alert.get("reason_category", "unknown").lower()
            if raw_cat in ("data_falsification", "falsification"):
                raw_cat = "fabrication"
            reason_cat = raw_cat

            weight_share = float(alert.get("weight_share", 0.0))
            flips = bool(alert.get("flips", False))
            guidelines = alert.get("guidelines", [])
            guideline_count = len(guidelines)

            base = compute_base_score(reason_cat, weight_share, flips, guideline_count)
            weight_bucket = get_weight_bucket(weight_share)
            flips_str = str(flips).lower()

            alert_features = {
                "reason": reason_cat,
                "weight_bucket": weight_bucket,
                "flips": flips_str,
            }

            # Match active rules
            item_rules = []
            raw_delta_sum = 0.0
            for r in active_rules:
                feat = r["feature"]
                val = str(r["value"]).lower()
                if val in ("data_falsification", "falsification"):
                    val = "fabrication"
                if alert_features.get(feat) == val:
                    item_rules.append(r)
                    raw_delta_sum += float(r["delta"])
                    all_applied_rules[r["id"]] = r

            # Invariant 1: Rule adjustment cap at [-0.4, +0.4]
            capped_delta = min(DELTA_CAP_MAX, max(DELTA_CAP_MIN, raw_delta_sum))
            adjusted_score = base + capped_delta

            # Invariant 2: Clinical safety floor
            # Alerts with fabrication or statistical flips can never score below 0.5
            is_critical = (reason_cat == "fabrication") or flips
            if is_critical:
                final_score = max(SAFETY_FLOOR_SCORE, min(1.0, round(adjusted_score, 4)))
            else:
                final_score = max(0.0, min(1.0, round(adjusted_score, 4)))

            ranked_items.append({
                "review_id": rev_id,
                "title": alert.get("title", f"Review {rev_id}"),
                "base": base,
                "score": final_score,
                "delta": round(capped_delta, 4),
                "raw_delta": round(raw_delta_sum, 4),
                "reason_category": reason_cat,
                "weight_share": weight_share,
                "weight_bucket": weight_bucket,
                "flips": flips,
                "guidelines": guidelines,
                "applied_rules": item_rules,
                "safety_floor_active": is_critical and (adjusted_score < SAFETY_FLOOR_SCORE),
            })

        # Sort descending by personalized score, then base
        ranked_items.sort(key=lambda x: (x["score"], x["base"]), reverse=True)

        for rank_idx, item in enumerate(ranked_items, start=1):
            item["rank"] = rank_idx

        ranking_id = None
        if persist:
            ranking_id = self.memory.record_ranking(
                retraction_id=retraction_id,
                ranked_items=ranked_items,
                applied_rules=list(all_applied_rules.values()),
            )

        return ranked_items, ranking_id
