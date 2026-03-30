#!/usr/bin/env python3
"""
Test MongoDB Atlas connection
"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

from pymongo import MongoClient
import time

# Use the actual MongoDB Atlas URL
MONGODB_URL = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/bhiv_db?appName=Cluster0&retryWrites=true&w=majority"
DATABASE_NAME = "bhiv_db"

print("=" * 70)
print("MONGODB ATLAS CONNECTION TEST")
print("=" * 70)
print()

print(f"MongoDB URL: {MONGODB_URL[:60]}...")
print(f"Database: {DATABASE_NAME}")
print()

print("Attempting to connect...")
start_time = time.time()

try:
    # Try with shorter timeout
    client = MongoClient(
        MONGODB_URL,
        serverSelectionTimeoutMS=15000,  # 15 seconds
        connectTimeoutMS=15000,
        socketTimeoutMS=15000
    )

    # Test connection
    print("Pinging MongoDB...")
    client.admin.command('ping')

    elapsed = time.time() - start_time
    print(f"[SUCCESS] Connected to MongoDB Atlas in {elapsed:.2f} seconds")
    print()

    # Get database
    db = client[DATABASE_NAME]

    # Check collections
    print("Fetching collections...")
    collections = db.list_collection_names()
    print(f"Collections found: {len(collections)}")
    for coll in collections:
        count = db[coll].count_documents({})
        print(f"  - {coll}: {count} documents")

    print()

    # Check admin user
    print("Checking admin user...")
    user = db.users.find_one({"username": "admin"})
    if user:
        print(f"[OK] Admin user found")
        print(f"  _id: {user.get('_id')}")
        print(f"  username: {user.get('username')}")
        print(f"  is_active: {user.get('is_active')}")
        print(f"  has password_hash: {bool(user.get('password_hash'))}")
    else:
        print("[ERROR] Admin user not found")

    client.close()
    print()
    print("[SUCCESS] MongoDB Atlas connection is working!")

except Exception as e:
    elapsed = time.time() - start_time
    print(f"[ERROR] Connection failed after {elapsed:.2f} seconds")
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)
