import os
import sys

os.environ.setdefault("MONGODB_URL", "mongodb://localhost")
os.environ.setdefault("JWT_SECRET_KEY", "x")
os.environ.setdefault("BUCKET_URL", "https://bhiv-bucket.onrender.com")
sys.path.insert(0, ".")

from app.geometry_generator_real import _compute_doors, _compute_shared_walls, _layout_rooms, generate_real_glb

rooms = [
    "master_bedroom",
    "bedroom_2",
    "bedroom_3",
    "hall",
    "dining",
    "kitchen",
    "master_bathroom",
    "bathroom_2",
    "common_bathroom",
    "balcony_1",
    "balcony_2",
]
rdims = {
    "master_bedroom": {"width_m": 4.0, "length_m": 4.5},
    "bedroom_2": {"width_m": 3.5, "length_m": 4.0},
    "bedroom_3": {"width_m": 3.0, "length_m": 3.5},
    "hall": {"width_m": 4.5, "length_m": 5.5},
    "dining": {"width_m": 3.0, "length_m": 4.0},
    "kitchen": {"width_m": 3.0, "length_m": 4.0},
    "master_bathroom": {"width_m": 2.0, "length_m": 2.5},
    "bathroom_2": {"width_m": 1.8, "length_m": 2.2},
    "common_bathroom": {"width_m": 1.5, "length_m": 2.0},
    "balcony_1": {"width_m": 1.5, "length_m": 4.0},
    "balcony_2": {"width_m": 1.2, "length_m": 3.0},
}
adjacency = {
    "master_bedroom": ["master_bathroom", "hall", "balcony_1"],
    "bedroom_2": ["bathroom_2", "hall"],
    "bedroom_3": ["common_bathroom", "hall"],
    "hall": ["dining", "master_bedroom", "bedroom_2", "bedroom_3", "balcony_2"],
    "dining": ["kitchen", "hall"],
    "kitchen": ["dining"],
}

layout = _layout_rooms(rooms, rdims, 11.0, 2.8)
shared = _compute_shared_walls(layout)
doors = _compute_doors(layout, adjacency)

print("Room layout + shared wall suppression:")
for i, (n, x, y, w, l, h) in enumerate(layout):
    sw = [k for k, v in shared[i].items() if v]
    dw = [k for k, v in doors[i].items() if v]
    print(f"  {n:20s}  x={x:5.2f} y={y:5.2f} w={w:.2f} l={l:.2f}" f"  suppress={sw}  doors={dw}")

spec = {
    "rooms": rooms,
    "dimensions": {"width": 11.0, "length": 10.5, "height": 2.8},
    "room_dimensions": rdims,
    "adjacency": adjacency,
    "stories": 1,
}
glb = generate_real_glb(spec)
with open("arch_3bhk_fixed.glb", "wb") as f:
    f.write(glb)
print(f"\nGLB written: {len(glb):,} bytes  valid={glb[:4] == b'glTF'}")
