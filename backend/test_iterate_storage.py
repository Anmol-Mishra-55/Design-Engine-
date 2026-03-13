#!/usr/bin/env python3
"""
Test iterate endpoint storage verification
"""
import os
import sys

sys.path.append(".")

import json
from datetime import datetime, timezone

from app.database_mongodb import get_database


def test_iterate_storage():
    """Test if iterate endpoint stored data correctly"""
    print("Testing Iterate Storage")
    print("=" * 40)

    try:
        db = next(get_db())

        # 1. Check iterations in database
        iterations = db.query(Iteration).all()
        print(f"Total iterations in database: {len(iterations)}")

        if iterations:
            for iter in iterations:
                print(f"  ID: {iter.id}")
                print(f"  Spec: {iter.spec_id}")
                print(f"  User: {iter.user_id}")
                print(f"  Query: {iter.query}")
                print(f"  Created: {iter.created_at}")
                print(f"  Cost Delta: {iter.cost_delta}")
                print(f"  New Total: {iter.new_total_cost}")
                print("-" * 30)
        else:
            print("  No iterations found in database")

        # 2. Check specs table for version updates
        specs = db.query(Spec).all()
        print(f"Total specs in database: {len(specs)}")

        for spec in specs:
            print(f"  Spec ID: {spec.id}")
            print(f"  Version: {spec.version}")
            print(f"  Updated: {spec.updated_at}")
            print(f"  Cost: {spec.estimated_cost}")
            print("-" * 30)

        # 3. Check in-memory storage
        try:
            from app.spec_storage import get_all_specs

            stored_specs = get_all_specs()
            print(f"Specs in memory storage: {len(stored_specs)}")

            for spec_id, spec_data in stored_specs.items():
                print(f"  Memory Spec: {spec_id}")
                print(f"  Version: {spec_data.get('spec_version', 1)}")
                print(f"  Updated: {spec_data.get('updated_at', 'N/A')}")
                print("-" * 30)

        except Exception as e:
            print(f"Memory storage check failed: {e}")

        # 4. Check for local iteration files
        iter_dirs = ["data/iterations", "data/specs", "data/geometry_outputs"]
        for dir_path in iter_dirs:
            if os.path.exists(dir_path):
                files = os.listdir(dir_path)
                print(f"Files in {dir_path}: {len(files)}")
                for file in files[:5]:  # Show first 5 files
                    print(f"  {file}")
            else:
                print(f"Directory {dir_path} does not exist")

        db.close()
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    success = test_iterate_storage()
    if success:
        print("\nStorage verification completed!")
    else:
        print("\nStorage verification failed!")
