#!/usr/bin/env python3
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database

db = next(get_db())

print("=== RL Live Feedback (Database) ===")
feedbacks = db.query(RLLiveFeedback).order_by(desc(RLLiveFeedback.created_at)).limit(5).all()
for fb in feedbacks:
    print(
        f"{fb.created_at} | {fb.feedback_id} | {fb.user_id} | {fb.city} | rating:{fb.rating} | training:{fb.training_triggered}"
    )

print("\n=== Local Log File ===")
log_file = "C:\\Users\\Anmol\\Desktop\\Backend\\data\\logs\\rl_live_feedback.jsonl"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        lines = f.readlines()
        print(f"Total entries: {len(lines)}")
        if lines:
            print("\nAll entries:")
            for line in lines:
                entry = json.loads(line)
                print(
                    f"  {entry['feedback_id']} | {entry['city']} | rating:{entry['rating']} | training:{entry['training_triggered']}"
                )
else:
    print("Log file does not exist")

db.close()
