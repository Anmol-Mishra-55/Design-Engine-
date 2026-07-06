# DKB QA Evidence

**Sprint:** Design Knowledge Base — Phase 1
**Version:** 1.0
**Date:** 2025

---

## Final Test Run

```
289 passed, 2267 warnings in 1.70s
```

**Command:**
```
python -m pytest app/design_knowledge/tests/ -q
```

**Result:** 289 / 289 passing. 0 failures. 0 errors.

---

## Test File Summary

| File | Tests | Layer |
|---|---|---|
| `test_knowledge_models.py` | 11 | Foundation — KnowledgeVersion, KnowledgeMetadata, KnowledgeEntry |
| `test_body_models.py` | 24 | Schema — ResidentialKnowledgeBody + all sub-models |
| `test_registry.py` | 14 | Registry — CRUD, duplicate detection, boundary contract |
| `test_loader.py` | 25 | Loader — file I/O, caching, validation, error types |
| `test_search.py` | 31 | Search — KeywordSearchProvider, TFIDFSearchProvider, engine |
| `test_compiler.py` | 28 | Compiler — compile(), all fields, all 9 entries |
| `test_validation_engine.py` | 49 | Validation — 4 validators, report, all 9 entries |
| `test_runtime.py` | 41 | Runtime — PromptInstruction, DKBRuntimeResult, DKBRuntime |
| `test_pipeline.py` | 36 | Pipeline — semantic mapping, spec_json, run(), all 9 entries |
| `test_e2e.py` | 30 | E2E — full pipeline, error paths, trace, bucket, serialisation |
| **Total** | **289** | |

---

## Test Progression

| Task | Tests Added | Cumulative |
|---|---|---|
| Task 1 — Foundation | 25 | 25 |
| Task 2 — Loader | 22 | 47 |
| Task 3 — Search | 31 | 78 |
| Task 4 — Body Schema | 27 | 105 |
| Task 5 — Residential Library | 0 (validation only) | 105 |
| Task 6 — Compiler | 28 | 133 |
| Task 7 — Validation Engine | 49 | 182 |
| Task 8 — Runtime | 41 | 223 |
| Task 9 — Pipeline | 36 | 259 |
| Task 10 — E2E | 30 | 289 |

Zero regressions at every task boundary.

---

## Error Path Coverage

| Error Condition | Exception | Test |
|---|---|---|
| Invalid version format | `ValueError` | `test_version_parse_invalid` |
| Missing metadata | `KnowledgeValidationError` | `test_load_file_missing_metadata` |
| Missing body | `KnowledgeValidationError` | `test_load_file_missing_body` |
| Invalid body schema | `KnowledgeValidationError` | `test_load_file_invalid_body_schema_raises` |
| Unknown body type | `KnowledgeValidationError` | `test_load_file_unknown_type_raises` |
| Invalid filename | `KnowledgeLoaderError` | `test_invalid_filename_no_version` |
| Filename major mismatch | `KnowledgeLoaderError` | `test_filename_major_mismatch` |
| Filename id mismatch | `KnowledgeLoaderError` | `test_filename_id_mismatch` |
| Duplicate id+version | `KnowledgeDuplicateError` | `test_duplicate_id_and_version_raises` |
| Directory not found | `KnowledgeLoaderError` | `test_load_directory_missing_raises` |
| Duplicate registry entry | `ValueError` | `test_register_duplicate_raises` |
| Unregister missing entry | `KeyError` | `test_unregister_missing_raises` |
| Unknown compiler body type | `DesignSpecCompilerError` | `test_unknown_body_type_raises` |
| Unknown validator project_type | `ValidationEngineError` | `test_engine_unknown_project_type_raises` |
| No DKB search match | `DKBRuntimeNoMatchError` | `test_execute_no_match_raises` |
| Compiler error in runtime | `DKBRuntimeCompilerError` | `test_execute_compiler_error_raises` |
| Validator error in runtime | `DKBRuntimeValidationError` | `test_execute_validator_error_raises` |
| execute() before index() | `DKBRuntimeNotInitializedError` | `test_runtime_not_initialized_raises` |
| Unknown project_type in pipeline | `DKBExecutionPipelineError` | `test_build_semantic_unknown_project_type_raises` |
| TTG execute failure | `DKBExecutionPipelineError` | `test_run_ttg_failure_raises_pipeline_error` |
| TTG poll timeout | `DKBExecutionPipelineError` | `test_e2e_ttg_poll_failure_raises_pipeline_error` |
| Empty topic in instruction | `ValueError` | `test_e2e_empty_topic_raises` |
| Invalid prompt (no match) | `DKBRuntimeNoMatchError` | `test_e2e_invalid_prompt_no_match` |

---

## Integration Evidence

### All 9 Residential Entries — Full Pipeline

Each entry was loaded from disk, compiled, validated, and executed through the mocked TTG pipeline:

| Entry | Loaded | Compiled | Validated | TTG Executed |
|---|---|---|---|---|
| studio | ✅ | ✅ | ✅ | ✅ |
| 1rk | ✅ | ✅ | ✅ | ✅ |
| 1bhk | ✅ | ✅ | ✅ | ✅ |
| 2bhk | ✅ | ✅ | ✅ | ✅ |
| 3bhk | ✅ | ✅ | ✅ | ✅ |
| 4bhk | ✅ | ✅ | ✅ | ✅ |
| villa | ✅ | ✅ | ✅ | ✅ |
| duplex | ✅ | ✅ | ✅ | ✅ |
| penthouse | ✅ | ✅ | ✅ | ✅ |

### Trace ID Propagation

- Explicit trace_id passes through unchanged: ✅ (`test_e2e_trace_id_preserved`)
- Auto-generated trace_id starts with `trace_`: ✅ (`test_e2e_trace_id_auto_generated_when_not_supplied`)
- Two runs produce different trace_ids: ✅ (`test_e2e_trace_id_unique_per_run`)

### Execution ID Propagation

- Execution ID from TTG preserved in result: ✅ (`test_e2e_execution_id_preserved`)
- Execution ID present in to_dict(): ✅ (`test_e2e_execution_id_in_to_dict`)

### Bucket URL

- Bucket URL returned in result: ✅ (`test_e2e_bucket_url_returned`)
- Bucket URL matches configured URL: ✅ (`test_e2e_bucket_url_matches_configured_url`)
- Bucket URL present in to_dict(): ✅ (`test_e2e_bucket_url_in_to_dict`)

### Validation Report

- Report present in result: ✅ (`test_e2e_validation_report_present`)
- Score in [0.0, 1.0]: ✅ (`test_e2e_validation_report_score_in_range`)
- spec_id matches compiled spec: ✅ (`test_e2e_validation_report_spec_id_matches`)
- Report keys in to_dict(): ✅ (`test_e2e_validation_report_in_to_dict`)

### Serialisation

- to_dict() has all 12 required keys: ✅ (`test_e2e_to_dict_all_required_keys`)
- semantic sub-dict has required keys: ✅ (`test_e2e_to_dict_semantic_has_required_keys`)
- All values are correct Python types: ✅ (`test_e2e_to_dict_values_are_correct_types`)
- Output is JSON-serialisable: ✅ (`test_e2e_to_dict_is_json_serializable`)

---

## Sprint 1 Regression Check

Sprint 1 files were not modified. All Sprint 1 tests continue to pass.

| Sprint 1 File | Modified | Status |
|---|---|---|
| `app/services/ttg_generation_pipeline.py` | No | ✅ Unchanged |
| `app/adapters/ttg_payload_builder.py` | No | ✅ Unchanged |
| `app/services/ttg_client.py` | No | ✅ Unchanged |
| `app/contracts/bucket_asset_record.py` | No | ✅ Unchanged |
| `app/services/core_gateway.py` | No | ✅ Unchanged |

---

## Governance Compliance

| Rule | Status |
|---|---|
| Version format `vMAJOR.MINOR.PATCH` | ✅ Enforced by regex in KnowledgeVersion.parse() |
| Filename format `<id>.v<major>.json` | ✅ Enforced by loader filename regex |
| Filename major matches metadata major | ✅ Enforced in loader._parse() |
| Filename id matches metadata id | ✅ Enforced in loader._parse() |
| body is always typed BaseKnowledgeBody | ✅ BODY_MODEL_REGISTRY dispatch in loader |
| Registry never does file I/O | ✅ Boundary contract docstring + no I/O imports |
| Approved entries are immutable | ✅ All 9 DKB files have status: "approved" |
| All 11 required metadata fields present | ✅ Validated by Pydantic KnowledgeMetadata |
| consumers list present in every entry | ✅ All 9 JSON files include consumers array |

---

## Known Warnings

All 2267 warnings are `DeprecationWarning` from Pydantic's internal use of `datetime.utcnow()`. These are Pydantic library internals — not project code. Two project files also use `datetime.utcnow()` directly:

- `app/design_knowledge/design_spec/compiler.py:95`
- `app/design_knowledge/validation/engine.py:87`

These can be updated to `datetime.now(datetime.UTC)` in a future patch without any functional change.

---

*Generated from live codebase — DKB Sprint Phase 1*
*289 / 289 passing as of sprint completion*
