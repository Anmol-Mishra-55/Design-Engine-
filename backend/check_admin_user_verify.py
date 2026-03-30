import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.utils import verify_password
from motor.motor_asyncio import AsyncIOMotorClient


async def check():
    c = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=10000)
    db = c[settings.MONGODB_DATABASE]
    u = await db.users.find_one({"username": "admin"})
    if not u:
        print("ERROR: admin user NOT found in MongoDB")
        c.close()
        return
    print("Found user:", u.get("username"))
    print("is_active:", u.get("is_active"))
    print("has password_hash:", bool(u.get("password_hash")))
    pw_ok = verify_password("bhiv2024", u.get("password_hash", ""))
    print("password 'bhiv2024' verifies:", pw_ok)
    c.close()


asyncio.run(check())
