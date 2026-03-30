import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Step 1: imports starting")

from app.config import settings

print("Step 2: settings loaded")
print("  MONGODB_URL:", settings.MONGODB_URL[:50])
print("  MONGODB_DATABASE:", settings.MONGODB_DATABASE)

from app.database_mongodb import connect_to_mongo, get_database
from app.utils import verify_password

print("Step 3: db modules loaded")


async def debug():
    print("Step 4: connecting to MongoDB...")
    try:
        await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("Step 5: connected OK")
    except Exception as e:
        print("Step 5 FAILED:", type(e).__name__, str(e)[:300])
        return

    db = get_database()
    print("Step 6: got db handle")

    user = await db.users.find_one({"username": "admin"})
    print("Step 7: user found:", user is not None)

    if not user:
        print("  -> No admin user in DB! Run create_admin_mongodb.py first.")
        return

    print("  is_active:", user.get("is_active"))
    ph = user.get("password_hash") or user.get("hashed_password")
    print("  password_hash present:", bool(ph))
    if ph:
        ok = verify_password("bhiv2024", ph)
        print("  verify('bhiv2024'):", ok)
    else:
        print("  ERROR: no password hash field found")
        print("  user keys:", list(user.keys()))


asyncio.run(debug())
print("Done.")
