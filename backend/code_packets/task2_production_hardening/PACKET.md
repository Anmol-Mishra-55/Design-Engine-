# Code Packet — Task 2: Production Hardening

**Sprint:** Production Readiness Sprint
**Task:** 2 of 5
**Type:** Engineering — new production-grade subsystems
**Status:** COMPLETE — 42/42 tests pass

---

## 1. Purpose

Close the four production readiness gaps identified in the Task 1 audit:

1. Logging was plain-text `basicConfig` — not parseable by log aggregators.
2. No trace_id was propagated through the request lifecycle.
3. The `/api/v1/health/detailed` endpoint returned hardcoded mock values.
4. No mechanism existed to replay a previously executed pipeline run.

All four gaps were closed without modifying the core pipeline
(`core_bucket_pipeline.py`) or any existing API contract.

---

## 2. Modified Files

| File | Change Type | Description |
|------|-------------|-------------|
| `app/logging_config.py` | **New** | `JsonFormatter` + `RotatingFileHandler` + thread-local trace context |
| `app/middleware/trace_context.py` | **New** | `TraceContextMiddleware` — injects trace_id per HTTP request |
| `app/middleware/__init__.py` | **New** | Package init for middleware module |
| `app/api/health.py` | **Modified** | Replaced mocked values with 5 real async dependency checks |
| `app/replay/replay_service.py` | **New** | `ReplayService` — reads stored trace + spec, re-executes pipeline |
| `app/replay/__init__.py` | **New** | Package init for replay module |
| `app/api/replay.py` | **New** | 3 REST endpoints for replay (list / trace summary / execute) |
| `app/main.py` | **Modified** | Registered `TraceContextMiddleware` and `replay.router` |
| `tests/test_production_hardening.py` | **New** | 42 tests across 11 test classes |

**Files NOT modified:** `core_bucket_pipeline.py`, `storage.py`, `database_mongodb.py`,
all existing API routers, all existing schemas, all DKB modules.

---

## 3. Entry Point

**Application startup:**
```
app/main.py
  └── setup_logging()                    ← replaces basicConfig
  └── app.add_middleware(TraceContextMiddleware)
  └── app.include_router(replay.router, prefix="/api/v1")
```

**Logging subsystem:**
```
app/logging_config.py :: setup_logging()
  └── JsonFormatter → StreamHandler (stdout)
  └── JsonFormatter → RotatingFileHandler (logs/bhiv.log, 10 MB × 5)
```

**Per-request trace flow:**
```
HTTP request
  └── TraceContextMiddleware.dispatch()
        └── set_trace_context(trace_id, execution_id, pipeline_stage)
        └── call_next(request)
        └── response.headers["X-Trace-ID"] = trace_id
        └── finally: clear_trace_context()
```

**Health check entry:**
```
GET /api/v1/health/detailed
  └── app/api/health.py :: detailed_health()
        └── asyncio.gather(check_db_connection, _check_redis,
                           _check_bucket, _check_external_service × 2)
```

**Replay entry:**
```
POST /api/v1/replay/{spec_id}
  └── app/api/replay.py :: replay_spec()
        └── ReplayService.replay(spec_id)
              └── _load_trace(spec_id)       ← data/bucket_traces/
              └── _load_spec_payload(spec_id) ← data/specs/
              └── CoreBucketCanonicalOrchestrator.execute(replay_spec_id, payload)
```

---

## 4. Dependency Impact

| Subsystem | Impact |
|-----------|--------|
| Logging | Root logger reconfigured at startup. All existing `logging.getLogger(__name__)` calls throughout the codebase automatically emit JSON without any changes to call sites. |
| Middleware stack | `TraceContextMiddleware` added after `CORSMiddleware`. Adds one thread-local write per request. No impact on existing middleware. |
| Health API | `_check_redis`, `_check_bucket`, `_check_external_service` are new private functions inside `health.py`. The existing `/health` and `/api/v1/health` routes are unchanged. Only `/api/v1/health/detailed` was modified. |
| Replay | New module `app/replay/`. No existing module imports it except `app/api/replay.py` and `app/main.py`. Zero circular dependency risk. |
| `app/main.py` | Two additions only: `add_middleware(TraceContextMiddleware)` and `include_router(replay.router)`. All existing routers and middleware unchanged. |

**New runtime dependencies introduced:** none. All imports (`redis.asyncio`, `httpx`,
`starlette.middleware.base`) were already present in `requirements.txt`.

---

## 5. Runtime Impact

| Behaviour | Before Task 2 | After Task 2 |
|-----------|---------------|--------------|
| Log format | Plain text via `basicConfig` | JSON — one object per line, 12 fields |
| Log destination | stdout only | stdout + `logs/bhiv.log` (rotating) |
| trace_id in logs | Not present | Present in every log line |
| X-Trace-ID header | Not returned | Returned on every response |
| `/api/v1/health/detailed` | Hardcoded mock `{"status": "healthy"}` | Real latency_ms per dependency |
| Replay capability | Not available | `GET/POST /api/v1/replay/*` — JWT required |
| Per-request overhead | Baseline | +1 thread-local write + +1 header write (< 0.1 ms) |

---

## 6. Reviewer Notes

- **No architectural changes.** The core pipeline (`CoreBucketCanonicalOrchestrator`),
  all existing API routes, all schemas, and all database models are untouched.

- **Backward compatible.** Existing clients see no breaking changes. The only
  visible addition is the `X-Trace-ID` response header and the new `/api/v1/replay/*`
  endpoints.

- **Health check degradation is intentional.** Redis and external services
  (Sohum MCP, Ranjeet RL) are not always reachable in the development environment.
  The endpoint correctly returns `degraded` rather than `unhealthy` when only
  non-critical dependencies are down. MongoDB down → `unhealthy`.

- **Replay does not modify originals.** Every replay generates a new `spec_id`
  prefixed `replay_` and a new trace file. The original `data/bucket_traces/` and
  `data/specs/` entries are read-only during replay.

- **Test isolation.** All 42 tests use `tempfile.TemporaryDirectory` or
  `unittest.mock.patch` for file I/O. No test touches the live database,
  live bucket, or live external services.

- **Test command:**
  ```bash
  cd backend
  pytest tests/test_production_hardening.py -v
  # 42 passed
  ```
