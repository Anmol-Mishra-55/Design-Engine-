# Troubleshooting Guide - Backend Issues

## Issue 1: MongoDB Index Creation Error
**Error:** `'int' object has no attribute 'in_transaction'`

### Root Cause
The `create_index()` method in Motor (async MongoDB driver) was being called with incorrect argument format. Motor expects field specifications as a list of tuples, not positional arguments.

### Solution Applied
✅ **FIXED** - Updated `database_mongodb.py` line 113+

Changed from:
```python
await db.users.create_index("username", unique=True)  # ❌ Wrong
```

To:
```python
await db.users.create_index([("username", ASCENDING)], unique=True)  # ✅ Correct
```

### Verification
After restart, you should see:
```
✅ MongoDB indexes created successfully
```

---

## Issue 2: MongoDB Connection Timeout
**Error:** `TimeoutError: [WinError 10060] A connection attempt failed...`

### Root Cause
MongoDB Atlas cluster is unreachable. This is a **network/infrastructure issue**, not a code bug.

### Possible Causes
1. MongoDB Atlas cluster is paused or stopped
2. Network connectivity issue (firewall, VPN, ISP)
3. IP whitelist not configured in MongoDB Atlas
4. Connection string is incorrect

### Solutions

#### Option A: Check MongoDB Atlas Status
1. Go to https://cloud.mongodb.com
2. Login to your account
3. Check if cluster `cluster0` is running (should show green status)
4. If paused, click "Resume" to start it

#### Option B: Verify IP Whitelist
1. In MongoDB Atlas, go to **Network Access** → **IP Whitelist**
2. Add your current IP address or use `0.0.0.0/0` (allows all IPs - for development only)
3. Wait 5-10 minutes for changes to propagate

#### Option C: Test Connection Manually
```bash
# Test if MongoDB is reachable
python -c "
import pymongo
try:
    client = pymongo.MongoClient('mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?retryWrites=true&w=majority', serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print('✅ MongoDB connection successful')
except Exception as e:
    print(f'❌ Connection failed: {e}')
"
```

#### Option D: Use Local MongoDB (Development)
If you want to use local MongoDB instead:
1. Install MongoDB Community Edition
2. Start MongoDB service
3. Update `.env`:
```
MONGODB_URL=mongodb://localhost:27017
MONGODB_DATABASE=bhiv_db
```

---

## Issue 3: "No valid AI API keys found, will use template fallback"
**Message:** `No valid AI API keys found, will use template fallback`

### Root Cause
This is **INTENTIONAL BEHAVIOR**, not an error. The system is designed to work without external AI services.

### Explanation
- When external Prompt Runner is unavailable, the system falls back to deterministic stub mode
- This allows the API to function without external dependencies
- Designs are generated using template-based logic instead of real AI

### How It Works
1. **Stub Mode** (Current): Uses deterministic templates based on prompt analysis
2. **External Mode** (When available): Calls real AI service via `platform_adapter.run_from_platform()`

### To Enable Real AI Integration
Set these environment variables in `.env`:
```
PROMPT_RUNNER_MODE=external
PROMPT_RUNNER_REPO_PATH=/path/to/siddhesh/repo
PROMPT_RUNNER_MODULE=platform_adapter
PROMPT_RUNNER_ENTRYPOINT=run_from_platform
```

Or configure specific AI providers:
```
LM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# OR
LM_PROVIDER=yotta
YOTTA_API_KEY=...
YOTTA_URL=https://api.yotta.ai/v1/inference
```

### Current Status
✅ **System is working correctly** - Using deterministic stub mode as fallback

---

## Issue 4: "stable-baselines3 not available"
**Error:** `Warning: stable-baselines3 not available: No module named 'stable_baselines3'`

### Root Cause
The `stable-baselines3` package is not installed in your virtual environment.

### Solution Applied
✅ **FIXED** - Added to `requirements.txt`:
```
stable-baselines3>=2.0.0
torch>=2.0.0
transformers>=4.30.0
trl>=0.7.0
```

### Installation Steps
```bash
# Activate virtual environment
cd Backend
.venv\Scripts\activate

# Install updated requirements
pip install -r backend/requirements.txt

# Verify installation
python -c "import stable_baselines3; print('✅ stable-baselines3 installed')"
```

### Verification
After installation, you should see:
```
✅ stable-baselines3 installed
```

---

## Quick Fix Checklist

- [ ] **MongoDB Indexes**: Restart the server - should now create indexes without error
- [ ] **MongoDB Connection**:
  - [ ] Check MongoDB Atlas cluster is running
  - [ ] Verify IP whitelist includes your IP
  - [ ] Test connection manually
- [ ] **AI API Keys**: This is normal - system works in stub mode
- [ ] **stable-baselines3**: Run `pip install -r backend/requirements.txt`

---

## Testing After Fixes

### 1. Test MongoDB Connection
```bash
curl http://localhost:8000/api/v1/health/db
```

Expected response:
```json
{
  "status": "healthy",
  "database": "mongodb",
  "latency_ms": 45.23
}
```

### 2. Test Design Generation
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Design a modern 3-bedroom apartment",
    "user_id": "test_user",
    "city": "Mumbai"
  }'
```

### 3. Check Logs
```bash
# View recent logs
tail -f logs/bhiv.log

# Look for these success messages:
# ✅ MongoDB connected successfully
# ✅ MongoDB indexes created successfully
# Prompt Runner adapter loaded in external mode (or stub mode)
```

---

## Environment Variables Reference

### MongoDB
```
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=bhiv_db
```

### AI/LM Configuration
```
LM_PROVIDER=local|yotta|openai
OPENAI_API_KEY=sk-...
YOTTA_API_KEY=...
YOTTA_URL=https://api.yotta.ai/v1/inference
```

### Prompt Runner
```
PROMPT_RUNNER_MODE=stub|external
PROMPT_RUNNER_REPO_PATH=/path/to/repo
PROMPT_RUNNER_MODULE=platform_adapter
PROMPT_RUNNER_ENTRYPOINT=run_from_platform
```

---

## Support

If issues persist:
1. Check logs: `logs/bhiv.log`
2. Verify all environment variables in `.env`
3. Ensure virtual environment is activated
4. Try restarting the server
5. Check MongoDB Atlas dashboard for cluster status
