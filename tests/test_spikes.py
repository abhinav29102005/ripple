"""
Pytest integration for verification Spikes A through D.
"""
import time
import multiprocessing as mp
from collections import Counter
import pytest
from graph import graph_manager

def test_spike_c_cypher_features():
    g = graph_manager.get_graph("test_spike_c")
    graph_manager.delete_graph("test_spike_c")
    g = graph_manager.get_graph("test_spike_c")

    # 1. Index creation
    g.query("CREATE INDEX FOR (n:TestLabel) ON (n.id)")
    
    # 2. MERGE with params
    g.query("MERGE (n:TestLabel {id: $id}) SET n.tag = 'temp'", {"id": "t1"})
    
    # 3. SET null removes property
    g.query("MATCH (n:TestLabel {id: $id}) SET n.tag = null", {"id": "t1"})
    res = g.query("MATCH (n:TestLabel {id: $id}) RETURN n.tag", {"id": "t1"})
    assert res.result_set[0][0] is None

    # 4. OPTIONAL MATCH with collect(DISTINCT) and WITH ... WHERE
    g.query("""
    CREATE (a:Review {id: 'r1'}), (b:Guideline {id: 'g1'}), (c:Guideline {id: 'g2'}),
           (a)-[:INFORMS]->(b), (a)-[:INFORMS]->(c)
    """)
    res = g.query("""
    MATCH (a:Review {id: 'r1'})
    OPTIONAL MATCH (a)-[:INFORMS]->(g:Guideline)
    WITH a, collect(DISTINCT g.id) AS g_ids
    WHERE size(g_ids) > 0
    RETURN a.id, g_ids
    """)
    assert res.result_set[0][0] == "r1"
    assert set(res.result_set[0][1]) == {"g1", "g2"}

    # 5. Variable length paths
    g.query("CREATE (x:N {id:'x'})-[:REL_A]->(y:N {id:'y'})-[:REL_B]->(z:N {id:'z'})")
    res = g.query("MATCH p = (x:N {id:'x'})-[:REL_A|REL_B*1..3]->(z:N {id:'z'}) RETURN length(p)")
    assert res.result_set[0][0] == 2

    # 6. Pattern predicates in WHERE
    res = g.query("MATCH (a:Review) WHERE (a)-[:INFORMS]->(:Guideline) RETURN a.id")
    assert res.result_set[0][0] == "r1"

    # 7. List parameters
    res = g.query("UNWIND $items AS x RETURN x", {"items": [1, 2, 3]})
    assert [r[0] for r in res.result_set] == [1, 2, 3]

    graph_manager.delete_graph("test_spike_c")

def test_spike_d_algorithms():
    g = graph_manager.get_graph("test_spike_d")
    graph_manager.delete_graph("test_spike_d")
    g = graph_manager.get_graph("test_spike_d")

    # Seed test structure
    g.query("""
    CREATE (a:Review {id: 'A'}), (b:Review {id: 'B'}), (c:Guideline {id: 'C'}),
           (x:Review {id: 'X'}), (y:Review {id: 'Y'}),
           (a)-[:INFORMS]->(b), (b)-[:INFORMS]->(c),
           (a)-[:SHARES_TRIAL {n: 1}]->(b),
           (x)-[:SHARES_TRIAL {n: 2}]->(y)
    """)

    # 1. PageRank
    pr_res = g.query('CALL algo.pageRank("Review", "INFORMS") YIELD node, score RETURN node.id, score')
    assert len(pr_res.result_set) > 0

    # 2. WCC (Weakly Connected Components)
    wcc_res = g.query("CALL algo.WCC() YIELD node, componentId RETURN node.id, componentId")
    assert len(wcc_res.result_set) == 5

    # 3. SPpaths (Shortest Path)
    sp_res = g.query("""
    MATCH (a:Review {id: 'A'}), (c:Guideline {id: 'C'})
    CALL algo.SPpaths({sourceNode: a, targetNode: c}) YIELD path
    RETURN path
    """)
    assert len(sp_res.result_set) == 1
    p = sp_res.result_set[0][0]
    node_ids = [n.properties.get("id") for n in p.nodes()]
    assert node_ids == ["A", "B", "C"]

    graph_manager.delete_graph("test_spike_d")

def _claim_worker(agent_id, results_queue):
    from falkordb import FalkorDB
    from config import settings
    db = FalkorDB(host=settings.falkordb_host, port=settings.falkordb_port)
    g = db.select_graph("test_spike_b_coord")
    claimed = []
    
    query = """
    MATCH (t:Task {status: 'queued', type: $type})
    OPTIONAL MATCH (t)-[:DEPENDS_ON]->(d:Task) WHERE d.status <> 'done'
    WITH t, count(d) AS open WHERE open = 0
    WITH t ORDER BY t.priority DESC, t.created ASC LIMIT 1
    SET t.status = 'claimed', t.claimed_by = $agent,
        t.lease_until = $now + $lease, t.attempts = t.attempts + 1
    RETURN t.id AS id, t.payload AS payload
    """
    
    while True:
        now = int(time.time())
        res = g.query(query, {
            "type": "dummy",
            "agent": f"worker-{agent_id}",
            "now": now,
            "lease": 30
        })
        if not res.result_set:
            check = g.query("MATCH (t:Task {status: 'queued', type: $type}) RETURN count(t)", {"type": "dummy"})
            remaining = check.result_set[0][0] if check.result_set else 0
            if remaining == 0:
                break
            time.sleep(0.01)
            continue
        claimed.append(res.result_set[0][0])
    
    results_queue.put(claimed)

def test_spike_b_concurrency_atomic_claim():
    g = graph_manager.get_graph("test_spike_b_coord")
    graph_manager.delete_graph("test_spike_b_coord")
    g = graph_manager.get_graph("test_spike_b_coord")
    g.query("CREATE INDEX FOR (t:Task) ON (t.status)")
    g.query("CREATE INDEX FOR (t:Task) ON (t.type)")

    total_tasks = 200
    now = int(time.time())
    params = [{
        "id": f"t-{i:03d}", "key": f"k-{i:03d}", "type": "dummy",
        "status": "queued", "priority": i % 3, "created": now + i,
        "lease_until": 0, "attempts": 0, "max_attempts": 3, "payload": "{}"
    } for i in range(total_tasks)]
    
    g.query("""
    UNWIND $batch AS p
    CREATE (t:Task {
        id: p.id, key: p.key, type: p.type, status: p.status,
        priority: p.priority, created: p.created, lease_until: p.lease_until,
        attempts: p.attempts, max_attempts: p.max_attempts, payload: p.payload
    })
    """, {"batch": params})

    num_workers = 8
    ctx = mp.get_context("spawn")
    results_queue = ctx.Queue()
    workers = [ctx.Process(target=_claim_worker, args=(w, results_queue)) for w in range(num_workers)]
    for w in workers:
        w.start()

    all_claimed = []
    for _ in range(num_workers):
        all_claimed.extend(results_queue.get())

    for w in workers:
        w.join()

    counts = Counter(all_claimed)
    double_claims = [t_id for t_id, cnt in counts.items() if cnt > 1]
    assert len(double_claims) == 0, f"Double claims detected: {double_claims}"
    assert len(counts) == total_tasks, f"Expected {total_tasks} claimed, got {len(counts)}"

    graph_manager.delete_graph("test_spike_b_coord")
