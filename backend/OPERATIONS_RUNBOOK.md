# Operations Runbook

**Design Engine API — Production Operations**
**Last updated:** 2026-07-22

---

## 1. Production Health Checks

### Quick liveness check

```bash
curl https://<your-service>.onrender.com/health
# Expected: {"status": "ok", "service": "Design Engine API", "version": "0.1.0"}
```

### Full dependency check

```bash
curl https://<your-service>.onrender.com/api/v1/health/detailed
```

Expected response shape:
```json
{
  "overall": "healthy",
  "components": {
    "database":   { "status": "healthy",        "latency_ms": 42 },
    "redis":      { "status": "not_configured", "latency_ms": 0 },
    "bucket":     { "status": "healthy",        "latency_ms": 1465 },
    "sohum_mcp":  { "status": "healthy",        "latency_ms": 320 },
    "ranjeet_rl": { "status": "healthy",        "latency_ms": 280 }
  }
}
```

**Interpreting `overall`:**

| Value | Meaning | Action |
|-------|---------|--------|
| `healthy` | All components up | None |
| `degraded` | Non-DB component down (bucket, sohum, ranjeet, redis) | Investigate affected component; pipeline may still work |
| `unhealthy` | MongoDB down | Urgent — auth and spec storage unavailable |

### Using the health check script

```bash
cd deployment
./health_check.sh
# Checks backend API, database, and Redis in sequence
# Exit 0 = all healthy, Exit 1 = failure
```

---

## 2. Replay Procedure

Replay re-executes the full pipeline for a previously generated spec using the original request payload stored in the trace file.

### When to use replay

- Verify a spec can be reproduced deterministically
- Re-generate artifacts after a bucket failure
- Debug a pipeline issue by re-running with the same input

### Step 1 — List replayable specs

```bash
curl -H "Authorization: Bearer <token>" \
  https://<your-service>.onrender.com/api/v1/replay/
```

### Step 2 — Inspect trace before replaying

```bash
curl -H "Authorization: Bearer <token>" \
  https://<your-service>.onrender.com/api/v1/replay/spec_47d77f94/trace
```

Verify the trace has a `core_ingress` stage entry — this is what replay uses to reconstruct the original request.

### Step 3 — Execute replay

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  https://<your-service>.onrender.com/api/v1/replay/spec_47d77f94
```

### Step 4 — Verify result

Check `"status": "success"` and that `artifacts` contains four URLs (glb, stl, step, spec).

If `"status": "failed"`, check the `error` field and the structured logs for the `replay_spec_id`.

### Local replay (benchmark)

```bash
cd backend
python validation/run_benchmarks.py
# Runs replay against spec_6547c732a587 and writes validation/replay_metrics.json
```

---

## 3. Monitoring

### Overview endpoint

```bash
curl -H "Authorization: Bearer <token>" \
  https://<your-service>.onrender.com/api/v1/monitoring/overview
```

Returns DB-backed counts (total specs, users, recent activity). If DB is unavailable, returns zeros with `"status": "unavailable"` — the endpoint stays up.

### Performance metrics

```bash
curl https://<your-service>.onrender.com/api/v1/monitoring/metrics
```

Returns per-operation duration and success/fail counts tracked by `PerformanceMonitor`.

### Prometheus metrics

```bash
curl https://<your-service>.onrender.com/metrics
```

Available when `METRICS_ENABLED=true`. Compatible with Prometheus scraping.

---

## 4. Structured Logging

All logs are JSON-structured with `trace_id` on every line.

### Log file location

```
logs/bhiv.log          (rotating, 10 MB per file, 5 backups)
stdout                 (same JSON, captured by Render)
```

### Log line format

```json
{
  "timestamp":      "2026-07-22T07:11:35.766045+00:00",
  "level":          "INFO",
  "logger":         "app.core_bucket_pipeline",
  "message":        "Artifact stored in bucket: spec_47d77f94.glb",
  "trace_id":       "a3f7c2d1-8b4e-4f9a-b2c1-7d3e5f8a9b0c",
  "execution_id":   "spec_47d77f94",
  "pipeline_stage": "http_request",
  "module":         "core_bucket_pipeline",
  "func":           "store_artifact",
  "line":           87,
  "environment":    "production",
  "service":        "design_engine_api"
}
```

### Tracing a request

Every request gets a `trace_id` (from `X-Trace-ID` header or auto-generated UUID). To trace a specific request:

```bash
grep "a3f7c2d1-8b4e-4f9a-b2c1-7d3e5f8a9b0c" logs/bhiv.log | python -m json.tool
```

Or filter by spec_id:

```bash
grep "spec_47d77f94" logs/bhiv.log
```

### Bucket trace files

Every pipeline execution writes a JSONL trace file:

```
data/bucket_traces/core_bucket_spec_47d77f94.jsonl
```

Each line is a stage entry: `core_ingress`, `bucket_request_stored`, `prompt_runner_response`, `bucket_persist_complete`, `core_response_ready`.

```bash
cat data/bucket_traces/core_bucket_spec_47d77f94.jsonl | python -m json.tool
```

---

## 5. Failure Recovery

### 5.1 MongoDB unavailable

**Symptoms:** `overall=unhealthy` in health check, 503 on auth endpoints.

**Recovery:**
1. Check MongoDB Atlas dashboard for cluster status
2. Verify `MONGODB_URL` is correct and the IP whitelist includes the Render service IP
3. Restart the Render service after Atlas recovers

**Impact while down:** Auth, spec storage, and monitoring unavailable. The `/health` and `/bhiv/v1/design` endpoints remain up but degraded.

---

### 5.2 Bucket service unavailable

**Symptoms:** `overall=degraded`, `bucket.status=unhealthy`. Pipeline requests return HTTP 500.

**Recovery:**
1. Check `https://bhiv-bucket.onrender.com/health` directly
2. If Render cold-start: wait 60 seconds and retry — the bucket service spins down after inactivity
3. If persistent failure: contact Siddhesh (bucket service owner)

**Bucket lineage conflicts (parallel writes):** The system retries automatically up to 5 times with backoff. No manual action needed unless all 5 retries fail.

---

### 5.3 Sohum MCP unavailable

**Symptoms:** `sohum_mcp.status=unhealthy` in health check. `/bhiv/v1/design` returns `compliance.compliant=false` with empty violations.

**Recovery:** Contact Sohum. The `/bhiv/v1/design` endpoint continues to function — compliance degrades gracefully to `compliant=false`.

---

### 5.4 Ranjeet RL unavailable

**Symptoms:** `ranjeet_rl.status=unhealthy`. `/bhiv/v1/design` returns `rl_optimization=null` or mock RL response.

**Recovery:** Contact Ranjeet. The endpoint continues to function — RL optimization degrades gracefully to mock response.

---

### 5.5 Render cold-start latency

**Symptoms:** First request after inactivity takes 30–60 seconds. Subsequent requests are normal.

**Recovery:** No action needed. This is expected behaviour for Render free-tier services. Consider upgrading to a paid Render plan to eliminate cold starts.

---

### 5.6 Replay fails — trace file not found

**Symptoms:** `POST /api/v1/replay/{spec_id}` returns 404 or `"status": "failed"` with `"error": "Trace file not found"`.

**Cause:** The spec was generated before trace files were implemented, or the `data/bucket_traces/` directory was cleared.

**Recovery:** Replay is not possible without a trace file. The original spec artifacts remain in the Bucket and are accessible via their artifact URLs.

---

## 6. Secret Rotation

### JWT secret key

1. Generate new secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Update `JWT_SECRET_KEY` in Render environment variables
3. Restart the service
4. All existing tokens are immediately invalidated — users must log in again

### MongoDB credentials

1. Rotate credentials in MongoDB Atlas
2. Update `MONGODB_URL` in Render environment variables
3. Restart the service

### Core internal token

1. Generate new token: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Update `CORE_INTERNAL_TOKEN` in Render environment variables
3. Restart the service

---

## 7. Service Ownership

| Service | Owner | URL | Notes |
|---------|-------|-----|-------|
| Design Engine API | Anmol | `https://bhiv-backend.onrender.com` | This service |
| Bucket storage | Siddhesh | `https://bhiv-bucket.onrender.com` | Append-only artifact store |
| Sohum MCP compliance | Sohum | `https://ai-rule-api-w7z5.onrender.com` | City DCR compliance checks |
| Ranjeet RL optimizer | Ranjeet | `https://land-utilization-rl.onrender.com` | Land utilization RL |
| MongoDB Atlas | Anmol | MongoDB Atlas dashboard | Primary database |

---

## 8. Operational Checklist

### Daily

- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] `GET /api/v1/health/detailed` returns `overall=healthy` or investigate degraded components
- [ ] Check `logs/bhiv.log` for ERROR-level entries

### Before a release

- [ ] Run full test suite: `pytest tests/ --ignore=tests/test_complete_system.py -q`
- [ ] Run production validation: `python run_production_validation.py` — expect 20/20 PASS
- [ ] Run benchmarks: `python validation/run_benchmarks.py`
- [ ] Verify `deployment/deploy_production.sh` completes without rollback

### After a release

- [ ] `GET /health` returns 200
- [ ] `GET /api/v1/health/detailed` returns `overall=healthy`
- [ ] Send one test request to `POST /api/v1/core/generate`
- [ ] Verify artifact URLs in response are reachable
- [ ] Check `logs/bhiv.log` for any new ERROR entries

### Rollback

```bash
cd deployment
./rollback.sh
```

Rolls back to the previous Docker image tag. The deploy script triggers this automatically if the post-deploy health check fails.
