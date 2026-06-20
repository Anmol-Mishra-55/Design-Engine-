import os
import sys

os.environ.setdefault("MONGODB_URL", "mongodb://localhost")
os.environ.setdefault("JWT_SECRET_KEY", "x")
os.environ.setdefault("BUCKET_URL", "https://bhiv-bucket.onrender.com")
sys.path.insert(0, ".")

from app.geometry_generator_real import generate_real_glb

DOMAINS = [
    {
        "name": "vehicles_drone",
        "spec": {
            "domain": "vehicles",
            "design_type": "drone",
            "rooms": ["frame", "rotor_assembly", "landing_gear"],
            "room_dimensions": {
                "frame": {"width_m": 1.0, "length_m": 1.0},
                "rotor_assembly": {"width_m": 1.0, "length_m": 0.3},
                "landing_gear": {"width_m": 1.0, "length_m": 0.2},
            },
            "adjacency": {
                "frame": ["rotor_assembly", "landing_gear"],
                "rotor_assembly": ["frame"],
                "landing_gear": ["frame"],
            },
            "dimensions": {"width": 1.0, "length": 1.5, "height": 0.5},
            "stories": 1,
        },
    },
    {
        "name": "vehicles_spacecraft",
        "spec": {
            "domain": "vehicles",
            "design_type": "spacecraft",
            "rooms": ["fuselage", "engine_bay", "docking_port"],
            "room_dimensions": {
                "fuselage": {"width_m": 5.0, "length_m": 12.0},
                "engine_bay": {"width_m": 5.0, "length_m": 4.0},
                "docking_port": {"width_m": 2.0, "length_m": 2.0},
            },
            "adjacency": {
                "fuselage": ["engine_bay", "docking_port"],
                "engine_bay": ["fuselage"],
                "docking_port": ["fuselage"],
            },
            "dimensions": {"width": 5.0, "length": 18.0, "height": 5.0},
            "stories": 1,
        },
    },
    {
        "name": "objects_crate",
        "spec": {
            "domain": "objects",
            "design_type": "crate",
            "rooms": ["body"],
            "room_dimensions": {"body": {"width_m": 1.0, "length_m": 1.0}},
            "adjacency": {},
            "dimensions": {"width": 1.0, "length": 1.0, "height": 1.0},
            "stories": 1,
        },
    },
    {
        "name": "objects_staircase",
        "spec": {
            "domain": "objects",
            "design_type": "staircase",
            "rooms": ["steps", "landing"],
            "room_dimensions": {
                "steps": {"width_m": 1.2, "length_m": 2.5},
                "landing": {"width_m": 1.2, "length_m": 0.5},
            },
            "adjacency": {"steps": ["landing"], "landing": ["steps"]},
            "dimensions": {"width": 1.2, "length": 3.0, "height": 3.0},
            "stories": 1,
        },
    },
    {
        "name": "gameplay_obstacle",
        "spec": {
            "domain": "gameplay",
            "design_type": "obstacle",
            "rooms": ["body"],
            "room_dimensions": {"body": {"width_m": 1.0, "length_m": 1.0}},
            "adjacency": {},
            "dimensions": {"width": 1.0, "length": 1.0, "height": 1.5},
            "stories": 1,
        },
    },
    {
        "name": "gameplay_checkpoint",
        "spec": {
            "domain": "gameplay",
            "design_type": "checkpoint",
            "rooms": ["trigger_zone", "arch_left", "arch_right"],
            "room_dimensions": {
                "trigger_zone": {"width_m": 3.0, "length_m": 0.3},
                "arch_left": {"width_m": 0.3, "length_m": 3.0},
                "arch_right": {"width_m": 0.3, "length_m": 3.0},
            },
            "adjacency": {
                "trigger_zone": ["arch_left", "arch_right"],
                "arch_left": ["trigger_zone"],
                "arch_right": ["trigger_zone"],
            },
            "dimensions": {"width": 3.6, "length": 3.0, "height": 3.0},
            "stories": 1,
        },
    },
    {
        "name": "environment_forest",
        "spec": {
            "domain": "environment",
            "design_type": "forest",
            "rooms": ["canopy_zone", "undergrowth_zone", "path"],
            "room_dimensions": {
                "canopy_zone": {"width_m": 20.0, "length_m": 50.0},
                "undergrowth_zone": {"width_m": 20.0, "length_m": 50.0},
                "path": {"width_m": 10.0, "length_m": 50.0},
            },
            "adjacency": {
                "canopy_zone": ["undergrowth_zone"],
                "undergrowth_zone": ["canopy_zone", "path"],
                "path": ["undergrowth_zone"],
            },
            "dimensions": {"width": 50.0, "length": 50.0, "height": 20.0},
            "stories": 1,
        },
    },
    {
        "name": "environment_city_block",
        "spec": {
            "domain": "environment",
            "design_type": "city_block",
            "rooms": ["road", "sidewalk", "building_shell"],
            "room_dimensions": {
                "road": {"width_m": 15.0, "length_m": 60.0},
                "sidewalk": {"width_m": 5.0, "length_m": 60.0},
                "building_shell": {"width_m": 20.0, "length_m": 60.0},
            },
            "adjacency": {
                "road": ["sidewalk"],
                "sidewalk": ["road", "building_shell"],
                "building_shell": ["sidewalk"],
            },
            "dimensions": {"width": 40.0, "length": 60.0, "height": 10.0},
            "stories": 1,
        },
    },
]

print(f"{'='*60}")
print(f"Generating {len(DOMAINS)} domain GLBs...")
print(f"{'='*60}\n")

for d in DOMAINS:
    try:
        glb = generate_real_glb(d["spec"])
        fname = f"{d['name']}.glb"
        with open(fname, "wb") as f:
            f.write(glb)
        print(f"[OK] {fname:35s}  {len(glb):>8,} bytes  valid={glb[:4]==b'glTF'}")
    except Exception as e:
        print(f"[FAIL] {d['name']:33s}  error: {e}")

print(f"\nAll files saved to: c:\\Users\\Anmol\\Desktop\\Backend\\backend\\")
