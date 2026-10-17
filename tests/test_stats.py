"""
Unit tests for meta-analysis pooling math in stats.py.
Verifies fixed-effect and random-effects pooling against reference test vectors.
"""
import pytest
from stats import compute_fixed_effect, assess_impact

def test_spec_required_vector_fixed_effect():
    """
    Test vector from Section 8.1 of RIPPLE_PROJECT.md:
    Trial A: yi = -0.4, sei = 0.20 (w = 25)
    Trial B: yi = -0.5, sei = 0.25 (w = 16)
    Trial C (retracted): yi = -0.9, sei = 0.15 (w = 44.444)
    """
    trials = [
        {"id": "A", "yi": -0.4, "sei": 0.20},
        {"id": "B", "yi": -0.5, "sei": 0.25},
        {"id": "C", "yi": -0.9, "sei": 0.15},
    ]

    # Before: all 3 trials
    res_before = compute_fixed_effect(trials)
    assert pytest.approx(res_before["pooled"], abs=1e-3) == -0.6788
    assert pytest.approx(res_before["se"], abs=1e-3) == 0.1082
    assert pytest.approx(res_before["ci_lo"], abs=1e-3) == -0.891
    assert pytest.approx(res_before["ci_hi"], abs=1e-3) == -0.467

    # After: C removed
    remaining = [t for t in trials if t["id"] != "C"]
    res_after = compute_fixed_effect(remaining)
    assert pytest.approx(res_after["pooled"], abs=1e-3) == -0.4390
    assert pytest.approx(res_after["se"], abs=1e-3) == 0.1562
    assert pytest.approx(res_after["ci_lo"], abs=1e-3) == -0.745
    assert pytest.approx(res_after["ci_hi"], abs=1e-3) == -0.133

    # Assess impact
    impact = assess_impact(trials, retracted_trial_ids=["C"], method="fixed")
    assert pytest.approx(impact["before"], abs=1e-3) == -0.6788
    assert pytest.approx(impact["after"], abs=1e-3) == -0.4390
    # pct_change is (after - before) / abs(before) = (-0.4390 - (-0.6788)) / 0.6788 = +0.3533 (effect attenuated by ~35%)
    assert pytest.approx(impact["pct_change"], abs=1e-2) == 0.353
    assert impact["flips"] is False
    assert impact["sign_flip"] is False
    assert impact["significance_flip"] is False

def test_impact_flips_clinical_significance():
    """
    Second test vector: retraction causes the pooled effect 95% CI to cross zero,
    flipping statistical significance.
    """
    trials = [
        {"id": "T1", "yi": -0.15, "sei": 0.20},  # weak effect, high uncertainty
        {"id": "T2", "yi": -0.20, "sei": 0.20},  # weak effect, high uncertainty
        {"id": "T3_retracted", "yi": -0.90, "sei": 0.08}, # dominant, tight effect driving significance
    ]

    impact = assess_impact(trials, retracted_trial_ids=["T3_retracted"], method="fixed")
    # Before retraction: CI was strictly negative (significant)
    assert impact["before_hi"] < 0.0
    # After retraction: CI crosses zero (insignificant)
    assert impact["after_lo"] <= 0.0 <= impact["after_hi"]
    # Flips must be True
    assert impact["flips"] is True
    assert impact["significance_flip"] is True

def test_impact_flips_sign_reversal():
    """
    Third test vector: retraction causes effect to reverse sign completely.
    """
    trials = [
        {"id": "T1", "yi": 0.30, "sei": 0.15},   # positive effect
        {"id": "T2_retracted", "yi": -0.80, "sei": 0.10}, # large negative retracted trial
    ]
    impact = assess_impact(trials, retracted_trial_ids=["T2_retracted"], method="fixed")
    assert impact["before"] < 0
    assert impact["after"] > 0
    assert impact["flips"] is True
    assert impact["sign_flip"] is True
