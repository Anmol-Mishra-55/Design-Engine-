# Roadmap

**Design Engine API — Known Gaps and Future Work**
**Last updated:** 2026-07-22

---

## Near-term — Test Infrastructure

These are test-only issues. None affect production runtime.

| Item | File | Action |
|------|------|--------|
| 35 test errors cascade from missing `demo/demo123` user | `tests/conftest.py` | Seed user in conftest fixture or mock auth |
| `test_complete_system.py` is a dead SQLAlchemy-era file | `tests/test_complete_system.py` | Delete |
| `test_simple.py` — 2 tests use undefined `User`/`Spec` models | `tests/test_simple.py` | Delete or rewrite for MongoDB |
| `test_auth.py` — hardcoded credentials not in test DB | `tests/test_auth.py` | Add test fixtures |
| `test_endpoints.py::TestHealth::test_health_detailed` — expects `"healthy"` from real DB | `tests/test_endpoints.py` | Mock DB check in this test |
| `test_switch.py::test_switch_without_auth` — expects 401/403 but gets 422 | `tests/test_switch.py` | Fix test expectation |

Fixing the `demo/demo123` fixture alone resolves all 35 errors automatically.

---

## Near-term — City Data

| Item | Detail |
|------|--------|
| Bangalore city data missing | Listed in `SUPPORTED_CITIES` but rules/context not loaded — returns 404 on city endpoints |
| Add Bangalore DCR rules | `app/multi_city/city_data_loader.py` + data files |

---

## Medium-term — Features

| Item | Detail | Owner |
|------|--------|-------|
| Commercial domain in DKB | DKB currently supports residential only (studio, 1RK, 1BHK–5BHK, villa, duplex, penthouse). Add commercial knowledge entries | Anmol |
| Redis caching activation | `REDIS_URL` is configured but caching is not actively used for spec lookups | Anmol |
| Meshy large-GLB bucket support | Meshy generates 20–50 MB GLBs exceeding the 16 MB bucket limit. Options: chunked upload, or increase bucket payload limit | Siddhesh |
| `large_artifact_url` field in Bucket schema | Allow storing external CDN references alongside bucket-stored artifacts | Siddhesh |
| Webhook notifications | Notify caller when pipeline completes (async jobs) | Anmol |

---

## Medium-term — Deployment

| Item | Detail |
|------|--------|
| Update `docker-compose.yml` | Replace `postgres:14` service with `mongo:7` for local development parity |
| Render paid plan | Eliminate cold-start latency on bucket and backend services |
| CI/CD pipeline | Automate `pytest` + `run_production_validation.py` on every push |

---

## Long-term

| Item | Detail |
|------|--------|
| Multi-tenant authentication | Per-organisation user isolation |
| Frontend integration guide | Document how a frontend consumes artifact URLs and renders GLB |
| Additional cities | Delhi, Bangalore, Chennai, Hyderabad DCR rules |
| RLHF training pipeline | Activate `app/rlhf/` training scripts with real feedback data |
| Prefect workflow orchestration | Activate `workflows/` Prefect flows for async pipeline execution |

---

## Completed (reference)

| Item | Sprint | Status |
|------|--------|--------|
| JSON structured logging | Production Readiness Sprint Task 2 | DONE |
| Trace context middleware | Production Readiness Sprint Task 2 | DONE |
| Real health checks | Production Readiness Sprint Task 2 | DONE |
| Replay service | Production Readiness Sprint Task 2 | DONE |
| 20-case production validation | Production Readiness Sprint Task 3 | DONE |
| Benchmark artifacts | Production Readiness Sprint Task 4 | DONE |
| `SohumMCPClient.get_mock_compliance_response` fix | Task 4 Category 1 | DONE |
| `test_error_handling` assertion fix | Task 4 Category 1 | DONE |
| Full documentation suite | Task 4 Documentation Sprint | DONE |
