# GEOMETRY_VALIDATION.md

**Version:** 2.0
**Status:** ENFORCED — run before every release

---

## Vertex / Face Formula

```
vertices = len(spec["rooms"]) × stories × 24
faces    = len(spec["rooms"]) × stories × 12
```

Each room mesh = 6 quads (floor + ceiling + 4 walls) = 12 triangles = 24 vertices.

## BHK Room → Mesh Count

| BHK Type  | Rooms | Meshes (1 storey) |
|-----------|-------|-------------------|
| 1BHK      | 4     | 4                 |
| 2BHK      | 6     | 6                 |
| 3BHK      | 9     | 9                 |
| 4BHK      | 12    | 12                |
| 5BHK      | 15    | 15                |
| VILLA     | 16    | 16                |
| PENTHOUSE | 13    | 13                |

## Confirmed Outputs (Determinism Test)

| Prompt          | BHK  | Rooms | GLB bytes | Hash             |
|-----------------|------|-------|-----------|------------------|
| Generate 1BHK   | 1BHK | 4     | 3,240     | 122ba765f8d740e9 |
| Generate 2BHK   | 2BHK | 6     | 4,536     | 5409aa2f640c18b8 |
| Generate 3BHK   | 3BHK | 9     | 6,480     | ea826cc928f4d3ad |

## GLB Format Requirements

| Field | Required |
|-------|----------|
| Magic bytes [0:4] | `b"glTF"` |
| Version [4:8] | `2` (uint32 LE) |
| Accessor 0 | POSITION, VEC3, FLOAT (5126) |
| Accessor 1 | NORMAL, VEC3, FLOAT (5126) |
| Accessor 2 | indices, SCALAR, UNSIGNED_SHORT (5123) |
| Primitive mode | `4` (TRIANGLES) |

## Forbidden Geometry

- Single bounding-box cube
- Hardcoded 10×10×3 box
- Zero-vertex mesh
- Repeated identical meshes (no positional offset)
- `create_slab_geometry()` / `create_box_geometry()` calls

## Validation Checklist

- [ ] `glb[:4] == b"glTF"`
- [ ] `len(verts) == len(rooms) * stories * 24`
- [ ] `len(faces) == len(rooms) * stories * 12`
- [ ] No room has identical dimensions to all others (semantics applied)
- [ ] Multi-storey: each story offset by `story_index × (floor_height + 0.15)` on Z
- [ ] Output URL starts with `/api/v1/files/geometry/`
- [ ] No `open()` call in geometry pipeline

## Storage Rule

```python
# CORRECT
bucket_url = await upload_to_bucket("geometry", f"{spec_id}.glb", glb_bytes)
return bucket_url

# FORBIDDEN
with open(f"data/{spec_id}.glb", "wb") as f: ...
```
