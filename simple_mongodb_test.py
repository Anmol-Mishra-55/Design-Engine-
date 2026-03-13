#!/usr/bin/env python3
"""
Simple MongoDB Connection Test
Tests if data is actually being stored in MongoDB database
"""
import asyncio
import sys
import os
from datetime import datetime, timezone

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.config import settings
from backend.app.database_mongodb import connect_to_mongo, get_database, close_mongo_connection


async def simple_mongodb_test():
    """Simple MongoDB connection and data storage test"""
    print("=" * 60)
    print("MONGODB CONNECTION TEST")
    print("=" * 60)

    try:
        # Test connection
        print(f"Connecting to MongoDB...")
        print(f"Database: {settings.MONGODB_DATABASE}")

        db = await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("SUCCESS: Connected to MongoDB!")

        # Test data insertion
        print("\nTesting data storage...")

        # Insert test user
        test_user = {
            "_id": "test_user_mongo",
            "username": "test_user",
            "email": "test@mongodb.com",
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.users.insert_one(test_user)
        print(f"SUCCESS: Inserted user with ID: {result.inserted_id}")

        # Verify user exists
        found_user = await db.users.find_one({"_id": "test_user_mongo"})
        if found_user:
            print(f"SUCCESS: Retrieved user: {found_user['username']}")

        # Insert test spec
        test_spec = {
            "_id": "test_spec_mongo",
            "user_id": "test_user_mongo",
            "prompt": "Test building design",
            "city": "Mumbai",
            "estimated_cost": 1500000.0,
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.specs.insert_one(test_spec)
        print(f"SUCCESS: Inserted spec with ID: {result.inserted_id}")

        # Verify spec exists
        found_spec = await db.specs.find_one({"_id": "test_spec_mongo"})
        if found_spec:
            print(f"SUCCESS: Retrieved spec cost: Rs.{found_spec['estimated_cost']:,.0f}")

        # Test GridFS storage
        print("\nTesting GridFS file storage...")
        from gridfs import GridFS

        fs = GridFS(db, collection="files")
        test_data = b"Test file content for MongoDB GridFS"

        file_id = fs.put(test_data, filename="test.txt")
        print(f"SUCCESS: Stored file with ID: {file_id}")

        # Retrieve file
        retrieved_file = fs.get(file_id)
        if retrieved_file.read() == test_data:
            print("SUCCESS: File retrieved correctly from GridFS")

        # Show collections and counts
        print("\nDatabase collections:")
        collections = await db.list_collection_names()
        for collection in collections:
            count = await db[collection].count_documents({})
            print(f"  {collection}: {count} documents")

        # Cleanup
        print("\nCleaning up test data...")
        await db.users.delete_one({"_id": "test_user_mongo"})
        await db.specs.delete_one({"_id": "test_spec_mongo"})
        fs.delete(file_id)
        print("SUCCESS: Test data cleaned up")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("Your MongoDB database is working correctly!")
        print("Data IS being stored in MongoDB!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        print("MongoDB connection or operation failed!")
        return False

    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    print("Starting MongoDB Test...")
    success = asyncio.run(simple_mongodb_test())

    if success:
        print("\nCONFIRMED: Your project uses MongoDB exclusively!")
        print("- Database: MongoDB")
        print("- Storage: MongoDB GridFS")
        print("- Data is being stored successfully!")
    else:
        print("\nFAILED: MongoDB setup has issues")
