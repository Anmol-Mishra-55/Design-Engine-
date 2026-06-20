import sys

sys.path.insert(0, ".")
from app.design_semantics import extract_semantics
from app.geometry_generator_real import generate_real_glb
from app.prompt_runner_adapter import (
    _build_architecture_spec,
    _build_non_architecture_spec,
    _detect_domain_and_subtype,
    _extract_dimensions,
)

tests = [
    "Generate a delivery drone with cargo bay",
    "Generate a house",
    "Design a 2BHK apartment",
    "Create a forest environment",
    "Make a checkpoint marker",
    "Design a 3BHK villa in Pune",
    "Create a cargo ship",
    "Build a desert biome",
]

all_ok = True
for prompt in tests:
    sem = extract_semantics(prompt)
    inst = {"module": "general_processor", "intent": "process_request"}
    domain, subtype, sem2 = _detect_domain_and_subtype(prompt, inst)
    dims = _extract_dimensions({}, prompt, {})
    if domain == "architecture":
        spec = _build_architecture_spec(subtype, sem2, dims, "modern", 1, "Mumbai")
    else:
        spec = _build_non_architecture_spec(domain, subtype, dims, prompt)
    try:
        glb = generate_real_glb(spec)
        print(f"PASS  GLB={len(glb):8d}b  [{domain:15s}/{subtype:15s}]  {prompt[:40]}")
    except Exception as e:
        all_ok = False
        print(f"FAIL  [{domain:15s}/{subtype:15s}]  {prompt[:40]}  => {e}")

print()
print("ALL PASS" if all_ok else "SOME FAILED")
