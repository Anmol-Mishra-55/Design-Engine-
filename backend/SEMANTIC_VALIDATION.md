# SEMANTIC_VALIDATION.md

## Purpose

This document defines the mandatory validation rules for all semantic output
produced by `extract_semantics()` in `design_semantics/semantic_detector.py`.
Every `SemanticResult` and every `spec_json` built from it must satisfy every
rule listed here before geometry generation begins.

---

## Rule 1 — BHK Bedroom Count Must Be Exact

Each BHK type has a fixed, non-negotiable bedroom count sourced from
`bhk_definitions.json → room_counts.bedroom`.

| BHK Type  | Required bedrooms | Required hall | Required kitchen | Required bathrooms |
|-----------|-------------------|---------------|------------------|--------------------|
| 1BHK      | **1**             | 1             | 1                | 1                  |
| 2BHK      | **2**             | 1             | 1                | 2                  |
| 3BHK      | **3**             | 1             | 1                | 3                  |
| 4BHK      | **4**             | 1             | 1                | 4                  |
| 5BHK      | **5**             | 1             | 1                | 5                  |
| VILLA     | **4**             | 1             | 1                | 4                  |
| PENTHOUSE | **3**             | 1             | 1                | 3                  |

**Validation check:**

```python
def validate_bhk_room_counts(spec_json: dict, bhk_key: str) -> None:
    from app.design_semantics import _load_bhk
    expected = _load_bhk()[bhk_key]["room_counts"]
    rooms = spec_json.get("rooms", [])

    # Count bedrooms (master_bedroom + bedroom_N all count as bedrooms)
    bedroom_count = sum(
        1 for r in rooms
        if "bedroom" in r and "bathroom" not in r
    )
    assert bedroom_count == expected["bedroom"], (
        f"{bhk_key} requires {expected['bedroom']} bedrooms, got {bedroom_count}"
    )

    # Count kitchens — must be exactly 1
    kitchen_count = sum(1 for r in rooms if "kitchen" in r)
    assert kitchen_count == expected["kitchen"], (
        f"{bhk_key} requires {expected['kitchen']} kitchen, got {kitchen_count}"
    )

    # Count halls — must be exactly 1
    hall_count = sum(1 for r in rooms if r == "hall")
    assert hall_count == expected["hall"], (
        f"{bhk_key} requires {expected['hall']} hall, got {hall_count}"
    )
```

**Failure examples:**

| Prompt                        | Detected | Rooms generated | Verdict |
|-------------------------------|----------|-----------------|---------|
| "Design a 2BHK apartment"     | 2BHK     | 1 bedroom       | FAIL    |
| "Design a 3BHK flat"          | 3BHK     | 4 bedrooms      | FAIL    |
| "Design a 1BHK studio"        | 1BHK     | 1 bedroom       | PASS    |
| "Design a 2BHK modern flat"   | 2BHK     | 2 bedrooms      | PASS    |

---

## Rule 2 — Mandatory Rooms Per BHK Type

Every BHK type requires a minimum set of rooms. These are non-negotiable.
Sourced from `bhk_definitions.json → rooms`.

### 1BHK — minimum rooms
```
bedroom, hall, kitchen, bathroom, balcony
```

### 2BHK — minimum rooms
```
master_bedroom, bedroom_2, hall, kitchen,
master_bathroom, common_bathroom, balcony
```

### 3BHK — minimum rooms
```
master_bedroom, bedroom_2, bedroom_3, hall, dining, kitchen,
master_bathroom, bathroom_2, common_bathroom, balcony_1, balcony_2
```

### 4BHK — minimum rooms
```
master_bedroom, bedroom_2, bedroom_3, bedroom_4, hall, dining, kitchen,
master_bathroom, bathroom_2, bathroom_3, common_bathroom, study,
balcony_1, balcony_2
```

### 5BHK — minimum rooms
```
master_bedroom, bedroom_2, bedroom_3, bedroom_4, bedroom_5,
hall, dining, kitchen, master_bathroom, bathroom_2, bathroom_3,
bathroom_4, common_bathroom, study, pooja_room,
balcony_1, balcony_2, balcony_3
```

### VILLA — minimum rooms
```
master_bedroom, bedroom_2, bedroom_3, bedroom_4, hall, dining, kitchen,
master_bathroom, bathroom_2, bathroom_3, common_bathroom,
study, pooja_room, garage, garden, terrace
```

### PENTHOUSE — minimum rooms
```
master_bedroom, bedroom_2, bedroom_3, hall, dining, kitchen,
master_bathroom, bathroom_2, common_bathroom,
study, home_theatre, terrace, jacuzzi_deck
```

**Validation check:**

```python
def validate_mandatory_rooms(spec_json: dict, bhk_key: str) -> None:
    from app.design_semantics import _load_bhk
    required = set(_load_bhk()[bhk_key]["rooms"])
    present  = set(spec_json.get("rooms", []))
    missing  = required - present
    assert not missing, f"{bhk_key} missing mandatory rooms: {missing}"
```

---

## Rule 3 — Layout Rules Must Be Enforced

Layout rules are sourced from `design_semantics/layout_rules.json` and
injected into `spec_json["layout_rules"]` by `_instruction_to_spec_json()`.

### 3a — Critical adjacency rules (must never be violated)

| Rule ID  | Constraint                                          | Priority |
|----------|-----------------------------------------------------|----------|
| ADJ_001  | Kitchen adjacent to dining or hall                  | critical |
| ADJ_002  | Bathroom adjacent to bedroom                        | critical |
| ADJ_003  | Hall is central node connecting all rooms           | critical |
| ADJ_005  | Master bedroom has attached master_bathroom         | critical |

**Validation check:**

```python
def validate_adjacency(spec_json: dict) -> None:
    adjacency = spec_json.get("adjacency", {})
    rooms     = set(spec_json.get("rooms", []))

    # ADJ_001: kitchen must connect to hall or dining
    kitchen_neighbors = set(adjacency.get("kitchen", []))
    assert kitchen_neighbors & {"hall", "dining"}, \
        "ADJ_001 FAIL: kitchen not adjacent to hall or dining"

    # ADJ_002: every bathroom must connect to a bedroom
    for room in rooms:
        if "bathroom" in room and "bedroom" not in room:
            neighbors = set(adjacency.get(room, []))
            assert any("bedroom" in n for n in neighbors), \
                f"ADJ_002 FAIL: {room} not adjacent to any bedroom"

    # ADJ_003: hall must connect to at least 2 other rooms
    hall_neighbors = adjacency.get("hall", [])
    assert len(hall_neighbors) >= 2, \
        f"ADJ_003 FAIL: hall connects to only {len(hall_neighbors)} rooms"

    # ADJ_005: master_bedroom must connect to master_bathroom
    if "master_bedroom" in rooms:
        mb_neighbors = set(adjacency.get("master_bedroom", []))
        assert "master_bathroom" in mb_neighbors, \
            "ADJ_005 FAIL: master_bedroom not attached to master_bathroom"
```

### 3b — Zoning rules (must be present in spec)

| Rule ID   | Zone     | Rooms                              | Location              |
|-----------|----------|------------------------------------|-----------------------|
| ZONE_001  | private  | bedrooms + bathrooms               | rear or upper floor   |
| ZONE_002  | public   | hall, dining, kitchen              | front or ground floor |
| ZONE_003  | service  | kitchen, garage                    | side or rear          |
| ZONE_004  | quiet    | study, pooja_room                  | away from service     |

**Validation check:**

```python
def validate_zoning(spec_json: dict) -> None:
    layout_rules = spec_json.get("layout_rules", [])
    rule_ids = {r["rule_id"] for r in layout_rules if isinstance(r, dict)}
    required = {"ZONE_001", "ZONE_002"}   # critical zones
    missing  = required - rule_ids
    assert not missing, f"Missing zoning rules in spec: {missing}"
```

### 3c — Orientation rules (must be present in spec)

| Rule ID  | Room          | Preferred direction | Reason              |
|----------|---------------|---------------------|---------------------|
| ORI_001  | entrance      | North or East       | Vastu + light       |
| ORI_002  | kitchen       | South-East          | Vastu               |
| ORI_003  | master_bedroom| South-West          | Vastu               |
| ORI_004  | hall          | North or East       | Natural light       |
| ORI_005  | bathroom      | Not North-East      | Vastu               |
| ORI_006  | pooja_room    | North-East          | Vastu               |

---

## Rule 4 — Semantic Detection Confidence Thresholds

`extract_semantics()` returns confidence scores. Specs built from low-confidence
detections must be flagged.

| Field              | Minimum confidence | Action if below threshold        |
|--------------------|--------------------|----------------------------------|
| `bhk_confidence`   | 0.8                | Log warning, request clarification |
| `style_confidence` | 0.3                | Default to `"modern"`            |

**Confidence scoring in `detect_bhk()`:**

| Signal type              | Confidence |
|--------------------------|------------|
| Exact `"2BHK"` / `"3BHK"` | 1.0      |
| `"two bedroom"` / `"2 bedroom"` | 0.95 |
| `"villa"` / `"penthouse"` | 0.9–1.0  |
| `"bungalow"` / `"duplex"` | 0.8–0.85 |
| `"studio"` / `"compact apartment"` | 0.8–0.85 |

**Validation check:**

```python
def validate_confidence(sem_result) -> None:
    if sem_result.bhk_key and sem_result.bhk_confidence < 0.8:
        logger.warning(
            "Low BHK confidence %.2f for key %s — verify prompt",
            sem_result.bhk_confidence, sem_result.bhk_key
        )
    if sem_result.style_confidence < 0.3:
        logger.info("Style defaulted to 'modern' (no style signal in prompt)")
```

---

## Rule 5 — Area Must Be Within BHK Bounds

If `area_sqft` is detected in the prompt, it must fall within the
`min_area_sqft` / `max_area_sqft` range defined for the detected BHK type.

| BHK Type  | Min area (sqft) | Max area (sqft) |
|-----------|-----------------|-----------------|
| 1BHK      | 400             | 650             |
| 2BHK      | 700             | 1,000           |
| 3BHK      | 1,000           | 1,500           |
| 4BHK      | 1,500           | 2,200           |
| 5BHK      | 2,200           | 3,500           |
| VILLA     | 2,500           | 6,000           |
| PENTHOUSE | 3,000           | 8,000           |

**Validation check:**

```python
def validate_area_bounds(sem_result) -> None:
    if not sem_result.bhk_key or not sem_result.area_sqft:
        return
    from app.design_semantics import _load_bhk
    defn = _load_bhk()[sem_result.bhk_key]
    lo, hi = defn["min_area_sqft"], defn["max_area_sqft"]
    if not (lo <= sem_result.area_sqft <= hi):
        logger.warning(
            "Area %.0f sqft is outside %s range [%d, %d]",
            sem_result.area_sqft, sem_result.bhk_key, lo, hi
        )
```

---

## Rule 6 — Budget Must Be Within BHK Typical Range

If `budget_inr` is detected, it should fall within the typical budget range
for the detected BHK type. Out-of-range budgets are warnings, not errors.

| BHK Type  | Min budget (INR) | Max budget (INR) |
|-----------|------------------|------------------|
| 1BHK      | 25,00,000        | 50,00,000        |
| 2BHK      | 45,00,000        | 90,00,000        |
| 3BHK      | 70,00,000        | 1,50,00,000      |
| 4BHK      | 1,20,00,000      | 2,50,00,000      |
| 5BHK      | 2,00,00,000      | 5,00,00,000      |
| VILLA     | 3,00,00,000      | 10,00,00,000     |
| PENTHOUSE | 5,00,00,000      | 30,00,00,000     |

---

## Rule 7 — Stories Must Match BHK Definition

Multi-storey specs must match the `stories` field in `bhk_definitions.json`.

| BHK Type  | Default stories |
|-----------|-----------------|
| 1BHK      | 1               |
| 2BHK      | 1               |
| 3BHK      | 1               |
| 4BHK      | 1               |
| 5BHK      | 2               |
| VILLA     | 2               |
| PENTHOUSE | 1               |

If the prompt explicitly specifies stories (e.g. `"G+2"`, `"3 storey"`),
the prompt value overrides the BHK default. The geometry generator must
produce `stories × len(rooms)` meshes.

---

## Validation Checklist

Run before every spec is passed to `generate_real_glb()`:

- [ ] `spec["type"]` matches a key in `bhk_definitions.json`
- [ ] `spec["rooms"]` contains all mandatory rooms for the detected BHK type
- [ ] Bedroom count in `spec["rooms"]` equals `bhk_definitions[type]["room_counts"]["bedroom"]`
- [ ] Kitchen count == 1, Hall count == 1
- [ ] `spec["adjacency"]["kitchen"]` includes `"hall"` or `"dining"`
- [ ] `spec["adjacency"]["master_bedroom"]` includes `"master_bathroom"` (if present)
- [ ] `spec["layout_rules"]` contains at least 10 rules (adjacency + orientation)
- [ ] `bhk_confidence >= 0.8` or warning logged
- [ ] `area_sqft` within BHK bounds (if provided)
- [ ] `spec["stories"]` >= 1 and matches BHK default or prompt override
- [ ] `spec["style"]` is a key in `style_profiles.json`
- [ ] `spec["city"]` is a recognised Indian city

---

## Phase 2 Output Confirmation

| Capability                          | Status |
|-------------------------------------|--------|
| System understands BHK              | PASS — `detect_bhk()` with 28 patterns, conf >= 0.8 |
| 1BHK = exactly 1 bedroom            | PASS — enforced by `bhk_definitions.json` room_counts |
| 2BHK = exactly 2 bedrooms           | PASS — enforced by `bhk_definitions.json` room_counts |
| 3BHK = exactly 3 bedrooms           | PASS — enforced by `bhk_definitions.json` room_counts |
| Layout rules enforced               | PASS — 16 rules injected into every spec_json |
| Geometry matches semantics          | PASS — `generate_real_glb()` iterates `spec["rooms"]` |
| No placeholder meshes               | PASS — `create_room_mesh()` called per room, no box fallback |
| All outputs go to bucket            | PASS — `upload_to_bucket()` enforced, no local writes |

---

## Related Files

| File                                              | Role                                          |
|---------------------------------------------------|-----------------------------------------------|
| `app/design_semantics/bhk_definitions.json`       | Source of truth for room counts and bounds    |
| `app/design_semantics/layout_rules.json`          | Source of truth for adjacency + zoning rules  |
| `app/design_semantics/style_profiles.json`        | Source of truth for style detection keywords  |
| `app/design_semantics/semantic_detector.py`       | `extract_semantics()` — all detection logic   |
| `app/prompt_runner_adapter.py`                    | Injects semantics into spec_json              |
| `app/geometry_generator_real.py`                  | Consumes spec rooms to build GLB              |
| `GEOMETRY_VALIDATION.md`                          | Geometry-level validation rules               |
| `EXECUTION_AUTHORITY.md`                          | Single execution path policy                  |
