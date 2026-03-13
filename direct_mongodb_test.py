#!/usr/bin/env python3
"""
Direct MongoDB Connection Test
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

# Your MongoDB connection string
MONGODB_URL = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
DATABASE_NAME = "bhiv_db"

async def test_direct_mongodb():
    """Direct MongoDB connection test"""
    print("=" * 50)
    print("DIRECT MONGODB CONNECTION TEST")
    print("=" * 50)

    client = None
    try:
        # Connect directly to MongoDB
        print("Connecting to MongoDB...")
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=10000)
        db = client[DATABASE_NAME]

        # Test connection
        await client.admin.command('ping')
        print("SUCCESS: Connected to MongoDB!")

        # Show existing collections
        collections = await db.list_collection_names()
        print(f"\\nExisting collections: {collections}")

        # Test data insertion
        print("\\nTesting data storage...")

        # Insert test document
        test_doc = {
            "_id": "direct_test_123",
            "test_type": "direct_connection",
            "message": "This is a test document",
            "timestamp": datetime.now(timezone.utc),
            "success": True
        }

        result = await db.test_collection.insert_one(test_doc)
        print(f"SUCCESS: Inserted document with ID: {result.inserted_id}")

        # Retrieve document
        found_doc = await db.test_collection.find_one({"_id": "direct_test_123"})
        if found_doc:
            print(f"SUCCESS: Retrieved document: {found_doc['message']}")

        # Count documents in collections
        print("\\nDocument counts:")
        for collection_name in collections:
            count = await db[collection_name].count_documents({})
            print(f"  {collection_name}: {count} documents")

        # Test GridFS
        print("\\nTesting GridFS...")
        import gridfs
        fs = gridfs.GridFS(db.get_collection("fs"))

        # This is a sync operation, so we'll skip it for now
        print("GridFS test skipped (requires sync operations)")

        # Cleanup
        await db.test_collection.delete_one({"_id": "direct_test_123"})
        print("\\nCleaned up test document")

        print("\\n" + "=" * 50)
        print("SUCCESS: MongoDB is working!")
        print("Your data IS being stored in MongoDB!")
        print("Database:", DATABASE_NAME)
        print("=" * 50)

        return True

    except Exception as e:
        print(f"\\nERROR: {e}")
        print("MongoDB connection failed!")
        return False

    finally:
        if client:
            client.close()

if __name__ == "__main__":
    success = asyncio.run(test_direct_mongodb())

    if success:
        print("\\nCONFIRMED: Your project uses MongoDB!")
        print("- Connection: Working")
        print("- Data Storage: Working")
        print("- Database: bhiv_db")
    else:
        print("\\nFAILED: MongoDB connection issues")
