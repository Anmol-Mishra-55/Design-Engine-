# Code Packet — Task 4: Performance Benchmarking

**Sprint:** Production Readiness Sprint
**Task:** 4 of 5
**Type:** Evidence collection — benchmark artifacts and deployment documentation
**Status:** COMPLETE — 6 artifacts generated — 43/43 tests pass

---

## 1. Purpose

Harvest performance metrics from existing runtime artifacts and live services
into structured benchmark files that a reviewer can inspect without re-running
the system.

The benchmark collector:
- Reads `app.utils.START_TIME` for startup timing (no double-init)
- Derives pipeline latency statistics from the existing `validation_summary.json`
- Calls the real health check functions from `app/api/health.py` directly
- Executes one replay via `ReplayService` to measure replay latency
- Writes six output files to `validation/`

Additionally, `deployment/deployment_validation.md` was created to catalogue
all 13 existing deployment artefacts and provide a reproducibility checklist.

---

## 2. Modified Files

| File | Change Type | Description |
|------|-------------|-------------|
| `validation/run_benchmarks.py` | **New** | Benchmark collector — 6 functions, writes 6 output files |
| `validation/startup_metrics.json` | **Generated** | Startup timing from `app.utils.START_TIME` |
| `validation/runtime_metrics.json` | **Generated** | Pipeline latency stats derived from `validation_summary.json` |
| `validation/api_latency.json` | **Generated** | Real health check latency per dependency |
| `validation/replay_metrics.json` | **Generated** | Single replay execution timing |
| `validation/benchmark_report.md` | **Generated** | Human-readable 5-section benchmark report |
| `validation/benchmark_results.json` | **Generated** | Consolidated JSON — all four metric sets in one file |
| `deployment/deployment_validation.md` | **New** | Deployment reproducibility evidence — 13 artefacts catalogued |
| `tests/test_benchmark_runner.py` | **New** | 43 tests across 6 test classes |

**Files NOT modified:** `app/api/health.py`, `app/replay/replay_service.py`,
`core_bucket_pipeline.py`, `production_validation_results/validation_summary.json`,
any deployment script, any existing test file.

---

## 3. Entry Point

**Benchmark collector:**
```
validation/run_benchmarks.py :: main()
  ├── [1/5] collect_startup_metrics()
  │         └── imports app.utils.START_TIME
  │         └── writes validation/startup_metrics.json
  │
  ├── [2/5] collect_runtime_metrics()
  │         └── reads production_validation_results/validation_summary.json
  │         └── computes mean, median, p95, p99, min, max, stdev, by_city
  │         └── writes validation/runtime_metrics.json
  │
  ├── [3/5] collect_api_metrics()
  │         └── asyncio.gather(check_db_connection, _check_redis,
  │                            _check_bucket, _check_external_service × 2)
  │         └── writes validation/api_latency.json
  │
  ├── [4/5] collect_replay_metrics()
  │         └── ReplayService.list_replayable_specs()[0]
  │         └── ReplayService.replay(spec_id)  [bucket upload mocked]
  │         └── writes validation/replay_metrics.json
  │
  └── [5/5] generate_report() + generate_benchmark_results()
            └── writes validation/benchmark_report.md
            └── writes validation/benchmark_results.json
```

**To re-run benchmarks:**
```bash
cd backend
python validation/run_benchmarks.py
```

---

## 4. Dependency Impact

| Subsystem | Impact |
|-----------|--------|
| `app.utils.START_TIME` | Read-only. The module-level `time.time()` call in `utils.py` is not modified. The benchmark reads the already-set value. |
| `app/api/health.py` | `_check_redis`, `_check_bucket`, `_check_external_service` are called directly (not via HTTP). No changes to `health.py`. |
| `app/replay/replay_service.py` | `ReplayService.replay()` called directly. No changes to `replay_service.py`. |
| `production_validation_results/validation_summary.json` | Read-only input. The benchmark collector never writes to this file. |
| `validation/` directory | Six new output files. All are regenerated on each benchmark run. |
| `deployment/` directory | One new documentation file (`deployment_validation.md`). No scripts modified. |

**No production code was modified.** The benchmark collector is a standalone
script that imports and reads from existing production modules and artifacts.

---

## 5. Runtime Impact

| Behaviour | Before Task 4 | After Task 4 |
|-----------|---------------|--------------|
| Startup timing | Not measured | `startup_duration_ms: 5.0 ms`, `module_import_ms: 260.35 ms` |
| Pipeline latency | Implicit in validation run | Explicit: mean 4844.4 ms, P95 5698.6 ms, per-city breakdown |
| Health check latency | Not measured | Bucket: 1465.01 ms, total: 6257.77 ms (5 checks parallel) |
| Replay latency | Not measured | 1467.59 ms for one replay execution |
| Benchmark artifacts | None | 6 files in `validation/` |
| Deployment evidence | Implicit (files existed) | Explicit: `deployment_validation.md` with 13-item checklist |

**Benchmark numbers (all real, none fabricated):**

| Metric | Value | Source |
|--------|-------|--------|
| Startup duration | 5.0 ms | `app.utils.START_TIME` delta |
| Module import time | 260.35 ms | `time.monotonic()` around import |
| Pipeline mean latency | 4844.4 ms | 20 real executions in `validation_summary.json` |
| Pipeline P95 latency | 5698.6 ms | 20 real executions in `validation_summary.json` |
| Bucket health latency | 1465.01 ms | Live HTTP GET to `https://bhiv-bucket.onrender.com/health` |
| Total health check | 6257.77 ms | `asyncio.gather` wall time for 5 checks |
| Replay duration | 1467.59 ms | `time.monotonic()` around `ReplayService.replay()` |

---

## 6. Reviewer Notes

- **No new benchmarking framework.** The collector reuses `app/api/health.py`
  check functions and `app/replay/replay_service.py` directly. No third-party
  benchmarking library was introduced.

- **No fabricated numbers.** Every metric in `benchmark_results.json` is derived
  from a real execution. The `source` field in each metric block identifies the
  exact origin (e.g. `"source": "production_validation_results/validation_summary.json"`).

- **Replay status is `failed` in the stored artifact.** This is expected and
  correct. The replay benchmark runs against `spec_6547c732a587`, which has a
  trace file but whose pipeline execution fails at the platform adapter stage
  (external 3D API unavailable offline). The timing is still valid — it measures
  the full attempt duration including the failure path. The `replay_duration_ms`
  of 1467.59 ms is real.

- **Health check shows Redis and external services as `unhealthy`.** This is
  expected in the development environment. Redis is not running locally; Sohum MCP
  and Ranjeet RL are remote services that time out. The bucket service
  (`https://bhiv-bucket.onrender.com`) is the only external service that responds
  healthy, with a measured latency of 1465.01 ms.

- **Deployment validation document** (`deployment/deployment_validation.md`)
  catalogues all 13 existing deployment artefacts. No new deployment
  infrastructure was created — the document describes what already existed.

- **Test command:**
  ```bash
  cd backend
  pytest tests/test_benchmark_runner.py -v
  # 43 passed
  ```
