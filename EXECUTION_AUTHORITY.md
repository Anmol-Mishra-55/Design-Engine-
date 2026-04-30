# EXECUTION_AUTHORITY.md

**Version:** 2.0 — Canonical Frozen State
**Status:** ENFORCED

---

## Canonical Execution Path

```
Client → /api/v1/generate → CoreBucketCanonicalOrchestrator
       → Bucket (store_request)
       → PromptRunnerAdapter (platform_adapter.process)
       → extract_semantics() → _instruction_to_spec_json()
       → generate_real_glb(spec_json)
       → Bucket (upload_to_bucket)
       → Core (return bucket URLs)
```

## Execution Authority: `platform_adapter.py`

- ONLY `prompt_runner_adapter.py` may call `platform_adapter.process()`
- ONLY `geometry_generator_real.py` may produce GLB output
- ONLY `storage.py → upload_to_bucket()` may persist artifacts

## Forbidden

| Action | Reason |
|--------|--------|
| Direct LLM calls from `generate.py` | Bypasses Core |
| Geometry fallback outside pipeline | Breaks determinism |
| Multiple execution paths | Violates single-path policy |
| Skipping Core or Bucket | Breaks trace/audit |
| Local file writes in pipeline | Bucket enforcement violated |
| Calling `platform_adapter` from any file except `prompt_runner_adapter.py` | Authority violation |

## Enforcement Files

| File | Role |
|------|------|
| `backend/app/api/generate.py` | HTTP boundary — delegates to Core only |
| `backend/app/core_bucket_pipeline.py` | Canonical orchestrator |
| `backend/app/prompt_runner_adapter.py` | Only caller of platform_adapter |
| `backend/app/geometry_generator_real.py` | Only GLB generator |
| `backend/app/storage.py` | Only bucket upload path |

## Violation Response

Any PR that introduces a second execution path, direct LLM call, or local file write in the pipeline is **rejected without review**.
