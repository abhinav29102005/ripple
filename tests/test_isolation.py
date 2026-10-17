"""
Tenant isolation verification tests for Ripple.
Ensures tenant A cannot read tenant B's episodes, rules, or sessions.
"""
import pytest
from graph import graph_manager
from memory import TenantMemory

@pytest.fixture(autouse=True)
def clean_tenants():
    graph_manager.delete_graph("tenant_cardiology")
    graph_manager.delete_graph("tenant_oncology")
    yield
    graph_manager.delete_graph("tenant_cardiology")
    graph_manager.delete_graph("tenant_oncology")

def test_tenant_isolation_episodes_and_rules():
    cardio_mem = TenantMemory("cardiology")
    onco_mem = TenantMemory("oncology")

    # Cardio records sessions, episodes, facts, and rules
    s_cardio = cardio_mem.create_session()
    cardio_mem.record_episode(
        session_id=s_cardio,
        kind="dismiss",
        reason="administrative",
        weight_bucket="low",
        flips=False,
        ext_review="SYN-REV-CARDIO-01",
        ext_retraction="SYN-RET-01",
    )
    cardio_mem.save_rule(
        rule_id="rule_cardio_specific",
        feature="reason",
        value="administrative",
        delta=-0.3,
        support=3,
        hit_rate=1.0,
        description="Cardio team dismissal policy",
    )
    cardio_mem.set_fact("guideline_authority", "Cardiology Clinical Evidence Board (CCEB)")

    # Verify Cardio sees its data
    assert len(cardio_mem.get_episodes()) == 1
    assert len(cardio_mem.get_active_rules()) == 1
    assert len(cardio_mem.get_facts()) == 1

    # Verify Oncology CANNOT see Cardio's data (must be completely empty)
    assert len(onco_mem.get_episodes()) == 0
    assert len(onco_mem.get_active_rules()) == 0
    assert len(onco_mem.get_facts()) == 0

    # Oncology sets its own fact
    onco_mem.set_fact("guideline_authority", "Oncology Research Review Board (ORRB)")
    assert len(onco_mem.get_facts()) == 1
    assert onco_mem.get_facts()[0]["value"] == "Oncology Research Review Board (ORRB)"

    # Cardio still only sees its own authority
    cardio_facts = cardio_mem.get_facts()
    assert len(cardio_facts) == 1
    assert cardio_facts[0]["value"] == "Cardiology Clinical Evidence Board (CCEB)"
