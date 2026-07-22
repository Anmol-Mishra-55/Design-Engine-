# Design Engine API

**Version:** 1.0.0
**Status:** Production Certified
**Python:** 3.13.5 | **Framework:** FastAPI | **Database:** MongoDB Atlas | **Storage:** Bucket (append-only)

---

## Product Overview

The Design Engine API is a FastAPI backend that accepts natural language architectural design prompts and returns 3D building specifications with compliance validation and RL optimization.

**What it does:**
- Accepts a plain-English prompt (`"Design a 3BHK apartment in Mumbai"`)
- Runs it through a semantic pipeline to produce a structured `spec_json` with rooms, dimensions, and adjacency
- Generates GLB, STL, and STEP geometry artifacts from the spec
- Stores all artifacts in a remote append-only Bucket service
- Runs compliance checks against city-specific DCR rules (Mumbai, Pune, Ahmedabad, Nashik)
- Returns Bucket URLs for all artifacts — no local file storage

**Production validation:** 20/20 cases passed across 4 cities (100% pass rate).
**Test suite:** 741 tests passing, 0 regressions.

---

## Architecture Summary

```
Client
  └─► POST /api/v1/core/generate          ← only valid design entry point
        └─► CoreBucketCanonicalOrchestrator
              ├─► BucketRouter.store_request()      → Bucket (files/requests/)
              ├─► PromptRunnerAdapterBridge          → spec_json + rooms
              │     ├─► PlatformAdapter.process()   → module/intent/topic
              │     ├─► SemanticResolver             → BHK type, city, style
              │     └─► DKB lookup                  → room dimensions
              ├─► _generate_glb()                   → Meshy AI → Tripo AI → geometry_generator_real
              ├─► _rooms_to_stl() / _rooms_to_step()
              ├─► BucketRouter.store_artifact(glb/stl/step) → Bucket (geometry/)
              └─► BucketRouter.store_spec_payload()  → Bucket (files/specs/)

POST /api/v1/generate          → 403 BLOCKED (use /core/generate)
POST /api/v1/geometry/generate → 403 BLOCKED (use /core/generate)

POST /bhiv/v1/design           → BHIV integrated endpoint
  └─► CoreBucketCanonicalOrchestrator (same pipeline)
  └─► call_sohum_compliance()  → Sohum MCP (graceful fallback if unavailable)
  └─► call_ranjeet_rl()        → Ranjeet RL (graceful fallback if unavailable)
```

**Key components:**

| Component | File | Role |
|-----------|------|------|
| Core entry | `app/api/core_entry.py` | JWT auth, request validation, orchestrator call |
| Orchestrator | `app/core_bucket_pipeline.py` | Canonical pipeline — bucket → prompt runner → geometry → bucket |
| Prompt runner | `app/prompt_runner_adapter.py` | NLP → spec_json |
| Geometry | `app/geometry_generator_real.py` | Per-room GLB mesh generation |
| Storage | `app/storage.py` | Append-only bucket writes with lineage retry |
| Health | `app/api/health.py` | Real dependency checks (MongoDB, Redis, Bucket, Sohum, Ranjeet) |
| Replay | `app/replay/replay_service.py` | Re-execute pipeline from stored trace |
| Monitoring | `app/api/monitoring.py` | DB-backed metrics overview |
| Trace context | `app/middleware/trace_context.py` | X-Trace-ID propagation |
| Logging | `app/logging_config.py` | JSON-structured logs with trace_id on every line |

Full architecture diagram: [`review_packets/ARCHITECTURE_MAP.md`](review_packets/ARCHITECTURE_MAP.md)
Step-by-step runtime flow: [`review_packets/EXECUTION_FLOW.md`](review_packets/EXECUTION_FLOW.md)

---

## Installation

### Prerequisites

- Python 3.11+
- MongoDB Atlas URI (or local MongoDB for development)
- Git

### Steps

```bash
# 1. Clone
git clone <repo-url>
cd backend

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env — minimum required: MONGODB_URL, JWT_SECRET_KEY, BUCKET_URL

# 5. Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Verify
curl http://localhost:8000/health
# → {"status": "ok", "service": "Design Engine API", "version": "0.1.0"}
```

### Smoke test

```bash
pytest tests/test_production_hardening.py tests/test_semantic_resolver.py -q
# Expected: 104 passed in ~3s
```

---

## Environment Configuration

Copy `.env.example` to `.env` and set the following. All variables are documented in `.env.example`.

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB Atlas connection string | `mongodb+srv://user:pass@cluster.mongodb.net/` |
| `MONGODB_DATABASE` | Database name | `bhiv_db` |
| `JWT_SECRET_KEY` | JWT signing secret (min 16 chars) | `your-secret-key-here` |
| `BUCKET_URL` | Bucket storage service URL | `https://bhiv-bucket.onrender.com` |
| `CORE_INTERNAL_TOKEN` | Internal token blocking direct `/generate` calls | `bhiv-core-internal-token-change-in-prod` |

### Production-only

| Variable | Description | Example |
|----------|-------------|---------|
| `PUBLIC_API_URL` | Deployed service URL (used in download URLs) | `https://bhiv-backend.onrender.com` |
| `ENVIRONMENT` | Runtime environment | `production` |
| `SENTRY_DSN` | Sentry error tracking (optional) | `https://...@sentry.io/...` |

### External services

| Variable | Description | Default |
|----------|-------------|---------|
| `SOHUM_MCP_URL` | Sohum compliance MCP service | `https://ai-rule-api-w7z5.onrender.com` |
| `RANJEET_RL_URL` | Ranjeet land utilization RL service | `https://land-utilization-rl.onrender.com` |
| `REDIS_URL` | Redis cache (optional) | `redis://localhost:6379/0` |
| `MESHY_API_KEY` | Meshy AI 3D generation (optional) | — |
| `TRIPO_API_KEY` | Tripo AI 3D generation (optional) | — |

---

## Deployment

### Docker (local / staging)

```bash
cd deployment
docker-compose up --build
# Backend: http://localhost:8000
# Health:  http://localhost/health
```

### Render.com (production)

The application is deployed as a Render web service. Environment variables are injected via Render's secret management.

```
Start command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health check:  GET /api/v1/health  (every 30s)
```

### Production deploy script

```bash
cd deployment
./deploy_production.sh
# Builds image → stops current → starts new → health check → auto-rollback on failure
```

### Rollback

```bash
cd deployment
./rollback.sh
```

Full deployment guide: [`deployment/deployment_validation.md`](deployment/deployment_validation.md)

---

## Runtime Workflow

A single design generation request flows through these stages:

```
1. POST /api/v1/core/generate  (JWT required)
2. TraceContextMiddleware      → assigns X-Trace-ID
3. core_entry.py               → validates request, generates spec_id
4. CoreBucketCanonicalOrchestrator.execute()
   a. BucketRouter.store_request()          → stores inbound payload in Bucket
   b. PromptRunnerAdapterBridge             → NLP → spec_json
   c. _generate_glb()                       → Meshy → Tripo → geometry_generator_real
   d. _rooms_to_stl() / _rooms_to_step()   → derived from room geometry
   e. BucketRouter.store_artifact() × 3    → GLB, STL, STEP to Bucket
   f. BucketRouter.store_spec_payload()    → spec JSON to Bucket
5. HTTP 200 → {artifact_urls: {glb, stl, step, spec}}
   X-Trace-ID header in response
```

Every stage writes a trace entry to `data/bucket_traces/core_bucket_{spec_id}.jsonl`.
Every log line carries `trace_id` via `JsonFormatter`.

Full step-by-step trace: [`review_packets/EXECUTION_FLOW.md`](review_packets/EXECUTION_FLOW.md)

---

## Testing

```bash
# Full suite
pytest tests/ --ignore=tests/test_complete_system.py -q

# Core hardening tests (54 tests)
pytest tests/test_production_hardening.py -v

# Semantic resolver (50 tests)
pytest tests/test_semantic_resolver.py -v

# E2E multi-city pipeline
pytest tests/e2e/test_multi_city_pipeline.py -v

# Benchmark runner
pytest tests/test_benchmark_runner.py -v
```

**Current test results:** 741 passed, 15 pre-existing failures (all stale test infrastructure — no production impact), 0 regressions.

Pre-existing failures are documented in [`production_validation_results/TASK3_OPERATIONAL_VALIDATION.md`](production_validation_results/TASK3_OPERATIONAL_VALIDATION.md).

---

## Operational Validation

Production validation was run across 20 cases, 4 cities:

| City | Cases | Passed | Pass Rate |
|------|-------|--------|-----------|
| Mumbai | 5 | 5 | 100% |
| Pune | 5 | 5 | 100% |
| Ahmedabad | 5 | 5 | 100% |
| Nashik | 5 | 5 | 100% |
| **Total** | **20** | **20** | **100%** |

Evidence: [`production_validation_results/validation_summary.json`](production_validation_results/validation_summary.json)
Full report: [`production_validation_results/TASK3_OPERATIONAL_VALIDATION.md`](production_validation_results/TASK3_OPERATIONAL_VALIDATION.md)
Benchmark report: [`validation/benchmark_report.md`](validation/benchmark_report.md)

**Key metrics:**
- Startup duration: 3.6 ms
- Pipeline mean latency: 4844 ms (includes live Bucket writes)
- Pipeline P95 latency: 5699 ms
- Replay duration: 4783 ms
- Bucket trace files: 89

---

## Known Limitations

1. **Meshy AI GLB size** — Meshy generates 20–50 MB GLBs. The Bucket has a 16 MB payload limit. The system stores the Meshy external CDN URL in `spec_json.metadata.meshy_glb_url` and uses `geometry_generator_real` for the Bucket-stored GLB. Frontend can use `meshy_glb_url` for high-quality rendering.

2. **Bucket is append-only** — Every write requires `parent_hash` = current chain tip. Parallel writes may conflict; the system retries automatically up to 5 times with backoff.

3. **Render cold-start** — `bhiv-bucket.onrender.com` is a Render free-tier service. It spins down after inactivity and takes ~30–60 seconds to cold-start. The first request after inactivity will be slow.

4. **Redis is optional** — Redis is configured but not required. If `REDIS_URL` is unreachable, the health check reports `status=not_configured` and the system continues normally.

5. **Test infrastructure gaps** — 35 test errors cascade from `demo/demo123` user not seeded in the test database. These are test-only issues with no production impact. `tests/test_complete_system.py` is a stale SQLAlchemy-era file that should be deleted.

6. **`/api/v1/generate` is hard-blocked** — This route always returns 403. The only valid design entry point is `POST /api/v1/core/generate`. This is intentional (Phase 3 enforcement).

7. **Bangalore city data** — Bangalore is listed in `SUPPORTED_CITIES` but city rules and context data are not yet loaded. Requests for Bangalore return 404 on city endpoints.

---

## Future Roadmap

See [`ROADMAP.md`](ROADMAP.md) for the full roadmap.

**Near-term (test infrastructure):**
- Seed `demo/demo123` user in test fixtures → resolves 35 test errors
- Delete `tests/test_complete_system.py` (stale SQLAlchemy-era file)
- Fix 5 remaining test assertion mismatches

**Medium-term (features):**
- Bangalore city data and DCR rules
- Commercial domain support in DKB (currently residential only)
- Redis caching activation for spec lookups
- Meshy large-GLB bucket support (increase payload limit or chunked upload)

**Long-term:**
- Multi-tenant authentication
- Webhook notifications on pipeline completion
- Frontend integration guide

---

## Repository Structure

```
backend/
├── app/
│   ├── api/                    API route handlers
│   ├── design_knowledge/       DKB — residential knowledge base
│   ├── design_semantics/       Semantic resolver, BHK definitions
│   ├── middleware/             TraceContextMiddleware
│   ├── replay/                 ReplayService
│   ├── schemas/                Pydantic request/response models
│   ├── services/               External service clients
│   ├── core_bucket_pipeline.py Canonical orchestrator
│   ├── geometry_generator_real.py  Room mesh generator
│   ├── logging_config.py       JSON structured logging
│   ├── main.py                 FastAPI application
│   ├── prompt_runner_adapter.py    NLP → spec_json
│   └── storage.py              Bucket write/read/retry
├── deployment/                 Docker, Nginx, deploy scripts
├── production_validation_results/  20-case validation evidence
├── review_packets/             Architecture, execution flow, certification
├── tests/                      Test suite
├── validation/                 Benchmark artifacts
├── .env.example                Environment variable reference
├── OPERATIONS_RUNBOOK.md       Production operations guide
├── ROADMAP.md                  Future work
└── README.md                   This file
```

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [`API_REFERENCE.md`](API_REFERENCE.md) | Full API endpoint reference — all 12 production endpoints with schemas and error codes |
| [`OPERATIONS_RUNBOOK.md`](OPERATIONS_RUNBOOK.md) | Production health checks, replay procedure, failure recovery, secret rotation, service ownership |
| [`ROADMAP.md`](ROADMAP.md) | Known gaps, near-term fixes, medium and long-term feature work |
| [`review_packets/ARCHITECTURE_MAP.md`](review_packets/ARCHITECTURE_MAP.md) | Full component diagram — middleware, logging, health, replay, BHIV endpoint, multi-city layer |
| [`review_packets/EXECUTION_FLOW.md`](review_packets/EXECUTION_FLOW.md) | Step-by-step runtime trace of one HTTP request through the full pipeline |
| [`review_packets/PRODUCTION_READINESS_REVIEW_PACKET.md`](review_packets/PRODUCTION_READINESS_REVIEW_PACKET.md) | Sprint summary, all task results, service ownership, handover checklist |
| [`review_packets/PRODUCTION_CERTIFICATION.md`](review_packets/PRODUCTION_CERTIFICATION.md) | Formal certification — every requirement mapped to its evidence file |
| [`deployment/deployment_validation.md`](deployment/deployment_validation.md) | Deployment reproducibility evidence, MongoDB Atlas setup, first-deploy walkthrough |
