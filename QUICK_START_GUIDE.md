# Quick Start Guide - BHIV Design Engine

## Prerequisites
- Python 3.9+
- MongoDB Atlas account (or local MongoDB)
- Git

## 5-Minute Setup

### Step 1: Clone and Setup Environment (2 min)
```bash
cd Backend
python -m venv .venv
.venv\Scripts\activate  # Windows
# OR
source .venv/bin/activate  # Linux/Mac

pip install -r backend/requirements.txt
```

### Step 2: Configure Environment (1 min)
```bash
cd backend
copy .env.example .env  # Windows
# OR
cp .env.example .env  # Linux/Mac
```

Edit `.env` and set:
```env
# REQUIRED
MONGODB_URL=mongodb+srv://your-connection-string
MONGODB_DATABASE=bhiv_db
JWT_SECRET_KEY=your-secret-key-min-16-chars

# OPTIONAL - Prompt Runner Configuration
PROMPT_RUNNER_MODE=stub  # or 'external' when Siddhesh repo is available
# PROMPT_RUNNER_REPO_PATH=/path/to/siddhesh/repo  # Only for external mode
# PROMPT_RUNNER_MODULE=platform_adapter
# PROMPT_RUNNER_ENTRYPOINT=run_from_platform
```

### Step 3: Start Server (1 min)
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: Verify (1 min)
Open browser to:
- Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

## Test the System

### 1. Get Auth Token
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

### 2. Generate Design
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "user_id": "test_user",
    "prompt": "Modern 2BHK apartment in Mumbai",
    "city": "Mumbai",
    "style": "modern"
  }'
```

### 3. Download Exports
Response will include:
```json
{
  "spec_id": "spec_abc123",
  "export_urls": {
    "glb": "/static/geometry/spec_abc123.glb",
    "stl": "/static/exports/spec_abc123.stl",
    "step": "/static/exports/spec_abc123.step"
  }
}
```

Download via:
- GLB: http://localhost:8000/static/geometry/spec_abc123.glb
- STL: http://localhost:8000/static/exports/spec_abc123.stl
- STEP: http://localhost:8000/static/exports/spec_abc123.step

## Canonical Execution Flow

Every request follows this path:
```
User Request
    ↓
POST /api/v1/generate (Core)
    ↓
CoreBucketCanonicalOrchestrator.execute()
    ↓
BucketRouter.append_trace() [Trace: core_ingress]
    ↓
PromptRunnerAdapterBridge.run_from_platform()
    ↓
[Stub Mode] → _build_stub_result()
[External Mode] → Siddhesh's platform_adapter.run_from_platform()
    ↓
Returns spec_json
    ↓
_generate_glb(spec_json) → GLB bytes
    ↓
_convert_glb_to_stl() → STL bytes
_convert_glb_to_step() → STEP bytes
    ↓
BucketRouter.store_artifact() for each format
    ↓
[Try Remote] upload_to_bucket()
[Fallback] Write to local data/ directory
    ↓
BucketRouter.append_trace() [Trace: bucket_persist_complete]
    ↓
Return GenerateResponse with export URLs
```

## Trace Logs

All executions are logged to:
```
backend/data/bucket_traces/core_bucket_{spec_id}.jsonl
```

Each line is a JSON object with:
- `timestamp`: ISO 8601 timestamp
- `trace_id`: Unique trace identifier
- `stage`: Execution stage name
- `payload`: Stage-specific data

Example stages:
1. `core_ingress` - Request received
2. `bucket_request_received` - Routed to Prompt Runner
3. `prompt_runner_response` - Spec JSON received
4. `bucket_persist_complete` - All artifacts stored
5. `core_response_ready` - Response ready

## Common Issues

### MongoDB Connection Failed
```
Error: ServerSelectionTimeoutError
```
**Fix**:
1. Check MongoDB Atlas cluster is running (not paused)
2. Verify IP whitelist includes your IP
3. Test connection string

### No Valid AI API Keys Warning
```
WARNING: No valid AI API keys configured
```
**Fix**: This is NORMAL in stub mode. System uses deterministic fallback.

### Import Errors
```
ModuleNotFoundError: No module named 'X'
```
**Fix**:
```bash
pip install -r backend/requirements.txt --upgrade
```

### Port Already in Use
```
Error: Address already in use
```
**Fix**:
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9
```

## Switching to External Prompt Runner

When Siddhesh's repository is available:

1. Update `.env`:
```env
PROMPT_RUNNER_MODE=external
PROMPT_RUNNER_REPO_PATH=/absolute/path/to/siddhesh/repo
PROMPT_RUNNER_MODULE=platform_adapter
PROMPT_RUNNER_ENTRYPOINT=run_from_platform
```

2. Restart server

3. Verify provider changed:
```bash
# Check response metadata
curl http://localhost:8000/api/v1/generate ... | jq '.lm_provider'
# Should show: "platform_adapter" instead of "prompt_runner_stub"
```

## File Locations

### Code
- Main entry: `backend/app/main.py`
- Core orchestrator: `backend/app/core_bucket_pipeline.py`
- Prompt Runner adapter: `backend/app/prompt_runner_adapter.py`
- Platform adapter: `backend/app/platform_adapter.py` or root `platform_adapter.py`
- Generate endpoint: `backend/app/api/generate.py`

### Data
- Geometry outputs: `backend/data/geometry_outputs/`
- Export outputs: `backend/data/export_outputs/`
- Trace logs: `backend/data/bucket_traces/`
- Spec payloads: `backend/data/specs/`

### Configuration
- Environment: `backend/.env`
- Settings: `backend/app/config.py`
- Requirements: `backend/requirements.txt`

## Next Steps

1. ✅ System running
2. ✅ Test generate endpoint
3. ✅ Verify exports downloadable
4. 📖 Read [CANONICAL_EXECUTION_FLOW.md](CANONICAL_EXECUTION_FLOW.md)
5. 📖 Read [EXPORT_PIPELINE.md](EXPORT_PIPELINE.md)
6. 📖 Read [FINAL_INTEGRATION_CONFIRMATION.md](FINAL_INTEGRATION_CONFIRMATION.md)

## Support

- Documentation: See [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
- Troubleshooting: See [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md)
- Setup Issues: See [SETUP_COMPLETE.md](SETUP_COMPLETE.md)
