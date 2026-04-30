# REVIEW_PACKET.md

**Version:** 2.0
**Status:** SUBMISSION READY

---

## 1. Entry Point

**Backend entry:** `backend/app/main.py`
FastAPI server on port 8000. Router includes `/api/v1/generate`.

---

## 2. Core Execution Flow (3 Files)

**File 1:** `backend/app/api/generate.py`
Receives POST `/api/v1/generate`, validates input, creates `CoreBucketCanonicalOrchestrator`, returns `GenerateResponse` with export URLs.

**File 2:** `backend/app/core_bucket_pipeline.py`
Orchestrates Core→Bucket→PromptRunner→Geometry→Bucket flow. Generates GLB/STL/STEP exports, stores artifacts, writes trace logs.

**File 3:** `backend/app/prompt_runner_adapter.py`
Calls `platform_adapter.process()` as execution authority. Converts `PromptInstruction` to `spec_json`. Returns deterministic response.

---

## 3. Design Semantics Folder

**Path:** `backend/app/design_semantics/`

| File | Role |
|------|------|
| `semantic_detector.py` | `extract_semantics()` — 28 BHK patterns, 12 cities |
| `bhk_definitions.json` | 7 BHK types, room counts, dimensions, adjacency |
| `layout_rules.json` | 16 layout rules (adjacency, orientation, zoning) |
| `style_profiles.json` | 6 style profiles (modern, traditional, luxury, etc.) |

---

## 4. Three Outputs (1BHK / 2BHK / 3BHK)

### 1BHK Output

**JSON:**
```json
{
  "spec_id": "spec_1bhk_canonical",
  "bhk_type": "1BHK",
  "style": "modern",
  "city": "Mumbai",
  "stories": 1,
  "dimensions": {"width_m": 7.0, "length_m": 6.5, "height_m": 2.7},
  "rooms": ["bedroom", "hall", "kitchen", "bathroom"],
  "room_count": 4,
  "adjacency": {
    "bedroom": ["bathroom", "hall"],
    "hall": ["kitchen", "bedroom", "balcony"],
    "kitchen": ["hall"],
    "bathroom": ["bedroom"]
  },
  "metadata": {
    "glb_bytes": 3396,
    "hash": "e8966c4bd72004dc",
    "vertices": 96,
    "faces": 48,
    "execution_path": "core->bucket->prompt_runner->geometry->bucket"
  }
}
```

**GLB:** `data/geometry_outputs/spec_1bhk_canonical.glb`
- Magic: `glTF`, Version: 2, Vertices: 96, Faces: 48, Bytes: 3,396

---

### 2BHK Output

**JSON:**
```json
{
  "spec_id": "spec_2bhk_canonical",
  "bhk_type": "2BHK",
  "style": "modern",
  "city": "Pune",
  "stories": 1,
  "dimensions": {"width_m": 9.0, "length_m": 8.5, "height_m": 2.7},
  "rooms": ["master_bedroom", "bedroom_2", "hall", "kitchen", "master_bathroom", "common_bathroom"],
  "room_count": 6,
  "adjacency": {
    "master_bedroom": ["master_bathroom", "hall"],
    "bedroom_2": ["common_bathroom", "hall"],
    "hall": ["kitchen", "master_bedroom", "bedroom_2", "balcony"],
    "kitchen": ["hall"],
    "master_bathroom": ["master_bedroom"],
    "common_bathroom": ["hall", "bedroom_2"]
  },
  "metadata": {
    "glb_bytes": 4680,
    "hash": "8fe5a09ab7f6a106",
    "vertices": 144,
    "faces": 72,
    "execution_path": "core->bucket->prompt_runner->geometry->bucket"
  }
}
```

**GLB:** `data/geometry_outputs/spec_2bhk_canonical.glb`
- Magic: `glTF`, Version: 2, Vertices: 144, Faces: 72, Bytes: 4,680

---

### 3BHK Output

**JSON:**
```json
{
  "spec_id": "spec_3bhk_canonical",
  "bhk_type": "3BHK",
  "style": "modern",
  "city": "Ahmedabad",
  "stories": 1,
  "dimensions": {"width_m": 11.0, "length_m": 10.5, "height_m": 2.8},
  "rooms": ["master_bedroom", "bedroom_2", "bedroom_3", "hall", "dining", "kitchen", "master_bathroom", "bathroom_2", "common_bathroom"],
  "room_count": 9,
  "adjacency": {
    "master_bedroom": ["master_bathroom", "hall", "balcony_1"],
    "bedroom_2": ["bathroom_2", "hall"],
    "bedroom_3": ["common_bathroom", "hall"],
    "hall": ["dining", "master_bedroom", "bedroom_2", "bedroom_3", "balcony_2"],
    "dining": ["kitchen", "hall"],
    "kitchen": ["dining"],
    "master_bathroom": ["master_bedroom"],
    "bathroom_2": ["bedroom_2"],
    "common_bathroom": ["hall"]
  },
  "metadata": {
    "glb_bytes": 6624,
    "hash": "8e0f065b6c769a47",
    "vertices": 216,
    "faces": 108,
    "execution_path": "core->bucket->prompt_runner->geometry->bucket"
  }
}
```

**GLB:** `data/geometry_outputs/spec_3bhk_canonical.glb`
- Magic: `glTF`, Version: 2, Vertices: 216, Faces: 108, Bytes: 6,624

---

## 5. Validation Docs

| File | Location | Status |
|------|----------|--------|
| `EXECUTION_AUTHORITY.md` | `Backend/` root | ✅ |
| `GEOMETRY_VALIDATION.md` | `Backend/` root | ✅ |
| `SEMANTIC_VALIDATION.md` | `Backend/` root | ✅ |
| `FINAL_SYSTEM_STATE.md` | `Backend/` root | ✅ |

---

## 6. Deployment

**Platform:** Render.com
**URL:** `https://<service>.onrender.com`
**Health:** `GET /health` → `{"status": "ok"}`
**Config:** `render.yaml`

---

## 7. Failure Cases

| Case | Behavior |
|------|----------|
| Missing prompt / user_id | HTTP 400 |
| Platform adapter unavailable | HTTP 503 |
| Storage failure | Fallback to local, returns `/static/geometry/spec_*.glb` |
| Empty rooms list | Fallback to single `main_space` room (logged as warning) |
| Extreme stories (>10) | Capped at 10 |

---

## 8. Test Results

- `test_prompts.py` — 12/12 determinism checks passed
- `qa_runner.py` — 21/21 edge cases, zero crashes

---

## 9. What Was Built

**Added:**
- `backend/app/design_semantics/` — semantic layer (4 files)
- `backend/app/prompt_runner_adapter.py` — canonical adapter
- `backend/app/core_bucket_pipeline.py` — canonical orchestrator
- `EXECUTION_AUTHORITY.md` — execution path policy
- `GEOMETRY_VALIDATION.md` — geometry validation rules
- `SEMANTIC_VALIDATION.md` — semantic validation rules
- `FINAL_SYSTEM_STATE.md` — frozen system state
- `review_packets/REVIEW_PACKET.md` — this file

**Modified:**
- `backend/app/api/generate.py` — delegates to `CoreBucketCanonicalOrchestrator`
- `backend/app/main.py` — static file serving for exports
