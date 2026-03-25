# Final Integration Confirmation

Date: March 6, 2026

## Authority Model Confirmation
- Prompt Runner is execution authority: **Implemented via adapter bridge**.
- Design Engine is export generator: **Implemented** (`GLB`, `STL`, `STEP`).
- Bucket is storage authority: **Implemented** (remote-first + local fallback).
- Core is routing authority: **Implemented** (canonical orchestrator path).

## Completed Now (Without Siddhesh Repo)
- Canonical orchestration layer created and wired into `/api/v1/generate`.
- Direct LM generation path removed from generation endpoint.
- Prompt Runner called only through adapter contract (`run_from_platform`).
- Export pipeline activated with API response URLs for `GLB`, `STL`, `STEP`.
- Static export serving enabled (`/static/geometry`, `/static/exports`).
- Canonical/bucket tracing enabled (`backend/data/bucket_traces`).

## Pending Until Siddhesh Repo Handoff
- Switch adapter from `stub` mode to `external` mode.
- Point to Siddhesh `platform_adapter.py` and validate live `run_from_platform(...)` behavior.
- Run final end-to-end verification with Siddhesh prompt runner outputs in deployment environment.

## Handoff Checklist For Siddhesh Repo Arrival
1. Set env vars:
   - `PROMPT_RUNNER_MODE=external`
   - `PROMPT_RUNNER_REPO_PATH=<repo_path>`
   - `PROMPT_RUNNER_MODULE=platform_adapter`
   - `PROMPT_RUNNER_ENTRYPOINT=run_from_platform`
2. Run generate flow and confirm provider changes from `prompt_runner_stub` to external provider.
3. Confirm deterministic response and exports are still generated and downloadable.
4. Confirm Render deployment endpoint still passes smoke tests.

## Current Status
System is ready for immediate use with deterministic local adapter mode and complete export foundation. External Prompt Runner finalization is the only remaining dependency.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER REQUEST                             │
│                    POST /api/v1/generate                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE (Routing Authority)                    │
│                  CoreBucketCanonicalOrchestrator                 │
│  • Validates request                                             │
│  • Creates spec_id and trace_id                                  │
│  • Orchestrates entire flow                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BUCKET (Storage Authority)                    │
│                         BucketRouter                             │
│  • Trace logging (append_trace)                                  │
│  • Artifact storage (store_artifact)                             │
│  • Remote-first, local-fallback strategy                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              PROMPT RUNNER (Execution Authority)                 │
│                 PromptRunnerAdapterBridge                        │
│  ┌──────────────────────┬──────────────────────┐                │
│  │   Stub Mode          │   External Mode      │                │
│  │  (Default)           │  (When available)    │                │
│  │  • _build_stub_result│  • Load external repo│                │
│  │  • Deterministic     │  • Call run_from_    │                │
│  │  • Fallback safe     │    platform()        │                │
│  └──────────────────────┴──────────────────────┘                │
│  Returns: {spec_json, provider, deterministic_hash}              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              DESIGN ENGINE (Export Generator)                    │
│                  Geometry Generation                             │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ 1. _generate_glb(spec_json)                         │        │
│  │    → GLB bytes (canonical source)                   │        │
│  │                                                      │        │
│  │ 2. _convert_glb_to_stl(glb_bytes, spec_json)        │        │
│  │    → STL bytes (ASCII format)                       │        │
│  │                                                      │        │
│  │ 3. _convert_glb_to_step(glb_bytes, spec_json)       │        │
│  │    → STEP bytes (ISO-10303-21)                      │        │
│  └─────────────────────────────────────────────────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BUCKET (Storage Authority)                    │
│                    Artifact Persistence                          │
│  For each format (GLB, STL, STEP):                              │
│  ┌─────────────────────────────────────────────────────┐        │
│  │ Try: upload_to_bucket(geometry_bucket, ...)         │        │
│  │   → Returns remote URL                              │        │
│  │                                                      │        │
│  │ Catch: Write to local fallback                      │        │
│  │   → backend/data/geometry_outputs/                  │        │
│  │   → backend/data/export_outputs/                    │        │
│  │   → Returns local URL                               │        │
│  └─────────────────────────────────────────────────────┘        │
│  Result: ArtifactLocation(kind, url, storage_mode)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE (Routing Authority)                    │
│                      Response Assembly                           │
│  • Add export URLs to spec_json.metadata                         │
│  • Save to MongoDB (non-blocking)                                │
│  • Return GenerateResponse with all URLs                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         USER RESPONSE                            │
│  {                                                               │
│    "spec_id": "spec_abc123",                                    │
│    "export_urls": {                                             │
│      "glb": "/static/geometry/spec_abc123.glb",                │
│      "stl": "/static/exports/spec_abc123.stl",                 │
│      "step": "/static/exports/spec_abc123.step"                │
│    },                                                            │
│    "lm_provider": "prompt_runner_stub",                        │
│    "generation_time_ms": 234                                    │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## Component Interaction Details

### Core ↔ Bucket
```python
# Core creates orchestrator with bucket
orchestrator = CoreBucketCanonicalOrchestrator()
# Bucket is initialized inside orchestrator
self.bucket = BucketRouter()

# Core uses bucket for tracing
self.bucket.append_trace(trace_id, stage, payload)

# Core uses bucket for storage
artifact = await self.bucket.store_artifact(spec_id, kind, data)
```

### Core ↔ Prompt Runner
```python
# Core creates adapter bridge
self.prompt_runner = PromptRunnerAdapterBridge()

# Core calls adapter
runner_result = await self.prompt_runner.run_from_platform(payload)

# Adapter returns canonical format
{
  "spec_json": {...},
  "provider": "prompt_runner_stub",
  "deterministic_hash": "abc123..."
}
```

### Prompt Runner ↔ External Repo
```python
# Adapter loads external module
if self.repo_path:
    sys.path.insert(0, str(self.repo_path))
module = importlib.import_module(self.module_name)
runner = getattr(module, self.entrypoint)

# Adapter calls external function
result = runner(payload)
if inspect.isawaitable(result):
    result = await result

# Adapter normalizes result
normalized = self._normalize_result(result, payload, provider)
```

### Design Engine ↔ Bucket
```python
# Design Engine generates artifacts
glb_bytes = self._generate_glb(spec_json)
stl_bytes = self._convert_glb_to_stl(glb_bytes, spec_json, spec_id)
step_bytes = self._convert_glb_to_step(glb_bytes, spec_json, spec_id)

# Design Engine stores via Bucket
artifacts = {
    "glb": await self.bucket.store_artifact(spec_id, "glb", glb_bytes),
    "stl": await self.bucket.store_artifact(spec_id, "stl", stl_bytes),
    "step": await self.bucket.store_artifact(spec_id, "step", step_bytes),
}
```

## Testing Procedures

### 1. Unit Tests

**Test Prompt Runner Adapter**:
```python
import pytest
from app.prompt_runner_adapter import PromptRunnerAdapterBridge

@pytest.mark.asyncio
async def test_stub_mode():
    adapter = PromptRunnerAdapterBridge()
    payload = {
        "prompt": "Modern 2BHK apartment",
        "city": "Mumbai",
        "user_id": "test_user"
    }
    result = await adapter.run_from_platform(payload)

    assert "spec_json" in result
    assert "provider" in result
    assert result["provider"] == "prompt_runner_stub"
    assert "deterministic_hash" in result
```

**Test Export Generation**:
```python
from app.core_bucket_pipeline import CoreBucketCanonicalOrchestrator

def test_stl_generation():
    orchestrator = CoreBucketCanonicalOrchestrator()
    spec_json = {
        "dimensions": {"width": 10.0, "length": 15.0, "height": 3.0}
    }
    glb_bytes = orchestrator._generate_glb(spec_json)
    stl_bytes = orchestrator._convert_glb_to_stl(glb_bytes, spec_json, "test_spec")

    stl_text = stl_bytes.decode('utf-8')
    assert stl_text.startswith('solid bhiv_')
    assert 'facet normal' in stl_text
    assert stl_text.strip().endswith('endsolid bhiv_')
```

**Test Bucket Storage**:
```python
import pytest
from app.core_bucket_pipeline import BucketRouter

@pytest.mark.asyncio
async def test_local_fallback():
    bucket = BucketRouter()
    test_data = b"test geometry data"

    artifact = await bucket.store_artifact("test_spec", "glb", test_data)

    assert artifact.kind == "glb"
    assert artifact.url.startswith("/static/geometry/")
    assert artifact.storage_mode in ["bucket_remote", "bucket_local_fallback"]
```

### 2. Integration Tests

**Test Full Generate Flow**:
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_generate_endpoint():
    # Get auth token
    auth_response = client.post("/api/v1/auth/login", json={
        "username": "admin",
        "password": "test_password"
    })
    token = auth_response.json()["access_token"]

    # Generate design
    response = client.post(
        "/api/v1/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": "test_user",
            "prompt": "Modern 2BHK apartment",
            "city": "Mumbai"
        }
    )

    assert response.status_code == 201
    data = response.json()

    # Verify response structure
    assert "spec_id" in data
    assert "export_urls" in data
    assert "glb" in data["export_urls"]
    assert "stl" in data["export_urls"]
    assert "step" in data["export_urls"]

    # Verify files exist
    spec_id = data["spec_id"]
    glb_response = client.get(data["export_urls"]["glb"])
    assert glb_response.status_code == 200

    stl_response = client.get(data["export_urls"]["stl"])
    assert stl_response.status_code == 200

    step_response = client.get(data["export_urls"]["step"])
    assert step_response.status_code == 200
```

**Test Trace Logging**:
```python
import json
from pathlib import Path

def test_trace_logs():
    # Generate design (from previous test)
    spec_id = "spec_abc123"  # From generate response
    trace_id = f"core_bucket_{spec_id}"

    # Read trace file
    trace_file = Path(f"backend/data/bucket_traces/{trace_id}.jsonl")
    assert trace_file.exists()

    # Parse trace entries
    stages = []
    with open(trace_file) as f:
        for line in f:
            entry = json.loads(line)
            stages.append(entry["stage"])

    # Verify all stages present
    expected_stages = [
        "core_ingress",
        "bucket_request_received",
        "prompt_runner_response",
        "bucket_persist_complete",
        "core_response_ready"
    ]
    assert stages == expected_stages
```

### 3. End-to-End Tests

**Test Complete User Journey**:
```bash
#!/bin/bash
# e2e_test.sh

set -e

echo "Starting E2E test..."

# 1. Health check
echo "1. Checking health..."
curl -f http://localhost:8000/health || exit 1

# 2. Login
echo "2. Logging in..."
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"test"}' | jq -r '.access_token')

if [ "$TOKEN" == "null" ]; then
  echo "Login failed"
  exit 1
fi

# 3. Generate design
echo "3. Generating design..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "user_id": "e2e_test",
    "prompt": "Modern 2BHK apartment in Mumbai",
    "city": "Mumbai"
  }')

SPEC_ID=$(echo $RESPONSE | jq -r '.spec_id')
if [ "$SPEC_ID" == "null" ]; then
  echo "Generate failed"
  echo $RESPONSE | jq .
  exit 1
fi

echo "Generated spec_id: $SPEC_ID"

# 4. Download exports
echo "4. Downloading exports..."
GLB_URL=$(echo $RESPONSE | jq -r '.export_urls.glb')
STL_URL=$(echo $RESPONSE | jq -r '.export_urls.stl')
STEP_URL=$(echo $RESPONSE | jq -r '.export_urls.step')

curl -f -o "test_${SPEC_ID}.glb" "http://localhost:8000${GLB_URL}" || exit 1
curl -f -o "test_${SPEC_ID}.stl" "http://localhost:8000${STL_URL}" || exit 1
curl -f -o "test_${SPEC_ID}.step" "http://localhost:8000${STEP_URL}" || exit 1

# 5. Validate files
echo "5. Validating files..."
if [ ! -s "test_${SPEC_ID}.glb" ]; then
  echo "GLB file is empty"
  exit 1
fi

if ! head -1 "test_${SPEC_ID}.stl" | grep -q "solid bhiv_"; then
  echo "STL file invalid"
  exit 1
fi

if ! head -1 "test_${SPEC_ID}.step" | grep -q "ISO-10303-21"; then
  echo "STEP file invalid"
  exit 1
fi

# 6. Check trace logs
echo "6. Checking trace logs..."
TRACE_FILE="backend/data/bucket_traces/core_bucket_${SPEC_ID}.jsonl"
if [ ! -f "$TRACE_FILE" ]; then
  echo "Trace file missing"
  exit 1
fi

STAGE_COUNT=$(wc -l < "$TRACE_FILE")
if [ $STAGE_COUNT -ne 5 ]; then
  echo "Expected 5 trace stages, got $STAGE_COUNT"
  exit 1
fi

echo "✅ E2E test passed!"
echo "Files generated:"
ls -lh test_${SPEC_ID}.*
```

### 4. Performance Tests

**Load Test**:
```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import requests

def generate_design(token, user_id):
    start = time.time()
    response = requests.post(
        "http://localhost:8000/api/v1/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": user_id,
            "prompt": "Modern apartment",
            "city": "Mumbai"
        }
    )
    duration = time.time() - start
    return response.status_code, duration

def load_test(num_requests=100, concurrency=10):
    # Get token
    auth_response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"username": "admin", "password": "test"}
    )
    token = auth_response.json()["access_token"]

    # Run concurrent requests
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(generate_design, token, f"user_{i}")
            for i in range(num_requests)
        ]
        results = [f.result() for f in futures]

    # Analyze results
    success_count = sum(1 for status, _ in results if status == 201)
    durations = [d for _, d in results]

    print(f"Total requests: {num_requests}")
    print(f"Successful: {success_count}")
    print(f"Failed: {num_requests - success_count}")
    print(f"Avg duration: {sum(durations)/len(durations):.2f}s")
    print(f"Min duration: {min(durations):.2f}s")
    print(f"Max duration: {max(durations):.2f}s")

if __name__ == "__main__":
    load_test(num_requests=100, concurrency=10)
```

## Deployment Checklist

### Pre-Deployment
- [ ] All unit tests passing
- [ ] All integration tests passing
- [ ] E2E test passing
- [ ] Load test results acceptable (< 2s avg response time)
- [ ] Environment variables configured
- [ ] MongoDB connection tested
- [ ] Storage buckets created and accessible
- [ ] Static file serving configured

### Deployment Steps
1. [ ] Set environment to production: `ENVIRONMENT=production`
2. [ ] Configure strong JWT secret (min 32 chars)
3. [ ] Set MongoDB production connection string
4. [ ] Configure remote storage (if using)
5. [ ] Set up monitoring (Sentry DSN)
6. [ ] Enable metrics: `ENABLE_METRICS=true`
7. [ ] Configure CORS origins for production domains
8. [ ] Set up SSL/TLS certificates
9. [ ] Configure rate limiting
10. [ ] Set up backup strategy for MongoDB

### Post-Deployment
- [ ] Run smoke tests on production
- [ ] Verify health endpoint: `GET /health`
- [ ] Test generate endpoint with real request
- [ ] Verify exports are downloadable
- [ ] Check trace logs are being written
- [ ] Monitor error rates in Sentry
- [ ] Check Prometheus metrics
- [ ] Verify MongoDB connections stable
- [ ] Test failover to local storage
- [ ] Document production URLs

### Monitoring
- [ ] Set up alerts for:
  - High error rate (> 5%)
  - Slow response time (> 5s)
  - MongoDB connection failures
  - Storage failures
  - High memory usage (> 80%)
  - High CPU usage (> 80%)
- [ ] Dashboard showing:
  - Requests per minute
  - Average response time
  - Error rate
  - Storage mode distribution (remote vs local)
  - Provider distribution (stub vs external)

## Rollback Procedure

If issues occur in production:

1. **Immediate**: Switch to previous version
   ```bash
   git checkout <previous-tag>
   docker-compose up -d
   ```

2. **Verify**: Check health endpoint
   ```bash
   curl https://api.production.com/health
   ```

3. **Monitor**: Watch error rates return to normal

4. **Investigate**: Review logs and traces
   ```bash
   tail -f logs/bhiv.log
   cat backend/data/bucket_traces/*.jsonl | jq 'select(.stage == "error")'
   ```

5. **Fix**: Address root cause in development

6. **Re-deploy**: After thorough testing
