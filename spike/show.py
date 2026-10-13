"""Print the notes and proposal of a result file for manual review. Usage: show.py llm-<label>.json"""

import json
import sys

with open(sys.argv[1]) as f:
    r = json.load(f)
n = r["notes"]
print("MODEL", r["model"], "| client:", n["client"])
for k in ["client_context", "problem", "goals", "requirements", "constraints", "budget_or_deadlines", "risks"]:
    print(f"\n[{k}]")
    for it in n[k]:
        print(f" - {it['text']}  ids={it['segment_ids']}")
print("\n[open_questions]")
for q in n["open_questions"]:
    print(" -", q)
p = r.get("proposal")
if p:
    print("\n=== PROPOSAL ===")
    print("SUMMARY:", p["summary"])
    print("PROBLEM:", p["problem_understanding"])
    for k in ("scope", "deliverables", "out_of_scope"):
        print(f"\n[{k}]")
        for it in p[k]:
            print(f" - {it['text']}  ids={it['segment_ids']} assumption={it['assumption']}")
    print("\nTIMELINE:", p["timeline"])
    print("OPEN QUESTIONS:", *p["open_questions"], sep="\n - ")
    print("\nINVESTMENT:", p["investment"])
    print("\nTERMS:", p["terms"])
