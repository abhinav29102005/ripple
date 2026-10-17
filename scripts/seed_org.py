"""
Deterministic synthetic organization generator for Track 03 (Company Brain).
Generates People, Committees, Decisions, Documents, Messages, and Tickets
connected to the scientific knowledge graph. Uses batched UNWIND queries for high performance.
"""
import time
from typing import Dict, List
from graph import graph_manager

PEOPLE = [
    {"id": "PER-001", "name": "Dr. Sarah Chen", "role": "Chief of Cardiology & Guideline Chair", "email": "schen@hospital.org", "topics": ["Cardiology"]},
    {"id": "PER-002", "name": "Dr. Marcus Vance", "role": "Senior Interventional Cardiologist", "email": "mvance@hospital.org", "topics": ["Cardiology"]},
    {"id": "PER-003", "name": "Dr. Elena Rostova", "role": "Director of Medical Oncology", "email": "erostova@hospital.org", "topics": ["Oncology"]},
    {"id": "PER-004", "name": "Dr. James Wilson", "role": "Clinical Trialist & Methodologist", "email": "jwilson@hospital.org", "topics": ["Immunology", "Cardiology"]},
    {"id": "PER-005", "name": "Dr. Priya Patel", "role": "Head of Clinical Pharmacy & Formulary", "email": "ppatel@hospital.org", "topics": ["Cardiology", "Oncology"]},
    {"id": "PER-006", "name": "Dr. Arthur Pendelton", "role": "Hospital Chief Medical Officer", "email": "apendelton@hospital.org", "topics": ["Neurology"]},
    {"id": "PER-007", "name": "Dr. Rebecca Kim", "role": "Thoracic Oncology Lead", "email": "rkim@hospital.org", "topics": ["Oncology"]},
    {"id": "PER-008", "name": "Dr. David Thorne", "role": "Vascular Surgery Section Chief", "email": "dthorne@hospital.org", "topics": ["Cardiology"]},
    {"id": "PER-009", "name": "Dr. Maya Lin", "role": "Biostatistics Core Director", "email": "mlin@hospital.org", "topics": ["Infectious Disease"]},
    {"id": "PER-010", "name": "Dr. Tariq Mansour", "role": "Internal Medicine Residency Director", "email": "tmansour@hospital.org", "topics": ["Cardiology"]},
    {"id": "PER-011", "name": "Dr. Chloe Bennett", "role": "Clinical Pharmacology Fellow", "email": "cbennett@hospital.org", "topics": ["Oncology"]},
    {"id": "PER-012", "name": "Dr. Samuel Green", "role": "Patient Safety Committee Chair", "email": "sgreen@hospital.org", "topics": ["Neurology"]},
]

COMMITTEES = [
    {"id": "COM-CARDIO", "name": "Cardiology Steering Committee", "members": ["PER-001", "PER-002", "PER-005", "PER-008", "PER-010"]},
    {"id": "COM-ONCO", "name": "Oncology Formulary Steering Committee", "members": ["PER-003", "PER-005", "PER-007", "PER-011"]},
    {"id": "COM-SAFETY", "name": "Hospital Quality & Patient Safety Board", "members": ["PER-004", "PER-006", "PER-009", "PER-012", "PER-001"]},
]

def seed_organization(seed: int = 42):
    g = graph_manager.get_graph("knowledge")
    print("Seeding synthetic organization structure (People, Committees, Decisions, Docs, Chats)...")

    # 1. People
    g.query("""
    UNWIND $batch AS p
    MERGE (per:Person {id: p.id})
    SET per.name = p.name, per.role = p.role, per.email = p.email, per.synthetic = true
    """, {"batch": PEOPLE})

    # Planted co-authorships with topics
    pub_batch = []
    for p in PEOPLE:
        for top_name in p["topics"]:
            pub_batch.append({
                "pid": p["id"],
                "tname": top_name,
                "doc_id": f"DOC-PUB-{p['id']}-{top_name[:3].upper()}",
                "doc_title": f"Investigative Analysis in {top_name} by {p['name']} (SYN)",
            })
    g.query("""
    UNWIND $batch AS p
    MATCH (per:Person {id: p.pid}), (top:Topic {name: p.tname})
    MERGE (doc:Document {id: p.doc_id})
    SET doc.title = p.doc_title, doc.kind = 'primary_research', doc.synthetic = true
    MERGE (per)-[:AUTHORED]->(doc)
    MERGE (doc)-[:ABOUT]->(top)
    """, {"batch": pub_batch})

    # 2. Committees & Membership
    for com in COMMITTEES:
        g.query("""
        MERGE (c:Committee {id: $id})
        SET c.name = $name, c.synthetic = true
        """, {"id": com["id"], "name": com["name"]})

        g.query("""
        MATCH (c:Committee {id: $cid})
        UNWIND $members AS mid
        MATCH (p:Person {id: mid})
        MERGE (p)-[:MEMBER_OF]->(c)
        """, {"cid": com["id"], "members": com["members"]})

    # Committee ownership of Guidelines
    g.query("""
    MATCH (c:Committee {id: 'COM-CARDIO'}), (g:Guideline {id: 'SYN-GL-001'})
    MERGE (c)-[:OWNS]->(g)
    """)
    g.query("""
    MATCH (c:Committee {id: 'COM-ONCO'}), (g:Guideline {id: 'SYN-GL-002'})
    MERGE (c)-[:OWNS]->(g)
    """)

    # Planted Authorship
    g.query("""
    MATCH (p:Person {id: 'PER-001'}), (rev:Review {id: 'SYN-REV-001'})
    MERGE (p)-[:AUTHORED]->(rev)
    """)
    g.query("""
    MATCH (p:Person {id: 'PER-003'}), (rev:Review {id: 'SYN-REV-002'})
    MERGE (p)-[:AUTHORED]->(rev)
    """)

    # 3. Decisions
    decisions = [
        {
            "id": "DEC-CARDIO-001",
            "title": "Hospital-wide Formulary Adoption of Triple-Antiplatelet Protocol",
            "date": "2023-04-12",
            "status": "active",
            "committee": "COM-CARDIO",
            "guideline": "SYN-GL-001",
            "reviews": ["SYN-REV-001", "SYN-REV-002"],
            "participants": ["PER-001", "PER-002", "PER-005"],
        },
        {
            "id": "DEC-CARDIO-002",
            "title": "Target LDL Threshold Standard for Post-Infarction Care",
            "date": "2023-07-20",
            "status": "active",
            "committee": "COM-CARDIO",
            "guideline": "SYN-GL-001",
            "reviews": ["SYN-REV-001"],
            "participants": ["PER-001", "PER-008"],
        },
        {
            "id": "DEC-ONCO-001",
            "title": "Adjuvant Immunotherapy First-Line Regimen Authorization",
            "date": "2023-09-15",
            "status": "active",
            "committee": "COM-ONCO",
            "guideline": "SYN-GL-002",
            "reviews": ["SYN-REV-002"],
            "participants": ["PER-003", "PER-007"],
        },
    ]

    for i in range(4, 16):
        com = "COM-CARDIO" if i % 2 == 0 else "COM-ONCO"
        gid = "SYN-GL-001" if i % 2 == 0 else "SYN-GL-002"
        rev_id = f"SYN-REV-{((i - 1) % 5) + 1:03d}"
        decisions.append({
            "id": f"DEC-GEN-{i:03d}",
            "title": f"Clinical Operational Protocol Decision #{i} (SYN)",
            "date": f"2023-{(i % 12) + 1:02d}-10",
            "status": "active",
            "committee": com,
            "guideline": gid,
            "reviews": [rev_id],
            "participants": ["PER-001", "PER-002"] if i % 2 == 0 else ["PER-003", "PER-004"],
        })

    dec_nodes = [{"id": d["id"], "title": d["title"], "date": d["date"], "status": d["status"], "com_id": d["committee"], "gid": d["guideline"]} for d in decisions]
    g.query("""
    UNWIND $batch AS p
    MERGE (dec:Decision {id: p.id})
    SET dec.title = p.title, dec.date = p.date, dec.status = p.status, dec.synthetic = true
    WITH dec, p
    MATCH (c:Committee {id: p.com_id})
    MERGE (dec)-[:MADE_BY]->(c)
    WITH dec, p
    MATCH (g:Guideline {id: p.gid})
    MERGE (dec)-[:ABOUT]->(g)
    """, {"batch": dec_nodes})

    # Link Reviews & Participants in batches
    dec_rev_links = [{"did": d["id"], "rid": rid} for d in decisions for rid in d["reviews"]]
    g.query("""
    UNWIND $batch AS p
    MATCH (dec:Decision {id: p.did}), (r:Review {id: p.rid})
    MERGE (dec)-[:BASED_ON]->(r)
    MERGE (r)-[:SUPPORTS]->(dec)
    """, {"batch": dec_rev_links})

    dec_part_links = [{"did": d["id"], "pid": pid} for d in decisions for pid in d["participants"]]
    g.query("""
    UNWIND $batch AS p
    MATCH (dec:Decision {id: p.did}), (per:Person {id: p.pid})
    MERGE (per)-[:PARTICIPATED_IN]->(dec)
    """, {"batch": dec_part_links})

    # 4. Documents (20 documents)
    documents = [
        {"id": "DOC-001", "kind": "policy_brief", "title": "Cardiology Triple-Antiplatelet Clinical Summary", "decision": "DEC-CARDIO-001"},
        {"id": "DOC-002", "kind": "budget_impact", "title": "Formulary Impact Assessment 2023-Q2", "decision": "DEC-CARDIO-001"},
        {"id": "DOC-003", "kind": "safety_audit", "title": "Bleeding Risk Retrospective Analysis", "decision": "DEC-CARDIO-001"},
        {"id": "DOC-004", "kind": "committee_minutes", "title": "Cardiology Steering Committee Minutes Apr 2023", "decision": "DEC-CARDIO-001"},
    ]
    for i in range(5, 21):
        target_dec = f"DEC-GEN-{((i - 1) % 12) + 4:03d}"
        documents.append({
            "id": f"DOC-{i:03d}",
            "kind": "clinical_summary" if i % 2 == 0 else "meeting_notes",
            "title": f"Supporting Evidence Dossier #{i} (SYN)",
            "decision": target_dec,
        })

    g.query("""
    UNWIND $batch AS p
    MERGE (d:Document {id: p.id})
    SET d.kind = p.kind, d.title = p.title, d.synthetic = true
    WITH d, p
    MATCH (dec:Decision {id: p.decision})
    MERGE (d)-[:SUPPORTS]->(dec)
    """, {"batch": documents})

    # 5. Messages (30 messages)
    messages = [
        {"id": "MSG-001", "channel": "#cardio-steering", "text": "Dr. Sarah Chen: Reviewing the SYN-REV-001 meta-analysis data for the antiplatelet protocol.", "decision": "DEC-CARDIO-001"},
        {"id": "MSG-002", "channel": "#cardio-steering", "text": "Dr. Marcus Vance: Effect sizes appear robust with tight confidence intervals.", "decision": "DEC-CARDIO-001"},
        {"id": "MSG-003", "channel": "#pharmacy-council", "text": "Pharmacy lead confirms stock ready once committee signs off on DEC-CARDIO-001.", "decision": "DEC-CARDIO-001"},
    ]
    for i in range(4, 31):
        target_dec = decisions[i % len(decisions)]["id"]
        messages.append({
            "id": f"MSG-{i:03d}",
            "channel": "#clinical-guidelines" if i % 2 == 0 else "#evidence-review",
            "text": f"Discussion thread message regarding evidence review for {target_dec}.",
            "decision": target_dec,
        })

    now = int(time.time())
    for m in messages:
        m["ts"] = now

    g.query("""
    UNWIND $batch AS p
    MERGE (msg:Message {id: p.id})
    SET msg.channel = p.channel, msg.text = p.text, msg.ts = p.ts, msg.synthetic = true
    WITH msg, p
    MATCH (dec:Decision {id: p.decision})
    MERGE (msg)-[:MENTIONS]->(dec)
    """, {"batch": messages})

    # 6. Tickets (10 tickets)
    tickets = [
        {"id": "TCK-001", "title": "Annual formulary review for DEC-CARDIO-001", "status": "open", "priority": "high", "decision": "DEC-CARDIO-001"},
        {"id": "TCK-002", "title": "Verify adverse event reporting on triple-therapy", "status": "in_progress", "priority": "normal", "decision": "DEC-CARDIO-001"},
    ]
    for i in range(3, 11):
        target_dec = decisions[i % len(decisions)]["id"]
        tickets.append({
            "id": f"TCK-{i:03d}",
            "title": f"Evidence monitoring ticket for {target_dec}",
            "status": "open" if i % 2 == 0 else "resolved",
            "priority": "normal",
            "decision": target_dec,
        })

    g.query("""
    UNWIND $batch AS p
    MERGE (tck:Ticket {id: p.id})
    SET tck.title = p.title, tck.status = p.status, tck.priority = p.priority, tck.synthetic = true
    WITH tck, p
    MATCH (dec:Decision {id: p.decision})
    MERGE (tck)-[:TRACKS]->(dec)
    """, {"batch": tickets})

    print("Synthetic organization successfully seeded and connected to evidence graph!")

if __name__ == "__main__":
    seed_organization()
