#!/usr/bin/env python3
"""
MongoDB Test Data Cleanup
Removes any leftover test data from verification tests
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

MONGODB_URL = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
DATABASE_NAME = "bhiv_db"

async def cleanup_test_data():
    """Clean up any leftover test data"""
    print("=" * 50)
    print("MONGODB TEST DATA CLEANUP")
    print("=" * 50)

    client = None
    try:
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=10000)
        db = client[DATABASE_NAME]

        # Test connection
        await client.admin.command('ping')
        print("Connected to MongoDB")

        # Clean up test collections
        print("\\nCleaning up test data...")

        # Remove test documents
        test_patterns = [
            "test_user", "complete_test", "direct_test", "verify_", "final_test", "fixed_test"
        ]

        users_deleted = 0
        specs_deleted = 0

        for pattern in test_patterns:
            # Clean users
            result = await db.users.delete_many({"_id": {"$regex": pattern}})
            users_deleted += result.deleted_count

            result = await db.users.delete_many({"username": {"$regex": pattern}})
            users_deleted += result.deleted_count

            # Clean specs
            result = await db.specs.delete_many({"_id": {"$regex": pattern}})
            specs_deleted += result.deleted_count

            result = await db.specs.delete_many({"user_id": {"$regex": pattern}})
            specs_deleted += result.deleted_count

        print(f"Deleted {users_deleted} test users")
        print(f"Deleted {specs_deleted} test specs")

        # Clean up test_collection
        result = await db.test_collection.delete_many({})
        print(f"Deleted {result.deleted_count} documents from test_collection")

        # Clean up GridFS test files
        buckets = ["files", "previews", "geometry", "compliance", "verification_files"]
        total_files_deleted = 0

        for bucket_name in buckets:
            try:
                bucket = AsyncIOMotorGridFSBucket(db, bucket_name=bucket_name)

                # Find test files
                test_files = []
                for pattern in test_patterns:
                    cursor = bucket.find({"filename": {"$regex": pattern}})
                    files = await cursor.to_list(length=None)
                    test_files.extend(files)

                # Delete test files
                for file_info in test_files:
                    await bucket.delete(file_info._id)
                    total_files_deleted += 1

                print(f"Cleaned {len(test_files)} files from {bucket_name} bucket")

            except Exception as e:
                print(f"Note: {bucket_name} bucket cleanup: {e}")

        print(f"Total GridFS files deleted: {total_files_deleted}")

        # Show final state
        print("\\nFinal database state:")
        collections = await db.list_collection_names()
        total_docs = 0

        for collection_name in collections:
            count = await db[collection_name].count_documents({})
            total_docs += count
            if count > 0:
                print(f"  {collection_name}: {count} documents")

        print(f"Total documents remaining: {total_docs}")

        print("\\n" + "=" * 50)
        print("CLEANUP COMPLETE!")
        print("Your database is now clean of test data")
        print("=" * 50)

    except Exception as e:
        print(f"Cleanup error: {e}")

    finally:
        if client:
            client.close()

if __name__ == "__main__":
    asyncio.run(cleanup_test_data())
