#!/usr/bin/env python3
"""
Debug authentication flow
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database
from app.utils import verify_password
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def debug_auth():
    """Debug authentication flow step by step"""
    try:
        print("=" * 70)
        print("AUTHENTICATION DEBUG")
        print("=" * 70)
        print()

        # Step 1: Connect to MongoDB
        print("Step 1: Connecting to MongoDB...")
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("[OK] Connected to MongoDB")
        print()

        # Step 2: Get database
        print("Step 2: Getting database...")
        db = get_database()
        print(f"[OK] Database: {settings.MONGODB_DATABASE}")
        print()

        # Step 3: Find user
        print("Step 3: Finding user 'admin'...")
        username = "admin"
        user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})

        if not user:
            print("[ERROR] User not found")
            return

        print(f"[OK] User found:")
        print(f"   _id: {user.get('_id')}")
        print(f"   username: {user.get('username')}")
        print(f"   email: {user.get('email')}")
        print(f"   is_active: {user.get('is_active')}")
        print()

        # Step 4: Get password hash
        print("Step 4: Getting password hash...")
        password_hash = user.get("password_hash") or user.get("hashed_password")

        if not password_hash:
            print("[ERROR] No password hash found")
            return

        print(f"[OK] Password hash found: {password_hash[:50]}...")
        print()

        # Step 5: Verify password
        print("Step 5: Verifying password 'bhiv2024'...")
        password = "bhiv2024"

        try:
            # Test with utils.verify_password
            print("   Testing with app.utils.verify_password...")
            result1 = verify_password(password, password_hash)
            print(f"   Result: {result1}")

            # Test with direct pwd_context
            print("   Testing with direct pwd_context.verify...")
            result2 = pwd_context.verify(password, password_hash)
            print(f"   Result: {result2}")

            if result1 and result2:
                print("[OK] Password verification PASSED")
            else:
                print("[ERROR] Password verification FAILED")

        except Exception as e:
            print(f"[ERROR] Password verification error: {e}")
            import traceback

            traceback.print_exc()
            return

        print()
        print("=" * 70)
        print("AUTHENTICATION FLOW COMPLETE")
        print("=" * 70)

    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_auth())
