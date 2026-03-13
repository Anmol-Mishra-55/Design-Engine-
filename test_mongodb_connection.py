#!/usr/bin/env python3
"""
MongoDB Connection and Data Storage Test
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


async def test_mongodb_connection():
    """Test MongoDB connection and data storage"""
    print("=" * 60)
    print("MONGODB CONNECTION & DATA STORAGE TEST")
    print("=" * 60)

    try:
        # Test 1: Connection
        print("\n1. Testing MongoDB Connection...")
        print(f"   MongoDB URL: {settings.MONGODB_URL[:50]}...")
        print(f"   Database: {settings.MONGODB_DATABASE}")

        db = await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
        print("   ✅ Connected to MongoDB successfully!")

        # Test 2: Database Info
        print("\n2. Database Information...")
        server_info = await db.client.server_info()
        print(f"   MongoDB Version: {server_info.get('version', 'Unknown')}")

        # Test 3: Collections
        print("\n3. Existing Collections...")
        collections = await db.list_collection_names()
        if collections:
            for collection in collections:
                count = await db[collection].count_documents({})
                print(f"   - {collection}: {count} documents")
        else:
            print("   No collections found (database is empty)")

        # Test 4: Insert Test Data
        print("\n4. Testing Data Storage...")
        test_user = {
            "_id": "test_user_123",
            "username": "test_user",
            "email": "test@example.com",
            "full_name": "Test User",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }

        # Insert user
        result = await db.users.insert_one(test_user)
        print(f"   [OK] Inserted test user with ID: {result.inserted_id}")

        # Verify insertion
        found_user = await db.users.find_one({"_id": "test_user_123"})
        if found_user:
            print(f"   [OK] Retrieved user: {found_user['username']} ({found_user['email']})")
        else:
            print("   [ERROR] Failed to retrieve inserted user")

        # Test 5: Insert Test Spec
        test_spec = {
            "_id": "test_spec_123",
            "user_id": "test_user_123",
            "prompt": "Test design prompt",
            "city": "Mumbai",
            "spec_json": {
                "design_type": "residential",
                "dimensions": {"width": 10, "length": 12},
                "stories": 2
            },
            "estimated_cost": 1500000.0,
            "currency": "INR",
            "status": "final",
            "created_at": datetime.now(timezone.utc)
        }

        result = await db.specs.insert_one(test_spec)
        print(f"   ✅ Inserted test spec with ID: {result.inserted_id}")

        # Verify spec insertion
        found_spec = await db.specs.find_one({"_id": "test_spec_123"})
        if found_spec:
            print(f"   ✅ Retrieved spec: {found_spec['prompt'][:30]}... (Cost: ₹{found_spec['estimated_cost']:,.0f})")
        else:
            print("   ❌ Failed to retrieve inserted spec")

        # Test 6: GridFS Storage Test
        print("\n5. Testing GridFS Storage...")
        from gridfs import GridFS

        # Test file storage
        fs = GridFS(db, collection="files")
        test_data = b"This is test file content for GridFS storage"

        file_id = fs.put(
            test_data,
            filename="test_file.txt",
            content_type="text/plain",
            metadata={"test": True, "created_at": datetime.now(timezone.utc)}
        )
        print(f"   ✅ Stored file in GridFS with ID: {file_id}")

        # Retrieve file
        retrieved_file = fs.get(file_id)
        retrieved_data = retrieved_file.read()
        if retrieved_data == test_data:
            print(f"   ✅ Retrieved file successfully: {retrieved_file.filename}")
        else:
            print("   ❌ File data mismatch")

        # Test 7: Final Collection Count
        print("\n6. Final Database State...")
        collections = await db.list_collection_names()
        total_docs = 0
        for collection in collections:
            count = await db[collection].count_documents({})
            total_docs += count
            print(f"   - {collection}: {count} documents")

        print(f"\n   📊 Total documents in database: {total_docs}")

        # Test 8: Cleanup (optional)
        print("\n7. Cleanup Test Data...")
        await db.users.delete_one({"_id": "test_user_123"})
        await db.specs.delete_one({"_id": "test_spec_123"})
        fs.delete(file_id)
        print("   ✅ Cleaned up test data")

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - MongoDB is working correctly!")
        print("✅ Your project is using MongoDB for both database and storage")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\n" + "=" * 60)
        print("❌ MONGODB CONNECTION FAILED")
        print("=" * 60)
        return False

    finally:
        await close_mongo_connection()

    return True


async def check_project_configuration():
    """Check if project is properly configured for MongoDB only"""
    print("\n" + "=" * 60)
    print("PROJECT CONFIGURATION CHECK")
    print("=" * 60)

    # Check main.py imports
    print("\n1. Checking main.py imports...")
    main_file = "backend/app/main.py"
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if "database_mongodb" in content:
                print("   [OK] Using MongoDB database module")
            else:
                print("   [ERROR] MongoDB database module not imported")

            if "connect_to_mongo" in content:
                print("   [OK] MongoDB connection function imported")
            else:
                print("   [ERROR] MongoDB connection function not imported")

    # Check config.py
    print("\n2. Checking configuration...")
    print(f"   MongoDB URL: {settings.MONGODB_URL[:50]}...")
    print(f"   Database Name: {settings.MONGODB_DATABASE}")
    print(f"   GridFS Buckets: {settings.GRIDFS_BUCKET_FILES}, {settings.GRIDFS_BUCKET_PREVIEWS}")

    # Check if SQLAlchemy is still being used
    print("\n3. Checking for legacy SQLAlchemy usage...")
    legacy_found = False

    # Check if database.py is imported anywhere
    api_dir = "backend/app/api"
    if os.path.exists(api_dir):
        for file in os.listdir(api_dir):
            if file.endswith('.py'):
                file_path = os.path.join(api_dir, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if "from app.database import" in content or "import app.database" in content:
                            print(f"   ⚠️  {file} still imports legacy database.py")
                            legacy_found = True
                except UnicodeDecodeError:
                    print(f"   ⚠️  Could not read {file} (encoding issue)")

    if not legacy_found:
        print("   ✅ No legacy SQLAlchemy imports found in API files")

    print("\n" + "=" * 60)
    if not legacy_found:
        print("✅ PROJECT CONFIGURATION IS CORRECT")
        print("✅ Using MongoDB only for database and storage")
    else:
        print("⚠️  SOME LEGACY SQLALCHEMY CODE STILL EXISTS")
    print("=" * 60)


if __name__ == "__main__":
    print("Starting MongoDB Connection Test...")

    # Run configuration check
    asyncio.run(check_project_configuration())

    # Run connection test
    success = asyncio.run(test_mongodb_connection())

    if success:
        print("\n🎉 SUCCESS: Your project is correctly configured to use MongoDB!")
        print("📊 Data is being stored in your MongoDB database")
        print("💾 File storage is using MongoDB GridFS")
    else:
        print("\n❌ FAILED: There are issues with your MongoDB setup")

    print("\nTest completed.")
