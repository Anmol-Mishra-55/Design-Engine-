#!/usr/bin/env python3
"""Test the improved GET /api/v1/reports/{spec_id} endpoint"""

import json

import requests

BASE_URL = "http://localhost:8000"

# First, login to get a valid token
print("Logging in...")
login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"username": "admin", "password": "bhiv2024"})

if login_response.status_code != 200:
    print("Login failed. Make sure the server is running and credentials are correct.")
    exit(1)

token = login_response.json()["access_token"]
print(f"Login successful! Token: {token[:20]}...\n")

# Test with invalid spec_id
print("=" * 80)
print("Testing GET /api/v1/reports/{spec_id} with INVALID spec_id")
print("=" * 80)

response = requests.get(f"{BASE_URL}/api/v1/reports/spec_test123", headers={"Authorization": f"Bearer {token}"})

print(f"\nStatus Code: {response.status_code}")
print(f"\nResponse:")
print(json.dumps(response.json(), indent=2))

# Test with valid spec_id
print("\n" + "=" * 80)
print("Testing GET /api/v1/reports/{spec_id} with VALID spec_id")
print("=" * 80)

# Get a valid spec_id from the database
from app.database_mongodb import SessionLocal

db = SessionLocal()
valid_spec = db.query(Spec).first()
db.close()

if valid_spec:
    print(f"\nUsing valid spec_id: {valid_spec.id}")

    response = requests.get(f"{BASE_URL}/api/v1/reports/{valid_spec.id}", headers={"Authorization": f"Bearer {token}"})

    print(f"\nStatus Code: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"\n[SUCCESS] Report retrieved:")
        print(f"   - Report ID: {data.get('report_id')}")
        print(f"   - Spec ID: {data.get('data', {}).get('spec_id')}")
        print(f"   - Version: {data.get('data', {}).get('version')}")
        print(f"   - City: {data.get('data', {}).get('city')}")
        print(f"   - Iterations: {len(data.get('iterations', []))}")
        print(f"   - Evaluations: {len(data.get('evaluations', []))}")
        print(f"   - Compliance Checks: {len(data.get('compliance_checks', []))}")
    else:
        print(f"\n[ERROR]:")
        print(json.dumps(response.json(), indent=2))
else:
    print("\n[ERROR] No specs found in database. Create one first using POST /api/v1/generate")

print("\n" + "=" * 80)
print("Test Complete")
print("=" * 80)
