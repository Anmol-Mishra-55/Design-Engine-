# FINAL SYSTEM STATE
**Date:** 2026-05-21
**Owner:** Anmol Mishra
**Status:** LOCKED — All phases complete and proven

---

## System Architecture

```
Client
  └─► POST /api/v1/core/generate          ← ONLY valid entry point
        └─► CoreBucketCanonicalOrchestrator
              ├─► BucketRouter.store_request()     → Bucket (files/requests/)
              ├─► PromptRunnerAdapterBridge         → spec_json + rooms
              ├─► _generate_glb()                  → geometry_generator_real
              ├─► BucketRouter.store_artifact(glb) → Bucket (geometry/)
              ├─► BucketRouter.store_artifact(stl) → Bucket (geometry/exports/)
              ├─► BucketRouter.store_artifact(step)→ Bucket (geometry/exports/)
              └─► BucketRouter.store_spec_payload() → Bucket (files/specs/)

POST /api/v1/generate          → 403 BLOCKED
POST /api/v1/geometry/generate → 403 BLOCKED
```

---

## Phase 3 — Core Entry Enforcement ✅

| Route | Status | Proof |
|---|---|---|
| `POST /api/v1/generate` | 403 BLOCKED | `generate.generate_design_blocked()` raises HTTPException(403) |
| `POST /api/v1/geometry/generate` | 403 BLOCKED | `geometry_generator.generate_geometry_blocked()` raises HTTPException(403) |
| `POST /api/v1/core/generate` | LIVE — only valid entry | Uses `CoreBucketCanonicalOrchestrator` |
| `POST /mobile/generate` | Routes to `core_generate` | No direct `generate_design` call |
| `bhiv_assistant.call_geometry_agent` | Uses `generate_real_glb` + `upload_to_bucket` | No `/api/v1/geometry/generate` call |
| `bhiv_integrated.create_design` | Uses `CoreBucketCanonicalOrchestrator` | No `run_prompt` bypass |
| `bhiv.BHIVAssistant._run_pipeline` | Uses `CoreBucketCanonicalOrchestrator` | No `run_local_lm` bypass |

---

## Phase 4 — Bucket Truth Enforcement ✅

| Component | Status | Proof |
|---|---|---|
| `storage.py` | Writes to `https://bhiv-bucket.onrender.com/bucket/artifacts/write` | Live round-trip verified |
| `files.py` | Proxies from Bucket via `POST /bucket/artifacts/read` | No GridFSStorage |
| `vr.py` | Reads GLB from Bucket via `download_from_bucket` | No `data/geometry_outputs/` |
| `evaluate.py` | Raises `RuntimeError` if DB unavailable | No `data/evaluations/` write |
| `reports.py` | Uploads to Bucket only | No local geometry/preview writes |
| `data_audit.py` | Reports Bucket as storage backend | No local path references |
| `core_entry.py` | Export URLs from `canonical_result.artifacts` only | No `_extract_export_urls` fallback |
| `generate.py._extract_export_urls` | Returns `""` when no Bucket URL | No `/api/v1/files/...` fallback |

### Bucket Chain State
- **Artifact count:** 138
- **Last hash:** `1308c24e34cc19bb9f513142fb52ddf1e18a4e1ae4c46f63f5de34199cf983d7`
- **Certification:** `append_only_enforced`
- **Storage:** `https://bhiv-bucket.onrender.com`

---

## Phase 5 — Real Validation ✅

| Prompt | City | Rooms | GLB Nodes | GLB Size | Bucket URL |
|---|---|---|---|---|---|
| 2BHK modern apartment in Mumbai | Mumbai | 6 | master_bedroom, bedroom_2, hall, kitchen, master_bathroom, common_bathroom | 32,116 bytes | `https://bhiv-bucket.onrender.com/bucket/artifact/d558cc77-...` |
| 3BHK luxury house in Pune | Pune | 9 | master_bedroom, bedroom_2, bedroom_3, hall, dining, kitchen, master_bathroom, bathroom_2, common_bathroom | 52,276 bytes | `https://bhiv-bucket.onrender.com/bucket/artifact/5939cb41-...` |
| 1BHK compact home in Ahmedabad | Ahmedabad | 4 | bedroom, hall, kitchen, bathroom | 21,040 bytes | `https://bhiv-bucket.onrender.com/bucket/artifact/dc9dbbad-...` |

**Geometry is visually different:**
- 1BHK: 4 rooms, 21 KB
- 2BHK: 6 rooms, 32 KB
- 3BHK: 9 rooms, 52 KB
- Room names are distinct per BHK type
- Cities are correctly assigned (no Mumbai-for-all bug)

---

## Phase 6 — QA Break Test ✅

| Test | Result |
|---|---|
| 5x parallel requests (Mumbai, Pune, Ahmedabad, Nashik, Bangalore) | PASS — no cross-contamination |
| Invalid input (no BHK type) | PASS — raises RuntimeError |
| Short prompt < 10 chars | PASS — blocked at core_generate |
| Missing user_id | PASS — blocked at core_generate |
| Blocked routes return 403 | PASS |
| Empty rooms raises ValueError | PASS |
| Same prompt, 3 different cities | PASS — cities distinct, no bleed |

**Bucket lineage conflict handling:** Parallel writes retry up to 5x with exponential backoff.

---

## Known Constraints

1. **Meshy AI GLBs > 12 MB** — Bucket has a 16 MB payload limit (base64 encoded). Meshy GLBs (26–43 MB) exceed this. The system stores the Meshy external URL in `metadata.meshy_glb_url` and uses `geometry_generator_real` for the Bucket-stored GLB. The Meshy URL is available to the frontend.

2. **Bucket is append-only** — Every write requires `parent_hash` = current chain tip. Parallel writes may conflict; the system retries automatically.

3. **Meshy API rate limit** — Parallel requests to Meshy may queue. The system handles this gracefully by falling through to `geometry_generator_real`.

---

## Files Modified (Phases 1–7)

| File | Change |
|---|---|
| `app/storage.py` | Bucket-only writes, lineage retry logic |
| `app/core_bucket_pipeline.py` | Bucket size limit handling, real STL/STEP from rooms |
| `app/geometry_generator_real.py` | Phase 2 geometry: enclosed volumes, adjacency doors |
| `app/api/generate.py` | 403 block, no local path fallback |
| `app/api/core_entry.py` | Bucket URLs from canonical_result.artifacts |
| `app/api/geometry_generator.py` | 403 block |
| `app/api/files.py` | Bucket proxy, no GridFS |
| `app/api/vr.py` | Bucket reads, no local disk |
| `app/api/mobile.py` | Routes to core_generate |
| `app/api/bhiv.py` | Core pipeline, no fake S3 |
| `app/api/bhiv_integrated.py` | Core pipeline, no fake S3 |
| `app/api/bhiv_assistant.py` | geometry_generator_real + Bucket |
| `app/api/evaluate.py` | Raises on DB failure, no local file |
| `app/api/reports.py` | Bucket uploads only |
| `app/api/data_audit.py` | Bucket storage reporting |
| `app/main.py` | Correct startup message |
