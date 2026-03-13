#!/usr/bin/env python3
"""
Check for specific BHIV integrated design spec
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database_mongodb import SessionLocal


def check_integrated_spec():
    db = SessionLocal()
    try:
        # Look for the specific spec ID from the response
        spec = db.query(Spec).filter(Spec.id == "spec_4778f4a3").first()

        if spec:
            print("=== INTEGRATED DESIGN SPEC FOUND ===")
            print(f"ID: {spec.id}")
            print(f"User ID: {spec.user_id}")
            print(f"Project ID: {spec.project_id}")
            print(f"Prompt: {spec.prompt}")
            print(f"City: {spec.city}")
            print(f"Design Type: {spec.design_type}")
            print(f"Status: {spec.status}")
            print(f"Estimated Cost: {spec.estimated_cost}")
            print(f"Created: {spec.created_at}")
            print(f"Spec JSON Preview: {str(spec.spec_json)[:200]}...")
        else:
            print("Spec spec_4778f4a3 not found in database")

        # Also check latest specs
        latest_specs = db.query(Spec).order_by(Spec.created_at.desc()).limit(3).all()
        print(f"\n=== LATEST 3 SPECS ===")
        for spec in latest_specs:
            print(f"{spec.id} - {spec.created_at}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    check_integrated_spec()
