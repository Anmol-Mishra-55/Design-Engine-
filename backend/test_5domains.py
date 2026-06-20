import asyncio
import sys

sys.path.insert(0, "..")
sys.path.insert(0, ".")
from app.prompt_runner_adapter import PromptRunnerAdapterBridge

bridge = PromptRunnerAdapterBridge()

payloads = [
    (
        "1. Architecture - 3BHK Mumbai",
        "architecture",
        "3BHK",
        {
            "user_id": "user_arch_01",
            "prompt": "Design a 3BHK modern apartment in Mumbai with 1200 sqft",
            "city": "Mumbai",
            "style": "modern",
            "project_id": "proj_arch_001",
            "context": {
                "domain": "architecture",
                "subtype": "3BHK",
                "geometry_family": "apartment_layout",
                "generation_mode": "layout",
            },
            "constraints": {
                "forbidden_object_classes": ["rotor", "spawn_point"],
                "spatial_scale": "micro",
                "units": "meters",
            },
        },
    ),
    (
        "2. Objects - Wooden Crate (Pune)",
        "objects",
        "crate",
        {
            "user_id": "user_obj_01",
            "prompt": "Generate an industrial wooden crate with slats and metal handle",
            "city": "Pune",
            "style": "functional",
            "project_id": "proj_obj_001",
            "context": {
                "domain": "objects",
                "subtype": "crate",
                "geometry_family": "primitive_prop",
                "generation_mode": "mesh",
            },
            "constraints": {
                "forbidden_object_classes": ["room", "rotor", "engine"],
                "spatial_scale": "micro",
                "units": "meters",
            },
        },
    ),
    (
        "3. Vehicles - Quadcopter Drone (Ahmedabad)",
        "vehicles",
        "drone",
        {
            "user_id": "user_veh_01",
            "prompt": "Design a quadcopter cargo drone with rotors camera mount and landing gear",
            "city": "Ahmedabad",
            "style": "modern",
            "project_id": "proj_veh_001",
            "context": {
                "domain": "vehicles",
                "subtype": "drone",
                "geometry_family": "rotorcraft",
                "generation_mode": "mesh",
            },
            "constraints": {
                "forbidden_object_classes": ["room", "bedroom", "wheel", "hull"],
                "spatial_scale": "micro",
                "units": "meters",
            },
        },
    ),
    (
        "4. Gameplay - Obstacle Course (Nashik)",
        "gameplay",
        "obstacle",
        {
            "user_id": "user_game_01",
            "prompt": "Create runner obstacles with collision boxes and material tags",
            "city": "Nashik",
            "style": "minimal",
            "project_id": "proj_game_001",
            "context": {
                "domain": "gameplay",
                "subtype": "obstacle",
                "geometry_family": "gameplay_prop",
                "generation_mode": "mesh",
            },
            "constraints": {
                "forbidden_object_classes": ["room", "rotor", "wheel", "engine"],
                "spatial_scale": "micro",
                "units": "game_units",
            },
        },
    ),
    (
        "5. Environment - Industrial Zone (Bangalore)",
        "environment",
        "industrial_zone",
        {
            "user_id": "user_env_01",
            "prompt": "Generate an industrial zone with factory shell smokestacks pipelines and loading area",
            "city": "Bangalore",
            "style": "brutalist",
            "project_id": "proj_env_001",
            "context": {
                "domain": "environment",
                "subtype": "industrial_zone",
                "geometry_family": "industrial_zone",
                "generation_mode": "grouped_geometry",
            },
            "constraints": {
                "forbidden_object_classes": ["rotor", "spawn_point", "tree", "wave"],
                "spatial_scale": "large",
                "units": "meters",
            },
        },
    ),
]


async def run():
    passed = 0
    failed = 0
    for name, exp_domain, exp_subtype, payload in payloads:
        print("=" * 60)
        print("TEST: " + name)
        print("=" * 60)
        try:
            result = await bridge.run_from_platform(payload)
            spec = result.get("spec_json", {})
            got_domain = spec.get("domain")
            got_subtype = spec.get("design_type")
            got_rooms = spec.get("rooms", [])
            got_dims = spec.get("dimensions", {})
            got_style = spec.get("style")
            got_city = spec.get("city")
            print("  domain       : " + str(got_domain))
            print("  design_type  : " + str(got_subtype))
            print("  rooms        : " + str(got_rooms))
            print("  dimensions   : " + str(got_dims))
            print("  style        : " + str(got_style))
            print("  city         : " + str(got_city))
            ok = got_domain == exp_domain and got_subtype == exp_subtype
            if ok:
                print("  RESULT       : PASS")
                passed += 1
            else:
                print(
                    "  RESULT       : FAIL  expected domain="
                    + exp_domain
                    + " subtype="
                    + exp_subtype
                    + "  got domain="
                    + str(got_domain)
                    + " subtype="
                    + str(got_subtype)
                )
                failed += 1
        except Exception as e:
            print("  RESULT       : FAIL - " + str(e))
            failed += 1
        print("")

    print("=" * 60)
    print("SUMMARY: " + str(passed) + " PASSED  " + str(failed) + " FAILED")
    print("=" * 60)


asyncio.run(run())
