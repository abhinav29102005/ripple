"""
Integration and acceptance tests for Milestone M6 (Track 01: Connected Data & MCP Analyst).
Verifies:
- MCP tools execute correctly over FalkorDB
- 'What should we do first?' query executes autonomous tool calling trace
- Built-in algorithms (PageRank, WCC, Shortest Path) produce verified outputs
- Incident ticket is automatically opened and linked in the graph
"""
import pytest
from graph import graph_manager
from scripts.seed_synthetic import seed_synthetic_data
from scripts.seed_org import seed_organization
import mcp_server
from analyst import AnalystAgent

@pytest.fixture(scope="module", autouse=True)
def setup_mcp_test_graphs():
    graph_manager.delete_graph("knowledge")
    graph_manager.delete_graph("coord")
    graph_manager.delete_graph("tenant_cardio")
    graph_manager.init_knowledge_schema()
    graph_manager.init_coord_schema()
    graph_manager.init_tenant_schema("cardio")
    seed_synthetic_data(scale="standard", seed=42)
    seed_organization(seed=42)
    yield

def test_mcp_individual_tools():
    # 1. blast_radius
    blast = mcp_server.blast_radius("SYN-RET-001")
    assert "SYN-TR-0001" in blast["affected_trials"]
    assert "SYN-REV-001" in blast["affected_reviews"]
    assert len(blast["traversed_node_ids"]) > 0

    # 2. rank_guidelines (PageRank)
    gl_rank = mcp_server.rank_guidelines(limit=3)
    assert gl_rank["algorithm"] == "algo.pageRank"
    assert len(gl_rank["top_guidelines"]) > 0
    assert "score" in gl_rank["top_guidelines"][0]

    # 3. contamination_clusters (WCC)
    clusters = mcp_server.contamination_clusters("SYN-RET-001")
    assert clusters["algorithm"] == "algo.WCC"
    assert "shared_trial_pairs" in clusters

    # 4. open_ticket
    tck = mcp_server.open_ticket("DEC-CARDIO-001", "Remediation Ticket", "high")
    assert tck["status"] == "created"
    assert tck["ticket_id"].startswith("TCK-MCP-")

def test_analyst_agent_what_should_we_do_first():
    agent = AnalystAgent("cardio")
    result = agent.execute_plan(
        retraction_id="SYN-RET-001",
        query="What should we do first about retraction SYN-RET-001?",
    )

    # Acceptance criteria verification:
    # 1. Produces tool-call trace
    trace = result["trace"]
    assert len(trace) >= 5
    tool_names = [step["tool"] for step in trace]
    assert "blast_radius" in tool_names
    assert "rank_guidelines" in tool_names
    assert "contamination_clusters" in tool_names
    assert "recall_team_history" in tool_names
    assert "open_ticket" in tool_names

    # 2. Uses built-in graph algorithms
    algorithms = result["algorithms_used"]
    assert "algo.pageRank" in algorithms
    assert "algo.WCC" in algorithms
    assert "algo.SPpaths" in algorithms

    # 3. Produces an opened ticket
    ticket_id = result["ticket_id"]
    assert ticket_id.startswith("TCK-MCP-")

    # 4. Verify ticket was written into FalkorDB knowledge graph
    g = graph_manager.get_graph("knowledge")
    res = g.query("MATCH (t:Ticket {id: $tid})-[:TRACKS]->(d:Decision) RETURN t.title, d.id", {"tid": ticket_id})
    assert len(res.result_set) == 1
    assert res.result_set[0][1] == result["target_decision_id"]

    # 5. Recommendation cites node IDs and follows medical disclaimer
    rec = result["recommendation"]
    assert "SYN-RET-001" in rec
    assert result["target_decision_id"] in rec
    assert ticket_id in rec
    assert "review" in rec.lower()
