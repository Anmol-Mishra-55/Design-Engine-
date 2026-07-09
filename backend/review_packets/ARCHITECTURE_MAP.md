# Architecture Map

**Project:** Design Engine API
**State:** Post Production Readiness Sprint (Tasks 1–4 complete)
**Version:** 1.0

---

## System Overview

The Design Engine API is a FastAPI application deployed on Render.com. It accepts
natural language design prompts, generates 3D architectural specifications, and
stores all artifacts in a remote Bucket service. Every request is traced, logged
in JSON, and health-monitored.

---

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT                                  │
│              (HTTP / mobile / frontend / test runner)           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP Request
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NGINX REVERSE PROXY                          │
│              deployment/nginx.conf                              │
│         TLS termination · security headers · port 80/443        │
└─────────────────────────────┬───────────────────────────────────┘
                              │ proxy_pass :8000
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FASTAPI APPLICATION                          │
│                    app/main.py  :8000                           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              MIDDLEWARE STACK (ordered)                  │   │
│  │                                                          │   │
│  │  1. CORSMiddleware          (FastAPI built-in)           │   │
│  │  2. TraceContextMiddleware  app/middleware/trace_context  │   │
│  │     · Reads X-Trace-ID header or generates UUID          │   │
│  │     · Injects trace_id into thread-local log context     │   │
│  │     · Adds X-Trace-ID to response headers                │   │
│  │     · Clears context after response                      │   │
│  │  3. log_requests middleware (inline in main.py)          │   │
│  │     · Logs method + path + status + duration             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    LOGGING LAYER                         │   │
│  │              app/logging_config.py                       │   │
│  │                                                          │   │
│  │  JsonFormatter                                           │   │
│  │    · One JSON object per log line                        │   │
│  │    · Fields: timestamp, level, logger, message,          │   │
│  │              trace_id, execution_id, pipeline_stage,     │   │
│  │              module, func, line, environment, service    │   │
│  │                                                          │   │
│  │  RotatingFileHandler → logs/bhiv.log                     │   │
│  │    · 10 MB per file · 5 backups                          │   │
│  │  StreamHandler → stdout                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    API ROUTERS                           │   │
│  │                                                          │   │
│  │  /health              app/api/health.py                  │   │
│  │  /api/v1/health       app/api/health.py                  │   │
│  │  /api/v1/health/detailed  (real dependency checks)       │   │
│  │  /api/v1/core/generate    app/api/core_entry.py          │   │
│  │  /api/v1/generate     app/api/generate.py  (403 blocked) │   │
│  │  /api/v1/replay/      app/api/replay.py                  │   │
│  │  /api/v1/auth/        app/api/auth.py                    │   │
│  │  /api/v1/monitoring/  app/api/monitoring_system.py       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
┌─────────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  HEALTH CHECKS  │  │    REPLAY    │  │   CORE PIPELINE      │
│  app/api/       │  │  app/replay/ │  │  app/core_bucket_    │
│  health.py      │  │  replay_     │  │  pipeline.py         │
│                 │  │  service.py  │  │                      │
│  · MongoDB      │  │              │  │  CoreBucketCanonical  │
│  · Redis        │  │  · replay()  │  │  Orchestrator        │
│  · Bucket       │  │  · list()    │  │                      │
│  · Sohum MCP    │  │  · summary() │  │  Step 1: store req   │
│  · Ranjeet RL   │  │              │  │  Step 2: prompt run  │
│                 │  │  Reads from: │  │  Step 3: gen GLB     │
│  Returns        │  │  data/bucket │  │  Step 4: store all   │
│  latency_ms     │  │  _traces/    │  │  Step 5: return URLs │
│  per component  │  │  data/specs/ │  │                      │
└─────────────────┘  └──────────────┘  └──────────┬───────────┘
                                                   │
                              ┌────────────────────┼────────────────────┐
                              │                    │                    │
                              ▼                    ▼                    ▼
                   ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
                   │  PROMPT RUNNER   │  │  GEOMETRY ENGINE │  │  BUCKET SERVICE  │
                   │  ADAPTER         │  │                  │  │                  │
                   │  app/prompt_     │  │  app/geometry_   │  │  app/storage.py  │
                   │  runner_adapter  │  │  generator_real  │  │                  │
                   │                  │  │                  │  │  upload_to_bucket│
                   │  platform_       │  │  generate_real_  │  │  → remote URL    │
                   │  adapter.process │  │  glb(spec_json)  │  │                  │
                   │  → spec_json     │  │  → GLB bytes     │  │  https://bhiv-   │
                   │                  │  │                  │  │  bucket.onrender │
                   │  Meshy AI        │  │  STL from rooms  │  │  .com            │
                   │  Tripo AI        │  │  STEP from rooms │  │                  │
                   │  geometry_real   │  │                  │  │  All artifacts   │
                   │  (fallback chain)│  │                  │  │  stored here     │
                   └──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## Middleware Stack Detail

```
Incoming Request
      │
      ▼
┌─────────────────────────────────────────┐
│  1. CORSMiddleware                      │
│     Allows configured origins           │
│     Handles preflight OPTIONS           │
└─────────────────────┬───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│  2. TraceContextMiddleware              │
│     app/middleware/trace_context.py     │
│                                         │
│     trace_id = X-Trace-ID header        │
│              OR uuid.uuid4()            │
│                                         │
│     set_trace_context(                  │
│         trace_id=trace_id,              │
│         execution_id="",               │
│         pipeline_stage="http_request"  │
│     )                                   │
│                                         │
│     response.headers["X-Trace-ID"]      │
│         = trace_id                      │
│                                         │
│     finally: clear_trace_context()      │
└─────────────────────┬───────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│  3. log_requests (inline middleware)    │
│     Logs: METHOD PATH from IP           │
│     Logs: STATUS METHOD PATH (Xms)      │
│     trace_id automatically in every log │
│     line via JsonFormatter              │
└─────────────────────┬───────────────────┘
                      │
                      ▼
                  Route Handler
```

---

## Logging Architecture

```
Any logger.info() / logger.error() call
              │
              ▼
┌─────────────────────────────────────────┐
│  JsonFormatter.format(record)           │
│  app/logging_config.py                  │
│                                         │
│  Reads thread-local context:            │
│    get_trace_context() →                │
│      trace_id, execution_id,            │
│      pipeline_stage                     │
│                                         │
│  Emits JSON:                            │
│  {                                      │
│    "timestamp": "...",                  │
│    "level": "INFO",                     │
│    "logger": "app.core_bucket_pipeline",│
│    "message": "...",                    │
│    "trace_id": "uuid-...",              │
│    "execution_id": "...",               │
│    "pipeline_stage": "...",             │
│    "module": "...",                     │
│    "func": "...",                       │
│    "line": 142,                         │
│    "environment": "development",        │
│    "service": "design_engine_api"       │
│  }                                      │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
       ▼               ▼
┌────────────┐  ┌──────────────────────────┐
│  stdout    │  │  logs/bhiv.log           │
│  (console) │  │  RotatingFileHandler     │
│            │  │  10 MB / 5 backups       │
└────────────┘  └──────────────────────────┘
```

---

## Health Check Architecture

```
GET /api/v1/health/detailed
              │
              ▼
┌─────────────────────────────────────────┐
│  asyncio.gather() — all 5 in parallel   │
│  5-second timeout per check             │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │  check_db_connection()          │    │
│  │  database_mongodb.py            │    │
│  │  → {status, latency_ms}         │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │  _check_redis()                 │    │
│  │  redis.asyncio ping             │    │
│  │  → {status, latency_ms}         │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │  _check_bucket()                │    │
│  │  GET {BUCKET_URL}/health        │    │
│  │  → {status, latency_ms}         │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │  _check_external_service(       │    │
│  │      "sohum_mcp", SOHUM_URL)    │    │
│  │  → {status, latency_ms}         │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │  _check_external_service(       │    │
│  │      "ranjeet_rl", RANJEET_URL) │    │
│  │  → {status, latency_ms}         │    │
│  └─────────────────────────────────┘    │
│                                         │
│  overall = "healthy"                    │
│          | "degraded"  (non-DB fail)    │
│          | "unhealthy" (DB fail)        │
└─────────────────────────────────────────┘
```

---

## Replay Architecture

```
POST /api/v1/replay/{spec_id}
              │
              ▼
┌─────────────────────────────────────────┐
│  ReplayService.replay(spec_id)          │
│  app/replay/replay_service.py           │
│                                         │
│  1. _load_trace(spec_id)                │
│     reads data/bucket_traces/           │
│           core_bucket_{spec_id}.jsonl   │
│                                         │
│  2. _extract_request_payload(entries)   │
│     finds core_ingress stage entry      │
│     reconstructs original request       │
│                                         │
│  3. Generate new IDs                    │
│     replay_spec_id = replay_{spec_id}   │
│     replay_trace_id = core_bucket_      │
│                       {replay_spec_id}  │
│                                         │
│  4. set_trace_context(                  │
│         trace_id=replay_trace_id,       │
│         execution_id=replay_spec_id,    │
│         pipeline_stage="replay"         │
│     )                                   │
│                                         │
│  5. CoreBucketCanonicalOrchestrator     │
│         .execute(replay_spec_id,        │
│                  request_payload)       │
│     → new artifacts in Bucket           │
│                                         │
│  6. Return ReplayResult                 │
│     {original_spec_id, replay_spec_id,  │
│      status, artifacts, replayed_at}    │
└─────────────────────────────────────────┘
```

---

## Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                      RENDER.COM                                 │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Web Service                                            │   │
│  │  uvicorn app.main:app --host 0.0.0.0 --port $PORT       │   │
│  │  python:3.11-slim (Dockerfile)                          │   │
│  │  Health check: GET /api/v1/health every 30s             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Environment variables injected via Render secret management:  │
│    MONGODB_URL, JWT_SECRET_KEY, BUCKET_URL,                     │
│    SOHUM_MCP_URL, RANJEET_RL_URL, REDIS_URL                     │
└─────────────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────────────┐
│  MongoDB Atlas          │    │  External Services              │
│  (primary database)     │    │                                 │
│  mongodb+srv://...      │    │  Bucket: bhiv-bucket.onrender   │
│                         │    │  Sohum MCP: ai-rule-api-w7z5    │
│  Collections:           │    │  Ranjeet RL: land-utilization-rl│
│  · users                │    │  Redis: redis://localhost:6379  │
│  · specs                │    │                                 │
└─────────────────────────┘    └─────────────────────────────────┘

Local Docker Compose (development/staging):
  backend:8000 · postgres:5432 · redis:6379 · nginx:80/443
  deployment/docker-compose.yml
```

---

## Monitoring Architecture

```
Runtime Metrics (PerformanceMonitor)
  app/api/monitoring_system.py
    · track_performance() decorator
    · Records duration_ms, success/fail counts per operation
    · Writes data/logs/metrics.json every 10 calls
    · GET /api/v1/monitoring/metrics → live summary

Structured Logs
  logs/bhiv.log
    · JSON per line
    · trace_id on every line
    · Queryable by log aggregator (Datadog, CloudWatch, etc.)

Sentry (optional)
  app/main.py
    · sentry_sdk.init() if SENTRY_DSN configured
    · Captures unhandled exceptions
    · GET /api/v1/health/test-error → test capture

Prometheus (optional)
  app/api/health.py
    · GET /api/v1/metrics → Prometheus text format
    · prometheus_fastapi_instrumentator
```

---

*Generated by Amazon Q — Production Readiness Sprint, Task 5*
