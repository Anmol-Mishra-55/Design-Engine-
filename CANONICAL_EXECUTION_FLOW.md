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
