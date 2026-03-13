#!/usr/bin/env python3
"""Test GET /api/v1/reports/{spec_id} with authentication"""

import json
import os
import subprocess

BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "bhiv2024"
SPEC_ID = "spec_015ba76e"


def authenticate():
    """Get JWT token"""
    print("=" * 80)
    print("Step 1: Authentication")
    print("=" * 80)

    # Create JSON payload file
    payload = {"username": USERNAME, "password": PASSWORD}
    with open("temp_auth.json", "w") as f:
        json.dump(payload, f)

    cmd = f'curl -X POST "{BASE_URL}/api/v1/auth/login" -H "Content-Type: application/json" -d @temp_auth.json -s'

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    # Cleanup
    if os.path.exists("temp_auth.json"):
        os.remove("temp_auth.json")

    try:
        response = json.loads(result.stdout)
        token = response.get("access_token")
        print(f"[+] Authentication successful")
        print(f"[+] Token: {token[:20]}...")
        return token
    except:
        print(f"[-] Authentication failed: {result.stdout}")
        return None


def test_get_report(token):
    """Test GET /api/v1/reports/{spec_id}"""
    print("\n" + "=" * 80)
    print("Step 2: Test GET /api/v1/reports/{spec_id}")
    print("=" * 80)

    cmd = f'curl -X GET "{BASE_URL}/api/v1/reports/{SPEC_ID}" -H "Authorization: Bearer {token}" -H "Content-Type: application/json" -s'

    print(f"\n[*] Request: GET {BASE_URL}/api/v1/reports/{SPEC_ID}")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    try:
        response = json.loads(result.stdout)
        print(f"\n[+] Response received:")
        print(json.dumps(response, indent=2))
        return response
    except:
        print(f"[-] Error: {result.stdout}")
        return None


def check_database():
    """Check database for spec data"""
    print("\n" + "=" * 80)
    print("Step 3: Verify Database Storage")
    print("=" * 80)

    try:
        from app.database_mongodb import engine

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, version, created_at FROM specs WHERE id = :spec_id"), {"spec_id": SPEC_ID}
            )
            spec = result.fetchone()

            if spec:
                print(f"[+] Spec found: ID={spec[0]}, Version={spec[1]}, Created={spec[2]}")
            else:
                print(f"[!] Spec {SPEC_ID} not found")

            result = conn.execute(
                text("SELECT COUNT(*) FROM iterations WHERE spec_id = :spec_id"), {"spec_id": SPEC_ID}
            )
            print(f"[+] Iterations: {result.fetchone()[0]}")

            result = conn.execute(
                text("SELECT COUNT(*) FROM evaluations WHERE spec_id = :spec_id"), {"spec_id": SPEC_ID}
            )
            print(f"[+] Evaluations: {result.fetchone()[0]}")
    except Exception as e:
        print(f"[-] Database check failed: {e}")


def check_local_storage():
    """Check local file storage"""
    print("\n" + "=" * 80)
    print("Step 4: Verify Local Storage")
    print("=" * 80)

    dirs = ["data/reports", "data/previews", "data/geometry_outputs"]

    for directory in dirs:
        if os.path.exists(directory):
            files = [f for f in os.listdir(directory) if SPEC_ID in f]
            print(f"\n[*] {directory}: {len(files)} files")
            for f in files[:3]:
                print(f"    - {f}")
        else:
            print(f"\n[!] {directory}: Not found")


if __name__ == "__main__":
    token = authenticate()
    if token:
        response = test_get_report(token)
        check_database()
        check_local_storage()
        print("\n" + "=" * 80)
        print("Test Complete")
        print("=" * 80)
