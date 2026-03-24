# Quick Fix - 3 Steps to Resolve All Issues

## Step 1: Install Missing Dependencies
```bash
cd Backend
.venv\Scripts\activate
pip install -r backend/requirements.txt --upgrade
```

**What this fixes:**
- ✅ stable-baselines3 warning
- ✅ torch, transformers, trl dependencies

---

## Step 2: Verify MongoDB Connection
```bash
# Check if MongoDB Atlas cluster is running
# Go to: https://cloud.mongodb.com
# Look for green status on cluster0

# If paused, click "Resume"
# Wait 2-3 minutes for it to start
```

**What this fixes:**
- ✅ MongoDB connection timeout error

---

## Step 3: Restart the Server
```bash
# Kill existing server (Ctrl+C if running)

# Restart
cd Backend
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

**What this fixes:**
- ✅ MongoDB index creation error
- ✅ All initialization issues

---

## Verification

After restart, you should see in logs:
```
✅ Connected to MongoDB: bhiv_db
✅ MongoDB indexes created successfully
```

And the "No valid AI API keys" message is **NORMAL** - it means the system is using stub mode (works fine).

---

## If Still Having Issues

### MongoDB Connection Still Timing Out?
1. Check IP whitelist in MongoDB Atlas
2. Add your IP: https://cloud.mongodb.com → Network Access → IP Whitelist
3. Or use `0.0.0.0/0` for development (less secure)

### Still Getting Index Error?
1. Make sure you restarted the server after code changes
2. Check that `database_mongodb.py` was updated correctly
3. Try: `pip install motor>=3.3.0 --upgrade`

### stable-baselines3 Still Not Found?
```bash
# Force reinstall
pip uninstall stable-baselines3 -y
pip install stable-baselines3==2.0.0 torch==2.0.0
```

---

## Summary of Changes Made

| Issue | File | Fix |
|-------|------|-----|
| Index creation error | `database_mongodb.py` | Changed `create_index("field")` to `create_index([("field", ASCENDING)])` |
| stable-baselines3 warning | `requirements.txt` | Added `stable-baselines3>=2.0.0` and dependencies |
| Import error handling | `train_ppo.py` | Improved error message with installation instructions |

All changes are backward compatible and don't affect existing functionality.
