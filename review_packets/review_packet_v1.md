# REVIEW PACKET V1

## 1. ENTRY POINT

**Frontend entry:**
Path: N/A (Backend-only system)

**Backend entry:**
Path: `backend/app/main.py`

System starts via FastAPI server on port 8000. Main router includes `/api/v1/generate` endpoint which triggers canonical execution flow.

## 2. CORE EXECUTION FLOW (MAX 3 FILES ONLY)

**File 1:**
Path: `backend/app/api/generate.py`
What it does: Receives POST /api/v1/generate request, validates input, creates CoreBucketCanonicalOrchestrator, returns GenerateResponse with export URLs.

**File 2:**
Path: `backend/app/core_bucket_pipeline.py`
What it does: Orchestrates Core→Bucket→PromptRunner→Geometry→Bucket flow, generates GLB/STL/STEP exports, stores artifacts, writes trace logs.

**File 3:**
Path: `backend/app/prompt_runner_adapter.py`
What it does: Calls platform_adapter.run_from_platform() as execution authority, converts PromptInstruction to spec_json, returns deterministic response.

## 3. LIVE FLOW (REAL EXECUTION)

**User action:**
POST /api/v1/generate with JSON body containing user_id, prompt, city

**System flow:**
Frontend → API (generate.py) → Core (CoreBucketCanonicalOrchestrator) → Bucket (trace logging) → Prompt Runner Adapter (platform_adapter.process) → Design Engine (GLB generation) → Bucket (artifact storage) → Response

**REAL RESPONSE JSON:**
```json
{
  "spec_id": "spec_f969698b775e",
  "spec_json": {
    "design_type": "house",
    "city": "Pune",
    "style": "modern",
    "dimensions": {
      "width": 10.0,
      "length": 10.0,
      "height": 3.0
    },
    "units": "meters",
    "stories": 1,
    "rooms": [],
    "objects": [
      {"type": "wall", "id": "walls", "count": 4}
    ],
    "metadata": {
      "execution_authority": "platform_adapter",
      "prompt_runner_module": "architecture",
      "prompt_runner_intent": "design_creation",
      "deterministic_hash": "68808e9a979771d4",
      "bucket_trace_id": "core_bucket_spec_f969698b775e",
      "canonical_flow": "core->bucket->prompt_runner_adapter->design_engine_geometry->bucket->core",
      "export_urls": {
        "glb": "/api/v1/files/geometry/69ca0738e964d6ba4ed2dbe9",
        "stl": "/api/v1/files/geometry/69ca0739e964d6ba4ed2dc41",
        "step": "/api/v1/files/geometry/69ca0739e964d6ba4ed2dc43"
      }
    }
  },
  "preview_url": "/api/v1/files/geometry/69ca0738e964d6ba4ed2dbe9",
  "estimated_cost": 2268000.0,
  "compliance_check_id": "check_spec_f969698b775e",
  "created_at": "2026-03-30T05:16:41.315898Z",
  "spec_version": 1,
  "user_id": "user_003",
  "city": "Pune",
  "lm_provider": "platform_adapter",
  "generation_time_ms": 137804,
  "export_urls": {
    "glb": "/api/v1/files/geometry/69ca0738e964d6ba4ed2dbe9",
    "stl": "/api/v1/files/geometry/69ca0739e964d6ba4ed2dc41",
    "step": "/api/v1/files/geometry/69ca0739e964d6ba4ed2dc43"
  },
  "glb_url": "/api/v1/files/geometry/69ca0738e964d6ba4ed2dbe9",
  "stl_url": "/api/v1/files/geometry/69ca0739e964d6ba4ed2dc41",
  "step_url": "/api/v1/files/geometry/69ca0739e964d6ba4ed2dc43"
}
```

## 4. WHAT WAS BUILT IN THIS TASK

**Added:**
* `backend/app/prompt_runner_adapter.py` - Day 1 canonical adapter using platform_adapter.py
* `platform_adapter.py` - Siddhesh's Prompt Runner (root level)
* `plugins/architecture/plugin.json` - Architecture domain plugin
* `backend/app/core_bucket_pipeline.py` - Canonical orchestrator with export pipeline
* `CANONICAL_EXECUTION_FLOW.md` - Day 3 execution documentation
* `EXPORT_PIPELINE.md` - Day 3 export documentation
* `FINAL_INTEGRATION_CONFIRMATION.md` - Day 3 authority confirmation
* `review_packets/review_packet_v1.md` - This file

**Modified:**
* `backend/app/api/generate.py` - Now uses CoreBucketCanonicalOrchestrator instead of direct LM calls
* `backend/app/main.py` - Added static file serving for /static/exports

**Not touched:**
* `backend/app/lm_adapter.py` - Still exists for AI enrichment but not primary execution path
* `backend/app/geometry_generator_real.py` - Still used for GLB generation fallback
* Database layer (MongoDB) - Unchanged
* Authentication system - Unchanged

## 5. FAILURE CASES

**Case 1: Missing prompt or user_id**
Behavior: HTTP 400 error with message "Prompt must be at least 10 characters" or "user_id is required"

**Case 2: Platform adapter unavailable**
Behavior: HTTP 503 error with message "Platform adapter execution failed: [error details]"

**Case 3: Storage failure (both remote and local)**
Behavior: System falls back to local storage, writes to backend/data/geometry_outputs and backend/data/export_outputs, returns local URLs like /static/geometry/spec_*.glb

## 6. PROOF

**Live URL:**
N/A (Local development system)

**Console logs:**
```
backend/data/bucket_traces/core_bucket_spec_f969698b775e.jsonl
```

**Trace stages (5 total):**
1. core_ingress - Request received
2. bucket_request_received - Routed to prompt_runner_adapter
3. prompt_runner_response - provider: groq-llama-3.3-70b, deterministic_hash: 68808e9a979771d4
4. bucket_persist_complete - All 3 artifacts stored (GLB, STL, STEP)
5. core_response_ready - Response returned

**Physical files created:**
* `backend/data/geometry_outputs/spec_f969698b775e.glb` (or remote bucket)
* `backend/data/export_outputs/spec_f969698b775e.stl` (or remote bucket)
* `backend/data/export_outputs/spec_f969698b775e.step` (or remote bucket)
* `backend/data/bucket_traces/core_bucket_spec_f969698b775e.jsonl`

**Verification command:**
```bash
cat backend/data/bucket_traces/core_bucket_spec_f969698b775e.jsonl | jq .
```
