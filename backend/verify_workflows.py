#!/usr/bin/env python3
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database

db = next(get_db())

print("=== Workflow Runs (Database) ===")
workflows = db.query(WorkflowRun).order_by(desc(WorkflowRun.created_at)).limit(5).all()
for wf in workflows:
    print(f"{wf.created_at} | {wf.flow_run_id} | {wf.flow_name} | {wf.status}")

print("\n=== Local Log File ===")
log_file = "C:\\Users\\Anmol\\Desktop\\Backend\\data\\logs\\workflow_executions.jsonl"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        lines = f.readlines()
        print(f"Total entries: {len(lines)}")
        if lines:
            print("\nAll entries:")
            for line in lines:
                entry = json.loads(line)
                city = entry.get("city", "N/A")
                print(f"  {entry['workflow_id']} | {entry['workflow_type']} | {city} | {entry['status']}")
else:
    print("Log file does not exist")

db.close()
