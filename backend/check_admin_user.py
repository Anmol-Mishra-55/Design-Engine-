#!/usr/bin/env python3
"""
Check admin user in MongoDB
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def check_admin_user():
    """Check if admin user exists and verify password"""
    try:
        # Connect to MongoDB
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        db = get_database()

        # Find admin user
        user = await db.users.find_one({"username": "admin"})

        if not user:
            print("[ERROR] Admin user not found in database")
            return

        print("[OK] Admin user found:")
        print(f"    _id: {user.get('_id')}")
        print(f"    username: {user.get('username')}")
        print(f"    email: {user.get('email')}")
        print(f"    is_active: {user.get('is_active')}")
        print(f"    password_hash exists: {bool(user.get('password_hash'))}")
        print()

        # Test password verification
        password_hash = user.get("password_hash")
        if password_hash:
            test_password = "bhiv2024"
            try:
                is_valid = pwd_context.verify(test_password, password_hash)
                print(f"Password verification test: {'PASS' if is_valid else 'FAIL'}")
                if is_valid:
                    print(f"    Password 'bhiv2024' is correct")
                else:
                    print(f"    Password 'bhiv2024' does NOT match")
            except Exception as e:
                print(f"[ERROR] Password verification failed: {e}")
        else:
            print("[ERROR] No password_hash found for user")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_admin_user())
