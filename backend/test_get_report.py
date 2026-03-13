#!/usr/bin/env python3
"""Test GET /api/v1/reports/{spec_id} endpoint"""

import json
import os
import subprocess
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
SPEC_ID = "spec_015ba76e"  # Use existing spec from README
TOKEN = "test_token_admin"  # Default test token


def run_curl_test():
    """Test the GET /api/v1/reports/{spec_id} endpoint using curl"""

    print("=" * 80)
    print("Testing GET /api/v1/reports/{spec_id} Endpoint")
    print("=" * 80)

    # Construct curl command
    curl_cmd = [
        "curl",
        "-X",
        "GET",
        f"{BASE_URL}/api/v1/reports/{SPEC_ID}",
        "-H",
        f"Authorization: Bearer {TOKEN}",
        "-H",
        "Content-Type: application/json",
        "-w",
        "\\n\\nHTTP Status: %{http_code}\\n",
        "-s",
    ]

    print(f"\n[*] Request:")
    print(f"   Method: GET")
    print(f"   URL: {BASE_URL}/api/v1/reports/{SPEC_ID}")
    print(f"   Headers: Authorization: Bearer {TOKEN}")

    try:
        # Execute curl command
        result = subprocess.run(curl_cmd, capture_output=True, text=True, shell=True)

        print(f"\n[+] Response:")
        print(result.stdout)

        # Parse JSON response
        try:
            response_lines = result.stdout.split("\n")
            json_response = None
            for line in response_lines:
                if line.strip().startswith("{"):
                    json_response = json.loads(line)
                    break

            if json_response:
                print(f"\n[*] Parsed Response:")
                print(json.dumps(json_response, indent=2))

                # Verify response structure
                print(f"\n[*] Verification:")
                print(f"   [+] report_id: {json_response.get('report_id')}")
                print(f"   [+] spec_id: {json_response.get('data', {}).get('spec_id')}")
                print(f"   [+] version: {json_response.get('data', {}).get('version')}")
                print(f"   [+] iterations count: {len(json_response.get('iterations', []))}")
                print(f"   [+] evaluations count: {len(json_response.get('evaluations', []))}")
                print(f"   [+] preview_urls count: {len(json_response.get('preview_urls', []))}")

                return json_response
        except json.JSONDecodeError as e:
            print(f"   [!] Could not parse JSON: {e}")

    except Exception as e:
        print(f"\n[-] Error: {e}")
        return None


def check_database_storage():
    """Check if report data exists in database"""
    print(f"\n" + "=" * 80)
    print("Checking Database Storage")
    print("=" * 80)

    try:
        from app.database_mongodb import engine

        with engine.connect() as conn:
            # Check Spec table
            result = conn.execute(
                text("SELECT id, version, created_at FROM specs WHERE id = :spec_id"), {"spec_id": SPEC_ID}
            )
            spec = result.fetchone()

            if spec:
                print(f"\n[+] Spec found in database:")
                print(f"   ID: {spec[0]}")
                print(f"   Version: {spec[1]}")
                print(f"   Created: {spec[2]}")
            else:
                print(f"\n[!] Spec {SPEC_ID} not found in database")

            # Check Iterations
            result = conn.execute(
                text("SELECT COUNT(*) FROM iterations WHERE spec_id = :spec_id"), {"spec_id": SPEC_ID}
            )
            iteration_count = result.fetchone()[0]
            print(f"\n[+] Iterations in database: {iteration_count}")

            # Check Evaluations
            result = conn.execute(
                text("SELECT COUNT(*) FROM evaluations WHERE spec_id = :spec_id"), {"spec_id": SPEC_ID}
            )
            eval_count = result.fetchone()[0]
            print(f"[+] Evaluations in database: {eval_count}")

    except Exception as e:
        print(f"\n[-] Database check failed: {e}")


def check_local_storage():
    """Check if report data exists in local storage"""
    print(f"\n" + "=" * 80)
    print("Checking Local Storage")
    print("=" * 80)

    # Check data directories
    directories = ["data/reports", "data/previews", "data/geometry_outputs", "data/uploads"]

    for directory in directories:
        if os.path.exists(directory):
            files = os.listdir(directory)
            related_files = [f for f in files if SPEC_ID in f]

            print(f"\n[*] {directory}:")
            if related_files:
                print(f"   [+] Found {len(related_files)} related files:")
                for file in related_files[:5]:  # Show first 5
                    file_path = os.path.join(directory, file)
                    size = os.path.getsize(file_path)
                    print(f"      - {file} ({size} bytes)")
            else:
                print(f"   [!] No files found for {SPEC_ID}")
        else:
            print(f"\n[*] {directory}: [!] Directory does not exist")


if __name__ == "__main__":
    # Run curl test
    response = run_curl_test()

    # Check database
    check_database_storage()

    # Check local storage
    check_local_storage()

    print(f"\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)
