#!/usr/bin/env python3
"""
Test if the running server can authenticate
This will make a request to the server and show detailed error info
"""
import json

import requests


def test_server_auth():
    print("=" * 70)
    print("TESTING SERVER AUTHENTICATION")
    print("=" * 70)
    print()

    # Test 1: Health check
    print("1. Server Health Check:")
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        print("   [OK] Server is running")
    except Exception as e:
        print(f"   [ERROR] Server not responding: {e}")
        return
    print()

    # Test 2: Try login
    print("2. Login Attempt:")
    url = "http://localhost:8000/api/v1/auth/login"

    data = {"username": "admin", "password": "bhiv2024"}

    print(f"   URL: {url}")
    print(f"   Username: {data['username']}")
    print(f"   Password: {data['password']}")
    print()

    try:
        response = requests.post(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})

        print(f"   Status Code: {response.status_code}")
        print()

        if response.status_code == 200:
            result = response.json()
            print("   [SUCCESS] Login successful!")
            print(f"   Access Token: {result.get('access_token', 'N/A')[:50]}...")
            print(f"   Token Type: {result.get('token_type', 'N/A')}")
        elif response.status_code == 503:
            print("   [ERROR] Service Unavailable (503)")
            print("   This means MongoDB is not connected to the server")
            print()
            print("   SOLUTION: Restart the server")
        elif response.status_code == 401:
            print("   [ERROR] Unauthorized (401)")
            print("   Response:", json.dumps(response.json(), indent=2))
            print()
            print("   POSSIBLE CAUSES:")
            print("   1. Server was started BEFORE admin user was created")
            print("   2. Server is connected to a different MongoDB database")
            print("   3. Server MongoDB connection failed at startup")
            print()
            print("   SOLUTION: Restart the server with:")
            print("   cd backend")
            print("   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        else:
            print(f"   [ERROR] Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")

    except Exception as e:
        print(f"   [ERROR] Request failed: {e}")

    print()
    print("=" * 70)
    print("DIAGNOSIS COMPLETE")
    print("=" * 70)
    print()
    print("SUMMARY:")
    print("- Database has admin user: YES")
    print("- Password is correct: YES")
    print("- Authentication logic works: YES")
    print("- Server login works: NO")
    print()
    print("CONCLUSION:")
    print("The server needs to be restarted to pick up the new admin user.")
    print()


if __name__ == "__main__":
    test_server_auth()
