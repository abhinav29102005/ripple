import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Deterministic synthetic evidence generator for Ripple.
Generates trials, reviews, guidelines, topics, and retraction events.
Standard scale for clean UI demos, benchmark scale for stress testing.
"""
import argparse
import random
from typing import Dict, List
from graph import graph_manager

TOPICS = ["Cardiology", "Oncology", "Immunology", "Neurology", "Infectious Disease"]
JOURNALS = [
    "New England Journal of Medicine (SYN)",
    "The Lancet (SYN)",
    "JAMA Cardiology (SYN)",
    "Journal of Clinical Oncology (SYN)",
    "Nature Medicine (SYN)",
]

REASONS = [
    ("fabrication", "Data fabrication and falsification in clinical patient records"),
    ("error", "Pervasive calculation error in baseline patient characteristic tables"),
    ("administrative", "Duplicate publication and lack of proper ethics committee disclosures"),
    ("unknown", "Author retraction notice without detailed methodological specification"),
]

def seed_synthetic_data(scale: str = "standard", seed: int = 42) -> Dict[str, int]:
    random.seed(seed)
    g = graph_manager.init_knowledge_schema()

    if scale == "bench":
        num_trials = 2000
        num_reviews = 400
        num_guidelines = 60
        num_retractions = 500
    else:
        num_trials = 40
        num_reviews = 10
        num_guidelines = 5
        num_retractions = 4

    print(f"Seeding synthetic evidence ({scale} scale: {num_trials} trials, {num_reviews} reviews, {num_guidelines} guidelines)...")

    # 1. Topics & Journals
    for top in TOPICS:
        g.query("MERGE (t:Topic {name: $name})", {"name": top})
    for j in JOURNALS:
        g.query("MERGE (j:Journal {name: $name})", {"name": j})

    # 2. Guidelines
    guideline_batch = []
    for i in range(1, num_guidelines + 1):
        gid = f"SYN-GL-{i:03d}"
        topic = TOPICS[(i - 1) % len(TOPICS)]
        guideline_batch.append({
            "id": gid,
            "title": f"Clinical Practice Guideline on {topic} Protocol {i} (SYN)",
            "body_org": f"National {topic} Society",
            "year": 2022 + (i % 3),
            "synthetic": True,
            "topic": topic,
        })
    g.query("""
    UNWIND $batch AS p
    MERGE (g:Guideline {id: p.id})
    SET g.title = p.title, g.body_org = p.body_org, g.year = p.year, g.synthetic = p.synthetic
    WITH g, p
    MATCH (top:Topic {name: p.topic})
    MERGE (g)-[:ON]->(top)
    """, {"batch": guideline_batch})

    # 3. Reviews
    review_batch = []
    for i in range(1, num_reviews + 1):
        rid = f"SYN-REV-{i:03d}"
        topic = TOPICS[(i - 1) % len(TOPICS)]
        # Map to 1-2 guidelines
        primary_g = f"SYN-GL-{((i - 1) % num_guidelines) + 1:03d}"
        g_ids = [primary_g]
        if i == 7:
            g_ids.append("SYN-GL-003")
        elif i == 8:
            g_ids.append("SYN-GL-001")
        elif i == 10:
            g_ids.append("SYN-GL-001")
        review_batch.append({
            "id": rid,
            "title": f"Systematic Review of {topic} Therapeutics Vol {i} (SYN)",
            "year": 2020 + (i % 4),
            "model": "fixed",
            "synthetic": True,
            "topic": topic,
            "guideline_ids": g_ids,
        })
    g.query("""
    UNWIND $batch AS p
    MERGE (r:Review {id: p.id})
    SET r.title = p.title, r.year = p.year, r.model = p.model, r.synthetic = p.synthetic
    WITH r, p
    MATCH (top:Topic {name: p.topic})
    MERGE (r)-[:ON]->(top)
    WITH r, p
    UNWIND p.guideline_ids AS gid
    MATCH (g:Guideline {id: gid})
    MERGE (r)-[:INFORMS]->(g)
    """, {"batch": review_batch})

    # 4. Trials & INCLUDED_IN edges
    trials_per_batch = 100
    for b in range(0, num_trials, trials_per_batch):
        t_batch = []
        for i in range(b + 1, min(b + trials_per_batch, num_trials) + 1):
            tid = f"SYN-TR-{i:04d}"
            # Assign trial to 1 or 2 reviews
            primary_rev = f"SYN-REV-{((i - 1) % num_reviews) + 1:03d}"
            # Some trials shared between reviews to produce contamination clusters
            shared_rev = f"SYN-REV-{((i % num_reviews) + 1):03d}" if i % 3 == 0 else primary_rev
            journal = JOURNALS[i % len(JOURNALS)]
            yi = round(random.uniform(-0.95, -0.15), 3)
            sei = round(random.uniform(0.10, 0.35), 3)
            t_batch.append({
                "id": tid,
                "title": f"Randomized Controlled Trial of Candidate Drug {i} (SYN)",
                "year": 2018 + (i % 5),
                "status": "active",
                "synthetic": True,
                "journal": journal,
                "primary_rev": primary_rev,
                "shared_rev": shared_rev,
                "yi": yi,
                "sei": sei,
            })
        g.query("""
        UNWIND $batch AS p
        MERGE (t:Trial {id: p.id})
        SET t.title = p.title, t.year = p.year, t.status = p.status, t.synthetic = p.synthetic
        WITH t, p
        MATCH (j:Journal {name: p.journal})
        MERGE (t)-[:PUBLISHED_IN]->(j)
        WITH t, p
        MATCH (r1:Review {id: p.primary_rev})
        MERGE (t)-[:INCLUDED_IN {yi: p.yi, sei: p.sei}]->(r1)
        WITH t, p
        MATCH (r2:Review {id: p.shared_rev})
        MERGE (t)-[:INCLUDED_IN {yi: p.yi, sei: p.sei}]->(r2)
        """, {"batch": t_batch})

    # 5. Plant initial Retractions
    retraction_batch = []
    for i in range(1, num_retractions + 1):
        ret_id = f"SYN-RET-{i:03d}"
        target_trial_id = f"SYN-TR-{i:04d}"
        category, reason_text = REASONS[(i - 1) % len(REASONS)]
        retraction_batch.append({
            "id": ret_id,
            "trial_id": target_trial_id,
            "reason_category": category,
            "reason": reason_text,
            "date": f"2024-{(i % 12) + 1:02d}-15",
            "notice_url": f"https://example.org/retractions/{ret_id.lower()}",
            "synthetic": True,
        })
    g.query("""
    UNWIND $batch AS p
    MERGE (r:Retraction {id: p.id})
    SET r.reason_category = p.reason_category,
        r.reason = p.reason,
        r.date = p.date,
        r.notice_url = p.notice_url,
        r.synthetic = p.synthetic
    WITH r, p
    MATCH (t:Trial {id: p.trial_id})
    SET t.status = 'retracted'
    MERGE (r)-[:RETRACTS]->(t)
    """, {"batch": retraction_batch})

    print(f"Successfully seeded {scale} synthetic knowledge graph!")
    return {
        "trials": num_trials,
        "reviews": num_reviews,
        "guidelines": num_guidelines,
        "retractions": num_retractions,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", default="standard", choices=["standard", "bench"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    seed_synthetic_data(scale=args.scale, seed=args.seed)
