#!/usr/bin/env python3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database

db = next(get_db())

# Check audit logs for BHIV activation
print("=== Recent Audit Logs ===")
logs = db.query(AuditLog).order_by(desc(AuditLog.created_at)).limit(5).all()
for log in logs:
    print(f"{log.created_at} | {log.action} | {log.resource_type} | {log.status}")

# Check workflow runs
print("\n=== Recent Workflow Runs ===")
workflows = db.query(WorkflowRun).order_by(desc(WorkflowRun.created_at)).limit(5).all()
for wf in workflows:
    print(f"{wf.created_at} | {wf.flow_name} | {wf.status}")

# Check local log file
log_file = "C:\\Users\\Anmol\\Desktop\\Backend\\data\\logs\\bhiv_assistant.jsonl"
print(f"\n=== Local Log File: {log_file} ===")
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        lines = f.readlines()
        print(f"Total entries: {len(lines)}")
        if lines:
            print("Last 3 entries:")
            for line in lines[-3:]:
                print(line.strip())
        else:
            print("Log file is empty")
else:
    print("Log file does not exist")
