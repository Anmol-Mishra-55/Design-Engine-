#!/usr/bin/env python3
"""
Test authentication flow
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database
from app.utils import verify_password


async def test_auth():
    """Test the authentication flow"""
    try:
        # Connect to MongoDB
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        db = get_database()

        username = "admin"
        password = "bhiv2024"

        print(f"Testing authentication for: {username}")
        print()

        # Find user
        user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})

        if not user:
            print("[FAIL] User not found or not active")
            return

        print("[OK] User found:")
        print(f"    _id: {user.get('_id')}")
        print(f"    username: {user.get('username')}")
        print(f"    is_active: {user.get('is_active')}")
        print()

        # Get password hash
        password_hash = user.get("password_hash") or user.get("hashed_password")

        if not password_hash:
            print("[FAIL] No password_hash found")
            return

        print("[OK] Password hash found")
        print()

        # Verify password
        try:
            is_valid = verify_password(password, password_hash)
            print(f"Password verification: {'PASS' if is_valid else 'FAIL'}")

            if is_valid:
                print()
                print("[SUCCESS] Authentication would succeed!")
                print(f"    Username: {username}")
                print(f"    Password: {password}")
            else:
                print()
                print("[FAIL] Password does not match")

        except Exception as e:
            print(f"[ERROR] Verification error: {e}")
            import traceback

            traceback.print_exc()

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_auth())
