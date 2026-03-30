#!/usr/bin/env python3
"""
Add detailed logging to auth endpoint to debug the issue
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database, is_connected
from app.utils import verify_password


async def debug_auth_endpoint():
    """Debug the authentication endpoint step by step"""
    print("=" * 70)
    print("DEBUGGING AUTHENTICATION ENDPOINT")
    print("=" * 70)
    print()

    # Connect to MongoDB
    print("Step 1: Connecting to MongoDB...")
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print(f"   [OK] Connected to {settings.MONGODB_DATABASE}")
    except Exception as e:
        print(f"   [ERROR] Connection failed: {e}")
        return
    print()

    # Check connection status
    print("Step 2: Checking connection status...")
    print(f"   is_connected(): {is_connected()}")
    print()

    # Get database
    print("Step 3: Getting database instance...")
    try:
        db = get_database()
        print("   [OK] Database instance obtained")
    except RuntimeError as e:
        print(f"   [ERROR] {e}")
        print()
        print("   THIS IS THE PROBLEM!")
        print("   The server's get_database() is raising RuntimeError")
        print("   This means MongoDB was not connected when the server started")
        return
    print()

    # Simulate the exact authentication flow from auth.py
    print("Step 4: Simulating _authenticate_against_mongodb()...")
    username = "admin"
    password = "bhiv2024"

    print(f"   Input: username='{username}', password='{password}'")
    print()

    # Step 4a: Find user
    print("   Step 4a: Finding user...")
    try:
        user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})

        if not user:
            print("   [FAIL] User not found")
            print("   This would return None and cause 401 error")
            return

        print(f"   [OK] User found: {user.get('username')}")
    except Exception as e:
        print(f"   [ERROR] Database query failed: {e}")
        return
    print()

    # Step 4b: Get password hash
    print("   Step 4b: Getting password hash...")
    password_hash = user.get("password_hash") or user.get("hashed_password")

    if not password_hash:
        print("   [FAIL] No password hash found")
        print("   This would return None and cause 401 error")
        return

    print(f"   [OK] Password hash found: {password_hash[:20]}...")
    print()

    # Step 4c: Verify password
    print("   Step 4c: Verifying password...")
    try:
        is_valid = verify_password(password, password_hash)

        if not is_valid:
            print("   [FAIL] Password verification failed")
            print("   This would return None and cause 401 error")
            return

        print("   [OK] Password verified successfully")
    except Exception as e:
        print(f"   [ERROR] Verification error: {e}")
        print("   This would return None and cause 401 error")
        return
    print()

    # Step 4d: Return subject
    print("   Step 4d: Returning subject...")
    subject = str(user.get("_id") or user.get("username"))
    print(f"   [OK] Subject: {subject}")
    print()

    print("=" * 70)
    print("[SUCCESS] Authentication flow completed successfully!")
    print("=" * 70)
    print()
    print("If the server is still failing, it means:")
    print("1. Server's MongoDB connection failed at startup")
    print("2. Server's get_database() is raising RuntimeError")
    print("3. Server needs to be restarted")
    print()


if __name__ == "__main__":
    asyncio.run(debug_auth_endpoint())
