"""
Fix MongoDB Index Conflict
Drops the old index and recreates with correct TTL settings
"""
import asyncio
import sys

from app.config import settings
from motor.motor_asyncio import AsyncIOMotorClient


async def fix_index_conflict():
    """Drop conflicting index and recreate with TTL"""
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DATABASE]

    try:
        # Check existing indexes
        print("\nExisting indexes on refresh_tokens:")
        indexes = await db.refresh_tokens.list_indexes().to_list(length=None)
        for idx in indexes:
            print(f"  - {idx['name']}: {idx.get('key', {})}")

        # Drop the old index without TTL
        print("\nDropping old 'expires_at_1' index...")
        try:
            await db.refresh_tokens.drop_index("expires_at_1")
            print("✅ Old index dropped")
        except Exception as e:
            if "not found" in str(e).lower():
                print("⚠️ Index 'expires_at_1' not found (already dropped)")
            else:
                print(f"❌ Error dropping index: {e}")

        # Create new TTL index
        print("\nCreating new TTL index 'expires_at_1_ttl'...")
        try:
            await db.refresh_tokens.create_index([("expires_at", 1)], name="expires_at_1_ttl", expireAfterSeconds=0)
            print("✅ TTL index created successfully")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("✅ TTL index already exists")
            else:
                print(f"❌ Error creating index: {e}")

        # Verify final state
        print("\nFinal indexes on refresh_tokens:")
        indexes = await db.refresh_tokens.list_indexes().to_list(length=None)
        for idx in indexes:
            ttl = idx.get("expireAfterSeconds", "N/A")
            print(f"  - {idx['name']}: {idx.get('key', {})} (TTL: {ttl}s)")

        print("\n✅ Index conflict resolved!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(fix_index_conflict())
