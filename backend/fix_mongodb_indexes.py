"""
Fix MongoDB Index Conflicts
Drops conflicting indexes and recreates them with correct options
"""
import asyncio
import sys

from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection string
MONGODB_URL = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
DATABASE_NAME = "bhiv_db"


async def fix_indexes():
    """Drop conflicting indexes and recreate them"""
    print("🔧 Connecting to MongoDB...")

    try:
        client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
        )

        db = client[DATABASE_NAME]

        # Test connection
        await client.admin.command("ping")
        print("✅ Connected to MongoDB")

        # Fix refresh_tokens collection indexes
        print("\n🔧 Fixing refresh_tokens indexes...")
        collection = db.refresh_tokens

        # Get existing indexes
        indexes = await collection.list_indexes().to_list(length=None)
        print(f"📋 Found {len(indexes)} existing indexes")

        # Drop the conflicting expires_at_1 index
        try:
            await collection.drop_index("expires_at_1")
            print("✅ Dropped conflicting expires_at_1 index")
        except Exception as e:
            print(f"ℹ️  Index may not exist or already dropped: {e}")

        # Recreate with correct options
        try:
            await collection.create_index([("expires_at", 1)], name="expires_at_1_ttl", expireAfterSeconds=0)
            print("✅ Created expires_at_1_ttl index with TTL")
        except Exception as e:
            print(f"⚠️  Could not create TTL index: {e}")

        # List all indexes after fix
        print("\n📋 Final indexes:")
        indexes = await collection.list_indexes().to_list(length=None)
        for idx in indexes:
            print(f"  - {idx.get('name')}: {idx.get('key')}")

        print("\n✅ Index fix complete!")

        client.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 70)
    print("MongoDB Index Fix Script")
    print("=" * 70)
    asyncio.run(fix_indexes())
