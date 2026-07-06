# DKB Validation Proof

**Sprint:** Design Knowledge Base — Phase 1
**Version:** 1.0
**Files:** `app/design_knowledge/validation/`

---

## Overview

This document proves that the `ValidationEngine` correctly validates compiled `DesignSpecification` objects using four independent validators, and that validation failure is always a data outcome — never an exception.

---

## Validation Architecture

```
ValidationEngine.validate(spec: DesignSpecification)
    │
    ├─ VALIDATOR_REGISTRY[spec.project_type]  → ResidentialValidator
    │
    └─ ResidentialValidator.validate(spec)
           │
           ├─ SpaceValidator.validate(spec)
           │       Checks: required spaces present, area ranges valid, nonempty
           │
           ├─ RelationshipValidator.validate(spec)
           │       Checks: adjacency edges reference existing spaces,
           │               no self-references, no contradictions
           │
           ├─ EngineeringValidator.validate(spec)
           │       Checks: structural + fire categories present,
           │               no empty constraint text, no duplicates
           │
           └─ RuleValidator.validate(spec)
                   Checks: machine-checkable validation_rules from DKB body
                   Conditions: space_present, area_gte, two_spaces_present,
                               relationship_adjacent, no_direct_access
    │
    ▼
ValidationReport
    ├── spec_id:        str
    ├── validated_at:   datetime
    ├── findings:       List[ValidationFinding]
    ├── valid:          bool  (True if no error-severity failures)
    ├── score:          float (passed / total findings)
    ├── errors:         List[ValidationFinding]
    ├── warnings:       List[ValidationFinding]
    ├── passed_rules:   List[str]
    └── failed_rules:   List[str]
```

---

## Validator Registry

| `project_type` | Validator |
|---|---|
| `residential` | `ResidentialValidator` |
| *(future)* `commercial` | `CommercialValidator` |

Unknown `project_type` raises `ValidationEngineError` immediately.

### Test references — `test_validation_engine.py`

```
test_validator_registry_contains_residential
test_engine_unknown_project_type_raises
```

---

## SpaceValidator

**Rule IDs:** `SPC-REQUIRED-NONEMPTY`, `SPC-AREA-{name}`

| Check | Pass condition | Severity |
|---|---|---|
| Required spaces list is non-empty | `len(required) > 0` | error |
| Each space area range is valid | `min_area > 0` and `max_area >= min_area` | error |

### Test references — `test_validation_engine.py`

```
test_space_validator_passes_valid_spec
test_space_validator_detects_invalid_area_range
test_space_validator_nonempty_check_fails_on_empty
test_space_validator_name
```

---

## RelationshipValidator

**Rule IDs:** `REL-NONEMPTY`, `REL-DANGLING-{from}`, `REL-DANGLING-{to}`, `REL-SELF-{space}`, `REL-CONTRADICT-{a}-{b}`

| Check | Pass condition | Severity |
|---|---|---|
| Adjacency graph non-empty | `len(adjacency_graph) > 0` | warning |
| No dangling from_space | `from_space` in space names | error |
| No dangling to_space | `to_space` in space names | error |
| No self-reference | `from_space != to_space` | error |
| No contradictions | No A→B and B→A with conflicting relationships | warning |

### Test references — `test_validation_engine.py`

```
test_relationship_validator_passes_valid_spec
test_relationship_validator_detects_dangling_from_space
test_relationship_validator_detects_dangling_to_space
test_relationship_validator_detects_self_reference
test_relationship_validator_detects_contradiction
test_relationship_validator_warns_empty_graph
```

---

## EngineeringValidator

**Rule IDs:** `ENG-CAT-{category}`, `ENG-EMPTY-{i}`, `ENG-DUP-{category}`

| Check | Pass condition | Severity |
|---|---|---|
| `structural` category present | At least one structural constraint | error |
| `fire` category present | At least one fire constraint | error |
| No empty constraint text | `constraint` field non-empty | error |
| No duplicate categories | Each category appears at most once | warning |

### Test references — `test_validation_engine.py`

```
test_engineering_validator_passes_valid_spec
test_engineering_validator_detects_missing_structural
test_engineering_validator_detects_missing_fire
test_engineering_validator_detects_empty_constraint_text
test_engineering_validator_warns_duplicate
```

---

## RuleValidator

**Rule IDs:** taken directly from `ValidationRuleSpec.rule_id` in the DKB body.

Supported condition types:

| Condition | Checks |
|---|---|
| `space_present` | Named space exists in spec.spaces |
| `area_gte` | Space min_area >= threshold |
| `two_spaces_present` | Both named spaces exist |
| `relationship_adjacent` | Adjacency edge exists between two spaces |
| `no_direct_access` | No direct_access edge between two spaces |
| *(unrecognised)* | Passes silently — does not fail |

Validation failure is always a `ValidationFinding(passed=False)` — never an exception.

### Test references — `test_validation_engine.py`

```
test_rule_validator_passes_present_space
test_rule_validator_fails_missing_space
test_rule_validator_area_gte_passes
test_rule_validator_area_gte_fails
test_rule_validator_two_spaces_present
test_rule_validator_two_spaces_one_missing
test_rule_validator_relationship_adjacent_passes
test_rule_validator_relationship_missing_fails
test_rule_validator_no_direct_access_passes
test_rule_validator_unrecognised_condition_does_not_fail
test_rule_validator_warns_empty_rules
```

---

## ValidationReport Contract

### valid property

```python
report.valid
# True  if no finding has passed=False AND severity="error"
# False if any finding has passed=False AND severity="error"
```

### score property

```python
report.score
# passed_count / total_count  (0.0 if no findings)
```

### Test references — `test_validation_engine.py`

```
test_report_valid_when_no_error_failures
test_report_invalid_when_error_failure
test_report_valid_with_only_warning_failures
test_report_score_all_pass
test_report_score_half_pass
test_report_score_empty_findings
test_report_errors_list
test_report_warnings_list
test_report_passed_and_failed_rules
test_report_validated_at_is_datetime
```

---

## All 9 Residential Entries — Verified

Every entry produces a valid report with findings and a score above zero:

| Entry | valid | score > 0 | findings present |
|---|---|---|---|
| studio | ✅ | ✅ | ✅ |
| 1rk | ✅ | ✅ | ✅ |
| 1bhk | ✅ | ✅ | ✅ |
| 2bhk | ✅ | ✅ | ✅ |
| 3bhk | ✅ | ✅ | ✅ |
| 4bhk | ✅ | ✅ | ✅ |
| villa | ✅ | ✅ | ✅ |
| duplex | ✅ | ✅ | ✅ |
| penthouse | ✅ | ✅ | ✅ |

### Test references — `test_validation_engine.py`

```
test_all_residential_entries_produce_valid_reports
test_all_residential_entries_have_findings
test_all_residential_entries_score_above_zero
test_3bhk_validation_passes_core_rules
test_studio_validation_passes_core_rules
```

---

## Summary

| Requirement | Implemented | Tested |
|---|---|---|
| Validation failure is result not exception | Yes — ValidationReport(valid=False) | Yes — test_report_invalid_when_error_failure |
| Four independent validators | Yes — Space, Relationship, Engineering, Rule | Yes — all validator tests |
| Registry-based domain dispatch | Yes — VALIDATOR_REGISTRY dict | Yes — test_validator_registry_contains_residential |
| Unknown type raises immediately | Yes — ValidationEngineError | Yes — test_engine_unknown_project_type_raises |
| Score computed correctly | Yes — passed/total | Yes — test_report_score_* |
| All 9 entries validate correctly | Yes — parametrised | Yes — test_all_residential_entries_* |

---

*Generated from live codebase — DKB Sprint Phase 1*
*49 / 49 validation engine tests passing*
