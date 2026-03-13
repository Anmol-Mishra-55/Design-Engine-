#!/usr/bin/env python3
"""
Test user history endpoint
"""
import sys

sys.path.append(".")

import json
from datetime import datetime, timezone

import requests
from app.database_mongodb import get_database


def test_user_history():
    """Test user history endpoint with real data"""
    print("Testing User History Endpoint")
    print("=" * 40)

    db = next(get_db())

    # 1. Create test specs for user 'user'
    test_specs = []
    for i in range(3):
        spec = Spec(
            id=f"spec_history_test_{i+1}",
            user_id="user",  # Match JWT token
            prompt=f"History test design {i+1}",
            city="Mumbai",
            spec_json={
                "objects": [{"id": f"obj_{i}", "type": "room", "material": "wood"}],
                "design_type": "house",
                "estimated_cost": {"total": 150000 * (i + 1), "currency": "INR"},
            },
            estimated_cost=150000.0 * (i + 1),
            version=1,
            project_id=f"project_{i+1}" if i == 0 else None,  # Only first spec has project
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(spec)
        test_specs.append(spec)
        print(f"Created spec: {spec.id}")

    db.commit()

    # 2. Verify specs exist
    user_specs = db.query(Spec).filter(Spec.user_id == "user").all()
    print(f'Total specs for user "user": {len(user_specs)}')

    # 3. Test API endpoint directly
    try:
        url = "http://localhost:8000/api/v1/history"
        headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIiwiZXhwIjoxNzY2MjQyMDc4fQ.AK8tllFORyGleQV7P24AtPaMl1HKCgxD1BV9O5azIJo"
        }

        # Test without filters
        response = requests.get(f"{url}?limit=5", headers=headers, timeout=10)
        print(f"API Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"Error: {response.text}")

        # Test with project filter
        response2 = requests.get(f"{url}?project_id=project_1", headers=headers, timeout=10)
        print(f"Project filter response: {response2.status_code}")
        if response2.status_code == 200:
            data2 = response2.json()
            print(f'Project filtered specs: {data2.get("total_specs", 0)}')

    except Exception as e:
        print(f"API test failed: {e}")

    db.close()
    return True


if __name__ == "__main__":
    test_user_history()
