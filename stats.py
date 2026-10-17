"""
Meta-analysis statistical pooling module for Ripple.
Computes fixed-effect (inverse-variance) and random-effects (DerSimonian-Laird)
pooled effect estimates before and after trial retractions.
"""
import math
from typing import Dict, List, Optional, Tuple, Any

def compute_fixed_effect(trials: List[Dict[str, float]]) -> Dict[str, float]:
    """
    Inverse-variance fixed-effect pooling:
    w_i = 1 / sei_i^2
    pooled = sum(w_i * yi_i) / sum(w_i)
    se = sqrt(1 / sum(w_i))
    ci = pooled ± 1.96 * se
    """
    if not trials:
        return {"pooled": 0.0, "se": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "k": 0}

    total_w = 0.0
    weighted_sum = 0.0
    for t in trials:
        sei = t["sei"]
        yi = t["yi"]
        if sei <= 0:
            continue
        w = 1.0 / (sei ** 2)
        total_w += w
        weighted_sum += w * yi

    if total_w <= 0:
        return {"pooled": 0.0, "se": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "k": 0}

    pooled = weighted_sum / total_w
    se = math.sqrt(1.0 / total_w)
    ci_lo = pooled - 1.96 * se
    ci_hi = pooled + 1.96 * se

    return {
        "pooled": pooled,
        "se": se,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "k": len(trials),
    }

def compute_random_effects(trials: List[Dict[str, float]]) -> Dict[str, float]:
    """
    DerSimonian-Laird random-effects pooling:
    Q = sum(w_i * (yi_i - pooled_fe)^2)
    tau2 = max(0, (Q - (k - 1)) / (sum(w) - sum(w^2)/sum(w)))
    w_star = 1 / (sei^2 + tau2)
    """
    k = len(trials)
    if k <= 1:
        return compute_fixed_effect(trials)

    fe = compute_fixed_effect(trials)
    pooled_fe = fe["pooled"]

    weights = [1.0 / (t["sei"] ** 2) for t in trials]
    sum_w = sum(weights)
    sum_w_sq = sum(w ** 2 for w in weights)

    q = sum(w * ((t["yi"] - pooled_fe) ** 2) for w, t in zip(weights, trials))
    c = sum_w - (sum_w_sq / sum_w)

    tau2 = max(0.0, (q - (k - 1)) / c) if c > 0 else 0.0

    star_weights = [1.0 / ((t["sei"] ** 2) + tau2) for t in trials]
    sum_star_w = sum(star_weights)
    pooled_re = sum(w * t["yi"] for w, t in zip(star_weights, trials)) / sum_star_w
    se_re = math.sqrt(1.0 / sum_star_w)

    return {
        "pooled": pooled_re,
        "se": se_re,
        "ci_lo": pooled_re - 1.96 * se_re,
        "ci_hi": pooled_re + 1.96 * se_re,
        "tau2": tau2,
        "q": q,
        "k": k,
    }

def assess_impact(
    all_trials: List[Dict[str, Any]],
    retracted_trial_ids: List[str],
    method: str = "fixed",
) -> Dict[str, Any]:
    """
    Computes before (all trials) and after (excluding retracted trials) pooling,
    calculates percentage change in effect, and evaluates whether the clinical
    conclusion flips (sign change or crossing the zero threshold).
    """
    pool_fn = compute_random_effects if method == "random" else compute_fixed_effect

    before_res = pool_fn(all_trials)
    
    remaining_trials = [t for t in all_trials if t.get("id") not in retracted_trial_ids]
    after_res = pool_fn(remaining_trials)

    before_pooled = before_res["pooled"]
    after_pooled = after_res["pooled"]

    # Percentage change relative to before
    if abs(before_pooled) > 1e-9:
        pct_change = (after_pooled - before_pooled) / abs(before_pooled)
    else:
        pct_change = 0.0

    # Flip criteria:
    # 1. Sign change (direction reverses)
    sign_flip = (before_pooled * after_pooled < 0)

    # 2. CI crossing zero change (e.g. was significant [does not cross 0], now insignificant [crosses 0], or vice versa)
    before_crosses_zero = (before_res["ci_lo"] <= 0.0 <= before_res["ci_hi"])
    after_crosses_zero = (after_res["ci_lo"] <= 0.0 <= after_res["ci_hi"])
    significance_flip = (before_crosses_zero != after_crosses_zero)

    flips = sign_flip or significance_flip

    # Total weight share of retracted trials
    total_w = sum(1.0 / (t["sei"] ** 2) for t in all_trials if t["sei"] > 0)
    retracted_w = sum(
        1.0 / (t["sei"] ** 2)
        for t in all_trials
        if t.get("id") in retracted_trial_ids and t["sei"] > 0
    )
    weight_share = (retracted_w / total_w) if total_w > 0 else 0.0

    return {
        "before": round(before_pooled, 4),
        "before_lo": round(before_res["ci_lo"], 4),
        "before_hi": round(before_res["ci_hi"], 4),
        "before_se": round(before_res["se"], 4),
        "after": round(after_pooled, 4),
        "after_lo": round(after_res["ci_lo"], 4),
        "after_hi": round(after_res["ci_hi"], 4),
        "after_se": round(after_res["se"], 4),
        "pct_change": round(pct_change, 4),
        "flips": bool(flips),
        "sign_flip": bool(sign_flip),
        "significance_flip": bool(significance_flip),
        "weight_share": round(weight_share, 4),
        "retracted_count": len(retracted_trial_ids),
        "remaining_count": len(remaining_trials),
    }
