"""
Multi-domain endpoint tester for /api/v1/core/generate
Tests all 5 domains: architecture, vehicles, objects, gameplay, environment
"""
import json
import sys
import time
import urllib.request

BASE = "http://localhost:8000/api/v1/core/generate"
LOGIN_URL = "http://localhost:8000/api/v1/auth/login"


def get_token():
    data = b"username=admin&password=bhiv2024"
    req = urllib.request.Request(
        LOGIN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())["access_token"]


TESTS = [
    {
        "name": "ARCHITECTURE — 3BHK Apartment (Mumbai)",
        "body": {
            "user_id": "user_arch_01",
            "prompt": "Design a modern 3BHK apartment with master bedroom hall and kitchen",
            "city": "Mumbai",
            "style": "modern",
            "project_id": "proj_arch_001",
            "context": {"domain": "architecture", "subtype": "3BHK", "generation_mode": "mesh"},
        },
    },
    {
        "name": "VEHICLES — Cargo Drone (Pune)",
        "body": {
            "user_id": "user_veh_01",
            "prompt": "Design a cargo delivery drone with rotor assembly and landing gear",
            "city": "Pune",
            "style": "industrial",
            "project_id": "proj_veh_001",
            "context": {"domain": "vehicles", "subtype": "drone", "generation_mode": "mesh"},
        },
    },
    {
        "name": "OBJECTS — Crates and Barrels (Ahmedabad)",
        "body": {
            "user_id": "user_obj_01",
            "prompt": "Create wooden crates and metal barrels for warehouse storage",
            "city": "Ahmedabad",
            "style": "industrial",
            "project_id": "proj_obj_001",
            "context": {"domain": "objects", "subtype": "crate", "generation_mode": "mesh"},
        },
    },
    {
        "name": "GAMEPLAY — Runner Obstacles (Nashik)",
        "body": {
            "user_id": "user_game_01",
            "prompt": "Create a set of runner obstacles with collision boxes and material tags",
            "city": "Nashik",
            "style": "minimal",
            "project_id": "proj_game_001",
            "context": {"domain": "gameplay", "subtype": "obstacle", "generation_mode": "mesh"},
            "constraints": {"spatial_scale": "micro", "units": "game_units"},
        },
    },
    {
        "name": "ENVIRONMENT — Forest Biome (Pune)",
        "body": {
            "user_id": "user_env_01",
            "prompt": "Generate a dense forest environment biome with canopy and undergrowth zones",
            "city": "Pune",
            "style": "realistic",
            "project_id": "proj_env_001",
            "context": {"domain": "environment", "subtype": "forest", "generation_mode": "mesh"},
        },
    },
]


def run_test(test, token):
    data = json.dumps(test["body"]).encode("utf-8")
    req = urllib.request.Request(
        BASE,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as resp:
        elapsed = int((time.time() - t0) * 1000)
        r = json.loads(resp.read())
        return r, elapsed


def summarize(name, r, elapsed):
    sj = r.get("spec_json", {})
    meta = sj.get("metadata", {})
    status = resp_status(r)
    print(f"\n{'='*60}")
    print(f"  {status} {name}")
    print(f"{'='*60}")
    print(f"  spec_id       : {r.get('spec_id')}")
    print(f"  domain        : {sj.get('domain')}")
    print(f"  design_type   : {sj.get('design_type')}")
    print(f"  rooms         : {sj.get('rooms')}")
    print(f"  dimensions    : {sj.get('dimensions')}")
    print(f"  glb_provider  : {meta.get('glb_provider')}")
    print(f"  glb_url       : {r.get('glb_url', '')}")
    print(f"  stl_url       : {r.get('stl_url', '')}")
    print(f"  step_url      : {r.get('step_url', '')}")
    print(f"  thumbnail_url : {r.get('thumbnail_url', '')}")
    print(f"  estimated_cost: {r.get('estimated_cost')} INR")
    print(f"  api_time_ms   : {r.get('generation_time_ms')} (wall: {elapsed}ms)")
    print(f"  canonical_flow: {meta.get('canonical_flow')}")
    export = r.get("export_urls", {})
    if export:
        print(f"  export_urls   :")
        for k, v in export.items():
            print(f"    {k:8s}: {v}")


def resp_status(r):
    if r.get("spec_id") and r.get("glb_url"):
        return "[PASS]"
    return "[WARN]"


if __name__ == "__main__":
    print("Authenticating...")
    try:
        token = get_token()
        print(f"Token obtained: {token[:40]}...")
    except Exception as e:
        print(f"[FAIL] Login failed: {e}")
        sys.exit(1)

    passed = failed = 0
    for test in TESTS:
        print(f"\nRunning: {test['name']} ...")
        try:
            result, elapsed = run_test(test, token)
            summarize(test["name"], result, elapsed)
            if result.get("spec_id") and result.get("glb_url"):
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[FAIL] {test['name']}")
            print(f"  Error: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} PASSED / {failed} FAILED / {len(TESTS)} TOTAL")
    print(f"{'='*60}\n")
