#!/usr/bin/env python3
"""
Comprehensive authentication diagnostics
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


async def diagnose_auth():
    """Comprehensive authentication diagnostics"""
    print("=" * 70)
    print("AUTHENTICATION DIAGNOSTICS")
    print("=" * 70)
    print()

    # 1. Check MongoDB connection settings
    print("1. MongoDB Configuration:")
    print(f"   URL: {settings.MONGODB_URL[:50]}...")
    print(f"   Database: {settings.MONGODB_DATABASE}")
    print()

    # 2. Connect to MongoDB
    try:
        print("2. Connecting to MongoDB...")
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("   [OK] Connected successfully")
        print()
    except Exception as e:
        print(f"   [ERROR] Connection failed: {e}")
        return

    # 3. Get database
    try:
        db = get_database()
        print("3. Database Access:")
        print("   [OK] Database accessible")
        print()
    except Exception as e:
        print(f"   [ERROR] Cannot access database: {e}")
        return

    # 4. Check users collection
    try:
        print("4. Users Collection:")
        user_count = await db.users.count_documents({})
        print(f"   Total users: {user_count}")
        print()
    except Exception as e:
        print(f"   [ERROR] Cannot access users collection: {e}")
        return

    # 5. Find admin user
    print("5. Admin User Lookup:")
    username = "admin"

    # Try exact match
    user = await db.users.find_one({"username": username})
    if user:
        print(f"   [OK] Found by username: {username}")
    else:
        print(f"   [FAIL] Not found by username: {username}")

    # Try with is_active filter (like the auth endpoint does)
    user_active = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})
    if user_active:
        print(f"   [OK] Found with is_active=True filter")
    else:
        print(f"   [FAIL] Not found with is_active=True filter")

    print()

    if not user:
        print("[ERROR] Admin user does not exist!")
        print()
        print("Run this to create it:")
        print("   python create_admin_mongodb.py")
        return

    # 6. Check user details
    print("6. User Details:")
    print(f"   _id: {user.get('_id')}")
    print(f"   username: {user.get('username')}")
    print(f"   email: {user.get('email')}")
    print(f"   is_active: {user.get('is_active')}")
    print(f"   is_admin: {user.get('is_admin')}")
    print(f"   password_hash exists: {bool(user.get('password_hash'))}")
    print(f"   hashed_password exists: {bool(user.get('hashed_password'))}")
    print()

    # 7. Check password hash
    password_hash = user.get("password_hash") or user.get("hashed_password")

    if not password_hash:
        print("[ERROR] No password hash found!")
        print("   User has no password_hash or hashed_password field")
        return

    print("7. Password Hash:")
    print(f"   Hash length: {len(password_hash)}")
    print(f"   Hash prefix: {password_hash[:20]}...")
    print(f"   Hash type: {'bcrypt' if password_hash.startswith('$2b$') else 'unknown'}")
    print()

    # 8. Test password verification
    print("8. Password Verification Test:")
    test_password = "bhiv2024"

    try:
        # Test with app.utils.verify_password
        is_valid_utils = verify_password(test_password, password_hash)
        print(f"   Using app.utils.verify_password: {'PASS' if is_valid_utils else 'FAIL'}")
    except Exception as e:
        print(f"   Using app.utils.verify_password: ERROR - {e}")
        is_valid_utils = False

    try:
        # Test with direct pwd_context
        is_valid_direct = pwd_context.verify(test_password, password_hash)
        print(f"   Using pwd_context.verify: {'PASS' if is_valid_direct else 'FAIL'}")
    except Exception as e:
        print(f"   Using pwd_context.verify: ERROR - {e}")
        is_valid_direct = False

    print()

    # 9. Simulate authentication flow
    print("9. Simulating Authentication Flow:")
    print(f"   Input username: {username}")
    print(f"   Input password: {test_password}")
    print()

    # Step 1: Find user
    auth_user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})

    if not auth_user:
        print("   [FAIL] User not found (step 1)")
        return
    print("   [OK] User found (step 1)")

    # Step 2: Get password hash
    auth_password_hash = auth_user.get("password_hash") or auth_user.get("hashed_password")

    if not auth_password_hash:
        print("   [FAIL] No password hash (step 2)")
        return
    print("   [OK] Password hash retrieved (step 2)")

    # Step 3: Verify password
    try:
        auth_is_valid = verify_password(test_password, auth_password_hash)
        if auth_is_valid:
            print("   [OK] Password verified (step 3)")
            print()
            print("=" * 70)
            print("[SUCCESS] Authentication should work!")
            print("=" * 70)
        else:
            print("   [FAIL] Password verification failed (step 3)")
            print()
            print("=" * 70)
            print("[FAIL] Authentication will fail - password mismatch")
            print("=" * 70)
    except Exception as e:
        print(f"   [ERROR] Password verification error (step 3): {e}")
        print()
        print("=" * 70)
        print(f"[ERROR] Authentication will fail - {e}")
        print("=" * 70)

    print()

    # 10. Check if server might be using different database
    print("10. Additional Checks:")

    # List all users
    all_users = []
    async for u in db.users.find({}).limit(10):
        all_users.append(u.get("username"))

    print(f"   All usernames in database: {all_users}")
    print()

    # Check demo mode
    print("11. Demo Mode Configuration:")
    print(f"   DEMO_MODE: {settings.DEMO_MODE}")
    print(f"   DEMO_USERNAME: {settings.DEMO_USERNAME}")
    print(f"   DEMO_PASSWORD exists: {bool(settings.DEMO_PASSWORD)}")
    print()


if __name__ == "__main__":
    asyncio.run(diagnose_auth())
