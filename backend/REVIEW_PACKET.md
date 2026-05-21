# REVIEW PACKET
**Author:** Anmol Mishra
**Date:** 2026-05-21
**For:** Raj Prajapati (Core), Siddhesh Narkar (Bucket), Vinayak Tiwari (QA)

---

## 1. PROOF: Core Entry Enforced

### What was enforced
Every design generation request MUST go through `POST /api/v1/core/generate`.
All other routes are hard-blocked.

### Evidence

**Blocked routes (return 403):**
```
POST /api/v1/generate          → 403 {"detail": "Direct access not allowed. Use /api/v1/core/generate."}
POST /api/v1/geometry/generate → 403 {"detail": "Direct geometry generation not allowed. Use /api/v1/core/generate."}
```

**Core entry (the only valid path):**
```
POST /api/v1/core/generate
  → CoreBucketCanonicalOrchestrator.execute()
  → PromptRunnerAdapterBridge.run_from_platform()
  → geometry_generator_real.generate_real_glb()
  → BucketRouter.store_artifact()
  → returns Bucket URLs only
```

**All bypass routes fixed:**
- `mobile.py` → routes to `core_generate` (was calling `generate_design` directly)
- `bhiv_assistant.py` → calls `generate_real_glb` + `upload_to_bucket` (was calling `/api/v1/geometry/generate`)
- `bhiv_integrated.py` → uses `CoreBucketCanonicalOrchestrator` (was calling `run_prompt` directly)
- `bhiv.py` → uses `CoreBucketCanonicalOrchestrator` (was calling `run_local_lm` directly)

**Verified by Phase 6 QA:**
- 5 parallel requests → all routed through Core, no bypass
- Blocked routes return 403, not 500

---

## 2. PROOF: Bucket Storage Enforced

### What was enforced
ALL outputs stored ONLY via the live Bucket service at `https://bhiv-bucket.onrender.com`.
No local disk writes for geometry, specs, or previews.

### Evidence

**Live Bucket write confirmed:**
```
POST https://bhiv-bucket.onrender.com/bucket/artifacts/write
{
  "requester_id": "core",
  "integration_id": "core",
  "artifact": {
    "schema_version": "1.0.0",
    "parent_hash": "<chain_tip>",
    ...
  }
}
→ {"success": true, "data": {"artifact_id": "...", "storage_type": "append_only"}}
```

**Bucket chain state (post Phase 5+6):**
- Artifact count: 138
- Last hash: `1308c24e34cc19bb9f513142fb52ddf1e18a4e1ae4c46f63f5de34199cf983d7`
- Certification: `append_only_enforced`

**All local storage paths removed:**
- `data/geometry_outputs/` — NOT written to (vr.py, reports.py fixed)
- `data/export_outputs/` — NOT written to (core_bucket_pipeline.py fixed)
- `data/specs/` — NOT written to (spec_storage.py is in-memory cache only)
- `data/previews/` — NOT written to (reports.py fixed)
- `data/evaluations/` — NOT written to (evaluate.py raises RuntimeError)
- `local://` URLs — REMOVED (vr.py fixed)
- `bhiv-previews.s3.amazonaws.com` — REMOVED (bhiv.py, bhiv_integrated.py fixed)

**Returned URLs are Bucket URLs:**
```
GLB:  https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>
STL:  https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>
STEP: https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>
```

**Delete local folder test:**
The `data/geometry_outputs/` folder can be deleted — system still works because all outputs go to Bucket.

---

## 3. PROOF: Geometry Fixed

### What was fixed
Each room is now a distinct enclosed volume with thick walls and door gaps.

### Evidence

**Phase 5 validation results:**

| Prompt | Rooms | GLB Nodes | GLB Size |
|---|---|---|---|
| 1BHK compact home in Ahmedabad | 4 | bedroom, hall, kitchen, bathroom | 21,040 bytes |
| 2BHK modern apartment in Mumbai | 6 | master_bedroom, bedroom_2, hall, kitchen, master_bathroom, common_bathroom | 32,116 bytes |
| 3BHK luxury house in Pune | 9 | master_bedroom, bedroom_2, bedroom_3, hall, dining, kitchen, master_bathroom, bathroom_2, common_bathroom | 52,276 bytes |

**Geometry properties:**
- Wall thickness: 0.25 m (visible at normal scale)
- Each room = floor + ceiling + 4 thick walls
- Adjacent rooms get door gaps (from spec adjacency JSON)
- Rooms are spatially separated (no overlap verified)
- Each room is a separate GLB mesh node (named)
- 1BHK ≠ 2BHK ≠ 3BHK — different room counts, different sizes, different layouts

**GLB structure (per room):**
```
- Floor slab
- Ceiling slab
- South wall (thick, optional door gap)
- North wall (thick, optional door gap)
- West wall (thick, optional door gap)
- East wall (thick, optional door gap)
```

**Not a slab:** Every mesh has >12 triangles (a flat slab = 2 triangles).

---

## 4. QA Break Test Results (Phase 6)

| Test | Expected | Result |
|---|---|---|
| 5x parallel requests, 5 cities | No cross-contamination | PASS |
| Mumbai, Pune, Ahmedabad, Nashik, Bangalore | Each city in correct spec | PASS |
| Invalid prompt (no BHK) | RuntimeError raised | PASS |
| Short prompt < 10 chars | 400 Bad Request | PASS |
| Missing user_id | 400 Bad Request | PASS |
| POST /generate | 403 Forbidden | PASS |
| POST /geometry/generate | 403 Forbidden | PASS |
| Empty rooms spec | ValueError raised | PASS |
| Same prompt, 3 cities | Cities distinct, no bleed | PASS |
| Bucket lineage conflict (parallel) | Auto-retry, succeeds | PASS |

---

## 5. Known Constraints (for Siddhesh / Bucket team)

**Meshy AI GLB size:** Meshy generates 20–50 MB GLBs. The Bucket's 16 MB payload limit means these cannot be stored directly. The system:
1. Stores the Meshy external CDN URL in `spec_json.metadata.meshy_glb_url`
2. Uses `geometry_generator_real` for the Bucket-stored GLB (20–50 KB)
3. Frontend can use `meshy_glb_url` for high-quality rendering, Bucket URL for persistence

**Recommendation for Siddhesh:** Consider adding a `large_artifact_url` field to the Bucket schema for external CDN references, or increase the payload limit to 64 MB.

---

## 6. Files to Review

**Core enforcement (Raj):**
- `app/api/generate.py` — 403 block
- `app/api/geometry_generator.py` — 403 block
- `app/api/core_entry.py` — canonical entry point
- `app/core_bucket_pipeline.py` — orchestrator

**Bucket enforcement (Siddhesh):**
- `app/storage.py` — write/read/retry logic
- `app/api/files.py` — Bucket proxy
- `app/api/vr.py` — Bucket reads

**Geometry (Anmol):**
- `app/geometry_generator_real.py` — room geometry engine

**QA (Vinayak):**
- Run `python phase5_validation.py` — 3 prompts, full pipeline
- Run `python phase6_qa.py` — break tests
