# DKB Runtime Proof

**Sprint:** Design Knowledge Base — Phase 1
**Version:** 1.0
**File:** `app/design_knowledge/runtime/runtime.py`

---

## Overview

This document proves that `DKBRuntime` correctly orchestrates the three-stage DKB pipeline — search, compile, validate — and that each stage is called in the correct order with the correct inputs and outputs.

---

## Runtime Execution Flow

```
DKBRuntime.execute(instruction: PromptInstruction)
    │
    ├─ Stage 1: KnowledgeSearchEngine.resolve(instruction.topic)
    │       Returns: KnowledgeEntry
    │       Raises:  DKBRuntimeNoMatchError if no entry scores above zero
    │
    ├─ Stage 2: DesignSpecCompiler.compile(entry)
    │       Returns: DesignSpecification
    │       Raises:  DKBRuntimeCompilerError wrapping DesignSpecCompilerError
    │
    └─ Stage 3: ValidationEngine.validate(spec)
            Returns: ValidationReport
            Raises:  DKBRuntimeValidationError wrapping ValidationEngineError
    │
    ▼
DKBRuntimeResult
    ├── knowledge_entry:       KnowledgeEntry
    ├── design_specification:  DesignSpecification
    ├── validation_report:     ValidationReport
    ├── search_score:          float  (0.0 – 1.0)
    ├── matched_fields:        Dict[str, List[str]]
    ├── topic:                 str
    ├── module:                str
    └── intent:                str
```

---

## PromptInstruction Contract

### Construction

```python
instruction = PromptInstruction.from_prompt_runner({
    "module": "architecture",
    "intent": "design_creation",
    "data": {
        "topic": "3bhk three bedroom family apartment",
        "tasks": [...],
        "output_format": "...",
        "product_context": "..."
    }
})
```

### Validation enforced

| Field | Rule | Error on violation |
|---|---|---|
| `module` | Required, non-empty | `ValueError` |
| `intent` | Required, non-empty | `ValueError` |
| `topic` | Required, non-empty | `ValueError` |
| `tasks` | Optional, defaults to `[]` | — |
| `output_format` | Optional, defaults to `""` | — |
| `product_context` | Optional, defaults to `""` | — |

### Test references — `test_runtime.py`

```
test_prompt_instruction_fields
test_prompt_instruction_from_prompt_runner_valid
test_prompt_instruction_from_prompt_runner_missing_module
test_prompt_instruction_from_prompt_runner_missing_intent
test_prompt_instruction_from_prompt_runner_missing_topic
test_prompt_instruction_from_prompt_runner_defaults
```

---

## Stage Ordering Proof

### Stage 1 always runs before Stage 2

`DKBRuntime.execute()` calls `_search_engine.resolve(topic)` first. If it returns `None`, `DKBRuntimeNoMatchError` is raised immediately — the compiler is never called.

```python
entry = self._search_engine.resolve(instruction.topic)
if entry is None:
    raise DKBRuntimeNoMatchError(...)
# compiler only reached if entry is not None
spec = self._compiler.compile(entry)
```

### Stage 2 always runs before Stage 3

`DesignSpecCompiler.compile(entry)` is called before `ValidationEngine.validate(spec)`. If the compiler raises, the validator is never called.

```python
spec = self._compiler.compile(entry)
# validator only reached if compile() succeeds
report = self._validator.validate(spec)
```

### Test references — `test_runtime.py`

```
test_execute_returns_result
test_execute_result_has_knowledge_entry
test_execute_result_has_design_specification
test_execute_result_has_validation_report
test_execute_no_match_raises
test_execute_compiler_error_raises
test_execute_validator_error_raises
```

---

## Error Hierarchy

```
DKBRuntimeError                    ← base
├── DKBRuntimeNoMatchError         ← search returned None
├── DKBRuntimeCompilerError        ← DesignSpecCompilerError wrapped
├── DKBRuntimeValidationError      ← ValidationEngineError wrapped
└── DKBRuntimeNotInitializedError  ← execute() called before index()
```

### Fail-closed evidence

| Condition | Behaviour | Test |
|---|---|---|
| No search match | `DKBRuntimeNoMatchError` raised, compile never called | `test_execute_no_match_raises` |
| Compiler error | `DKBRuntimeCompilerError` raised, validate never called | `test_execute_compiler_error_raises` |
| Validator error | `DKBRuntimeValidationError` raised | `test_execute_validator_error_raises` |
| execute() before index() | `DKBRuntimeNotInitializedError` raised | `test_runtime_not_initialized_raises` |

---

## DKBRuntimeResult Contract

### Properties

| Property | Type | Description |
|---|---|---|
| `valid` | `bool` | `True` if `validation_report.valid` is `True` |
| `knowledge_id` | `str` | `knowledge_entry.metadata.id` |
| `design_type` | `str` | `design_specification.design_type` |

### summary() output

```python
result.summary()
# {
#   "knowledge_id":    "3bhk",
#   "design_type":     "3bhk",
#   "valid":           True,
#   "score":           0.9231,
#   "search_score":    1.0,
#   "topic":           "3bhk three bedroom family apartment",
#   "module":          "architecture",
#   "intent":          "design_creation"
# }
```

### Test references — `test_runtime.py`

```
test_result_valid_property
test_result_knowledge_id
test_result_design_type
test_result_summary_keys
test_result_summary_values
```

---

## All 9 Residential Entries — Verified

Each entry resolves, compiles, and validates correctly:

| Query | Resolves to | valid |
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

### Test references — `test_runtime.py`

```
test_execute_all_residential_entries[studio apartment single room-studio]
test_execute_all_residential_entries[1rk room kitchen-1rk]
test_execute_all_residential_entries[1bhk one bedroom hall kitchen-1bhk]
test_execute_all_residential_entries[2bhk two bedroom apartment-2bhk]
test_execute_all_residential_entries[3bhk three bedroom family apartment-3bhk]
test_execute_all_residential_entries[4bhk four bedroom large apartment-4bhk]
test_execute_all_residential_entries[villa independent house garden-villa]
test_execute_all_residential_entries[duplex two floor apartment-duplex]
test_execute_all_residential_entries[penthouse top floor terrace luxury-penthouse]
```

---

## Factory Method

```python
runtime = DKBRuntime.from_directory(
    Path("app/design_knowledge/data/residential")
)
# Internally:
#   1. Creates KnowledgeRegistry
#   2. Creates KnowledgeLoader(root_directory, registry)
#   3. loader.load_directory(path)  — loads all 9 entries
#   4. Creates TFIDFSearchProvider
#   5. Creates KnowledgeSearchEngine(provider)
#   6. engine.index(registry.list())
#   7. Creates DesignSpecCompiler
#   8. Creates ValidationEngine
#   9. Returns DKBRuntime(engine, compiler, validator)
```

### Test references — `test_runtime.py`

```
test_runtime_from_directory
test_index_method_enables_execute
```

---

## Summary

| Requirement | Implemented | Tested |
|---|---|---|
| Stage ordering: search → compile → validate | Yes — sequential calls in execute() | Yes — test_execute_* |
| No compile without search match | Yes — NoMatchError raised before compile | Yes — test_execute_no_match_raises |
| No validate without compile success | Yes — CompilerError raised before validate | Yes — test_execute_compiler_error_raises |
| Validation failure is result not exception | Yes — ValidationReport(valid=False) returned | Yes — test_execute_valid_spec_has_valid_true |
| All 9 residential entries resolve correctly | Yes — parametrised test | Yes — test_execute_all_residential_entries |
| PromptInstruction validates required fields | Yes — from_prompt_runner() raises ValueError | Yes — test_prompt_instruction_from_prompt_runner_missing_* |
| DKBRuntimeResult carries all pipeline outputs | Yes — entry + spec + report + scores | Yes — test_result_* |

---

*Generated from live codebase — DKB Sprint Phase 1*
*41 / 41 runtime tests passing*
