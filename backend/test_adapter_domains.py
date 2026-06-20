import sys

sys.path.insert(0, "app")
from app.design_semantics import extract_semantics
from app.prompt_runner_adapter import (
    _build_architecture_spec,
    _build_non_architecture_spec,
    _detect_domain_and_subtype,
    _extract_dimensions,
)

tests = [
    ("Generate a delivery drone with cargo bay", "vehicles", "drone"),
    ("Generate a house", "architecture", "house"),
    ("Design a 2BHK modern apartment in Mumbai", "architecture", "2BHK"),
    ("Create a forest environment with dense trees", "environment", "forest"),
    ("Make a spawn point for players", "gameplay", "spawn_point"),
    ("Design a cargo ship hull", "vehicles", "ship"),
    ("Build a warehouse for storage", "architecture", "warehouse"),
    ("Create a collectible coin pickup", "gameplay", "collectible"),
    ("Design a city block with roads", "environment", "city_block"),
    ("Generate a mars rover chassis", "vehicles", "rover"),
    ("Design a 3BHK villa in Pune", "architecture", "3BHK"),
    ("Create a spacecraft with docking port", "vehicles", "spacecraft"),
    ("Generate a desert biome with dunes", "environment", "desert"),
]

all_ok = True
for prompt, exp_domain, exp_subtype in tests:
    sem = extract_semantics(prompt)
    inst = {"module": "general_processor", "intent": "process_request"}
    domain, subtype, sem2 = _detect_domain_and_subtype(prompt, inst)
    dims = _extract_dimensions({}, prompt, {})
    if domain == "architecture":
        spec = _build_architecture_spec(subtype, sem2, dims, "modern", 1, "Mumbai")
    else:
        spec = _build_non_architecture_spec(domain, subtype, dims, prompt)
    rooms = spec.get("rooms", [])
    rd = spec.get("room_dimensions", {})
    ok = len(rooms) > 0 and len(rd) > 0 and domain == exp_domain
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_ok = False
    print(
        f"{status}  rooms={len(rooms):2d}  domain={domain:15s}({exp_domain:15s})  subtype={subtype:15s}  prompt={prompt[:40]}"
    )

print()
print("ALL PASS" if all_ok else "SOME TESTS FAILED")
