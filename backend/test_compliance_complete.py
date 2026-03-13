#!/usr/bin/env python3
"""
Complete test for compliance endpoints
"""
import os
import sys

sys.path.append(".")

import json

import requests
from app.database_mongodb import get_database


def test_compliance_endpoints():
    """Test all compliance endpoints"""
    print("Testing Compliance Endpoints")
    print("=" * 40)

    base_url = "http://localhost:8000/api/v1/compliance"
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyIiwiZXhwIjoxNzY2MjQyMDc4fQ.AK8tllFORyGleQV7P24AtPaMl1HKCgxD1BV9O5azIJo",
        "Content-Type": "application/json",
    }

    # 1. Test endpoint
    print("1. Testing /test endpoint...")
    try:
        response = requests.get(f"{base_url}/test", headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {data}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

    # 2. Regulations endpoint
    print("\n2. Testing /regulations endpoint...")
    try:
        response = requests.get(f"{base_url}/regulations", headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Regulations: {len(data.get('regulations', []))}")
            for reg in data.get("regulations", [])[:2]:
                print(f"     - {reg['id']}: {reg['name']}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

    # 3. Run case endpoint (Mumbai)
    print("\n3. Testing /run_case endpoint...")
    try:
        case_data = {
            "project_id": "test_compliance_project",
            "case_id": "test_case_001",
            "city": "Mumbai",
            "parameters": {"plot_size": 800, "location": "urban", "road_width": 15},
        }

        response = requests.post(f"{base_url}/run_case", headers=headers, json=case_data, timeout=30)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Project: {data.get('project_id')}")
            print(f"   City: {data.get('city')}")
            print(f"   Rules Applied: {len(data.get('rules_applied', []))}")
            print(f"   Confidence: {data.get('confidence_score')}")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

    # 4. Check database storage
    print("\n4. Checking database storage...")
    try:
        db = next(get_db())
        compliance_checks = db.query(ComplianceCheck).all()
        print(f"   Compliance checks in database: {len(compliance_checks)}")
        for check in compliance_checks[:3]:
            print(f"     - {check.id}: {check.city} ({check.status})")
        db.close()
    except Exception as e:
        print(f"   Database error: {e}")

    # 5. Check local storage
    print("\n5. Checking local storage...")
    storage_dirs = ["data/compliance", "data/pdfs", "temp"]
    for dir_path in storage_dirs:
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            print(f"   {dir_path}: {len(files)} files")
            for file in files[:2]:
                print(f"     - {file}")
        else:
            print(f"   {dir_path}: does not exist")

    return True


if __name__ == "__main__":
    success = test_compliance_endpoints()
    if success:
        print("\nCompliance endpoints testing completed!")
    else:
        print("\nCompliance endpoints testing failed!")
