#!/usr/bin/env python3
"""Create or reset admin user in MongoDB."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone

from app.config import settings
from app.utils import hash_password
from motor.motor_asyncio import AsyncIOMotorClient


async def create_admin():
    client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGODB_DATABASE]

    username = "admin"
    password = "bhiv2024"
    hashed = hash_password(password)

    existing = await db.users.find_one({"username": username})
    if existing:
        # Reset password and ensure active
        await db.users.update_one(
            {"username": username},
            {"$set": {"password_hash": hashed, "is_active": True, "updated_at": datetime.now(timezone.utc)}},
        )
        print(f"[OK] Admin user updated: {username} / {password}")
    else:
        await db.users.insert_one(
            {
                "username": username,
                "email": "admin@bhiv.com",
                "password_hash": hashed,
                "is_active": True,
                "is_admin": True,
                "created_at": datetime.now(timezone.utc),
            }
        )
        print(f"[OK] Admin user created: {username} / {password}")

    client.close()


if __name__ == "__main__":
    asyncio.run(create_admin())
