#!/usr/bin/env python3
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database

db = next(get_db())

print("=== BHIV Activations (Database) ===")
activations = db.query(BHIVActivation).order_by(desc(BHIVActivation.created_at)).limit(3).all()
for act in activations:
    print(f"{act.created_at} | {act.activation_id} | {act.user_id} | {act.city} | {act.status}")

print("\n=== Audit Logs (Database) ===")
logs = (
    db.query(AuditLog).filter(AuditLog.action == "bhiv_activation").order_by(desc(AuditLog.created_at)).limit(3).all()
)
for log in logs:
    print(f"{log.created_at} | {log.action} | {log.resource_id} | {log.status}")

print("\n=== Local Log File ===")
log_file = "C:\\Users\\Anmol\\Desktop\\Backend\\data\\logs\\bhiv_assistant.jsonl"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        lines = f.readlines()
        print(f"Total entries: {len(lines)}")
        if lines:
            print("\nLast 2 entries:")
            for line in lines[-2:]:
                entry = json.loads(line)
                print(f"  {entry['activation_id']} | {entry['user_id']} | {entry['city']} | {entry['status']}")
        else:
            print("Log file is empty")
else:
    print("Log file does not exist")

db.close()
