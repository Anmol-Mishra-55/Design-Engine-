#!/usr/bin/env python3
"""
MongoDB Atlas Direct IP Connection Test
Bypasses DNS issues by connecting directly to MongoDB server IPs
"""
import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Your MongoDB credentials
USERNAME = "blackholeinfiverse55_db_user"
PASSWORD = "6SKTXNiidEZNTtDc"
DATABASE = "bhiv_db"

# Direct MongoDB server IPs (from SRV record resolution)
MONGODB_SERVERS = [
    "ac-xqai9lp-shard-00-00.acfgtzl.mongodb.net",
    "ac-xqai9lp-shard-00-01.acfgtzl.mongodb.net",
    "ac-xqai9lp-shard-00-02.acfgtzl.mongodb.net",
]


async def test_direct_connection():
    """Test direct connection to MongoDB servers"""
    print("=" * 60)
    print("MongoDB Atlas Direct Connection Test")
    print("=" * 60)

    # Try different connection approaches
    connection_strings = [
        # Original Atlas connection string
        f"mongodb+srv://{USERNAME}:{PASSWORD}@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority",
        # Direct connection to first server
        f"mongodb://{USERNAME}:{PASSWORD}@ac-xqai9lp-shard-00-00.acfgtzl.mongodb.net:27017/{DATABASE}?authSource=admin&ssl=true",
        # Connection with different DNS settings
        f"mongodb+srv://{USERNAME}:{PASSWORD}@cluster0.acfgtzl.mongodb.net/{DATABASE}?retryWrites=true&w=majority&authSource=admin",
    ]

    for i, conn_str in enumerate(connection_strings, 1):
        print(f"\n[TEST {i}] Testing connection approach {i}...")

        try:
            client = AsyncIOMotorClient(
                conn_str, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000, socketTimeoutMS=15000, maxPoolSize=1
            )

            # Test connection
            await client.admin.command("ping")
            print(f"[SUCCESS] Connection approach {i} WORKS!")

            # Test database access
            db = client[DATABASE]
            collections = await db.list_collection_names()
            print(f"[INFO] Database accessible with {len(collections)} collections")

            # Test a simple operation
            test_collection = db.test_connection
            result = await test_collection.insert_one({"test": "connection_successful", "approach": i})
            print(f"[INFO] Test document inserted with ID: {result.inserted_id}")

            # Clean up test document
            await test_collection.delete_one({"_id": result.inserted_id})
            print(f"[INFO] Test document cleaned up")

            client.close()
            return True

        except Exception as e:
            print(f"[FAIL] Connection approach {i} failed: {e}")
            continue

    print("\n[CRITICAL] All connection approaches failed!")
    return False


async def test_with_google_dns():
    """Test connection after suggesting DNS change"""
    print("\n" + "=" * 60)
    print("DNS TROUBLESHOOTING RECOMMENDATION")
    print("=" * 60)

    print("Your current DNS server (192.168.0.1) is causing MongoDB Atlas resolution issues.")
    print("\nRECOMMENDED SOLUTION:")
    print("1. Run 'fix_dns.bat' as Administrator to change DNS to Google DNS")
    print("2. Or manually change DNS servers to: 8.8.8.8, 8.8.4.4")
    print("3. Restart this test after DNS change")

    print("\nALTERNATIVE SOLUTIONS:")
    print("1. Check MongoDB Atlas Network Access settings")
    print("2. Add your IP (192.168.0.98) to Atlas IP whitelist")
    print("3. Verify your Atlas cluster is running")
    print("4. Try connecting from MongoDB Compass")


if __name__ == "__main__":
    try:
        success = asyncio.run(test_direct_connection())
        if not success:
            asyncio.run(test_with_google_dns())
    except Exception as e:
        print(f"Test failed: {e}")
        asyncio.run(test_with_google_dns())
