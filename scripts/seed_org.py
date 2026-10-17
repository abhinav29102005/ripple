"""
Deterministic synthetic organization generator for Ripple (Track 03 Company Brain).
Creates 12 people, 3 committees, 15 decisions, 20 documents, 30 messages, 10 tickets
interconnected with synthetic reviews and guidelines.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import random
from graph import graph_manager

PEOPLE = [
    {"id": "PER-001", "name": "Dr. Sarah Chen", "role": "Chief Medical Officer & Chair of Cardiology", "topic": "Cardiology"},
    {"id": "PER-002", "name": "Dr. Marcus Vance", "role": "Senior Clinical Methodologist", "topic": "Cardiology"},
    {"id": "PER-003", "name": "Dr. Elena Rostova", "role": "Head of Oncology Therapeutics", "topic": "Oncology"},
    {"id": "PER-004", "name": "Dr. James Wilson", "role": "Director of Evidence Synthesis", "topic": "Methods"},
    {"id": "PER-005", "name": "Dr. Priya Patel", "role": "Clinical Quality Lead", "topic": "Cardiology"},
    {"id": "PER-006", "name": "Dr. Robert Lang", "role": "Lead Biostatistician", "topic": "Methods"},
    {"id": "PER-007", "name": "Dr. Fatima Al-Mansoor", "role": "Oncology Safety Lead", "topic": "Oncology"},
    {"id": "PER-008", "name": "Dr. Alexander Kim", "role": "Cardiovascular Research Fellow", "topic": "Cardiology"},
    {"id": "PER-009", "name": "Dr. Hannah Schmidt", "role": "Systematic Reviewer", "topic": "Methods"},
    {"id": "PER-010", "name": "Dr. Carlos Ortiz", "role": "Clinical Pharmacology Specialist", "topic": "Cardiology"},
    {"id": "PER-011", "name": "Dr. David Brooks", "role": "Clinical Guidelines Coordinator", "topic": "Oncology"},
    {"id": "PER-012", "name": "Dr. Maya Lin", "role": "Audit & Compliance Officer", "topic": "Methods"},
]

COMMITTEES = [
    {"id": "COM-CARDIO", "name": "Cardiology Steering Committee", "lead": "PER-001", "members": ["PER-001", "PER-002", "PER-005", "PER-008", "PER-010"]},
    {"id": "COM-ONCO", "name": "Oncology Practice Committee", "lead": "PER-003", "members": ["PER-003", "PER-007", "PER-011"]},
    {"id": "COM-METHODS", "name": "Clinical Evidence & Methods Council", "lead": "PER-004", "members": ["PER-004", "PER-006", "PER-009", "PER-012"]},
]

def seed_organization(seed: int = 42):
    random.seed(seed)
    g = graph_manager.init_knowledge_schema()
    print("Seeding synthetic organization structure (People, Committees, Decisions, Docs, Chats)...")

    # 1. People
    g.query("""
    UNWIND $people AS p
    MERGE (n:Person {id: p.id})
    SET n.name = p.name, n.role = p.role, n.synthetic = true
    """, {"people": PEOPLE})

    # Link people to Topics for who-knows queries
    for p in PEOPLE:
        g.query("""
        MATCH (person:Person {id: $pid}), (top:Topic {name: $topic})
        MERGE (person)-[:AUTHORED]->(top)
        """, {"pid": p["id"], "topic": p["topic"]})

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

    # Planted Authorship: Dr. Sarah Chen authored SYN-REV-001 (crucial deliberate pattern)
    g.query("""
    MATCH (p:Person {id: 'PER-001'}), (rev:Review {id: 'SYN-REV-001'})
    MERGE (p)-[:AUTHORED]->(rev)
    """)
    g.query("""
    MATCH (p:Person {id: 'PER-003'}), (rev:Review {id: 'SYN-REV-002'})
    MERGE (p)-[:AUTHORED]->(rev)
    """)

    # 3. Decisions (15 decisions)
    # Planted Decision 1: DEC-CARDIO-001 based on SYN-REV-001 & SYN-REV-002
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

    # Add remaining decisions up to 15
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

    for d in decisions:
        g.query("""
        MERGE (dec:Decision {id: $id})
        SET dec.title = $title, dec.date = $date, dec.status = $status, dec.synthetic = true
        WITH dec
        MATCH (c:Committee {id: $com_id})
        MERGE (dec)-[:MADE_BY]->(c)
        WITH dec
        MATCH (g:Guideline {id: $gid})
        MERGE (dec)-[:ABOUT]->(g)
        """, {"id": d["id"], "title": d["title"], "date": d["date"], "status": d["status"], "com_id": d["committee"], "gid": d["guideline"]})

        # Link Reviews
        for rid in d["reviews"]:
            g.query("""
            MATCH (dec:Decision {id: $did}), (r:Review {id: $rid})
            MERGE (dec)-[:BASED_ON]->(r)
            """, {"did": d["id"], "rid": rid})

        # Link Participants
        for pid in d["participants"]:
            g.query("""
            MATCH (dec:Decision {id: $did}), (p:Person {id: $pid})
            MERGE (p)-[:PARTICIPATED_IN]->(dec)
            """, {"did": d["id"], "pid": pid})

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

    for doc in documents:
        g.query("""
        MERGE (d:Document {id: $id})
        SET d.kind = $kind, d.title = $title, d.synthetic = true
        WITH d
        MATCH (dec:Decision {id: $dec_id})
        MERGE (d)-[:SUPPORTS]->(dec)
        """, {"id": doc["id"], "kind": doc["kind"], "title": doc["title"], "dec_id": doc["decision"]})

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
        g.query("""
        MERGE (msg:Message {id: $id})
        SET msg.channel = $channel, msg.text = $text, msg.ts = $ts, msg.synthetic = true
        WITH msg
        MATCH (dec:Decision {id: $dec_id})
        MERGE (msg)-[:MENTIONS]->(dec)
        """, {"id": m["id"], "channel": m["channel"], "text": m["text"], "ts": now, "dec_id": m["decision"]})

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

    for t in tickets:
        g.query("""
        MERGE (tck:Ticket {id: $id})
        SET tck.title = $title, tck.status = $status, tck.priority = $priority, tck.synthetic = true
        WITH tck
        MATCH (dec:Decision {id: $dec_id})
        MERGE (tck)-[:TRACKS]->(dec)
        """, {"id": t["id"], "title": t["title"], "status": t["status"], "priority": t["priority"], "dec_id": t["decision"]})

    print("Synthetic organization successfully seeded and connected to evidence graph!")

if __name__ == "__main__":
    seed_organization()
