# API Reference

**Design Engine API — v1.0.0**
**Base URL (production):** `https://bhiv-backend.onrender.com`
**Base URL (local):** `http://localhost:8000`

Swagger UI is available at `/docs` when `DEMO_MODE=false` (development only).

---

## Authentication

All protected endpoints require a JWT Bearer token obtained from the login endpoint.

```
Authorization: Bearer <token>
```

Tokens expire after 24 hours (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

---

## Endpoints

### 1. Basic Health Check

```
GET /health
```

No authentication required. Used by Render health checks and load balancers.

**Response 200:**
```json
{
  "status": "ok",
  "service": "Design Engine API",
  "version": "0.1.0"
}
```

---

### 2. Detailed Health Check

```
GET /api/v1/health/detailed
```

No authentication required. Runs real dependency checks in parallel.

**Response 200:**
```json
{
  "overall": "healthy",
  "components": {
    "database":   { "status": "healthy",   "latency_ms": 42 },
    "redis":      { "status": "not_configured", "latency_ms": 0 },
    "bucket":     { "status": "healthy",   "latency_ms": 1465 },
    "sohum_mcp":  { "status": "healthy",   "latency_ms": 320 },
    "ranjeet_rl": { "status": "healthy",   "latency_ms": 280 }
  },
  "uptime_seconds": 3600
}
```

`overall` values: `"healthy"` | `"degraded"` (non-DB component down) | `"unhealthy"` (DB down)

---

### 3. Login

```
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded
```

No authentication required.

**Request body (form):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | yes | Registered username |
| `password` | string | yes | User password |

**Response 200:**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 401 | Invalid username or password |
| 503 | Database unavailable |

---

### 4. Register

```
POST /api/v1/auth/register
Content-Type: application/json
```

No authentication required.

**Request body:**
```json
{
  "username": "string",
  "password": "string",
  "email": "string"
}
```

**Response 201:**
```json
{
  "id": "string",
  "username": "string",
  "email": "string"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 400 | Username already exists |
| 503 | Database unavailable |

---

### 5. Core Generate (primary design endpoint)

```
POST /api/v1/core/generate
Authorization: Bearer <token>
Content-Type: application/json
```

The only valid design generation entry point. `POST /api/v1/generate` is permanently blocked (returns 403).

**Request body:**
```json
{
  "prompt":     "Design a 3BHK apartment with modern kitchen",
  "city":       "Mumbai",
  "style":      "modern",
  "user_id":    "user_123",
  "project_id": "proj_456"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `prompt` | string | yes | Minimum 10 characters |
| `city` | string | yes | Mumbai, Pune, Ahmedabad, Nashik |
| `style` | string | no | Default: `"modern"` |
| `user_id` | string | yes | Non-empty string |
| `project_id` | string | no | Optional project reference |

**Response 200:**
```json
{
  "spec_id": "spec_47d77f94",
  "status": "success",
  "artifact_urls": {
    "glb":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "stl":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "step": "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "spec": "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>"
  },
  "trace_id": "core_bucket_spec_47d77f94"
}
```

Response header: `X-Trace-ID: <uuid>`

**Error responses:**

| Code | Condition |
|------|-----------|
| 400 | Prompt too short, missing user_id, or invalid request |
| 401 | Missing or invalid JWT token |
| 403 | Token present but route hard-blocked (wrong endpoint) |
| 500 | Bucket unreachable or geometry generation failed |
| 503 | Prompt runner unavailable |

---

### 6. BHIV Integrated Design

```
POST /bhiv/v1/design
Content-Type: application/json
```

No authentication required. Runs the full pipeline plus compliance and RL optimization. Both external services degrade gracefully — the endpoint never returns 500 due to Sohum MCP or Ranjeet RL being unavailable.

**Request body:**
```json
{
  "user_id":    "user_123",
  "prompt":     "Design a 4-floor residential building",
  "city":       "Mumbai",
  "project_id": "proj_456",
  "context":    {}
}
```

| Field | Type | Required |
|-------|------|----------|
| `user_id` | string | yes |
| `prompt` | string | yes |
| `city` | string | yes |
| `project_id` | string | no |
| `context` | object | no |

**Response 200:**
```json
{
  "request_id":       "bhiv_20260722_071135",
  "spec_id":          "spec_47d77f94",
  "spec_json":        { "design_type": "apartment", "rooms": [...], "dimensions": {...} },
  "preview_url":      "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
  "compliance": {
    "compliant":      false,
    "violations":     [],
    "geometry_url":   null,
    "case_id":        null
  },
  "rl_optimization":  null,
  "processing_time_ms": 4823,
  "timestamp":        "2026-07-22T07:11:35Z"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 500 | Core pipeline failed (bucket unreachable, geometry failed) |
| 503 | Prompt runner unavailable |

---

### 7. Replay — List Replayable Specs

```
GET /api/v1/replay/
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "replayable_specs": ["spec_47d77f94", "spec_703a32fc"],
  "count": 2
}
```

---

### 8. Replay — Get Trace Summary

```
GET /api/v1/replay/{spec_id}/trace
Authorization: Bearer <token>
```

**Path parameter:** `spec_id` — the spec ID to inspect.

**Response 200:**
```json
{
  "spec_id":    "spec_47d77f94",
  "trace_id":   "core_bucket_spec_47d77f94",
  "stages":     ["core_ingress", "bucket_request_stored", "prompt_runner_response", "bucket_persist_complete", "core_response_ready"],
  "entry_count": 5,
  "first_timestamp": "2026-07-22T07:11:35Z",
  "last_timestamp":  "2026-07-22T07:11:40Z"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 404 | Trace file not found for spec_id |

---

### 9. Replay — Execute Replay

```
POST /api/v1/replay/{spec_id}
Authorization: Bearer <token>
```

Re-executes the full pipeline using the original request payload from the stored trace. Produces a new set of artifacts without overwriting the original.

**Path parameter:** `spec_id` — the spec ID to replay.

**Response 200:**
```json
{
  "original_spec_id": "spec_47d77f94",
  "replay_spec_id":   "replay_spec_47d77f94_bdacaaf9",
  "status":           "success",
  "artifacts": {
    "glb":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "stl":  "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "step": "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>",
    "spec": "https://bhiv-bucket.onrender.com/bucket/artifact/<uuid>"
  },
  "replayed_at": "2026-07-22T07:15:00Z"
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 404 | Trace file not found for spec_id |
| 200 with `"status": "failed"` | Replay executed but pipeline failed — check `error` field |

---

### 10. Monitoring Overview

```
GET /api/v1/monitoring/overview
Authorization: Bearer <token>
```

**Response 200:**
```json
{
  "status": "available",
  "total_specs": 89,
  "total_users": 12,
  "recent_activity": [...]
}
```

When DB is unavailable: returns `"status": "unavailable"` with zero counts — endpoint stays up.

---

### 11. City Rules

```
GET /api/v1/cities/{city}/rules
```

No authentication required.

**Path parameter:** `city` — one of `Mumbai`, `Pune`, `Ahmedabad`, `Nashik`.

**Response 200:**
```json
{
  "city":           "Mumbai",
  "fsi_base":       1.33,
  "dcr_version":    "DCR 2034",
  "setback_front_m": 4.5,
  "setback_rear_m":  3.0,
  "parking_ratio":   1.0
}
```

**Error responses:**

| Code | Condition |
|------|-----------|
| 404 | City not supported — `{"error": {"message": "City 'X' not supported"}}` |

---

### 12. City Context

```
GET /api/v1/cities/{city}/context
```

No authentication required.

**Response 200:**
```json
{
  "city":             "Mumbai",
  "dcr_version":      "DCR 2034",
  "constraints":      { "fsi_base": 1.33, "setback_front_m": 4.5, ... },
  "source_documents": ["DCR_2034.pdf"],
  "typical_use_cases": ["residential", "commercial"]
}
```

---

## Error Response Format

All error responses use this envelope:

```json
{
  "error": {
    "code":        "HTTP_ERROR",
    "message":     "Human-readable description",
    "status_code": 404
  }
}
```

---

## Blocked Routes

The following routes are permanently blocked and always return 403:

| Route | Reason |
|-------|--------|
| `POST /api/v1/generate` | Phase 3 enforcement — use `/api/v1/core/generate` |
| `POST /api/v1/geometry/generate` | Phase 3 enforcement — use `/api/v1/core/generate` |

---

## Response Headers

Every response includes:

| Header | Value |
|--------|-------|
| `X-Trace-ID` | UUID identifying the request trace |
