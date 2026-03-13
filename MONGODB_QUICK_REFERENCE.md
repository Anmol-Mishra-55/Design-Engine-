# MONGODB MIGRATION - QUICK REFERENCE SUMMARY

## FILES CREATED

1. **config_mongodb.py** - MongoDB configuration (replaces config.py)
2. **database_mongodb.py** - MongoDB connection & indexes
3. **storage_mongodb.py** - GridFS file storage
4. **models_mongodb.py** - Pydantic document models
5. **examples_mongodb.py** - Example endpoint implementations
6. **MONGODB_MIGRATION_GUIDE.md** - Detailed migration guide
7. **MONGODB_MIGRATION_CHECKLIST.md** - Step-by-step checklist
8. **MONGODB_REQUIREMENTS.txt** - Dependencies to install

## QUICK START (5 MINUTES)

### 1. Install Dependencies
```bash
pip install pymongo==4.6.0 motor==3.3.2 dnspython==2.4.2
```

### 2. Create MongoDB Cluster
- Go to https://www.mongodb.com/cloud/atlas
- Create free cluster
- Create database user
- Whitelist your IP
- Copy connection string

### 3. Update .env
```
MONGODB_URL=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=bhiv_db
```

### 4. Update main.py
```python
from app.database_mongodb import connect_to_mongo, close_mongo_connection

@app.on_event("startup")
async def startup():
    await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)

@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()
```

### 5. Update Endpoints
Convert from SQLAlchemy to MongoDB:
```python
# OLD
user = db.query(User).filter(User.id == user_id).first()

# NEW
db = get_database()
user = await db.users.find_one({"_id": user_id})
```

## KEY DIFFERENCES

| Feature | Supabase | MongoDB |
|---------|----------|---------|
| Database | PostgreSQL | MongoDB |
| ORM | SQLAlchemy | PyMongo/Motor |
| Storage | Supabase Storage | GridFS |
| Connection | Sync | Async (Motor) |
| Queries | SQL | MongoDB Query Language |
| Transactions | ACID | Multi-document ACID |
| Scaling | Vertical | Horizontal |

## COMMON OPERATIONS

### Create
```python
# OLD: db.add(obj); db.commit()
# NEW: await db.collection.insert_one(obj_dict)
```

### Read
```python
# OLD: db.query(Model).filter(...).first()
# NEW: await db.collection.find_one({...})
```

### Update
```python
# OLD: db.query(Model).filter(...).update({...}); db.commit()
# NEW: await db.collection.update_one({"_id": id}, {"$set": {...}})
```

### Delete
```python
# OLD: db.query(Model).filter(...).delete(); db.commit()
# NEW: await db.collection.delete_one({"_id": id})
```

### List
```python
# OLD: db.query(Model).all()
# NEW: await db.collection.find({}).to_list(None)
```

## FILE OPERATIONS

### Upload
```python
storage = GridFSStorage(db)
file_id = await storage.upload_bytes(
    data=file_bytes,
    bucket="geometry",
    destination_path="spec_123.glb",
    content_type="model/gltf-binary"
)
```

### Download
```python
file_data = await storage.download_file(file_id, "geometry")
```

### Delete
```python
await storage.delete_file(file_id, "geometry")
```

## MIGRATION TIMELINE

| Phase | Duration | Tasks |
|-------|----------|-------|
| Preparation | 1 day | Setup MongoDB, backup data, install deps |
| Code Migration | 2 days | Update config, modules, endpoints |
| Testing | 1 day | Unit, integration, API tests |
| Data Migration | 1 day | Migrate users, specs, files |
| Deployment | 1 day | Staging, production, verification |
| Cleanup | 1 day | Remove old code, optimize |

**Total: 1 week**

## CRITICAL STEPS

1. ✅ Backup all data before starting
2. ✅ Test in development first
3. ✅ Make all endpoints async
4. ✅ Create proper indexes
5. ✅ Verify data migration
6. ✅ Test all endpoints
7. ✅ Monitor after deployment

## TROUBLESHOOTING

### Connection Issues
```python
# Test connection
from app.database_mongodb import check_db_connection
health = await check_db_connection()
print(health)
```

### Query Issues
```python
# Use MongoDB query syntax
# Find with filter
await db.collection.find({"field": "value"}).to_list(None)

# Find with regex
await db.collection.find({"field": {"$regex": "pattern"}}).to_list(None)

# Find with comparison
await db.collection.find({"age": {"$gt": 18}}).to_list(None)
```

### Performance Issues
```python
# Create indexes
await db.collection.create_index("field_name")
await db.collection.create_index([("field1", 1), ("field2", -1)])

# Use projection
await db.collection.find({}, {"field1": 1, "field2": 1}).to_list(None)

# Use pagination
await db.collection.find({}).skip(10).limit(10).to_list(None)
```

## RESOURCES

- **MongoDB Atlas:** https://www.mongodb.com/cloud/atlas
- **PyMongo Docs:** https://pymongo.readthedocs.io/
- **Motor Docs:** https://motor.readthedocs.io/
- **MongoDB Query Language:** https://docs.mongodb.com/manual/reference/operator/query/

## SUPPORT

For issues:
1. Check MONGODB_MIGRATION_CHECKLIST.md
2. Review MONGODB_MIGRATION_GUIDE.md
3. Check MongoDB documentation
4. Review example implementations in examples_mongodb.py

## NEXT STEPS

1. Read MONGODB_MIGRATION_CHECKLIST.md for detailed steps
2. Follow MONGODB_MIGRATION_GUIDE.md for implementation
3. Use examples_mongodb.py as reference for endpoint updates
4. Test thoroughly before production deployment
5. Monitor performance after deployment

---

**Status:** Ready for implementation
**Last Updated:** 2024
**Version:** 1.0
