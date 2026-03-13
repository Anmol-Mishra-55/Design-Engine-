#!/usr/bin/env python3
"""
Check for workflow spec
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_workflow_spec():
    db = SessionLocal()
    try:
        # Look for the workflow spec
        spec = db.query(Spec).filter(Spec.id == "spec_cf30a57b").first()

        if spec:
            print("=== WORKFLOW SPEC FOUND ===")
            print(f"ID: {spec.id}")
            print(f"User ID: {spec.user_id}")
            print(f"Project ID: {spec.project_id}")
            print(f"Prompt: {spec.prompt}")
            print(f"City: {spec.city}")
            print(f"Status: {spec.status}")
            print(f"Created: {spec.created_at}")
        else:
            print("Workflow spec spec_cf30a57b not found in database")

        # Check all specs count
        total_specs = db.query(Spec).count()
        print(f"\nTotal specs in database: {total_specs}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_workflow_spec()
