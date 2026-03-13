"""
MONGODB MIGRATION GUIDE
Complete step-by-step process to migrate from Supabase to MongoDB
"""

# ============================================================================
# STEP 1: INSTALL DEPENDENCIES
# ============================================================================

# Add to requirements.txt:
pymongo==4.6.0
motor==3.3.2
dnspython==2.4.2

# Install:
pip install pymongo motor dnspython


# ============================================================================
# STEP 2: UPDATE .env FILE
# ============================================================================

# Replace Supabase settings with MongoDB:

# OLD (Supabase):
# DATABASE_URL=postgresql://...
# SUPABASE_URL=https://...
# SUPABASE_KEY=...

# NEW (MongoDB):
MONGODB_URL=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=bhiv_db


# ============================================================================
# STEP 3: BACKUP EXISTING DATA (OPTIONAL)
# ============================================================================

# Export PostgreSQL data to JSON:
# 1. Use pg_dump to backup PostgreSQL
# 2. Convert to JSON format
# 3. Import into MongoDB using mongoimport


# ============================================================================
# STEP 4: REPLACE CONFIGURATION FILE
# ============================================================================

# Option A: Replace existing config.py
# 1. Backup current config.py
# 2. Replace with config_mongodb.py content
# 3. Update imports in main.py

# Option B: Keep both and switch via environment variable
# In main.py:
# if os.getenv("USE_MONGODB") == "true":
#     from app.config_mongodb import settings
# else:
#     from app.config import settings


# ============================================================================
# STEP 5: UPDATE MAIN APPLICATION FILE
# ============================================================================

# In main.py, update startup/shutdown events:

from app.database_mongodb import connect_to_mongo, close_mongo_connection
from app.config_mongodb import settings

@app.on_event("startup")
async def startup():
    await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
    # ... other startup code

@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()
    # ... other shutdown code


# ============================================================================
# STEP 6: UPDATE DATABASE OPERATIONS
# ============================================================================

# OLD (SQLAlchemy):
# from app.database import get_db
# from app.models import User
#
# @router.get("/users/{user_id}")
# def get_user(user_id: str, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.id == user_id).first()
#     return user

# NEW (MongoDB):
from app.database_mongodb import get_database
from app.models_mongodb import User

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    db = get_database()
    user = await db.users.find_one({"_id": user_id})
    return user


# ============================================================================
# STEP 7: UPDATE STORAGE OPERATIONS
# ============================================================================

# OLD (Supabase Storage):
# from app.storage import upload_file, generate_signed_url
#
# url = upload_file(file_path, "files", destination)
# signed_url = generate_signed_url(url, "files")

# NEW (MongoDB GridFS):
from app.storage_mongodb import GridFSStorage, upload_preview, upload_geometry
from app.database_mongodb import get_database

db = get_database()
storage = GridFSStorage(db)

file_id = await storage.upload_bytes(data, "files", destination)
file_data = await storage.download_file(file_id, "files")


# ============================================================================
# STEP 8: MIGRATE AUTHENTICATION
# ============================================================================

# Authentication logic remains the same (JWT tokens)
# Only database queries change:

# OLD:
# user = db.query(User).filter(User.username == username).first()

# NEW:
# user_doc = await db.users.find_one({"username": username})
# user = User(**user_doc) if user_doc else None


# ============================================================================
# STEP 9: UPDATE API ENDPOINTS
# ============================================================================

# Make all endpoints async:

# OLD:
# @router.post("/specs")
# def create_spec(spec: SpecCreate, db: Session = Depends(get_db)):
#     db_spec = Spec(**spec.dict())
#     db.add(db_spec)
#     db.commit()
#     return db_spec

# NEW:
# @router.post("/specs")
# async def create_spec(spec: SpecCreate):
#     db = get_database()
#     result = await db.specs.insert_one(spec.dict())
#     return {"id": str(result.inserted_id)}


# ============================================================================
# STEP 10: MIGRATION CHECKLIST
# ============================================================================

MIGRATION_CHECKLIST = """
□ Install MongoDB dependencies (pymongo, motor, dnspython)
□ Create MongoDB cluster (MongoDB Atlas or local)
□ Update .env with MONGODB_URL and MONGODB_DATABASE
□ Replace config.py with config_mongodb.py
□ Create database_mongodb.py module
□ Create storage_mongodb.py module
□ Create models_mongodb.py module
□ Update main.py startup/shutdown events
□ Update all database queries to use MongoDB syntax
□ Update all storage operations to use GridFS
□ Make all endpoints async
□ Update authentication to use MongoDB
□ Test all endpoints
□ Migrate existing data (if needed)
□ Update tests to use MongoDB
□ Deploy to production
"""


# ============================================================================
# STEP 11: COMMON MONGODB OPERATIONS
# ============================================================================

# INSERT
await db.users.insert_one({"_id": user_id, "username": "john", "email": "john@example.com"})

# FIND ONE
user = await db.users.find_one({"_id": user_id})

# FIND MANY
users = await db.users.find({"is_active": True}).to_list(None)

# UPDATE
await db.users.update_one({"_id": user_id}, {"$set": {"email": "new@example.com"}})

# DELETE
await db.users.delete_one({"_id": user_id})

# COUNT
count = await db.users.count_documents({"is_active": True})

# AGGREGATE
pipeline = [
    {"$match": {"city": "Mumbai"}},
    {"$group": {"_id": "$city", "count": {"$sum": 1}}},
]
results = await db.specs.aggregate(pipeline).to_list(None)


# ============================================================================
# STEP 12: GRIDFS OPERATIONS
# ============================================================================

from app.storage_mongodb import GridFSStorage
from app.database_mongodb import get_database

db = get_database()
storage = GridFSStorage(db)

# UPLOAD
file_id = await storage.upload_bytes(
    data=file_bytes,
    bucket="geometry",
    destination_path="spec_123.glb",
    content_type="model/gltf-binary",
    metadata={"spec_id": "spec_123"}
)

# DOWNLOAD
file_data = await storage.download_file(file_id, "geometry")

# DELETE
await storage.delete_file(file_id, "geometry")

# LIST
files = await storage.list_files("geometry", metadata_filter={"spec_id": "spec_123"})

# GET INFO
info = await storage.get_file_info(file_id, "geometry")


# ============================================================================
# STEP 13: TESTING
# ============================================================================

# Create test fixtures:

import pytest
from motor.motor_asyncio import AsyncClient

@pytest.fixture
async def mongodb():
    client = AsyncClient("mongodb://localhost:27017")
    db = client.test_db
    yield db
    await client.drop_database("test_db")
    client.close()

@pytest.mark.asyncio
async def test_create_user(mongodb):
    result = await mongodb.users.insert_one({"username": "test", "email": "test@example.com"})
    assert result.inserted_id is not None


# ============================================================================
# STEP 14: PERFORMANCE OPTIMIZATION
# ============================================================================

# Create indexes for frequently queried fields:
await db.users.create_index("username", unique=True)
await db.specs.create_index([("user_id", 1), ("created_at", -1)])
await db.iterations.create_index("spec_id")

# Use connection pooling:
# Already configured in database_mongodb.py

# Use batch operations:
await db.specs.insert_many([spec1, spec2, spec3])


# ============================================================================
# STEP 15: TROUBLESHOOTING
# ============================================================================

# Connection issues:
# - Check MONGODB_URL format
# - Verify IP whitelist in MongoDB Atlas
# - Check network connectivity

# Performance issues:
# - Create appropriate indexes
# - Use projection to limit fields
# - Use pagination for large result sets

# Data migration issues:
# - Validate data types match MongoDB schema
# - Handle ObjectId conversions
# - Test with sample data first
