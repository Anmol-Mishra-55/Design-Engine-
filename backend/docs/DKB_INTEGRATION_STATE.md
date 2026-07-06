# DKB Integration State

**Version:** 1.0
**Sprint:** Design Knowledge Base — Phase 1
**Status:** COMPLETE
**Date:** 2025

---

## Overview

This repository implements the canonical DKB execution pipeline for knowledge-driven architectural design specification generation.

The system enforces:
- Versioned knowledge governance via Rudra's DKB policy
- Typed body validation before any entry enters the registry
- Design Specification compilation from typed knowledge only
- Architectural rule validation before TTG receives any specification
- Full trace propagation from Prompt Runner output through to bucket

No direct TTG execution is permitted from a raw prompt. Every generation request must pass through the full DKB pipeline.

---

## Supported Knowledge Domains

| Domain | Entries |
|---|---|
| `residential` | studio, 1rk, 1bhk, 2bhk, 3bhk, 4bhk, villa, duplex, penthouse |
| `commercial` | *(Phase 2)* |
| `infrastructure` | *(Phase 3)* |
| `style` | *(Phase 3)* |
| `engineering` | *(Phase 4)* |

---

## Canonical Pipeline

```
Prompt Runner output
    │  {module, intent, topic, tasks, output_format, product_context}
    ▼
PromptInstruction.from_prompt_runner(raw)
    │  app/design_knowledge/runtime/request.py
    │  validates: module, intent, topic required
    ▼
DKBExecutionPipeline.run(instruction, trace_id)
    │  app/design_knowledge/runtime/pipeline.py
    │
    ├─ DKBRuntime.execute(instruction)
    │      app/design_knowledge/runtime/runtime.py
    │      │
    │      ├─ KnowledgeSearchEngine.resolve(topic)
    │      │      app/design_knowledge/knowledge/search.py
    │      │      TFIDFSearchProvider — cosine similarity
    │      │      returns: KnowledgeEntry  (or raises DKBRuntimeNoMatchError)
    │      │
    │      ├─ DesignSpecCompiler.compile(entry)
    │      │      app/design_knowledge/design_spec/compiler.py
    │      │      returns: DesignSpecification
    │      │
    │      └─ ValidationEngine.validate(spec)
    │             app/design_knowledge/validation/engine.py
    │             ResidentialValidator → SpaceValidator
    │                                  → RelationshipValidator
    │                                  → EngineeringValidator
    │                                  → RuleValidator
    │             returns: ValidationReport
    │
    ├─ _build_semantic(spec)
    │      residential → architecture / layout / apartment_layout
    │
    ├─ _build_spec_json(spec, dkb_result)
    │      DesignSpecification → TTG spec_json dict
    │
    └─ TTGGenerationPipeline (Sprint 1 — unchanged)
           _step_payload()   → TTGExecutePayload
           _step_execute()   → POST /core/execute
           _step_poll()      → GET /core/execution/{id}
           _step_record()    → BucketAssetRecord
    │
    ▼
DKBExecutionResult
    ├── dkb_result.knowledge_entry
    ├── dkb_result.design_specification
    ├── dkb_result.validation_report
    ├── execution_id
    ├── bucket_url
    ├── execution_status
    └── to_dict()
```

---

## Knowledge Authority

**Primary Authority: KnowledgeLoader + KnowledgeRegistry**

| File | Role |
|---|---|
| `app/design_knowledge/knowledge/loader.py` | Reads JSON, validates, caches by mtime, registers |
| `app/design_knowledge/knowledge/registry.py` | In-memory store — no file I/O ever |
| `app/design_knowledge/knowledge/models.py` | KnowledgeVersion, KnowledgeMetadata, KnowledgeEntry |
| `app/design_knowledge/knowledge/body_models.py` | BaseKnowledgeBody, ResidentialKnowledgeBody |

**Enforcement Rules:**
- Version format `vMAJOR.MINOR.PATCH` — enforced by regex in KnowledgeVersion.parse()
- Filename format `<id>.v<major>.json` — enforced by loader filename regex
- Filename major must match metadata major — enforced in loader._parse()
- Filename id must match metadata id — enforced in loader._parse()
- body is always a typed BaseKnowledgeBody subclass — never a raw dict
- Registry never does file I/O — boundary contract enforced by docstring + no I/O imports
- Approved entries are immutable — new version = new file; old file stays frozen

---

## Search Authority

**Primary Authority: TFIDFSearchProvider (default)**

| File | Role |
|---|---|
| `app/design_knowledge/knowledge/search.py` | SearchProvider ABC, both providers, KnowledgeSearchEngine |

**Resolution pipeline (KnowledgeSearchEngine.resolve):**
1. Tokenise query (lowercase, strip punctuation)
2. Build TF-IDF vectors from title (×3) + tags (×2) + description + type
3. Compute cosine similarity between query TF vector and each document TF-IDF vector
4. Normalise scores to [0.0, 1.0] relative to top result
5. Return single best-matching KnowledgeEntry, or None if no match

**Provider contract:**
- `SearchProvider` is the only extension point
- `KnowledgeSearchEngine` never instantiates a provider — it receives one
- Swapping TF-IDF for embeddings requires only a new `SearchProvider` subclass

---

## Compiler Authority

**Primary Authority: DesignSpecCompiler**

| File | Role |
|---|---|
| `app/design_knowledge/design_spec/compiler.py` | KnowledgeEntry → DesignSpecification |
| `app/design_knowledge/design_spec/models.py` | DesignSpecification + all sub-models |

**Domain dispatch table:**

| Body Type | Compiler Method |
|---|---|
| `ResidentialKnowledgeBody` | `_compile_residential()` |
| *(future)* `CommercialKnowledgeBody` | `_compile_commercial()` |

**Enforcement Rules:**
- Compiler is stateless — every compile() call is independent
- Never reads files, never touches the registry, never calls external services
- Unknown body type raises `DesignSpecCompilerError` immediately

---

## Validation Authority

**Primary Authority: ValidationEngine**

| File | Role |
|---|---|
| `app/design_knowledge/validation/engine.py` | Orchestrates domain validators |
| `app/design_knowledge/validation/models.py` | ValidationReport, ValidationFinding |
| `app/design_knowledge/validation/validators/spaces.py` | Required spaces + area constraints |
| `app/design_knowledge/validation/validators/relationships.py` | Adjacency graph integrity |
| `app/design_knowledge/validation/validators/engineering.py` | Mandatory engineering categories |
| `app/design_knowledge/validation/validators/rules.py` | Machine-checkable validation_rules |
| `app/design_knowledge/validation/validators/residential.py` | Orchestrates all 4 for residential |

**Validator registry:**

| project_type | Validator |
|---|---|
| `residential` | `ResidentialValidator` |
| *(future)* `commercial` | `CommercialValidator` |

**Enforcement Rules:**
- Validation failure is a data outcome — it returns `ValidationReport(valid=False)`, never raises
- Unknown project_type raises `ValidationEngineError` immediately
- Validator is stateless — every validate() call is independent

---

## TTG Integration Authority

**Sprint 1 files — unchanged**

| File | Role |
|---|---|
| `app/services/ttg_generation_pipeline.py` | Steps 2–6 called directly by DKBExecutionPipeline |
| `app/adapters/ttg_payload_builder.py` | Assembles TTGExecutePayload from semantic + spec_json |
| `app/services/ttg_client.py` | POST /core/execute + polling |
| `app/contracts/bucket_asset_record.py` | Asset record with trace_id + execution_id + bucket_url |

**Integration approach:**
- `DKBExecutionPipeline` bypasses `_step_gateway()` (CoreGateway) because DKBRuntime already resolved semantic context
- Steps 2–6 of `TTGGenerationPipeline` are called directly
- No Sprint 1 file was modified

**Semantic mapping (DKB → TTG):**

| DKB project_type | TTG domain | generation_mode | geometry_family |
|---|---|---|---|
| `residential` | `architecture` | `layout` | `apartment_layout` |
| `commercial` | `architecture` | `layout` | `apartment_layout` |

---

## Allowed Routes

```
Prompt Runner output → DKBRuntime → DesignSpecification → TTG
Prompt Runner output → DKBRuntime → ValidationReport (valid=False) → TTG (with warning)
```

---

## Blocked Routes

```
Raw prompt → TTG                          (no DKB resolution)
Raw prompt → DesignSpecCompiler           (no knowledge lookup)
Raw dict → KnowledgeRegistry             (no file I/O in registry)
Unvalidated JSON → KnowledgeEntry.body   (body must be typed BaseKnowledgeBody)
Unknown type → Compiler                  (DesignSpecCompilerError raised)
Unknown type → ValidationEngine          (ValidationEngineError raised)
```

---

## Testing Evidence

| Metric | Value |
|---|---|
| Total DKB tests | 289 |
| Passing | 289 |
| Failing | 0 |
| Pass rate | 100% |
| Execution time | 1.69s |
| Network calls | 0 (all mocked) |

**Test files:**

| File | Tests | Coverage |
|---|---|---|
| `test_knowledge_models.py` | 11 | Version, metadata, entry, source_path |
| `test_body_models.py` | 24 | All sub-models, ResidentialKnowledgeBody |
| `test_registry.py` | 14 | CRUD, duplicate detection, boundary |
| `test_loader.py` | 25 | File load, directory, cache, validation, errors |
| `test_search.py` | 31 | Both providers, engine, resolve() |
| `test_compiler.py` | 28 | compile(), all fields, all 9 entries |
| `test_validation_engine.py` | 49 | All 4 validators, report, all 9 entries |
| `test_runtime.py` | 41 | PromptInstruction, DKBRuntimeResult, DKBRuntime |
| `test_pipeline.py` | 36 | Semantic mapping, spec_json, run(), all 9 entries |
| `test_e2e.py` | 30 | Full pipeline, error paths, trace, bucket, serialisation |

---

## Sprint Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Foundation — models, registry | ✅ Complete |
| Phase 2 | Loader — file I/O, caching, validation | ✅ Complete |
| Phase 3 | Search — TF-IDF + keyword providers | ✅ Complete |
| Phase 4 | Body Schema — typed ResidentialKnowledgeBody | ✅ Complete |
| Phase 5 | Residential Knowledge Library — 9 entries | ✅ Complete |
| Phase 6 | Design Specification Compiler | ✅ Complete |
| Phase 7 | Validation Engine — 4 validators | ✅ Complete |
| Phase 8 | DKB Runtime orchestrator | ✅ Complete |
| Phase 9 | DKB → TTG integration pipeline | ✅ Complete |
| Phase 10 | End-to-end integration tests | ✅ Complete |

---

*Generated from live codebase — DKB Sprint Phase 1*
*289 / 289 passing as of sprint completion*
