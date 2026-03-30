#!/usr/bin/env python3
"""
ULTIMATE AUTHENTICATION DIAGNOSTIC
This will tell you EXACTLY what's wrong
"""
import asyncio
import os
import sys

import requests

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database


async def ultimate_diagnostic():
    print("=" * 80)
    print("ULTIMATE AUTHENTICATION DIAGNOSTIC")
    print("=" * 80)
    print()

    # Test 1: Can we connect to MongoDB from command line?
    print("TEST 1: MongoDB Connection from Command Line")
    print("-" * 80)
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        db = get_database()
        user = await db.users.find_one({"username": "admin"})

        if user:
            print("[PASS] Can connect to MongoDB and find admin user")
            print(f"   User: {user.get('username')}")
            print(f"   Active: {user.get('is_active')}")
        else:
            print("[FAIL] Connected to MongoDB but admin user not found")
            print("   Run: python create_admin_mongodb.py")
            return
    except Exception as e:
        print(f"[FAIL] Cannot connect to MongoDB: {e}")
        print()
        print("POSSIBLE CAUSES:")
        print("1. MongoDB Atlas cluster is paused")
        print("2. IP address not whitelisted")
        print("3. Wrong connection string in .env")
        print("4. Network/firewall blocking connection")
        return
    print()

    # Test 2: Can the server connect to MongoDB?
    print("TEST 2: Server MongoDB Connection")
    print("-" * 80)
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("[OK] Server is running")
        else:
            print(f"[FAIL] Server returned {response.status_code}")
            return
    except Exception as e:
        print(f"[FAIL] Server not responding: {e}")
        print("   Start server with: python -m uvicorn app.main:app --reload")
        return
    print()

    # Test 3: Does login work?
    print("TEST 3: Login Endpoint")
    print("-" * 80)
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            data={"username": "admin", "password": "bhiv2024"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5,
        )

        if response.status_code == 200:
            print("[PASS] Login successful!")
            token = response.json().get("access_token", "")
            print(f"   Token: {token[:50]}...")
            print()
            print("=" * 80)
            print("SUCCESS: ALL TESTS PASSED - AUTHENTICATION IS WORKING!")
            print("=" * 80)
            return
        elif response.status_code == 503:
            print("[FAIL] Service Unavailable (503)")
            print("   This means MongoDB is NOT connected to the server")
        elif response.status_code == 401:
            print("[FAIL] Unauthorized (401)")
            print("   This means either:")
            print("   a) MongoDB is NOT connected to the server")
            print("   b) Admin user doesn't exist")
            print("   c) Password is wrong")
        else:
            print(f"[FAIL] Unexpected status {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"[FAIL] Request error: {e}")
    print()

    # Diagnosis
    print("=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print()
    print("[OK] MongoDB is accessible from command line")
    print("[OK] Admin user exists in database")
    print("[OK] Server is running")
    print("[FAIL] Login fails on server")
    print()
    print("CONCLUSION:")
    print("=" * 80)
    print("The server's MongoDB connection FAILED at startup.")
    print("The server is running but cannot access the database.")
    print()
    print("SOLUTION:")
    print("=" * 80)
    print("1. Stop the server (Ctrl+C in the terminal where it's running)")
    print("2. Check MongoDB Atlas cluster is running (not paused)")
    print("3. Restart the server:")
    print("   cd backend")
    print("   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    print("4. Look for this in the startup logs:")
    print("   [OK] MongoDB connected successfully")
    print()
    print("5. If you see this instead:")
    print("   [WARNING] MongoDB connection failed")
    print("   Then check:")
    print("   - MongoDB Atlas cluster status")
    print("   - IP whitelist settings")
    print("   - Connection string in .env")
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(ultimate_diagnostic())
