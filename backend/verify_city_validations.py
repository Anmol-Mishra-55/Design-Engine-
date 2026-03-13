#!/usr/bin/env python3
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import get_database

db = next(get_db())

print("=== City Validations (Database) ===")
validations = db.query(CityValidation).order_by(desc(CityValidation.created_at)).limit(5).all()
for val in validations:
    print(f"{val.created_at} | {val.city} | {val.location} | plot:{val.plot_size} | {val.validation_status}")

print("\n=== Local Log File ===")
log_file = "C:\\Users\\Anmol\\Desktop\\Backend\\data\\logs\\city_validations.jsonl"
if os.path.exists(log_file):
    with open(log_file, "r") as f:
        lines = f.readlines()
        print(f"Total entries: {len(lines)}")
        if lines:
            print("\nAll entries:")
            for line in lines:
                entry = json.loads(line)
                print(f"  {entry['city']} | {entry['validation_status']} | plot:{entry['parameters']['plot_size']}")
else:
    print("Log file does not exist")

db.close()
