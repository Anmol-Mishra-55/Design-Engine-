#!/usr/bin/env python3
"""
Test login endpoint directly
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database_mongodb import connect_to_mongo, get_database
from app.utils import verify_password
from jose import jwt


async def test_login_flow():
    """Test the complete login flow"""
    try:
        print("=" * 70)
        print("LOGIN ENDPOINT TEST")
        print("=" * 70)
        print()

        # Connect to MongoDB
        print("Connecting to MongoDB...")
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("[OK] Connected")
        print()

        # Simulate login request
        username = "admin"
        password = "bhiv2024"

        print(f"Testing login with:")
        print(f"  Username: {username}")
        print(f"  Password: {password}")
        print()

        # Step 1: Get database
        db = get_database()

        # Step 2: Find user (same as _authenticate_against_mongodb)
        print("Step 1: Finding user...")
        user = await db.users.find_one({"$or": [{"username": username}, {"email": username}], "is_active": True})

        if not user:
            print("[ERROR] User not found")
            return

        print(f"[OK] User found: {user.get('username')}")
        print()

        # Step 3: Get password hash
        print("Step 2: Getting password hash...")
        password_hash = user.get("password_hash") or user.get("hashed_password")

        if not password_hash:
            print("[ERROR] No password hash found")
            return

        print(f"[OK] Password hash exists")
        print()

        # Step 4: Verify password
        print("Step 3: Verifying password...")
        try:
            is_valid = verify_password(password, password_hash)
            print(f"[OK] Password verification result: {is_valid}")

            if not is_valid:
                print("[ERROR] Password verification failed")
                return
        except Exception as e:
            print(f"[ERROR] Password verification exception: {e}")
            return

        print()

        # Step 5: Get subject (user ID)
        print("Step 4: Getting subject...")
        subject = str(user.get("_id") or user.get("username"))
        print(f"[OK] Subject: {subject}")
        print()

        # Step 6: Issue token
        print("Step 5: Issuing access token...")
        token_data = {
            "sub": subject,
            "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        }
        token = jwt.encode(token_data, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        print(f"[OK] Token issued: {token[:50]}...")
        print()

        print("=" * 70)
        print("LOGIN TEST SUCCESSFUL")
        print("=" * 70)
        print()
        print("Response:")
        print(f"  access_token: {token}")
        print(f"  token_type: bearer")

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_login_flow())
