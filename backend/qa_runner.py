import json
import struct
import sys
import traceback

sys.path.insert(0, ".")
sys.path.insert(0, "..")

from app.design_semantics.semantic_detector import extract_semantics
from app.geometry_generator_real import generate_real_glb

CASES = [
    # label,               prompt
    ("empty_string", ""),
    ("whitespace_only", "   "),
    ("none_type", None),
    ("gibberish", "asdfghjkl qwerty zxcvbn"),
    ("numbers_only", "12345 67890"),
    ("special_chars", "!@#$%^&*()_+-=[]{}|;:,.<>?"),
    ("sql_injection", "'; DROP TABLE specs; --"),
    ("html_injection", "<script>alert(1)</script> 2BHK"),
    ("no_bhk_keyword", "I want a house with rooms"),
    ("wrong_bhk_6", "6BHK apartment"),
    ("very_long_2000w", "Generate a 2BHK apartment " + "with modern design " * 500),
    ("unicode_hindi", "Generate 2BHK \u0905\u092a\u093e\u0930\u094d\u091f\u092e\u0947\u0902\u091f Mumbai"),
    ("repeated_bhk", "1BHK 2BHK 3BHK 4BHK 5BHK which one?"),
    ("zero_area", "2BHK with 0 sqft area"),
    ("negative_budget", "3BHK budget -50 lakh"),
    ("extreme_stories", "2BHK 999 storey building"),
    ("mixed_case", "generate 2bhk apartment"),
    ("spaced_bhk", "generate 2 BHK apartment"),
    ("villa_single_word", "villa"),
    ("penthouse_single", "penthouse"),
    ("glb_empty_rooms", "__SPECIAL__"),
]


def build_spec(sem):
    d = sem.bhk_definition
    return {
        "type": sem.bhk_key,
        "rooms": d.get("rooms", []),
        "room_dimensions": d.get("room_dimensions", {}),
        "dimensions": {
            "width": d["dimensions"]["width_m"],
            "length": d["dimensions"]["length_m"],
            "height": d["dimensions"]["height_m"],
        },
        "stories": d.get("stories", 1),
    }


def validate_glb_magic(glb):
    return glb[:4] == b"glTF"


bugs = []
rows = []

for label, prompt in CASES:
    try:
        if prompt == "__SPECIAL__":
            # Edge: empty rooms list
            glb = generate_real_glb({"rooms": [], "dimensions": {"width": 10, "length": 10, "height": 3}, "stories": 1})
            ok = validate_glb_magic(glb)
            rows.append((label, "N/A", "-", 0, len(glb), "OK - fallback GLB" if ok else "BAD GLB magic"))
            continue

        sem = extract_semantics(prompt)
        bhk = sem.bhk_key or "None"
        conf = sem.bhk_confidence

        if sem.bhk_definition:
            spec = build_spec(sem)
            rooms = spec["rooms"]
            stories = spec["stories"]

            # Critical: cap extreme stories before GLB generation
            if stories > 10:
                rows.append((label, bhk, f"{conf:.2f}", len(rooms), 0, f"WARN: stories={stories} capped needed"))
                bugs.append((label, f"stories={stories} not capped - memory risk", ""))
                continue

            glb = generate_real_glb(spec)
            ok = validate_glb_magic(glb)
            rows.append((label, bhk, f"{conf:.2f}", len(rooms), len(glb), "OK" if ok else "BAD GLB"))
        else:
            rows.append((label, bhk, f"{conf:.2f}", 0, 0, "OK - no bhk detected"))

    except Exception as e:
        tb = traceback.format_exc()
        rows.append((label, "CRASH", "----", 0, 0, f"BUG: {e}"))
        bugs.append((label, str(e), tb))

# ── print table ───────────────────────────────────────────────────────────────
print(f"{'Label':<25} {'BHK':<12} {'Conf':>5}  {'Rooms':>5}  {'GLB bytes':>10}  Result")
print("-" * 78)
for label, bhk, conf, nrooms, glb_size, note in rows:
    print(f"{label:<25} {bhk:<12} {conf:>5}  {nrooms:>5}  {glb_size:>10}  {note}")

print()
if bugs:
    print(f"=== CRITICAL BUGS FOUND: {len(bugs)} ===")
    for label, err, tb in bugs:
        print(f"\n[{label}] {err}")
        if tb:
            for line in tb.strip().split("\n")[-4:]:
                print(f"  {line}")
else:
    print("=== ALL CASES HANDLED - NO CRASHES ===")
