# Design Knowledge Base — Architecture

**Sprint:** DKB Phase 1
**Version:** 1.0
**Tests:** 289 / 289 passing

---

## Folder Structure

```
app/design_knowledge/
├── knowledge/
│   ├── models.py          KnowledgeVersion, KnowledgeMetadata, KnowledgeEntry
│   ├── body_models.py     BaseKnowledgeBody, ResidentialKnowledgeBody + sub-models
│   ├── registry.py        KnowledgeRegistry  — in-memory store, no file I/O
│   ├── loader.py          KnowledgeLoader    — file I/O, caching, validation
│   └── search.py          SearchProvider ABC, KeywordSearchProvider,
│                          TFIDFSearchProvider, KnowledgeSearchEngine
│
├── design_spec/
│   ├── models.py          DesignSpecification + sub-models
│   └── compiler.py        DesignSpecCompiler — KnowledgeEntry → DesignSpecification
│
├── validation/
│   ├── models.py          ValidationReport, ValidationFinding
│   ├── engine.py          ValidationEngine — orchestrates domain validators
│   └── validators/
│       ├── base.py        BaseValidator ABC
│       ├── spaces.py      SpaceValidator
│       ├── relationships.py  RelationshipValidator
│       ├── engineering.py EngineeringValidator
│       ├── rules.py       RuleValidator — executes machine-checkable DKB rules
│       └── residential.py ResidentialValidator — orchestrates all four
│
├── runtime/
│   ├── request.py         PromptInstruction — wraps Prompt Runner output
│   ├── response.py        DKBRuntimeResult
│   ├── exceptions.py      DKBRuntimeError hierarchy
│   ├── runtime.py         DKBRuntime — search → compile → validate
│   └── pipeline.py        DKBExecutionPipeline — DKBRuntime → TTGGenerationPipeline
│
├── data/
│   └── residential/
│       ├── studio.v1.json
│       ├── 1rk.v1.json
│       ├── 1bhk.v1.json
│       ├── 2bhk.v1.json
│       ├── 3bhk.v1.json
│       ├── 4bhk.v1.json
│       ├── villa.v1.json
│       ├── duplex.v1.json
│       └── penthouse.v1.json
│
└── tests/
    ├── test_knowledge_models.py   11 tests
    ├── test_body_models.py        24 tests
    ├── test_registry.py           14 tests
    ├── test_loader.py             25 tests
    ├── test_search.py             31 tests
    ├── test_compiler.py           28 tests
    ├── test_validation_engine.py  49 tests
    ├── test_runtime.py            41 tests
    ├── test_pipeline.py           36 tests
    └── test_e2e.py                30 tests
```

---

## Full Pipeline

```
User Prompt
    │
    ▼
Prompt Runner  (Siddhesh — unchanged)
    │  returns: {module, intent, topic, tasks, output_format, product_context}
    │
    ▼
PromptInstruction.from_prompt_runner(raw)
    │  validates: module, intent, topic required
    │
    ▼
DKBExecutionPipeline.run(instruction, trace_id?)
    │
    ├─── DKBRuntime.execute(instruction)
    │         │
    │         ├─ KnowledgeSearchEngine.resolve(topic)
    │         │       TFIDFSearchProvider scores all loaded entries
    │         │       Returns: best-matching KnowledgeEntry
    │         │       Raises:  DKBRuntimeNoMatchError if no match
    │         │
    │         ├─ DesignSpecCompiler.compile(entry)
    │         │       Dispatches by body type via _COMPILER_REGISTRY
    │         │       Returns: DesignSpecification
    │         │       Raises:  DKBRuntimeCompilerError on failure
    │         │
    │         └─ ValidationEngine.validate(spec)
    │                 Dispatches by project_type via VALIDATOR_REGISTRY
    │                 Runs: Space + Relationship + Engineering + Rule validators
    │                 Returns: ValidationReport (valid, score, findings)
    │                 Raises:  DKBRuntimeValidationError on engine failure
    │
    ├─── _build_semantic(spec)
    │         DesignSpecification → {domain, entity, generation_mode, geometry_family}
    │
    ├─── _build_spec_json(spec, dkb_result)
    │         DesignSpecification → TTG spec_json dict
    │
    └─── TTGGenerationPipeline  (Sprint 1 — unchanged)
              _step_payload()   assemble TTGExecutePayload
              _step_execute()   POST /core/execute
              _step_poll()      GET /core/execution/{id}
              _step_record()    BucketAssetRecord
    │
    ▼
DKBExecutionResult
    ├── dkb_result         (KnowledgeEntry + DesignSpecification + ValidationReport)
    ├── execution_id
    ├── domain / entity
    ├── bucket_url
    ├── execution_status
    └── to_dict()          JSON-serialisable
```

---

## Component Responsibilities

| Component | File | Responsibility |
|---|---|---|
| KnowledgeVersion | models.py | Parse, compare, and serialise vMAJOR.MINOR.PATCH versions |
| KnowledgeMetadata | models.py | 11-field governance metadata for every DKB entry |
| KnowledgeEntry | models.py | Container: metadata + typed body + source_path |
| BaseKnowledgeBody | body_models.py | Abstract base for all domain knowledge bodies |
| ResidentialKnowledgeBody | body_models.py | Typed residential engineering knowledge schema |
| KnowledgeRegistry | registry.py | In-memory store keyed by id — no file I/O ever |
| KnowledgeLoader | loader.py | Load, validate, cache, and register DKB JSON files |
| SearchProvider | search.py | Abstract interface: index() + search() |
| KeywordSearchProvider | search.py | Exact token matching — deterministic, for tests |
| TFIDFSearchProvider | search.py | Cosine similarity — default production provider |
| KnowledgeSearchEngine | search.py | Provider-agnostic engine with resolve() |
| DesignSpecification | design_spec/models.py | Typed output of the compiler — input to TTG |
| DesignSpecCompiler | design_spec/compiler.py | Stateless KnowledgeEntry → DesignSpecification |
| ValidationFinding | validation/models.py | Single validator result: rule_id, passed, severity |
| ValidationReport | validation/models.py | Aggregated findings with valid, score, errors, warnings |
| SpaceValidator | validators/spaces.py | Check required spaces present and area ranges valid |
| RelationshipValidator | validators/relationships.py | Check adjacency edges reference real spaces |
| EngineeringValidator | validators/engineering.py | Check structural + fire categories present |
| RuleValidator | validators/rules.py | Execute machine-checkable DKB validation_rules |
| ResidentialValidator | validators/residential.py | Orchestrate all four validators for residential specs |
| ValidationEngine | validation/engine.py | Dispatch to domain validator, return ValidationReport |
| PromptInstruction | runtime/request.py | Typed wrapper for Prompt Runner output |
| DKBRuntimeResult | runtime/response.py | Search score + entry + spec + report in one object |
| DKBRuntime | runtime/runtime.py | Orchestrate search → compile → validate |
| DKBExecutionPipeline | runtime/pipeline.py | Bridge DKBRuntime to TTGGenerationPipeline |

---

## Sequence Diagram — Residential Query

```
User          PromptRunner    DKBRuntime      SearchEngine    Compiler    Validator    TTG
 │                │               │               │              │            │         │
 │──"3bhk flat"──▶│               │               │              │            │         │
 │                │──instruction──▶│               │              │            │         │
 │                │               │──resolve()────▶│              │            │         │
 │                │               │◀──KnowledgeEntry──────────────│            │         │
 │                │               │──compile()────────────────────▶│            │         │
 │                │               │◀──DesignSpecification──────────│            │         │
 │                │               │──validate()───────────────────────────────▶│         │
 │                │               │◀──ValidationReport────────────────────────│         │
 │                │◀──DKBRuntimeResult────────────│               │            │         │
 │                │──run()────────────────────────────────────────────────────────────▶│
 │                │◀──DKBExecutionResult──────────────────────────────────────────────│
 │◀───result──────│               │               │              │            │         │
```

---

## Registry Pattern

All three dispatch registries follow the same pattern — a dict maps a key to a handler. Adding a new domain requires one line in each dict:

```python
# loader.py
BODY_MODEL_REGISTRY = {
    "residential": ResidentialKnowledgeBody,
    "commercial":  CommercialKnowledgeBody,   # ← add this for Task 6
}

# compiler.py
_COMPILER_REGISTRY = {
    ResidentialKnowledgeBody: "_compile_residential",
    CommercialKnowledgeBody:  "_compile_commercial",  # ← add this
}

# engine.py
VALIDATOR_REGISTRY = {
    "residential": ResidentialValidator,
    "commercial":  CommercialValidator,   # ← add this
}
```

---

## Governance Rules (Rudra)

| Rule | Enforcement |
|---|---|
| Version format `vMAJOR.MINOR.PATCH` | Regex in `KnowledgeVersion.parse()` |
| Filename `<id>.v<major>.json` | Regex in `KnowledgeLoader._validate_filename()` |
| Filename major matches metadata major | Check in `KnowledgeLoader._parse()` |
| Filename id matches metadata id | Check in `KnowledgeLoader._parse()` |
| body is always typed | `BODY_MODEL_REGISTRY` dispatch in loader |
| Registry never does file I/O | Boundary contract docstring; no pathlib/json/os imports |
| All 11 metadata fields required | Pydantic `KnowledgeMetadata` model |
| Approved entries are immutable | All 9 DKB files carry `"status": "approved"` |

---

## Public APIs

### KnowledgeLoader
```python
KnowledgeLoader(root_directory: Path, registry: KnowledgeRegistry)
.load_file(path: Path) -> KnowledgeEntry
.load_directory(path: Path) -> int          # returns count loaded
.reload() -> int
.find(id: str) -> KnowledgeEntry | None
.list_versions(id: str) -> list[str]
.latest(id: str) -> KnowledgeEntry | None
```

### KnowledgeSearchEngine
```python
KnowledgeSearchEngine(provider: SearchProvider)
.index(entries: list[KnowledgeEntry]) -> None
.reindex(entries: list[KnowledgeEntry]) -> None
.search(query: str, top_k: int = 5) -> list[SearchResult]
.resolve(query: str) -> KnowledgeEntry | None
```

### DesignSpecCompiler
```python
DesignSpecCompiler()
.compile(entry: KnowledgeEntry) -> DesignSpecification
```

### ValidationEngine
```python
ValidationEngine()
.validate(spec: DesignSpecification) -> ValidationReport
```

### DKBRuntime
```python
DKBRuntime(search_engine, compiler, validator)
DKBRuntime.from_directory(path: Path) -> DKBRuntime
.index(entries: list[KnowledgeEntry]) -> None
.execute(instruction: PromptInstruction) -> DKBRuntimeResult
```

### DKBExecutionPipeline
```python
DKBExecutionPipeline(dkb_runtime, bucket_urls, ttg_pipeline)
DKBExecutionPipeline.from_directory(path, bucket_urls, ttg_pipeline) -> DKBExecutionPipeline
.run(instruction: PromptInstruction, trace_id: str | None = None) -> DKBExecutionResult
```

---

## Layer Boundaries

Each layer has an explicit contract — no layer reaches into another layer's internals:

```
JSON Files
    │  (only KnowledgeLoader reads files)
    ▼
KnowledgeLoader
    │  (only calls registry.register())
    ▼
KnowledgeRegistry
    │  (only stores KnowledgeEntry objects)
    ▼
KnowledgeSearchEngine
    │  (only calls provider.search())
    ▼
DesignSpecCompiler
    │  (only reads entry.body fields)
    ▼
ValidationEngine
    │  (only reads DesignSpecification fields)
    ▼
DKBRuntime
    │  (only calls search, compile, validate)
    ▼
DKBExecutionPipeline
    │  (only calls runtime.execute() + TTG steps)
    ▼
TTGGenerationPipeline  (Sprint 1 — unchanged)
```

---

*DKB Sprint Phase 1 — 289 / 289 tests passing*
