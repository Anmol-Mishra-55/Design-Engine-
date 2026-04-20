# POST /api/v1/generate — Execution Guide

## Endpoint
```
POST http://localhost:8000/api/v1/generate
```

## Authentication
```
Authorization: Bearer <your_jwt_token>
```

Get token first:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}'
```

---

## Request Schema

### Required Fields
| Field | Type | Description | Example |
|---|---|---|---|
| `user_id` | string | User identifier | `"user_001"` |
| `prompt` | string | Natural language design request (min 10 chars) | `"Generate 2BHK modern apartment"` |

### Optional Fields
| Field | Type | Default | Description |
|---|---|---|---|
| `city` | string | `"Mumbai"` | Indian city for compliance rules |
| `style` | string | `"modern"` | Architectural style |
| `project_id` | string | `null` | Project grouping ID |
| `context` | object | `{}` | Additional metadata |
| `constraints` | object | `{}` | Design constraints (budget, area, etc.) |

### Supported Cities
`Mumbai`, `Pune`, `Ahmedabad`, `Nashik`, `Bangalore`, `Delhi`, `Hyderabad`, `Chennai`, `Kolkata`

### Supported Styles
`modern`, `traditional`, `contemporary`, `luxury`, `minimalist`, `rustic`

---

## Test Cases

### 1. Minimal Request (1BHK)
```json
{
  "user_id": "test_user",
  "prompt": "Generate 1BHK"
}
```

**Expected Output:**
- `spec_json.type`: `"1BHK"`
- `spec_json.rooms`: `["bedroom", "hall", "kitchen", "bathroom"]` (4 rooms)
- `glb_url`: `/api/v1/files/geometry/spec_<id>.glb`
- `estimated_cost`: ~₹25-50 lakh (Mumbai)

---

### 2. Standard Request (2BHK)
```json
{
  "user_id": "test_user",
  "prompt": "Generate 2BHK modern apartment in Mumbai",
  "city": "Mumbai",
  "style": "modern"
}
```

**Expected Output:**
- `spec_json.type`: `"2BHK"`
- `spec_json.rooms`: `["master_bedroom", "bedroom_2", "hall", "kitchen", "master_bathroom", "common_bathroom"]` (6 rooms)
- `spec_json.style`: `"modern"`
- `spec_json.city`: `"Mumbai"`
- GLB size: ~4,536 bytes
- Vertices: 144 (6 rooms × 1 story × 24)

---

### 3. Full Request (3BHK with constraints)
```json
{
  "user_id": "architect_001",
  "prompt": "Design a 3BHK luxury apartment with 1200 sqft area",
  "city": "Bangalore",
  "style": "luxury",
  "project_id": "proj_2024_001",
  "context": {
    "client_name": "John Doe",
    "deadline": "2024-03-01"
  },
  "constraints": {
    "budget": 12000000,
    "area_sqft": 1200,
    "stories": 1
  }
}
```

**Expected Output:**
- `spec_json.type`: `"3BHK"`
- `spec_json.rooms`: 9 rooms (master_bedroom, bedroom_2, bedroom_3, hall, dining, kitchen, 3 bathrooms)
- `spec_json.area_sqft`: `1200`
- `spec_json.budget_inr`: `12000000`
- `estimated_cost`: ~₹11,400,000 (95% of budget)
- `spec_json.style_hints.cost_multiplier`: `2.5` (luxury)

---

### 4. Villa Request
```json
{
  "user_id": "test_user",
  "prompt": "Design a villa with garden and garage",
  "city": "Pune",
  "style": "traditional"
}
```

**Expected Output:**
- `spec_json.type`: `"VILLA"`
- `spec_json.rooms`: 16 rooms (4 bedrooms, hall, dining, kitchen, 4 bathrooms, study, pooja_room, garage, garden, terrace)
- `spec_json.stories`: `2`
- GLB size: ~21,388 bytes
- Vertices: 768 (16 rooms × 2 stories × 24)

---

### 5. Penthouse Request
```json
{
  "user_id": "premium_client",
  "prompt": "Generate penthouse with home theatre and jacuzzi",
  "city": "Mumbai",
  "style": "luxury"
}
```

**Expected Output:**
- `spec_json.type`: `"PENTHOUSE"`
- `spec_json.rooms`: 13 rooms (3 bedrooms, hall, dining, kitchen, 3 bathrooms, study, home_theatre, terrace, jacuzzi_deck)
- `estimated_cost`: ~₹5-30 crore
- `spec_json.style_hints.cost_multiplier`: `2.5`

---

### 6. Multi-Storey Request
```json
{
  "user_id": "test_user",
  "prompt": "Generate 2BHK G+2 building",
  "city": "Ahmedabad"
}
```

**Expected Output:**
- `spec_json.type`: `"2BHK"`
- `spec_json.stories`: `2` (G+2 = ground + 2 = 3 floors, but capped at 2 by BHK default)
- Vertices: 288 (6 rooms × 2 stories × 24)

---

### 7. Budget-Constrained Request
```json
{
  "user_id": "test_user",
  "prompt": "Generate 2BHK apartment budget 50 lakh",
  "city": "Nashik",
  "constraints": {
    "budget": 5000000
  }
}
```

**Expected Output:**
- `spec_json.budget_inr`: `5000000`
- `estimated_cost`: `4750000` (95% of budget)
- Lower cost multiplier applied

---

### 8. Area-Specified Request
```json
{
  "user_id": "test_user",
  "prompt": "Generate 3BHK apartment 1500 sqft",
  "city": "Mumbai"
}
```

**Expected Output:**
- `spec_json.area_sqft`: `1500`
- `spec_json.area_sqm`: `139.35` (auto-converted)
- Dimensions adjusted to match area

---

### 9. Edge Case — Extreme Stories (Capped)
```json
{
  "user_id": "test_user",
  "prompt": "Generate 2BHK 999 storey building"
}
```

**Expected Output:**
- `spec_json.stories`: `10` (capped at max)
- Vertices: 1,440 (6 rooms × 10 stories × 24)
- No crash, no OOM

---

### 10. Edge Case — No BHK Detected
```json
{
  "user_id": "test_user",
  "prompt": "I want a house with rooms"
}
```

**Expected Output:**
- `spec_json.type`: `"house"` (inferred from "house" keyword)
- `spec_json.rooms`: Empty or minimal fallback
- Still generates valid GLB (fallback to bounding box)

---

## Response Schema

### Success Response (201 Created)
```json
{
  "spec_id": "spec_a1b2c3d4e5f6",
  "spec_json": {
    "type": "2BHK",
    "design_type": "2BHK",
    "rooms": ["master_bedroom", "bedroom_2", "hall", "kitchen", "master_bathroom", "common_bathroom"],
    "layout_rules": [...],
    "style": "modern",
    "style_hints": {...},
    "objects": [...],
    "city": "Mumbai",
    "dimensions": {
      "width": 9.0,
      "length": 8.5,
      "height": 2.7
    },
    "units": "meters",
    "stories": 1,
    "room_counts": {
      "bedroom": 2,
      "hall": 1,
      "kitchen": 1,
      "bathroom": 2,
      "balcony": 1
    },
    "adjacency": {...},
    "room_dimensions": {...},
    "estimated_cost": {
      "total": 6500000,
      "currency": "INR"
    },
    "metadata": {
      "execution_authority": "platform_adapter",
      "routing_authority": "core",
      "storage_authority": "bucket",
      "deterministic_hash": "5409aa2f640c18b8",
      "bucket_trace_id": "core_bucket_spec_a1b2c3d4e5f6",
      "canonical_flow": "core->bucket->prompt_runner->geometry->bucket->core",
      "estimated_cost": 6500000,
      "currency": "INR",
      "generation_provider": "platform_adapter",
      "city": "Mumbai",
      "style": "modern",
      "generation_time_ms": 1234,
      "export_urls": {
        "glb": "/api/v1/files/geometry/spec_a1b2c3d4e5f6.glb",
        "stl": "/api/v1/files/geometry/exports/spec_a1b2c3d4e5f6.stl",
        "step": "/api/v1/files/geometry/exports/spec_a1b2c3d4e5f6.step"
      }
    }
  },
  "preview_url": "/api/v1/files/geometry/spec_a1b2c3d4e5f6.glb",
  "estimated_cost": 6500000,
  "compliance_check_id": "check_spec_a1b2c3d4e5f6",
  "created_at": "2024-01-15T10:30:00Z",
  "spec_version": 1,
  "user_id": "test_user",
  "city": "Mumbai",
  "lm_provider": "platform_adapter",
  "generation_time_ms": 1234,
  "export_urls": {
    "glb": "/api/v1/files/geometry/spec_a1b2c3d4e5f6.glb",
    "stl": "/api/v1/files/geometry/exports/spec_a1b2c3d4e5f6.stl",
    "step": "/api/v1/files/geometry/exports/spec_a1b2c3d4e5f6.step"
  },
  "glb_url": "/api/v1/files/geometry/spec_a1b2c3d4e5f6.glb",
  "stl_url": "/api/v1/files/geometry/exports/spec_a1b2c3d4e5f6.stl",
  "step_url": "/api/v1/files/geometry/exports/spec_a1b2c3d4e5f6.step",
  "thumbnail_url": null,
  "meshy_video_url": null
}
```

### Error Responses

**400 Bad Request — Prompt too short**
```json
{
  "detail": "Prompt must be at least 10 characters"
}
```

**400 Bad Request — Missing user_id**
```json
{
  "detail": "user_id is required"
}
```

**401 Unauthorized — No token**
```json
{
  "detail": "Not authenticated"
}
```

**503 Service Unavailable — Prompt Runner failed**
```json
{
  "detail": "Prompt Runner execution failed: <error message>"
}
```

---

## cURL Examples

### 1. Basic 2BHK Request
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "user_id": "test_user",
    "prompt": "Generate 2BHK modern apartment"
  }'
```

### 2. Full 3BHK Request with Constraints
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "user_id": "architect_001",
    "prompt": "Design a 3BHK luxury apartment with 1200 sqft area",
    "city": "Bangalore",
    "style": "luxury",
    "project_id": "proj_2024_001",
    "constraints": {
      "budget": 12000000,
      "area_sqft": 1200
    }
  }'
```

### 3. Villa Request
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "user_id": "test_user",
    "prompt": "Design a villa with garden and garage",
    "city": "Pune",
    "style": "traditional"
  }'
```

---

## Python Example

```python
import requests

# 1. Get auth token
login_response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={"username": "admin", "password": "your_password"}
)
token = login_response.json()["access_token"]

# 2. Generate design
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload = {
    "user_id": "test_user",
    "prompt": "Generate 2BHK modern apartment in Mumbai",
    "city": "Mumbai",
    "style": "modern",
    "constraints": {
        "budget": 7000000,
        "area_sqft": 850
    }
}

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    headers=headers,
    json=payload
)

if response.status_code == 201:
    result = response.json()
    print(f"✅ Design generated: {result['spec_id']}")
    print(f"   Rooms: {len(result['spec_json']['rooms'])}")
    print(f"   Cost: ₹{result['estimated_cost']:,.0f}")
    print(f"   GLB: {result['glb_url']}")
    print(f"   Hash: {result['spec_json']['metadata']['deterministic_hash']}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.json())
```

---

## Validation Rules

### Prompt Validation
- Minimum length: 10 characters
- Maximum length: unlimited (tested up to 2000 words)
- Supports Unicode (Hindi, etc.)
- HTML/SQL injection safe (sanitized)

### BHK Detection
- Patterns: `1BHK`, `2BHK`, `3BHK`, `4BHK`, `5BHK`, `VILLA`, `PENTHOUSE`
- Confidence threshold: 0.8
- If no BHK detected: falls back to generic "house" type

### Stories Cap
- Maximum: 10 stories (prevents memory exhaustion)
- Input `"999 storey"` → capped to 10

### Budget
- Accepted formats: `"50 lakh"`, `"1.5 crore"`, `"Rs 5000000"`
- If provided: estimated_cost = 95% of budget
- If not provided: calculated from area × city rate

---

## Determinism Guarantee

**Same input → Same output hash**

Test:
```bash
# Run twice with identical payload
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "prompt": "Generate 2BHK"}' \
  | jq '.spec_json.metadata.deterministic_hash'

# Output: "5409aa2f640c18b8" (same every time)
```

---

## Download Generated Files

### GLB (3D Model)
```bash
curl -O http://localhost:8000/api/v1/files/geometry/spec_<id>.glb
```

### STL (CAD Export)
```bash
curl -O http://localhost:8000/api/v1/files/geometry/exports/spec_<id>.stl
```

### STEP (CAD Export)
```bash
curl -O http://localhost:8000/api/v1/files/geometry/exports/spec_<id>.step
```

---

## Troubleshooting

### Issue: "Not authenticated"
**Solution:** Get a fresh token via `/api/v1/auth/login`

### Issue: "Prompt must be at least 10 characters"
**Solution:** Expand prompt to minimum 10 chars

### Issue: "Prompt Runner execution failed"
**Solution:** Check server logs for platform_adapter errors

### Issue: Empty rooms list
**Solution:** Ensure BHK keyword is in prompt (e.g. "2BHK", "villa", "penthouse")

### Issue: Wrong city/style applied
**Solution:** Explicitly set `city` and `style` fields in request body

---

## Performance Benchmarks

| BHK Type | Rooms | Stories | Vertices | GLB Size | Generation Time |
|---|---|---|---|---|---|
| 1BHK | 4 | 1 | 96 | 3,240 bytes | ~800ms |
| 2BHK | 6 | 1 | 144 | 4,536 bytes | ~1,000ms |
| 3BHK | 9 | 1 | 216 | 6,480 bytes | ~1,200ms |
| VILLA | 16 | 2 | 768 | 21,388 bytes | ~2,500ms |
| PENTHOUSE | 13 | 1 | 312 | 9,072 bytes | ~1,800ms |

---

**For more details, see:**
- `FINAL_SYSTEM_STATE.md` — System guarantees
- `SEMANTIC_VALIDATION.md` — BHK detection rules
- `GEOMETRY_VALIDATION.md` — GLB output rules
