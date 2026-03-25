# Canonical Execution Flow

## Objective
Define and lock the system-wide execution path as:

`User -> Core -> Bucket -> Prompt Runner Adapter -> Design Engine Geometry -> Bucket -> Core`

## Implemented Path
1. User request enters `POST /api/v1/generate`.
2. Core orchestration is executed by `CoreBucketCanonicalOrchestrator` in `backend/app/core_bucket_pipeline.py`.
3. Request payload is routed through Bucket ingress (`BucketRouter.append_trace`).
4. Prompt Runner is invoked only via adapter bridge:
   - `backend/app/prompt_runner_adapter.py`
   - entrypoint contract: `run_from_platform(...)`
5. Prompt Runner response becomes canonical `spec_json`.
6. Design Engine generates canonical geometry (`GLB`) from that spec.
7. Bucket stores `GLB`, `STL`, `STEP`, plus `spec_json` payload.
8. Core returns API response with export URLs.

## Deterministic Controls
- Adapter output includes deterministic hash (`metadata.deterministic_hash`).
- Canonical flow marker is stored in metadata:
  - `metadata.canonical_flow = core->bucket->prompt_runner_adapter->design_engine_geometry->bucket->core`
- Bucket trace logs are written to:
  - `backend/data/bucket_traces/<trace_id>.jsonl`

## Adapter Integration Modes
- Default now: `stub` mode (until Siddhesh repo arrives).
- External mode (when repo is available):
  - `PROMPT_RUNNER_MODE=external`
  - `PROMPT_RUNNER_REPO_PATH=<absolute_path_to_repo>`
  - `PROMPT_RUNNER_MODULE=platform_adapter`
  - `PROMPT_RUNNER_ENTRYPOINT=run_from_platform`

## Files Changed For Canonical Lock
- `backend/app/core_bucket_pipeline.py`
- `backend/app/prompt_runner_adapter.py`
- `backend/app/api/generate.py`

## Detailed Execution Trace

### Request Flow
```
1. POST /api/v1/generate
   ├─ Validate request (GenerateRequest schema)
   ├─ Extract user_id, prompt, city, style, constraints
   └─ Create spec_id = f"spec_{uuid.uuid4().hex[:12]}"

2. CoreBucketCanonicalOrchestrator.execute(spec_id, payload)
   ├─ Create trace_id = f"core_bucket_{spec_id}"
   ├─ BucketRouter.append_trace("core_ingress", {...})
   │  └─ Write to: backend/data/bucket_traces/{trace_id}.jsonl
   │
   ├─ BucketRouter.append_trace("bucket_request_received", {...})
   │
   ├─ PromptRunnerAdapterBridge.run_from_platform(payload)
   │  ├─ [Stub Mode] _build_stub_result(payload)
   │  │  ├─ Detect design_type from prompt
   │  │  ├─ Extract dimensions from prompt/constraints
   │  │  ├─ Build deterministic spec_json
   │  │  └─ Return {spec_json, provider, deterministic_hash}
   │  │
   │  └─ [External Mode] Load external platform_adapter
   │     ├─ Import from PROMPT_RUNNER_REPO_PATH
   │     ├─ Call run_from_platform(payload)
   │     └─ Normalize result to canonical format
   │
   ├─ Validate spec_json structure
   ├─ Add metadata:
   │  ├─ execution_authority = "prompt_runner_adapter"
   │  ├─ routing_authority = "core"
   │  ├─ storage_authority = "bucket"
   │  ├─ deterministic_hash
   │  ├─ bucket_trace_id
   │  └─ canonical_flow marker
   │
   ├─ BucketRouter.append_trace("prompt_runner_response", {...})
   │
   ├─ Generate Geometry:
   │  ├─ _generate_glb(spec_json)
   │  │  ├─ Try: geometry_generator_real.generate_real_glb()
   │  │  └─ Fallback: _fallback_glb() (minimal valid GLB)
   │  │
   │  ├─ _convert_glb_to_stl(glb_bytes, spec_json, spec_id)
   │  │  ├─ Extract dimensions from spec_json
   │  │  ├─ Generate box vertices
   │  │  ├─ Create 12 triangular faces
   │  │  ├─ Calculate normals
   │  │  ├─ Include source GLB hash
   │  │  └─ Return ASCII STL format
   │  │
   │  └─ _convert_glb_to_step(glb_bytes, spec_json, spec_id)
   │     ├─ Extract dimensions from spec_json
   │     ├─ Generate ISO-10303-21 header
   │     ├─ Add source GLB hash metadata
   │     ├─ Add dimension metadata
   │     ├─ Generate CARTESIAN_POINT entries
   │     └─ Return STEP format
   │
   ├─ Store Artifacts:
   │  ├─ For each format (glb, stl, step):
   │  │  ├─ BucketRouter.store_artifact(spec_id, kind, data)
   │  │  │  ├─ Try: upload_to_bucket(geometry_bucket, path, data)
   │  │  │  │  └─ Returns remote URL
   │  │  │  └─ Catch: Write to local fallback
   │  │  │     ├─ backend/data/geometry_outputs/{spec_id}.glb
   │  │  │     ├─ backend/data/export_outputs/{spec_id}.stl
   │  │  │     └─ backend/data/export_outputs/{spec_id}.step
   │  │  └─ Return ArtifactLocation(kind, url, storage_mode, ...)
   │  │
   │  └─ Update spec_json.metadata.export_urls
   │
   ├─ BucketRouter.store_spec_payload(spec_id, spec_json)
   │  ├─ Try: upload_to_bucket(files_bucket, "specs/{spec_id}.json", ...)
   │  └─ Fallback: Write to backend/data/specs/{spec_id}.json
   │
   ├─ BucketRouter.append_trace("bucket_persist_complete", {...})
   │
   └─ BucketRouter.append_trace("core_response_ready", {...})

3. Save to Database (non-blocking)
   ├─ Create user if not exists
   ├─ Insert spec document to MongoDB
   └─ Log errors but don't fail request

4. Return GenerateResponse
   ├─ spec_id
   ├─ spec_json (with all metadata)
   ├─ preview_url (GLB URL)
   ├─ estimated_cost
   ├─ export_urls: {glb, stl, step}
   ├─ glb_url, stl_url, step_url (convenience)
   └─ generation_time_ms, lm_provider, etc.
```

## Error Handling

### Prompt Runner Unavailable
```python
if mode == "external" and runner not loaded:
    raise PromptRunnerUnavailableError(
        "Prompt Runner is configured as external but unavailable"
    )
```
**Recovery**: Falls back to stub mode if mode != "external"

### Invalid spec_json
```python
if not isinstance(spec_json, dict):
    raise PromptRunnerUnavailableError(
        "Prompt Runner adapter response missing valid spec_json"
    )
```
**Recovery**: Request fails with HTTP 503

### Geometry Generation Failure
```python
try:
    return generate_real_glb(spec_json)
except Exception:
    logger.warning("Real geometry generation failed, using fallback")
    return _fallback_glb()  # Minimal valid GLB
```
**Recovery**: Always succeeds with fallback

### Storage Failure
```python
try:
    remote_url = await upload_to_bucket(...)
    return ArtifactLocation(storage_mode="bucket_remote", url=remote_url)
except Exception:
    logger.warning("Bucket upload failed, using local fallback")
    local_path.write_bytes(data)
    return ArtifactLocation(storage_mode="bucket_local_fallback", url=local_url)
```
**Recovery**: Always succeeds with local fallback

### Database Save Failure
```python
try:
    await db.specs.insert_one(spec_data)
except Exception as db_error:
    logger.error("Database save failed: %s", db_error)
    # Continue - don't fail the request
```
**Recovery**: Request succeeds, spec not in DB (can be re-saved)

## Trace Log Interpretation

### Reading Trace Files
```bash
# View trace for a specific spec
cat backend/data/bucket_traces/core_bucket_spec_abc123.jsonl | jq .

# Extract specific stage
cat backend/data/bucket_traces/core_bucket_spec_abc123.jsonl | \
  jq 'select(.stage == "prompt_runner_response")'

# Check execution time
cat backend/data/bucket_traces/core_bucket_spec_abc123.jsonl | \
  jq -r '.timestamp' | head -1  # Start time
cat backend/data/bucket_traces/core_bucket_spec_abc123.jsonl | \
  jq -r '.timestamp' | tail -1  # End time
```

### Trace Stages
1. **core_ingress**: Request received, contains user_id, city, prompt keys
2. **bucket_request_received**: Routed to Prompt Runner adapter
3. **prompt_runner_response**: Spec JSON received, contains provider and hash
4. **bucket_persist_complete**: All artifacts stored, contains URLs
5. **core_response_ready**: Response ready to return

### Example Trace Entry
```json
{
  "timestamp": "2026-01-15T10:30:45.123456Z",
  "trace_id": "core_bucket_spec_abc123",
  "stage": "prompt_runner_response",
  "payload": {
    "provider": "prompt_runner_stub",
    "deterministic_hash": "a1b2c3d4e5f6g7h8",
    "design_type": "apartment"
  }
}
```

## Verification Steps

### 1. Check Trace Logs
```bash
# Should have 5 stages
cat backend/data/bucket_traces/core_bucket_spec_abc123.jsonl | wc -l
# Expected: 5
```

### 2. Verify Artifacts Created
```bash
ls -lh backend/data/geometry_outputs/spec_abc123.glb
ls -lh backend/data/export_outputs/spec_abc123.stl
ls -lh backend/data/export_outputs/spec_abc123.step
```

### 3. Validate Export Files
```bash
# STL should start with "solid bhiv_"
head -1 backend/data/export_outputs/spec_abc123.stl

# STEP should start with "ISO-10303-21;"
head -1 backend/data/export_outputs/spec_abc123.step

# GLB should have glTF header
xxd backend/data/geometry_outputs/spec_abc123.glb | head -1
# Should show: 676c 5446  ("glTF" in hex)
```

### 4. Check Metadata
```bash
# Verify canonical flow marker
cat backend/data/specs/spec_abc123.json | \
  jq '.metadata.canonical_flow'
# Expected: "core->bucket->prompt_runner_adapter->design_engine_geometry->bucket->core"

# Verify export URLs
cat backend/data/specs/spec_abc123.json | \
  jq '.metadata.export_urls'
```

## Debugging

### Enable Debug Logging
```env
# In .env
LOG_LEVEL=DEBUG
DEBUG=true
```

### Check Prompt Runner Mode
```python
# In Python console
from app.prompt_runner_adapter import PromptRunnerAdapterBridge
bridge = PromptRunnerAdapterBridge()
print(f"Mode: {bridge.mode}")
print(f"Repo: {bridge.repo_path}")
```

### Test Stub Mode
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "user_id": "test",
    "prompt": "Test apartment",
    "city": "Mumbai"
  }' | jq '.lm_provider'
# Expected: "prompt_runner_stub"
```

### Test External Mode
```bash
# After setting PROMPT_RUNNER_MODE=external
curl ... | jq '.lm_provider'
# Expected: "platform_adapter" or "prompt_runner_external"
```
