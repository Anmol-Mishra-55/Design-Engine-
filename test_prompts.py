"""
Step 12 — Test Prompts
======================
Runs "Generate 1BHK", "Generate 2BHK", "Generate 3BHK" through the
canonical pipeline and checks:
  1. Correct rooms (matches bhk_definitions.json)
  2. Valid GLB geometry (magic bytes, vertex/face counts)
  3. Determinism (same hash on two runs)

Run from repo root:
    cd backend
    python ../test_prompts.py
"""

import hashlib
import json
import struct
import sys
from pathlib import Path

# ── path setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from app.design_semantics.semantic_detector import extract_semantics
from app.geometry_generator_real import generate_real_glb

# ── expected rooms from bhk_definitions.json ─────────────────────────────────
BHK_DEF_PATH = APP / "design_semantics" / "bhk_definitions.json"
with open(BHK_DEF_PATH, encoding="utf-8") as f:
    BHK_DEFS = json.load(f)

PROMPTS = [
    ("Generate 1BHK", "1BHK"),
    ("Generate 2BHK", "2BHK"),
    ("Generate 3BHK", "3BHK"),
]

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"


# ── helpers ───────────────────────────────────────────────────────────────────

def build_spec(prompt: str) -> dict:
    """Run semantic detection and build a minimal spec_json."""
    sem = extract_semantics(prompt)
    bhk_def = sem.bhk_definition or {}
    dims = bhk_def.get("dimensions", {})
    return {
        "type":           sem.bhk_key,
        "rooms":          bhk_def.get("rooms", []),
        "room_dimensions": bhk_def.get("room_dimensions", {}),
        "dimensions": {
            "width":  dims.get("width_m",  10.0),
            "length": dims.get("length_m", 10.0),
            "height": dims.get("height_m",  2.8),
        },
        "stories": bhk_def.get("stories", 1),
    }


def glb_sha256(glb: bytes) -> str:
    return hashlib.sha256(glb).hexdigest()[:16]


def validate_glb(glb: bytes, rooms: list, stories: int) -> list[str]:
    """Return list of failure messages (empty = all good)."""
    errors = []

    # magic
    if glb[:4] != b"glTF":
        errors.append(f"Bad GLB magic: {glb[:4]!r}")
        return errors  # can't parse further

    # version
    version = struct.unpack_from("<I", glb, 4)[0]
    if version != 2:
        errors.append(f"GLB version {version} != 2")

    # JSON chunk
    json_len  = struct.unpack_from("<I", glb, 12)[0]
    json_type = glb[16:20]
    if json_type != b"JSON":
        errors.append(f"Chunk 0 type {json_type!r} != JSON")
        return errors

    gltf = json.loads(glb[20 : 20 + json_len])

    # accessor counts
    accessors = gltf.get("accessors", [])
    if len(accessors) < 3:
        errors.append(f"Expected >=3 accessors, got {len(accessors)}")
        return errors

    n_verts   = accessors[0]["count"]
    n_normals = accessors[1]["count"]
    n_indices = accessors[2]["count"]

    expected_verts = len(rooms) * stories * 24
    expected_faces = len(rooms) * stories * 12
    expected_idx   = expected_faces * 3

    if n_verts != expected_verts:
        errors.append(f"Vertex count {n_verts} != expected {expected_verts} ({len(rooms)} rooms × {stories} stories × 24)")
    if n_normals != n_verts:
        errors.append(f"Normal count {n_normals} != vertex count {n_verts}")
    if n_indices != expected_idx:
        errors.append(f"Index count {n_indices} != expected {expected_idx}")

    return errors


# ── main test loop ────────────────────────────────────────────────────────────

def run_tests():
    total = passed = 0
    results = []

    for prompt, bhk_key in PROMPTS:
        print(f"\n{'='*60}")
        print(f"Prompt : \"{prompt}\"")
        print(f"BHK    : {bhk_key}")

        expected_rooms = BHK_DEFS[bhk_key]["rooms"]
        stories        = BHK_DEFS[bhk_key]["stories"]

        # ── CHECK 1: Semantic detection ───────────────────────────────────────
        total += 1
        sem = extract_semantics(prompt)
        if sem.bhk_key == bhk_key and sem.bhk_confidence >= 0.8:
            print(f"  [1] Semantic detection  : {PASS}  bhk={sem.bhk_key} conf={sem.bhk_confidence:.2f}")
            passed += 1
        else:
            print(f"  [1] Semantic detection  : {FAIL}  got bhk={sem.bhk_key} conf={sem.bhk_confidence:.2f}")

        # ── CHECK 2: Correct rooms ────────────────────────────────────────────
        total += 1
        spec = build_spec(prompt)
        actual_rooms = spec["rooms"]
        missing = set(expected_rooms) - set(actual_rooms)
        extra   = set(actual_rooms)  - set(expected_rooms)
        if not missing and not extra:
            print(f"  [2] Rooms               : {PASS}  {actual_rooms}")
            passed += 1
        else:
            print(f"  [2] Rooms               : {FAIL}")
            if missing: print(f"       missing : {sorted(missing)}")
            if extra:   print(f"       extra   : {sorted(extra)}")

        # ── CHECK 3: Valid GLB geometry ───────────────────────────────────────
        total += 1
        glb1 = generate_real_glb(spec)
        geo_errors = validate_glb(glb1, actual_rooms, stories)
        if not geo_errors:
            print(f"  [3] GLB geometry        : {PASS}  {len(glb1):,} bytes  "
                  f"verts={len(actual_rooms)*stories*24}  faces={len(actual_rooms)*stories*12}")
            passed += 1
        else:
            print(f"  [3] GLB geometry        : {FAIL}")
            for e in geo_errors:
                print(f"       {e}")

        # ── CHECK 4: Determinism ──────────────────────────────────────────────
        total += 1
        glb2 = generate_real_glb(spec)
        h1, h2 = glb_sha256(glb1), glb_sha256(glb2)
        if h1 == h2:
            print(f"  [4] Determinism         : {PASS}  sha256[:16]={h1}")
            passed += 1
        else:
            print(f"  [4] Determinism         : {FAIL}  run1={h1}  run2={h2}")

        results.append((prompt, bhk_key, actual_rooms, len(glb1), h1))

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"RESULT: {passed}/{total} checks passed")
    print(f"{'='*60}\n")

    print(f"{'Prompt':<20} {'BHK':<10} {'Rooms':>5} {'GLB bytes':>10} {'Hash':<16}")
    print("-" * 65)
    for prompt, bhk, rooms, size, h in results:
        print(f"{prompt:<20} {bhk:<10} {len(rooms):>5} {size:>10,} {h:<16}")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
