# Execution Flow

**Project:** Design Engine API
**State:** Post Production Readiness Sprint (Tasks 1–4 complete)
**Version:** 1.0

---

## Overview

This document traces a single design generation request from the moment it
arrives at the server to the moment bucket artifact URLs are returned to the
caller. It shows every component touched, every log line emitted, and every
trace_id propagation point.

Architecture = components.
This document = runtime.

---

## Entry Point

```
POST /api/v1/core/generate
Content-Type: application/json
X-Trace-ID: <optional — generated if absent>

{
  "prompt": "Design a 3BHK apartment with modern kitchen",
  "city": "Mumbai",
  "style": "modern",
  "user_id": "user_123"
}
```

`POST /api/v1/generate` is permanently blocked (returns 403).
The only valid entry point is `/api/v1/core/generate` via `app/api/core_entry.py`.

---

## Step-by-Step Flow

### Step 1 — CORS Middleware

```
CORSMiddleware
  · Validates Origin header against settings.CORS_ORIGINS
  · Adds Access-Control-Allow-* headers to response
  · Passes request to next middleware
```

No logging. No trace context yet.

---

### Step 2 — Trace Context Middleware

```
TraceContextMiddleware.dispatch()
  app/middleware/trace_context.py

  trace_id = request.headers.get("X-Trace-ID")
           or str(uuid.uuid4())
           → e.g. "a3f7c2d1-8b4e-4f9a-b2c1-7d3e5f8a9b0c"

  set_trace_context(
      trace_id     = "a3f7c2d1-...",
      execution_id = "",
      pipeline_stage = "http_request"
  )
  → stored in threading.local()

  [All subsequent log lines in this thread now carry trace_id automatically]
```

Log emitted:
```json
{
  "timestamp": "2026-07-09T16:11:18.123Z",
  "level": "INFO",
  "logger": "app.main",
  "message": "POST /api/v1/core/generate from 127.0.0.1",
  "trace_id": "a3f7c2d1-8b4e-4f9a-b2c1-7d3e5f8a9b0c",
  "pipeline_stage": "http_request"
}
```

---

### Step 3 — Request Logging Middleware

```
log_requests (inline middleware in main.py)

  Logs: "POST /api/v1/core/generate from 127.0.0.1"
  Calls next handler
  Logs: "OK POST /api/v1/core/generate -> 200 (4.844s)"
```

trace_id is in both log lines automatically via JsonFormatter.

---

### Step 4 — Route Handler

```
app/api/core_entry.py
  POST /api/v1/core/generate

  · Validates JWT token (HTTPBearer)
  · Extracts prompt, city, style, user_id from request body
  · Generates spec_id = "spec_{uuid.hex[:8]}"
    e.g. "spec_47d77f94"
  · Builds payload dict
  · Calls CoreBucketCanonicalOrchestrator().execute(spec_id, payload)
```

---

### Step 5 — Core Bucket Orchestrator: Ingress

```
CoreBucketCanonicalOrchestrator.execute()
  app/core_bucket_pipeline.py

  trace_id = "core_bucket_spec_47d77f94"

  BucketRouter._append_trace(trace_id, "core_ingress", {
      "spec_id": "spec_47d77f94",
      "user_id": "user_123",
      "city": "Mumbai"
  })
  → writes to data/bucket_traces/core_bucket_spec_47d77f94.jsonl
```

Log emitted:
```json
{
  "message": "Request stored in bucket: https://bhiv-bucket.onrender.com/...",
  "trace_id": "a3f7c2d1-...",
  "pipeline_stage": "http_request"
}
```

---

### Step 6 — Bucket: Store Request

```
BucketRouter.store_request(trace_id, request_payload)

  payload_bytes = json.dumps(request_payload).encode("utf-8")
  bucket_path   = "requests/core_bucket_spec_47d77f94.json"

  upload_to_bucket("files", bucket_path, payload_bytes)
  → returns "https://bhiv-bucket.onrender.com/bucket/artifact/{uuid}"

  _append_trace(trace_id, "bucket_request_stored", {
      "bucket_path": "requests/...",
      "url": "https://..."
  })
```

---

### Step 7 — Prompt Runner Adapter

```
PromptRunnerAdapterBridge.run_from_platform(data)
  app/prompt_runner_adapter.py

  platform_adapter.process(prompt)
  → calls platform_adapter.py (Siddhesh's module)
  → returns {module, intent, topic, tasks, ...}

  extract_semantics(prompt)
  → detects BHK type, city, style from prompt text
  → returns {bhk_type: "3BHK", city: "Mumbai", style: "modern"}

  _instruction_to_spec_json(instruction, semantics)
  → builds spec_json dict:
    {
      "design_type": "apartment",
      "bhk_type": "3BHK",
      "city": "Mumbai",
      "style": "modern",
      "rooms": ["master_bedroom", "bedroom_2", "bedroom_3",
                "hall", "dining", "kitchen", ...],
      "dimensions": {"width": 11.0, "length": 10.5, "height": 2.8},
      "stories": 1
    }

  Returns {spec_json, provider, deterministic_hash}
```

Log emitted:
```json
{
  "message": "Prompt runner response received",
  "trace_id": "a3f7c2d1-...",
  "pipeline_stage": "http_request"
}
```

---

### Step 8 — Orchestrator: Metadata Enrichment

```
CoreBucketCanonicalOrchestrator.execute() (continued)

  spec_json["metadata"] = {
      "execution_authority": "prompt_runner_adapter",
      "routing_authority":   "core",
      "storage_authority":   "bucket",
      "deterministic_hash":  "8e0f065b6c769a47",
      "bucket_trace_id":     "core_bucket_spec_47d77f94",
      "canonical_flow":      "core->bucket->prompt_runner->geometry->bucket->core"
  }

  _append_trace(trace_id, "prompt_runner_response", {
      "provider": "prompt_runner_adapter",
      "design_type": "apartment",
      "rooms_count": 9
  })
```

---

### Step 9 — GLB Generation

```
CoreBucketCanonicalOrchestrator._generate_glb(spec_json, prompt, spec_id)

  Chain (first success wins):

  1. Meshy AI
     if settings.MESHY_API_KEY and len > 10:
       generate_3d_with_meshy(prompt, dimensions)
       → if GLB <= 12 MB: return (glb_bytes, "meshy_ai")
       → if GLB > 12 MB: store external URL in metadata, fall through

  2. Tripo AI
     if settings.TRIPO_API_KEY and len > 10:
       generate_3d_with_tripo(prompt, dimensions, tripo_key)
       → if GLB <= 12 MB: return (glb_bytes, "tripo_ai")

  3. geometry_generator_real (always fits Bucket)
     generate_real_glb(spec_json)
     → builds per-room meshes with thick walls and door gaps
     → returns (glb_bytes, "geometry_generator_real")
     → raises RuntimeError on failure (no dummy meshes)
```

Log emitted:
```json
{
  "message": "GLB generated via: geometry_generator_real (6624 bytes)",
  "trace_id": "a3f7c2d1-..."
}
```

---

### Step 10 — STL and STEP Generation

```
_rooms_to_stl(spec_json, spec_id, glb_bytes)
  · One ASCII STL solid per room
  · Rooms spatially separated by WALL_T gap
  · source_hash = sha256(glb_bytes)[:16]

_rooms_to_step(spec_json, spec_id, glb_bytes)
  · One CARTESIAN_POINT block per room corner
  · ISO-10303-21 format
  · source_hash embedded in DESCRIPTIVE_REPRESENTATION_ITEM
```

---

### Step 11 — Bucket: Store All Artifacts

```
BucketRouter.store_artifact(spec_id, "glb", glb_bytes)
  → upload_to_bucket("geometry", "spec_47d77f94.glb", glb_bytes)
  → returns ArtifactLocation(url="https://bhiv-bucket.onrender.com/...")

BucketRouter.store_artifact(spec_id, "stl", stl_bytes)
  → upload_to_bucket("geometry", "exports/spec_47d77f94.stl", stl_bytes)
  → returns ArtifactLocation(url="https://bhiv-bucket.onrender.com/...")

BucketRouter.store_artifact(spec_id, "step", step_bytes)
  → upload_to_bucket("geometry", "exports/spec_47d77f94.step", step_bytes)
  → returns ArtifactLocation(url="https://bhiv-bucket.onrender.com/...")

BucketRouter.store_spec_payload(spec_id, spec_json)
  → upload_to_bucket("files", "specs/spec_47d77f94.json", payload_bytes)
  → returns {"url": "https://...", "bucket_path": "specs/..."}
```

Log emitted per artifact:
```json
{
  "message": "Artifact stored in bucket: spec_47d77f94.glb -> https://...",
  "trace_id": "a3f7c2d1-..."
}
```

---

### Step 12 — Trace Completion

```
_append_trace(trace_id, "bucket_persist_complete", {
    "artifacts": {
        "glb":  {"url": "https://...", "kind": "glb"},
        "stl":  {"url": "https://...", "kind": "stl"},
        "step": {"url": "https://...", "kind": "step"},
        "spec": {"url": "https://...", "kind": "spec"}
    }
})

_append_trace(trace_id, "core_response_ready", {"spec_id": "spec_47d77f94"})
```

Trace file `data/bucket_traces/core_bucket_spec_47d77f94.jsonl` now contains
5 entries: `core_ingress`, `bucket_request_stored`, `prompt_runner_response`,
`bucket_persist_complete`, `core_response_ready`.

---

### Step 13 — Response

```
CoreBucketCanonicalOrchestrator.execute() returns:

CanonicalExecutionResult(
    spec_json          = {...},
    provider           = "geometry_generator_real",
    deterministic_hash = "8e0f065b6c769a47",
    bucket_trace_id    = "core_bucket_spec_47d77f94",
    artifacts = {
        "glb":  ArtifactLocation(url="https://bhiv-bucket.onrender.com/..."),
        "stl":  ArtifactLocation(url="https://bhiv-bucket.onrender.com/..."),
        "step": ArtifactLocation(url="https://bhiv-bucket.onrender.com/..."),
        "spec": ArtifactLocation(url="https://bhiv-bucket.onrender.com/...")
    }
)
```

Route handler serialises to HTTP 200:
```json
{
  "spec_id": "spec_47d77f94",
  "status": "success",
  "artifact_urls": {
    "glb":  "https://bhiv-bucket.onrender.com/bucket/artifact/...",
    "stl":  "https://bhiv-bucket.onrender.com/bucket/artifact/...",
    "step": "https://bhiv-bucket.onrender.com/bucket/artifact/...",
    "spec": "https://bhiv-bucket.onrender.com/bucket/artifact/..."
  },
  "trace_id": "core_bucket_spec_47d77f94"
}
```

---

### Step 14 — Trace Context Cleanup

```
TraceContextMiddleware.dispatch() finally block:
  clear_trace_context()
  → _ctx.trace_id = ""
  → _ctx.execution_id = ""
  → _ctx.pipeline_stage = ""

Response header added:
  X-Trace-ID: a3f7c2d1-8b4e-4f9a-b2c1-7d3e5f8a9b0c
```

---

## Complete Flow Summary

```
HTTP POST /api/v1/core/generate
    │
    ▼
CORSMiddleware
    │
    ▼
TraceContextMiddleware          ← trace_id injected into all logs
    │  X-Trace-ID: uuid
    ▼
log_requests middleware         ← logs method + path + status
    │
    ▼
JWT validation (HTTPBearer)
    │
    ▼
core_entry.py route handler
    │  spec_id = "spec_47d77f94"
    ▼
CoreBucketCanonicalOrchestrator.execute()
    │
    ├─ BucketRouter.store_request()
    │      → upload request JSON to Bucket
    │      → append "core_ingress" to trace JSONL
    │
    ├─ PromptRunnerAdapterBridge.run_from_platform()
    │      → platform_adapter.process(prompt)
    │      → extract_semantics(prompt)
    │      → _instruction_to_spec_json()
    │      → returns spec_json
    │
    ├─ _generate_glb()
    │      → Meshy AI (if key configured)
    │      → Tripo AI (if key configured)
    │      → geometry_generator_real (always available)
    │      → returns (glb_bytes, provider)
    │
    ├─ _rooms_to_stl()  → stl_bytes
    ├─ _rooms_to_step() → step_bytes
    │
    ├─ BucketRouter.store_artifact("glb")  → glb URL
    ├─ BucketRouter.store_artifact("stl")  → stl URL
    ├─ BucketRouter.store_artifact("step") → step URL
    ├─ BucketRouter.store_spec_payload()   → spec URL
    │
    └─ append "bucket_persist_complete" + "core_response_ready" to trace
    │
    ▼
HTTP 200 response
    {artifact_urls: {glb, stl, step, spec}}
    X-Trace-ID: a3f7c2d1-...
    │
    ▼
TraceContextMiddleware finally: clear_trace_context()
```

---

## Replay Flow

When `POST /api/v1/replay/{spec_id}` is called, the flow is identical from
Step 5 onwards, with two differences:

1. The request payload is reconstructed from the stored trace file
   (`data/bucket_traces/core_bucket_{spec_id}.jsonl`) rather than from
   an HTTP request body.

2. A new `replay_spec_id` is generated (`replay_{spec_id[:12]}_{uuid[:8]}`)
   so the replay produces a new set of artifacts without overwriting the
   original.

The trace context is set to `pipeline_stage="replay"` for the duration of
the replay execution.

---

## DKB Integration Flow

When the Design Knowledge Base (DKB) pipeline is invoked, it runs between
the Prompt Runner response and the geometry generation step:

```
PromptRunnerAdapterBridge.run_from_platform()
    │
    ▼
DKBExecutionPipeline.run(instruction, trace_id)
    │
    ├─ DKBRuntime.execute(instruction)
    │      ├─ KnowledgeSearchEngine.resolve(topic)
    │      ├─ DesignSpecCompiler.compile(entry)
    │      └─ ValidationEngine.validate(spec)
    │
    ├─ _build_semantic()
    ├─ _build_spec_json()
    │
    └─ TTGGenerationPipeline (Sprint 1)
    │
    ▼
spec_json returned to CoreBucketCanonicalOrchestrator
```

The DKB pipeline enriches the spec_json with validated architectural knowledge
before geometry generation.

---

---

## BHIV /design Endpoint Flow

When `POST /bhiv/v1/design` is called the flow diverges from the core
generate flow after Step 4 (route handler):

### Step 4b — BHIV Route Handler

```
app/api/bhiv_integrated.py
  create_design(request: DesignRequest)

  request_id = "bhiv_{timestamp}"
  spec_id    = create_new_spec_id()

  core_payload = {
      spec_id, user_id, project_id,
      prompt, city, style, context
  }
```

### Steps 5–12 — Core pipeline (identical)

Same as the core generate flow: bucket store request,
prompt runner, GLB generation, bucket store artifacts.

### Step 13b — Compliance check

```
call_sohum_compliance(spec_json, city, project_id)
  app/api/bhiv_integrated.py

  case_data = {spec_json, city, project_id}

  try:
    result = await sohum_client.run_compliance_case(case_data)
    service_health["sohum_mcp"] = HEALTHY
    return result
  except Exception as e:
    logger.error(f"Sohum MCP service failed: {e}")
    service_health["sohum_mcp"] = UNHEALTHY
    return {
        "compliant": False,
        "violations": [],
        "geometry_url": None,
        "case_id": None
    }
```

Log emitted on fallback:
```json
{
  "level": "ERROR",
  "message": "Sohum MCP service failed: ...",
  "trace_id": "a3f7c2d1-..."
}
```

### Step 13c — RL optimization (non-blocking)

```
call_ranjeet_rl(spec_json, city)
  app/api/bhiv_integrated.py

  try:
    result = await ranjeet_client.optimize_design(spec_json, city)
    service_health["ranjeet_rl"] = HEALTHY
    return result
  except Exception as e:
    service_health["ranjeet_rl"] = UNHEALTHY
    mock = ranjeet_client.get_mock_rl_response(spec_json, city)
    mock["fallback_reason"] = str(e)
    return mock
```

### Step 14b — BHIV Response

```json
{
  "request_id": "bhiv_20260722_071135",
  "spec_id": "spec_47d77f94",
  "spec_json": {...},
  "preview_url": "https://bhiv-bucket.onrender.com/bucket/artifact/...",
  "compliance": {
    "compliant": false,
    "violations": [],
    "geometry_url": null,
    "case_id": null
  },
  "rl_optimization": null,
  "processing_time_ms": 4823,
  "timestamp": "2026-07-22T07:11:35Z"
}
```

---

## Replay Fallback Implementation

The replay service reconstructs the original request payload from the
stored trace file. If the `core_ingress` stage entry does not contain
a full request payload (e.g. older traces), a `_FALLBACK_PAYLOAD` is
used to prevent replay failure:

```
ReplayService._extract_request_payload(entries)
  app/replay/replay_service.py

  Searches entries for stage == "core_ingress"
  Extracts: spec_id, user_id, city from payload

  Reconstructs:
    {
      spec_id, user_id, city,
      prompt: "Replay of {spec_id}",
      style: "modern",
      context: {}
    }

  If reconstruction fails (KeyError / missing fields):
    _FALLBACK_PAYLOAD is used:
    {
      spec_id: "replay_fallback",
      user_id: "replay_user",
      prompt: "Design a 2BHK apartment",
      city: "Mumbai",
      style: "modern",
      context: {}
    }
    This ensures replay never crashes on malformed traces.
```

Log emitted on fallback:
```json
{
  "level": "WARNING",
  "message": "Replay payload reconstruction failed, using fallback",
  "trace_id": "core_bucket_replay_..."
}
```

---

*Generated by Amazon Q — Production Readiness Sprint, Task 5*
*Updated: Task 4 Documentation Sprint — BHIV endpoint flow, replay fallback implementation*
