# Export Pipeline

## Objective
Generate and deliver downloadable design artifacts in:

- `GLB`
- `STL`
- `STEP`

## Canonical Source
`GLB` generated from Prompt Runner-produced `spec_json` is the canonical geometry source.

Pipeline:
1. `spec_json` -> geometry generator -> `GLB`
2. `GLB` + spec dimensions -> `STL`
3. `GLB` + spec dimensions -> `STEP`

Implementation location:
- `backend/app/core_bucket_pipeline.py`

## Storage Strategy (Bucket Authority)
Remote-first, local-fallback:

- Remote bucket upload via `app.storage.upload_to_bucket(...)`
- If remote upload fails, local fallback paths are used:
  - `backend/data/geometry_outputs/<spec_id>.glb`
  - `backend/data/export_outputs/<spec_id>.stl`
  - `backend/data/export_outputs/<spec_id>.step`

Static serving:
- `GET /static/geometry/<spec_id>.glb`
- `GET /static/exports/<spec_id>.stl`
- `GET /static/exports/<spec_id>.step`

Configured in:
- `backend/app/main.py`

## API Response Contract
`POST /api/v1/generate` now returns export URLs in:

- `export_urls.glb`
- `export_urls.stl`
- `export_urls.step`

And convenience fields:

- `glb_url`
- `stl_url`
- `step_url`

Schema updated in:
- `backend/app/schemas/generate.py`

## Notes
- `STL` is generated as deterministic ASCII mesh export.
- `STEP` is generated as deterministic STEP payload with canonical geometry envelope metadata.
- Both are traceable to source `GLB` via hash metadata in generated files.
