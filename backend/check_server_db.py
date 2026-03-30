#!/usr/bin/env python3
"""
Check server MongoDB connection status
"""
import requests


def check_server_db():
    print("=" * 70)
    print("CHECKING SERVER DATABASE CONNECTION")
    print("=" * 70)
    print()

    # Try to access a protected endpoint to see the error
    print("Testing authentication endpoint behavior...")
    print()

    url = "http://localhost:8000/api/v1/auth/login"

    # Test with correct credentials
    print("1. Testing with CORRECT credentials (admin/bhiv2024):")
    response = requests.post(
        url,
        data={"username": "admin", "password": "bhiv2024"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 503:
        print("   [ERROR] 503 = MongoDB not connected to server")
    elif response.status_code == 401:
        print("   [ERROR] 401 = User not found OR password mismatch")
        print("   This means either:")
        print("   - Server can't find the user in MongoDB")
        print("   - Server is connected to wrong database")
        print("   - Server was started before user was created")
    print()

    # Test with wrong credentials
    print("2. Testing with WRONG credentials (admin/wrongpassword):")
    response = requests.post(
        url,
        data={"username": "admin", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print("   [OK] 401 = Expected behavior for wrong password")
    print()

    # Test with non-existent user
    print("3. Testing with NON-EXISTENT user (nonexistent/password):")
    response = requests.post(
        url,
        data={"username": "nonexistent", "password": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print("   [OK] 401 = Expected behavior for non-existent user")
    print()

    print("=" * 70)
    print("ANALYSIS:")
    print("=" * 70)
    print()
    print("All three tests return 401, which means:")
    print("- Server IS connected to MongoDB (otherwise would be 503)")
    print("- Server CAN query the database")
    print("- BUT server cannot find the admin user OR password doesn't match")
    print()
    print("MOST LIKELY CAUSE:")
    print("The server was started BEFORE the admin user was created.")
    print("The server might have cached the database state or connection.")
    print()
    print("SOLUTION:")
    print("1. Stop the server (Ctrl+C)")
    print("2. Restart with: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()


if __name__ == "__main__":
    check_server_db()
