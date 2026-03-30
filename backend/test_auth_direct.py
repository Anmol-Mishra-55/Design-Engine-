#!/usr/bin/env python3
"""
Direct test of authentication against running server
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database
from app.utils import verify_password


async def test_auth_directly():
    """Test authentication directly against MongoDB"""
    print("=" * 70)
    print("DIRECT AUTHENTICATION TEST")
    print("=" * 70)
    print()

    # Connect to MongoDB
    print("Connecting to MongoDB...")
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("[OK] Connected to MongoDB")
    except Exception as e:
        print(f"[ERROR] Failed to connect: {e}")
        return

    print()

    # Test credentials
    username = "admin"
    password = "bhiv2024"

    print(f"Testing credentials:")
    print(f"  Username: {username}")
    print(f"  Password: {password}")
    print()

    # Get database
    db = get_database()

    # Find user - EXACT same query as in auth.py
    print("Step 1: Finding user with query...")
    query = {"$or": [{"username": username}, {"email": username}], "is_active": True}
    print(f"  Query: {query}")

    user = await db.users.find_one(query)

    if not user:
        print("[ERROR] User not found!")
        print()
        print("Checking all users in database...")
        all_users = await db.users.find({}).to_list(length=100)
        print(f"Total users: {len(all_users)}")
        for u in all_users:
            print(f"  - {u.get('username')} (is_active: {u.get('is_active')})")
        return

    print(f"[OK] User found:")
    print(f"  _id: {user.get('_id')}")
    print(f"  username: {user.get('username')}")
    print(f"  email: {user.get('email')}")
    print(f"  is_active: {user.get('is_active')}")
    print()

    # Get password hash
    print("Step 2: Getting password hash...")
    password_hash = user.get("password_hash") or user.get("hashed_password")

    if not password_hash:
        print("[ERROR] No password hash found!")
        print(f"User keys: {list(user.keys())}")
        return

    print(f"[OK] Password hash found")
    print(f"  Hash (first 50 chars): {password_hash[:50]}...")
    print()

    # Verify password
    print("Step 3: Verifying password...")
    print(f"  Password to verify: '{password}'")
    print(f"  Password length: {len(password)}")
    print(f"  Password bytes: {password.encode('utf-8')}")

    try:
        result = verify_password(password, password_hash)
        print(f"  Verification result: {result}")

        if result:
            print("[OK] Password verification PASSED")
        else:
            print("[ERROR] Password verification FAILED")

            # Try with different password variations
            print()
            print("Trying password variations...")
            variations = [
                "bhiv2024",
                "bhiv2024 ",
                " bhiv2024",
                "bhiv2024\n",
                "bhiv2024\r\n",
            ]
            for var in variations:
                try:
                    res = verify_password(var, password_hash)
                    print(f"  '{repr(var)}': {res}")
                except Exception as e:
                    print(f"  '{repr(var)}': ERROR - {e}")

    except Exception as e:
        print(f"[ERROR] Exception during verification: {e}")
        import traceback

        traceback.print_exc()
        return

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_auth_directly())
