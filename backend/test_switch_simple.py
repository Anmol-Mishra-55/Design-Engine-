#!/usr/bin/env python3
"""
Simple switch storage test
"""
import sys

sys.path.append(".")

from app.spec_storage import get_spec, list_specs


def test_switch_simple():
    """Simple test of switch storage"""
    print("Testing Switch Storage")
    print("=" * 40)

    # Check in-memory storage
    stored_specs = list_specs()
    print(f"Specs in memory storage: {len(stored_specs)}")

    if stored_specs:
        for spec_id, spec_data in stored_specs.items():
            print(f"Spec ID: {spec_id}")
            print(f"Version: {spec_data.get('spec_version', 1)}")

            objects = spec_data.get("spec_json", {}).get("objects", [])
            print(f"Objects: {len(objects)}")

            for obj in objects[:3]:
                print(f"  {obj['id']}: color={obj.get('color_hex', 'N/A')}")
    else:
        print("No specs found in memory storage")
        print("This is expected if server restarted - specs are stored in database")

    # Test database storage
    try:
        from app.database_mongodb import get_database

        db = next(get_db())
        specs = db.query(Spec).all()
        print(f"Specs in database: {len(specs)}")

        for spec in specs:
            print(f"DB Spec: {spec.id}, Version: {spec.version}")
            objects = spec.spec_json.get("objects", [])
            for obj in objects[:2]:
                print(f"  {obj['id']}: color={obj.get('color_hex', 'N/A')}")

        db.close()

    except Exception as e:
        print(f"Database check failed: {e}")

    return True


if __name__ == "__main__":
    test_switch_simple()
