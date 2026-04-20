# GEOMETRY_VALIDATION.md

## Purpose

This document defines the mandatory validation rules for all geometry output
produced by the BHIV Design Engine. Every GLB file emitted by
`generate_real_glb()` must satisfy every rule listed here before it is
uploaded to the bucket.

---

## Rule 1 — Every Room Must Map to Geometry

**Requirement:**
For every entry in `spec["rooms"]`, exactly one room mesh must exist in the
output GLB. No room may be silently skipped or merged with another.

**Implementation contract (`geometry_generator_real.py`):**

```python
for room in spec["rooms"]:
    create_room_mesh(room)   # must be called once per room, no exceptions
```

**Room mesh anatomy — each room produces exactly:**

| Surface   | Quads | Triangles | Vertices |
|-----------|-------|-----------|----------|
| Floor     | 1     | 2         | 4        |
| Ceiling   | 1     | 2         | 4        |
| South wall| 1     | 2         | 4        |
| North wall| 1     | 2         | 4        |
| West wall | 1     | 2         | 4        |
| East wall | 1     | 2         | 4        |
| **Total** | **6** | **12**    | **24**   |

**Vertex / face count formula:**

```
expected_vertices = len(spec["rooms"]) × stories × 24
expected_faces    = len(spec["rooms"]) × stories × 12
```

**Validation check:**

```python
assert len(all_verts) == len(rooms) * stories * 24
assert len(all_faces) == len(rooms) * stories * 12
```

**Failure mode:** If `spec["rooms"]` is empty, the generator falls back to a
single `main_space` room sized to the total footprint. This is the only
permitted fallback and must be logged as a warning.

---

## Rule 2 — No Placeholder Meshes Allowed

**Requirement:**
The output GLB must contain only geometry derived from `spec["rooms"]` and
`spec["room_dimensions"]`. The following are strictly forbidden:

| Forbidden element          | Reason                                      |
|----------------------------|---------------------------------------------|
| Single bounding-box cube   | Does not represent any room                 |
| Zero-vertex mesh           | Invalid GLB, crashes renderers              |
| Repeated identical meshes  | Indicates copy-paste placeholder logic      |
| Hardcoded 10×10×3 box      | Not derived from spec semantics             |
| Automotive geometry        | Irrelevant to architectural output          |
| Electronics geometry       | Irrelevant to architectural output          |
| `create_slab_geometry()`   | Removed — slabs are not rooms               |
| `create_box_geometry()`    | Removed — generic boxes are not rooms       |

**How to detect a placeholder:**

A mesh is a placeholder if:
- All rooms share identical vertex coordinates (no positional offset)
- Vertex count does not match `len(rooms) × 24`
- GLB binary is smaller than `len(rooms) × 24 × 12` bytes (vertex data alone)

**Minimum valid GLB size:**

```
min_bytes = len(rooms) × 24 × 12   # 12 bytes per vertex (3 × float32)
           + len(rooms) × 12 × 3 × 2  # index data (3 indices × uint16 per face)
           + 200                       # GLB header + JSON overhead
```

For a 2BHK (7 rooms): minimum ≈ 2,216 bytes. Actual output: ~5,184 bytes.

---

## Rule 3 — Output Must Reflect Semantic Structure

**Requirement:**
The geometry must be a direct spatial representation of the semantic spec
produced by `extract_semantics()` and injected by `_instruction_to_spec_json()`.
The following mappings are mandatory:

### 3a — Room count must match BHK definition

| BHK Type   | Rooms in spec | Expected meshes in GLB |
|------------|---------------|------------------------|
| 1BHK       | 5             | 5                      |
| 2BHK       | 7             | 7                      |
| 3BHK       | 11            | 11                     |
| 4BHK       | 14            | 14                     |
| 5BHK       | 18            | 18                     |
| VILLA      | 16            | 16                     |
| PENTHOUSE  | 13            | 13                     |

### 3b — Room dimensions must come from semantic layer

Dimension resolution priority (highest to lowest):

```
1. spec["room_dimensions"][room_name]   ← from bhk_definitions.json
2. _ROOM_DEFAULTS[base_room_type]       ← canonical fallback table
3. (3.5m × 4.0m × floor_height)        ← absolute last resort
```

A room dimension of exactly `3.5 × 4.0` for every room is a validation
failure — it means the semantic layer was not consulted.

### 3c — Stories must produce stacked geometry

For `spec["stories"] > 1`, each story must be offset on the Z axis:

```
z_offset = story_index × (floor_height + 0.15)
```

A 2-storey spec must produce `2 × len(rooms)` meshes. A single-storey
output for a multi-storey spec is a validation failure.

### 3d — Total footprint must match spec dimensions

The bounding box of all room meshes combined must not exceed:

```
max_x ≤ spec["dimensions"]["width"]  + tolerance(0.5m)
max_y ≤ spec["dimensions"]["length"] + tolerance(0.5m)
max_z ≤ spec["dimensions"]["height"] + tolerance(0.3m)
```

---

## Rule 4 — GLB Binary Format Requirements

Every output file must be a valid GLB 2.0 binary satisfying:

| Field              | Required value / constraint                     |
|--------------------|-------------------------------------------------|
| Magic bytes [0:4]  | `b"glTF"`                                       |
| Version [4:8]      | `2` (little-endian uint32)                      |
| JSON chunk type    | `b"JSON"`                                       |
| BIN chunk type     | `b"BIN\x00"`                                    |
| Accessor 0         | POSITION, VEC3, FLOAT (componentType 5126)      |
| Accessor 1         | NORMAL, VEC3, FLOAT (componentType 5126)        |
| Accessor 2         | indices, SCALAR, UNSIGNED_SHORT (componentType 5123) |
| Primitive mode     | `4` (TRIANGLES)                                 |
| All bufferViews    | 4-byte aligned                                  |
| NORMAL accessor    | count == POSITION accessor count                |

---

## Rule 5 — Storage Enforcement

**Requirement:**
The GLB bytes must be uploaded to the `geometry` bucket via `upload_to_bucket()`
before any URL is returned. Local file paths are not valid output.

```python
# CORRECT
bucket_url = await upload_to_bucket("geometry", f"{spec_id}.glb", glb_bytes)
return bucket_url                          # "/api/v1/files/geometry/<id>"

# FORBIDDEN
with open(f"data/{spec_id}.glb", "wb") as f:
    f.write(glb_bytes)
return f"/static/geometry/{spec_id}.glb"  # local path — NOT ALLOWED
```

---

## Validation Checklist

Run before every release:

- [ ] `glb[:4] == b"glTF"` — valid GLB magic
- [ ] `len(all_verts) == len(rooms) * stories * 24` — room count matches
- [ ] `len(all_faces) == len(rooms) * stories * 12` — face count matches
- [ ] No room has dimensions exactly `(3.5, 4.0)` for all rooms — semantics applied
- [ ] Multi-storey spec produces `stories` layers of meshes
- [ ] Bounding box fits within `spec["dimensions"]` + tolerance
- [ ] Output URL starts with `/api/v1/files/geometry/` — bucket upload confirmed
- [ ] No `open()` call in geometry pipeline — no local writes
- [ ] `spec["rooms"]` list is non-empty before `generate_real_glb()` is called

---

## Canonical Room Dimension Reference

Sourced from `design_semantics/bhk_definitions.json` and
`geometry_generator_real._ROOM_DEFAULTS`:

| Room              | Width (m) | Length (m) | Height (m) |
|-------------------|-----------|------------|------------|
| master_bedroom    | 4.0       | 4.5        | 2.8        |
| bedroom           | 3.5       | 4.0        | 2.7        |
| hall              | 4.5       | 5.5        | 2.8        |
| kitchen           | 3.0       | 4.0        | 2.7        |
| dining            | 3.5       | 4.0        | 2.7        |
| master_bathroom   | 2.5       | 3.0        | 2.4        |
| bathroom          | 2.0       | 2.5        | 2.4        |
| common_bathroom   | 1.8       | 2.2        | 2.4        |
| balcony           | 1.5       | 3.5        | 2.4        |
| study             | 3.0       | 3.5        | 2.7        |
| pooja_room        | 2.0       | 2.5        | 2.7        |
| garage            | 6.0       | 6.0        | 2.5        |
| terrace           | 8.0       | 10.0       | 0.3        |
| home_theatre      | 5.0       | 6.0        | 2.8        |
| jacuzzi_deck      | 4.0       | 5.0        | 0.5        |
| garden            | 6.0       | 8.0        | 0.1        |

---

## Related Files

| File                                          | Role                                      |
|-----------------------------------------------|-------------------------------------------|
| `app/geometry_generator_real.py`              | Room mesh generator — enforces Rules 1–4 |
| `app/design_semantics/bhk_definitions.json`   | Canonical room counts and dimensions      |
| `app/design_semantics/semantic_detector.py`   | Extracts BHK type and room list           |
| `app/prompt_runner_adapter.py`                | Injects semantics into spec_json          |
| `app/core_bucket_pipeline.py`                 | Calls generator, enforces Rule 5          |
| `app/storage.py`                              | `upload_to_bucket()` — bucket-only upload |
| `EXECUTION_AUTHORITY.md`                      | Single execution path policy              |
