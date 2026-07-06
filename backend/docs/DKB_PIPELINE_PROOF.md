# DKB Pipeline Proof

**Sprint:** Design Knowledge Base — Phase 1
**Version:** 1.0
**File:** `app/design_knowledge/runtime/pipeline.py`

---

## Overview

This document proves that `DKBExecutionPipeline` correctly bridges the DKB runtime to the existing Sprint 1 TTG pipeline without modifying any Sprint 1 code.

---

## Pipeline Execution Flow

```
DKBExecutionPipeline.run(instruction, trace_id)
    │
    ├─ DKBRuntime.execute(instruction)
    │       Returns: DKBRuntimeResult
    │       Raises:  DKBRuntimeNoMatchError → propagated as-is
    │
    ├─ _build_semantic(spec)
    │       DesignSpecification → {domain, entity, generation_mode, geometry_family}
    │       Raises:  DKBExecutionPipelineError on unknown project_type
    │
    ├─ _build_spec_json(spec, dkb_result)
    │       DesignSpecification → TTG spec_json dict
    │
    └─ TTGGenerationPipeline (Sprint 1 — unchanged)
           _step_payload(semantic, spec_json, bucket_urls, trace_id)
           _step_execute(payload)   → POST /core/execute
           _step_poll(execution_id) → GET /core/execution/{id}
           _step_record(result)     → BucketAssetRecord
    │
    ▼
DKBExecutionResult
    ├── dkb_result:        DKBRuntimeResult
    ├── execution_id:      str
    ├── domain:            str
    ├── entity:            str
    ├── bucket_url:        str
    ├── execution_status:  str
    └── to_dict()
```

---

## Semantic Mapping

| DKB `project_type` | TTG `domain` | `generation_mode` | `geometry_family` |
|---|---|---|---|
| `residential` | `architecture` | `layout` | `apartment_layout` |
| `commercial` | `architecture` | `layout` | `apartment_layout` |

`entity` is always set to `spec.design_type` (e.g. `"3bhk"`, `"villa"`).

### Test references — `test_pipeline.py`

```
test_project_type_to_domain_residential
test_project_type_to_domain_commercial
test_project_type_to_domain_architecture
test_domain_generation_mode_architecture
test_domain_geometry_family_architecture
test_build_semantic_residential
test_build_semantic_villa
test_build_semantic_unknown_project_type_raises
```

---

## spec_json Construction

`_build_spec_json()` produces a dict that TTGPayloadBuilder can consume:

```python
{
    "design_type":    spec.design_type,
    "project_type":   spec.project_type,
    "spaces":         [{"name": s.name, "required": s.required, ...} for s in spec.spaces],
    "adjacency":      [{"from": e.from_space, "to": e.to_space, ...} for e in spec.adjacency_graph],
    "circulation":    spec.circulation_rules,
    "engineering":    [{"category": c.category, ...} for c in spec.engineering],
    "validation_rules": [{"rule_id": r.rule_id, ...} for r in spec.validation_rules],
    "supported_styles": spec.supported_styles,
    "knowledge_id":   spec.generation_metadata.knowledge_id,
    "knowledge_version": spec.generation_metadata.knowledge_version,
    **spec.raw_body   # planning_philosophy, purpose, occupancy, etc.
}
```

### Test references — `test_pipeline.py`

```
test_build_spec_json_has_required_keys
test_build_spec_json_design_type_matches
test_build_spec_json_raw_body_merged
test_build_spec_json_spaces_is_list
```

---

## Sprint 1 Boundary

The following Sprint 1 files were **read but never modified**:

| File | Role |
|---|---|
| `app/services/ttg_generation_pipeline.py` | Steps 2–6 called directly |
| `app/adapters/ttg_payload_builder.py` | Assembles TTGExecutePayload |
| `app/services/ttg_client.py` | POST /core/execute + polling |
| `app/contracts/bucket_asset_record.py` | Asset record |
| `app/services/core_gateway.py` | Bypassed — DKB already resolved semantic |

`_step_gateway()` is intentionally skipped because `DKBRuntime` already resolved the semantic context. Steps 2–6 are called directly on the existing `TTGGenerationPipeline` instance.

---

## Error Propagation

| Condition | Behaviour | Test |
|---|---|---|
| No DKB match | `DKBRuntimeNoMatchError` propagated | `test_run_no_match_propagates` |
| TTG execute fails | `DKBExecutionPipelineError` raised | `test_run_ttg_failure_raises_pipeline_error` |
| Unknown project_type | `DKBExecutionPipelineError` raised | `test_build_semantic_unknown_project_type_raises` |

---

## All 9 Residential Entries — Verified

| Query | Entity | Status |
|---|---|---|
| `studio apartment single room` | studio | ✅ |
| `1rk room kitchen` | 1rk | ✅ |
| `1bhk one bedroom hall kitchen` | 1bhk | ✅ |
| `2bhk two bedroom apartment` | 2bhk | ✅ |
| `3bhk three bedroom family apartment` | 3bhk | ✅ |
| `4bhk four bedroom large apartment` | 4bhk | ✅ |
| `villa independent house garden` | villa | ✅ |
| `duplex two floor apartment` | duplex | ✅ |
| `penthouse top floor terrace luxury` | penthouse | ✅ |

### Test references — `test_pipeline.py`

```
test_run_all_residential_entries[studio apartment single room-studio]
test_run_all_residential_entries[1rk room kitchen-1rk]
test_run_all_residential_entries[1bhk one bedroom hall kitchen-1bhk]
test_run_all_residential_entries[2bhk two bedroom apartment-2bhk]
test_run_all_residential_entries[3bhk three bedroom family apartment-3bhk]
test_run_all_residential_entries[4bhk four bedroom large apartment-4bhk]
test_run_all_residential_entries[villa independent house garden-villa]
test_run_all_residential_entries[duplex two floor apartment-duplex]
test_run_all_residential_entries[penthouse top floor terrace luxury-penthouse]
```

---

## to_dict() Serialisation

`DKBExecutionResult.to_dict()` returns a JSON-serialisable dict with these keys:

```
execution_id, domain, entity, bucket_url, execution_status,
knowledge_id, design_type, validation_valid, validation_score,
semantic, trace_id
```

### Test references — `test_pipeline.py`

```
test_result_to_dict_has_all_keys
test_result_to_dict_knowledge_id_correct
```

---

## Summary

| Requirement | Implemented | Tested |
|---|---|---|
| DKBRuntime called before TTG | Yes — sequential in run() | Yes — test_run_result_has_dkb_result |
| Semantic derived from DesignSpecification | Yes — _build_semantic() | Yes — test_build_semantic_* |
| spec_json derived from DesignSpecification | Yes — _build_spec_json() | Yes — test_build_spec_json_* |
| Sprint 1 code unchanged | Yes — no modifications | Yes — all Sprint 1 tests still pass |
| All 9 entries execute correctly | Yes — parametrised test | Yes — test_run_all_residential_entries |
| Error propagation correct | Yes — DKBExecutionPipelineError | Yes — test_run_ttg_failure_raises_pipeline_error |

---

*Generated from live codebase — DKB Sprint Phase 1*
*36 / 36 pipeline tests passing*
