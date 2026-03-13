# SUPABASE TO MONGODB MIGRATION - COMPLETE STEP-BY-STEP GUIDE

## PHASE 1: PREPARATION (Day 1)

### Step 1.1: Set Up MongoDB
- [ ] Create MongoDB Atlas account (https://www.mongodb.com/cloud/atlas)
- [ ] Create a new cluster (free tier available)
- [ ] Create database user with strong password
- [ ] Whitelist your IP address in Network Access
- [ ] Get connection string (mongodb+srv://...)
- [ ] Test connection locally

### Step 1.2: Backup Existing Data
- [ ] Export PostgreSQL data using pg_dump
- [ ] Export Supabase storage files (if needed)
- [ ] Store backups in safe location
- [ ] Document current data structure

### Step 1.3: Install Dependencies
```bash
pip install pymongo==4.6.0 motor==3.3.2 dnspython==2.4.2
```
- [ ] Verify installation: `python -c "import pymongo; print(pymongo.__version__)"`

---

## PHASE 2: CODE MIGRATION (Day 2-3)

### Step 2.1: Update Configuration
- [ ] Copy `config_mongodb.py` to `backend/app/`
- [ ] Update `.env` file with MongoDB credentials:
  ```
  MONGODB_URL=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
  MONGODB_DATABASE=bhiv_db
  ```
- [ ] Remove old Supabase settings from `.env`
- [ ] Verify configuration loads without errors

### Step 2.2: Create MongoDB Modules
- [ ] Copy `database_mongodb.py` to `backend/app/`
- [ ] Copy `storage_mongodb.py` to `backend/app/`
- [ ] Copy `models_mongodb.py` to `backend/app/`
- [ ] Verify imports work: `python -c "from app.database_mongodb import connect_to_mongo"`

### Step 2.3: Update Main Application File
In `backend/app/main.py`:
- [ ] Replace imports:
  ```python
  # OLD: from app.config import settings
  # NEW: from app.config_mongodb import settings

  # OLD: from app.database import init_db
  # NEW: from app.database_mongodb import connect_to_mongo, close_mongo_connection
  ```

- [ ] Update startup event:
  ```python
  @app.on_event("startup")
  async def startup():
      await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
      # ... rest of startup code
  ```

- [ ] Update shutdown event:
  ```python
  @app.on_event("shutdown")
  async def shutdown():
      await close_mongo_connection()
      # ... rest of shutdown code
  ```

### Step 2.4: Update Authentication Module
In `backend/app/auth.py`:
- [ ] Update `authenticate_user()` to use MongoDB:
  ```python
  async def authenticate_user(username: str, password: str):
      db = get_database()
      user = await db.users.find_one({"username": username})
      # ... rest of logic
  ```

- [ ] Update `get_current_user()` to use MongoDB
- [ ] Update `create_refresh_token()` to use MongoDB
- [ ] Update `verify_refresh_token()` to use MongoDB
- [ ] Update `revoke_refresh_token()` to use MongoDB

### Step 2.5: Update API Endpoints
For each endpoint file in `backend/app/api/`:
- [ ] Make all endpoints async (add `async` keyword)
- [ ] Replace `db: Session = Depends(get_db)` with `db = get_database()`
- [ ] Convert SQLAlchemy queries to MongoDB queries:
  ```python
  # OLD: db.query(User).filter(User.id == user_id).first()
  # NEW: await db.users.find_one({"_id": user_id})
  ```

- [ ] Convert create operations:
  ```python
  # OLD: db.add(obj); db.commit()
  # NEW: await db.collection.insert_one(obj_dict)
  ```

- [ ] Convert update operations:
  ```python
  # OLD: db.query(Model).filter(...).update({...}); db.commit()
  # NEW: await db.collection.update_one({"_id": id}, {"$set": {...}})
  ```

- [ ] Convert delete operations:
  ```python
  # OLD: db.query(Model).filter(...).delete(); db.commit()
  # NEW: await db.collection.delete_one({"_id": id})
  ```

### Step 2.6: Update Storage Operations
In files using storage:
- [ ] Replace Supabase imports:
  ```python
  # OLD: from app.storage import upload_file, generate_signed_url
  # NEW: from app.storage_mongodb import GridFSStorage, upload_preview, upload_geometry
  ```

- [ ] Update upload operations:
  ```python
  # OLD: url = upload_file(file_path, "files", destination)
  # NEW: storage = GridFSStorage(db)
  #      file_id = await storage.upload_bytes(data, "files", destination)
  ```

- [ ] Update download operations:
  ```python
  # OLD: data = download_file(url)
  # NEW: file_data = await storage.download_file(file_id, "files")
  ```

---

## PHASE 3: TESTING (Day 4)

### Step 3.1: Unit Tests
- [ ] Update test fixtures to use MongoDB
- [ ] Create test database connection
- [ ] Update all test queries to MongoDB syntax
- [ ] Run unit tests: `pytest tests/ -v`
- [ ] Fix any failing tests

### Step 3.2: Integration Tests
- [ ] Test user creation and authentication
- [ ] Test spec creation and retrieval
- [ ] Test file uploads and downloads
- [ ] Test compliance checks
- [ ] Test RL feedback system
- [ ] Test audit logging

### Step 3.3: API Tests
- [ ] Test all GET endpoints
- [ ] Test all POST endpoints
- [ ] Test all PUT endpoints
- [ ] Test all DELETE endpoints
- [ ] Test error handling
- [ ] Test pagination
- [ ] Test search functionality

### Step 3.4: Performance Tests
- [ ] Test with 1000+ documents
- [ ] Test concurrent requests
- [ ] Monitor memory usage
- [ ] Check query performance
- [ ] Verify indexes are working

---

## PHASE 4: DATA MIGRATION (Day 5)

### Step 4.1: Prepare Data Migration Script
- [ ] Create migration script: `migrate_data.py`
- [ ] Connect to old PostgreSQL database
- [ ] Connect to new MongoDB database
- [ ] Map data types appropriately

### Step 4.2: Migrate Users
```python
# Pseudo-code
for user in old_db.users:
    await new_db.users.insert_one({
        "_id": user.id,
        "username": user.username,
        "email": user.email,
        "password_hash": user.password_hash,
        "created_at": user.created_at,
        # ... other fields
    })
```
- [ ] Verify user count matches
- [ ] Check data integrity

### Step 4.3: Migrate Specs
- [ ] Migrate all specifications
- [ ] Verify relationships (user_id references)
- [ ] Check data completeness

### Step 4.4: Migrate Files
- [ ] Download files from Supabase storage
- [ ] Upload to MongoDB GridFS
- [ ] Update file references in specs
- [ ] Verify file integrity (checksums)

### Step 4.5: Migrate Other Collections
- [ ] Migrate iterations
- [ ] Migrate evaluations
- [ ] Migrate RL feedback
- [ ] Migrate audit logs
- [ ] Migrate compliance checks
- [ ] Migrate workflow runs

### Step 4.6: Verify Migration
- [ ] Compare document counts
- [ ] Spot-check random documents
- [ ] Verify relationships
- [ ] Check file integrity
- [ ] Validate indexes

---

## PHASE 5: DEPLOYMENT (Day 6)

### Step 5.1: Pre-Deployment Checks
- [ ] All tests passing
- [ ] No console errors
- [ ] Performance acceptable
- [ ] Data migration complete
- [ ] Backup of old system ready

### Step 5.2: Deploy to Staging
- [ ] Update staging environment
- [ ] Run full test suite
- [ ] Perform smoke tests
- [ ] Check logs for errors
- [ ] Monitor performance

### Step 5.3: Deploy to Production
- [ ] Schedule maintenance window
- [ ] Notify users of downtime
- [ ] Deploy new code
- [ ] Verify all services running
- [ ] Run health checks
- [ ] Monitor error rates

### Step 5.4: Post-Deployment
- [ ] Monitor application logs
- [ ] Check database performance
- [ ] Verify user access
- [ ] Test critical workflows
- [ ] Collect performance metrics

---

## PHASE 6: CLEANUP (Day 7)

### Step 6.1: Remove Old Code
- [ ] Delete old SQLAlchemy models
- [ ] Delete old Supabase storage code
- [ ] Delete old database.py
- [ ] Delete old storage.py
- [ ] Clean up imports

### Step 6.2: Update Documentation
- [ ] Update README with MongoDB setup
- [ ] Document new API changes
- [ ] Update deployment guide
- [ ] Document data schema
- [ ] Create troubleshooting guide

### Step 6.3: Archive Old System
- [ ] Keep PostgreSQL backup for 30 days
- [ ] Keep Supabase storage backup
- [ ] Document old system configuration
- [ ] Archive old code version

### Step 6.4: Optimize
- [ ] Review and optimize indexes
- [ ] Analyze slow queries
- [ ] Optimize hot paths
- [ ] Set up monitoring alerts

---

## COMMON ISSUES & SOLUTIONS

### Issue: Connection Timeout
**Solution:**
- Check MongoDB Atlas IP whitelist
- Verify MONGODB_URL format
- Test connection with mongosh

### Issue: ObjectId Conversion Errors
**Solution:**
```python
from bson import ObjectId
# Always convert ObjectId to string for JSON responses
result["_id"] = str(result["_id"])
```

### Issue: Async/Await Errors
**Solution:**
- Ensure all database operations use `await`
- Make endpoints `async`
- Use `motor` for async MongoDB driver

### Issue: Data Type Mismatches
**Solution:**
- Validate data before insertion
- Use Pydantic models for validation
- Handle datetime conversions

### Issue: Performance Degradation
**Solution:**
- Create appropriate indexes
- Use projection to limit fields
- Implement pagination
- Use connection pooling

---

## VERIFICATION CHECKLIST

- [ ] All endpoints working
- [ ] Authentication working
- [ ] File uploads working
- [ ] File downloads working
- [ ] Search functionality working
- [ ] Compliance checks working
- [ ] RL feedback working
- [ ] Audit logging working
- [ ] Performance acceptable
- [ ] No error logs
- [ ] Data integrity verified
- [ ] Backups in place

---

## ROLLBACK PLAN

If issues occur:
1. Stop application
2. Restore PostgreSQL from backup
3. Restore Supabase storage from backup
4. Revert code to previous version
5. Restart application
6. Notify users

---

## SUPPORT RESOURCES

- MongoDB Documentation: https://docs.mongodb.com/
- Motor Documentation: https://motor.readthedocs.io/
- PyMongo Documentation: https://pymongo.readthedocs.io/
- MongoDB Atlas: https://www.mongodb.com/cloud/atlas

---

## TIMELINE SUMMARY

- **Day 1:** Preparation & Setup
- **Day 2-3:** Code Migration
- **Day 4:** Testing
- **Day 5:** Data Migration
- **Day 6:** Deployment
- **Day 7:** Cleanup & Optimization

**Total Duration:** 1 week

---

## ESTIMATED EFFORT

- Development: 16-20 hours
- Testing: 8-10 hours
- Data Migration: 4-6 hours
- Deployment: 2-4 hours
- **Total:** 30-40 hours

---

## SUCCESS CRITERIA

✓ All tests passing
✓ All endpoints functional
✓ Data migrated successfully
✓ Performance acceptable
✓ No data loss
✓ Users can access system
✓ Monitoring in place
