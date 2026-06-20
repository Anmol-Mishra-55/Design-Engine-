# TTG Integration Analysis
**Author:** Amazon Q
**Date:** 2026-06-11
**Based on:** Full inspection of ttg_adapter.py, platform_adapter.py, prompt_runner_adapter.py, core_entry.py, semantic_resolver.py, generation_constraints.json, REVIEW_PACKET.md, FINAL_SYSTEM_STATE.md

---

## Question 1: Is /api/intent/compile only for gameplay generation?

**Yes — /api/intent/compile is gameplay-specific.**

From the TTG backend docs you provided:

```
POST /api/intent/compile
Input:  "fast runner game with obstacles"
Output: { "intent": {...}, "schema": {...} }
```

This endpoint does **text → gameplay execution contract** compilation.
It is a semantic compiler designed for freeform game descriptions.

Evidence this is NOT appropriate for the Design Engine pipeline:

| Factor | /api/intent/compile | Design Engine output |
|---|---|---|
| Input type | Raw freeform game text | Already-resolved semantic dict |
| Output type | gameplay intent + schema | Already known: domain/entity/generation_mode |
| Semantic authority | TTG's own NLP | Prompt Runner (already executed) |
| Duplication risk | HIGH — re-compiles what PR already did | N/A |

**Conclusion:** Calling /api/intent/compile after Prompt Runner + SemanticResolver would be **double semantic compilation** — running NLP twice on the same input, with a high risk of producing conflicting domain classifications.

The only valid use case for /api/intent/compile within this sprint is if a raw gameplay prompt is sent **directly to TTG without going through Prompt Runner first** — which violates the CoreGateway pipeline order enforced in Task 9.

---

## Question 2: Can /core/execute accept an external executionSchema without using /api/intent/compile?

**Yes — /core/execute is schema-first, not text-first.**

From the TTG docs pattern:

```
POST /core/execute
Body: {
  "executionSchema": { ... },   ← accepts external pre-built schema
  "metadata":        { ... },
  "assetRefs":       [ ... ],
  "bucketUrls":      { ... }
}
```

The key distinction is:

- `/api/intent/compile` = text → schema  (NLP stage)
- `/core/execute`       = schema → asset  (generation stage)

These are two separate stages. `/core/execute` does NOT require that the schema was produced by `/api/intent/compile`. It accepts **any valid executionSchema** as input.

This means the Design Engine can build its own `executionSchema` from SemanticResolver output and POST it directly to `/core/execute`, completely bypassing `/api/intent/compile`.

**Confirmed:** `/core/execute` is the correct target for Design Engine outputs.

---

## Question 3: What is the correct TTG endpoint for each domain?

| Domain | Correct TTG Endpoint | Reason |
|---|---|---|
| architecture | POST /core/execute | Pre-resolved layout schema — no NLP recompilation needed |
| vehicle | POST /core/execute | Pre-resolved mesh schema — rotorcraft/wheeled/marine geometry |
| object | POST /core/execute | Pre-resolved primitive/structural mesh |
| environment | POST /core/execute | Pre-resolved grouped geometry schema |
| gameplay | POST /core/execute | SemanticResolver already classified entity — no need for /api/intent/compile |

**All 5 domains use POST /core/execute.**
None of them should use /api/intent/compile because Prompt Runner is already the semantic authority.

---

## Question 4: How should asset metadata, geometry references, and bucket URLs be attached?

Based on the existing Bucket chain architecture in REVIEW_PACKET.md and FINAL_SYSTEM_STATE.md, the correct attachment structure for a `/core/execute` payload is:

```json
POST /core/execute
{
  "executionSchema": {
    "domain":          "vehicle",
    "entity":          "drone",
    "generation_mode": "mesh",
    "geometry_family": "rotorcraft",
    "generator":       "mesh_generator",
    "spec_version":    "1.0"
  },
  "spec_json": {
    "type":       "drone",
    "dimensions": { "width": 0.8, "length": 0.8, "height": 0.3 },
    "components": ["frame", "rotor", "motor", "battery", "camera_mount", "landing_gear"],
    "units":      "meters"
  },
  "metadata": {
    "trace_id":          "trace_abc123",
    "task_id":           "task_xyz789",
    "execution_token":   "tok_...",
    "prompt":            "Generate a cargo drone",
    "product_context":   "creator_core",
    "intent":            "design_creation",
    "output_format":     "step_by_step_guide"
  },
  "asset_refs": {
    "geometry_ref":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "spec_ref":      "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>"
  },
  "bucket_urls": {
    "glb":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "stl":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "step": "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>"
  },
  "output_formats": ["glb", "stl", "step"]
}
```

**Attachment rules:**

- `executionSchema` — built by TTGAdapter from SemanticResolver output. This is the semantic contract.
- `spec_json` — the fully enriched design specification from PromptRunnerAdapterBridge._instruction_to_spec_json().
- `metadata` — trace_id, task_id, execution_token from CoreExecutionRequest. Carries pipeline provenance.
- `asset_refs` — Bucket URLs of already-stored intermediate artifacts (e.g. geometry generated by geometry_generator_real).
- `bucket_urls` — Target write URLs for TTG to store its outputs. These come from BucketRouter.
- `output_formats` — Derived from semantic_templates.json `supported_outputs` field per entity.

---

## Question 5: What is the confirmed correct full pipeline?

```
Prompt
    ↓
CoreGateway._authorize()
    ↓  (POST /execute_task → Core, status must = success)
CoreGateway._call_prompt_runner()
    ↓  (POST /generate → https://prompt-runner.onrender.com)
    ↓  Returns: { module, intent, topic, tasks, output_format, product_context }
SemanticResolver.resolve()
    ↓  Returns: { domain, entity, generation_mode, geometry_family }
TTGAdapter.prepare_request()
    ↓  Validates contamination, routes domain → generator name
    ↓  Returns: CoreExecutionRequest (the execution contract)
[NEW] TTGPayloadBuilder.build()
    ↓  Assembles executionSchema + spec_json + metadata + asset_refs + bucket_urls
    ↓  Returns: TTGExecutePayload (ready for /core/execute)
[NEW] TTGClient.execute()
    ↓  POST /core/execute → TTG backend
    ↓  Returns: TTGExecutionResponse (with job_id)
[NEW] TTGClient.poll_until_complete()
    ↓  GET /core/execution/{id} → polls until status = complete
    ↓  Returns: TTGGenerationResult (with asset URLs)
BucketRouter.store_artifact()
    ↓  Writes TTG output GLB/STL/STEP to Bucket
    ↓  Returns: Bucket URLs
Response → Client
```

---

## What the Current ttg_adapter.py Covers vs What Is Missing

### Currently implemented (ttg_adapter.py):

| Capability | Status |
|---|---|
| Domain contamination checking | ✅ Done |
| geometry_family validation | ✅ Done |
| generation_mode validation | ✅ Done |
| Domain → generator name routing | ✅ Done |
| CoreExecutionRequest construction | ✅ Done |
| CoreExecutionResponse output validation | ✅ Done |

### Missing — needed for Tasks 10–14:

| Missing piece | File to create | Purpose |
|---|---|---|
| TTG execute payload builder | `ttg_payload_builder.py` | Assemble executionSchema + spec_json + metadata + asset_refs + bucket_urls |
| TTG HTTP client | `ttg_client.py` | POST /core/execute, GET /core/execution/{id} |
| TTG generation pipeline | `ttg_generation_pipeline.py` | Orchestrate build → execute → poll → store |
| TTGExecutePayload dataclass | inside `ttg_payload_builder.py` | Type-safe payload contract |
| TTGGenerationResult dataclass | inside `ttg_client.py` | Type-safe result contract |

---

## Risk Analysis

| Risk | Severity | Mitigation |
|---|---|---|
| Calling /api/intent/compile for non-gameplay domains | HIGH — double semantic compilation, conflicting outputs | Never call /api/intent/compile from Design Engine pipeline. Only use /core/execute. |
| Calling /api/intent/compile for gameplay | MEDIUM — SemanticResolver already resolved the entity | Still use /core/execute with pre-built schema. SemanticResolver is the authority. |
| Path traversal in _load_constraints (CWE-22, lines 194–195) | HIGH — identified by code scan | Fix in ttg_payload_builder.py: use `pathlib.Path(__file__).resolve().parent` instead of `os.path.join` |
| Bucket URL not attached to TTG payload | HIGH — TTG cannot write output to Bucket | TTGPayloadBuilder must always inject bucket_urls from BucketRouter before calling /core/execute |
| spec_json missing from TTG payload | HIGH — TTG has no geometry spec to work from | TTGPayloadBuilder must receive spec_json from PromptRunnerAdapterBridge output |

---

## Recommended Next Actions (Tasks 10–14)

**Task 10:** Create `ttg_payload_builder.py`
- Input: SemanticResolver output + spec_json + metadata + existing bucket URLs
- Output: TTGExecutePayload (validated dataclass)
- No HTTP. Pure data assembly.

**Task 11:** Create `ttg_client.py`
- POST /core/execute → returns job_id
- GET /core/execution/{id} → polls status
- Timeout: 120s, retries: 3, backoff: exponential
- Exceptions: TTGClientError, TTGTimeoutError, TTGValidationError

**Task 12:** Create `ttg_generation_pipeline.py`
- Orchestrates: build payload → execute → poll → return result
- Integrates with existing CoreGateway pipeline after SemanticResolver step

**Task 13:** Create TANTRA_INTEGRATION_STATE.md
- Records live status of all pipeline components

**Task 14:** Create REVIEW_PACKET.md update
- Documents Tasks 6–12 for Raj, Siddhesh, Vinayak

---

## Summary Answers

| Question | Answer |
|---|---|
| Is /api/intent/compile gameplay-only? | **Yes.** It is a text→gameplay NLP compiler. Using it after Prompt Runner duplicates semantic compilation. |
| Can /core/execute accept external executionSchema? | **Yes.** It is schema-first. No dependency on /api/intent/compile. |
| Which endpoint should receive Design Engine outputs? | **POST /core/execute** for all 5 domains. |
| How to attach asset metadata, geometry refs, bucket URLs? | Via `executionSchema`, `spec_json`, `metadata`, `asset_refs`, `bucket_urls` fields in the /core/execute body. |
| Is current ttg_adapter.py sufficient for Phase 4? | **No.** It is a transformer only. TTGPayloadBuilder + TTGClient + TTGGenerationPipeline are still required. |
| Risk of code duplication in Tasks 10–14? | **Zero.** ttg_adapter.py has no HTTP calls. No overlap with ttg_client.py. |
