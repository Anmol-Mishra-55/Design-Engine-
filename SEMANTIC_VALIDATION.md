# SEMANTIC_VALIDATION.md

**Version:** 2.0
**Status:** ENFORCED — run before every spec is passed to generate_real_glb()

---

## BHK Bedroom Count (Exact Match Required)

| BHK Type  | Bedrooms | Hall | Kitchen | Bathrooms |
|-----------|----------|------|---------|-----------|
| 1BHK      | 1        | 1    | 1       | 1         |
| 2BHK      | 2        | 1    | 1       | 2         |
| 3BHK      | 3        | 1    | 1       | 3         |
| 4BHK      | 4        | 1    | 1       | 4         |
| 5BHK      | 5        | 1    | 1       | 5         |
| VILLA     | 4        | 1    | 1       | 4         |
| PENTHOUSE | 3        | 1    | 1       | 3         |

Source: `bhk_definitions.json → room_counts`

## Detection Confidence Thresholds

| Signal | Confidence | Action if below |
|--------|-----------|-----------------|
| `"2BHK"` / `"3BHK"` (exact) | 1.0 | — |
| `"two bedroom"` / `"2 bedroom"` | 0.95 | — |
| `"villa"` / `"penthouse"` | 0.9–1.0 | — |
| `"bungalow"` / `"duplex"` | 0.8–0.85 | — |
| Below 0.8 | — | Log warning, request clarification |
| Style below 0.3 | — | Default to `"modern"` |

## Critical Adjacency Rules (Must Never Be Violated)

| Rule ID | Constraint |
|---------|-----------|
| ADJ_001 | Kitchen adjacent to dining or hall |
| ADJ_002 | Bathroom adjacent to bedroom |
| ADJ_003 | Hall connects to ≥ 2 rooms |
| ADJ_005 | master_bedroom attached to master_bathroom |

## Area Bounds

| BHK Type  | Min (sqft) | Max (sqft) |
|-----------|-----------|-----------|
| 1BHK      | 400       | 650       |
| 2BHK      | 700       | 1,000     |
| 3BHK      | 1,000     | 1,500     |
| 4BHK      | 1,500     | 2,200     |
| 5BHK      | 2,200     | 3,500     |
| VILLA     | 2,500     | 6,000     |
| PENTHOUSE | 3,000     | 8,000     |

## Stories Rules

- Default stories per BHK from `bhk_definitions.json`
- Prompt override allowed (e.g. `"G+2"`, `"3 storey"`)
- Hard cap: `_MAX_STORIES = 10` (prevents OOM on extreme inputs)
- Multi-storey geometry: Z offset = `story_index × (floor_height + 0.15)`

## Phase 2 Output Confirmation

| Capability | Status |
|-----------|--------|
| BHK detection (28 patterns) | PASS — conf ≥ 0.8 |
| 1BHK = exactly 1 bedroom | PASS |
| 2BHK = exactly 2 bedrooms | PASS |
| 3BHK = exactly 3 bedrooms | PASS |
| Layout rules injected (16 rules) | PASS |
| Geometry matches semantics | PASS |
| No placeholder meshes | PASS |
| All outputs to bucket | PASS |

## Validation Checklist

- [ ] `spec["type"]` is a key in `bhk_definitions.json`
- [ ] `spec["rooms"]` contains all mandatory rooms for BHK type
- [ ] Bedroom count == `bhk_definitions[type]["room_counts"]["bedroom"]`
- [ ] Kitchen count == 1, Hall count == 1
- [ ] `spec["adjacency"]["kitchen"]` includes `"hall"` or `"dining"`
- [ ] `spec["adjacency"]["master_bedroom"]` includes `"master_bathroom"` (if present)
- [ ] `spec["layout_rules"]` contains ≥ 10 rules
- [ ] `bhk_confidence >= 0.8` or warning logged
- [ ] `spec["stories"]` ≥ 1 and ≤ 10
- [ ] `spec["style"]` is a key in `style_profiles.json`
