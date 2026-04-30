"""
Generate canonical GLB files for 1BHK, 2BHK, 3BHK deliverables.
Produces valid GLB 2.0 binaries with room-based geometry.
"""
import json
import struct
import hashlib
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "backend", "data", "geometry_outputs")
os.makedirs(OUT_DIR, exist_ok=True)

SPECS = {
    "1bhk": {
        "rooms": ["bedroom", "hall", "kitchen", "bathroom"],
        "dims": {
            "bedroom":  (3.0, 3.5, 2.7),
            "hall":     (3.5, 4.0, 2.7),
            "kitchen":  (2.5, 3.0, 2.7),
            "bathroom": (1.5, 2.0, 2.4),
        },
        "stories": 1,
    },
    "2bhk": {
        "rooms": ["master_bedroom", "bedroom_2", "hall", "kitchen", "master_bathroom", "common_bathroom"],
        "dims": {
            "master_bedroom":  (3.5, 4.0, 2.7),
            "bedroom_2":       (3.0, 3.5, 2.7),
            "hall":            (4.0, 5.0, 2.7),
            "kitchen":         (2.5, 3.5, 2.7),
            "master_bathroom": (1.8, 2.2, 2.4),
            "common_bathroom": (1.5, 2.0, 2.4),
        },
        "stories": 1,
    },
    "3bhk": {
        "rooms": ["master_bedroom", "bedroom_2", "bedroom_3", "hall", "dining",
                  "kitchen", "master_bathroom", "bathroom_2", "common_bathroom"],
        "dims": {
            "master_bedroom":  (4.0, 4.5, 2.8),
            "bedroom_2":       (3.5, 4.0, 2.7),
            "bedroom_3":       (3.0, 3.5, 2.7),
            "hall":            (4.5, 5.5, 2.8),
            "dining":          (3.0, 4.0, 2.7),
            "kitchen":         (3.0, 4.0, 2.7),
            "master_bathroom": (2.0, 2.5, 2.4),
            "bathroom_2":      (1.8, 2.2, 2.4),
            "common_bathroom": (1.5, 2.0, 2.4),
        },
        "stories": 1,
    },
}


def room_mesh(w, l, h, x_off, y_off, z_off):
    """Return (vertices, normals, indices) for a single room box (6 quads)."""
    x0, x1 = x_off, x_off + w
    y0, y1 = y_off, y_off + l
    z0, z1 = z_off, z_off + h

    verts = [
        # floor (z0)
        x0,y0,z0, x1,y0,z0, x1,y1,z0, x0,y1,z0,
        # ceiling (z1)
        x0,y0,z1, x1,y0,z1, x1,y1,z1, x0,y1,z1,
        # south wall (y0)
        x0,y0,z0, x1,y0,z0, x1,y0,z1, x0,y0,z1,
        # north wall (y1)
        x0,y1,z0, x1,y1,z0, x1,y1,z1, x0,y1,z1,
        # west wall (x0)
        x0,y0,z0, x0,y1,z0, x0,y1,z1, x0,y0,z1,
        # east wall (x1)
        x1,y0,z0, x1,y1,z0, x1,y1,z1, x1,y0,z1,
    ]
    norms = (
        [0,0,-1]*4 + [0,0,1]*4 +
        [0,-1,0]*4 + [0,1,0]*4 +
        [-1,0,0]*4 + [1,0,0]*4
    )
    base = 0
    idxs = []
    for _ in range(6):
        b = base
        idxs += [b,b+1,b+2, b,b+2,b+3]
        base += 4
    return verts, norms, idxs


def build_glb(spec_key):
    spec = SPECS[spec_key]
    rooms = spec["rooms"]
    dims  = spec["dims"]
    stories = spec["stories"]

    all_verts, all_norms, all_idxs = [], [], []
    x_cursor = 0.0

    for story in range(stories):
        z_off = story * 3.15
        y_cursor = 0.0
        for room in rooms:
            w, l, h = dims[room]
            v, n, i = room_mesh(w, l, h, x_cursor, y_cursor, z_off)
            base = len(all_verts) // 3
            all_verts += v
            all_norms += n
            all_idxs  += [idx + base for idx in i]
            y_cursor += l + 0.1
        x_cursor += 5.0

    # Pack binary buffer
    vert_bytes  = struct.pack(f"{len(all_verts)}f", *all_verts)
    norm_bytes  = struct.pack(f"{len(all_norms)}f", *all_norms)
    idx_bytes   = struct.pack(f"{len(all_idxs)}H", *all_idxs)
    if len(idx_bytes) % 4:
        idx_bytes += b"\x00" * (4 - len(idx_bytes) % 4)

    v_off, v_len = 0, len(vert_bytes)
    n_off, n_len = v_len, len(norm_bytes)
    i_off, i_len = v_len + n_len, len(idx_bytes)
    buf_len = v_len + n_len + len(idx_bytes)

    n_verts = len(all_verts) // 3
    n_faces = len(all_idxs) // 3

    def minmax(lst, stride):
        pts = [lst[i:i+stride] for i in range(0, len(lst), stride)]
        mn = [min(p[k] for p in pts) for k in range(stride)]
        mx = [max(p[k] for p in pts) for k in range(stride)]
        return mn, mx

    vmin, vmax = minmax(all_verts, 3)

    gltf = {
        "asset": {"version": "2.0", "generator": "BHIV-DesignEngine"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": spec_key.upper()}],
        "meshes": [{
            "name": spec_key.upper(),
            "primitives": [{
                "attributes": {"POSITION": 0, "NORMAL": 1},
                "indices": 2,
                "mode": 4
            }]
        }],
        "accessors": [
            {"bufferView": 0, "byteOffset": 0, "componentType": 5126,
             "count": n_verts, "type": "VEC3",
             "min": vmin, "max": vmax},
            {"bufferView": 1, "byteOffset": 0, "componentType": 5126,
             "count": n_verts, "type": "VEC3"},
            {"bufferView": 2, "byteOffset": 0, "componentType": 5123,
             "count": n_faces * 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": v_off, "byteLength": v_len, "target": 34962},
            {"buffer": 0, "byteOffset": n_off, "byteLength": n_len, "target": 34962},
            {"buffer": 0, "byteOffset": i_off, "byteLength": i_len, "target": 34963},
        ],
        "buffers": [{"byteLength": buf_len}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    if len(json_bytes) % 4:
        json_bytes += b" " * (4 - len(json_bytes) % 4)

    bin_chunk = vert_bytes + norm_bytes + idx_bytes

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    glb = (
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<I", len(json_bytes)) + b"JSON" + json_bytes
        + struct.pack("<I", len(bin_chunk))  + b"BIN\x00" + bin_chunk
    )
    return glb


for key in SPECS:
    glb = build_glb(key)
    path = os.path.join(OUT_DIR, f"spec_{key}_canonical.glb")
    with open(path, "wb") as f:
        f.write(glb)
    h = hashlib.md5(glb).hexdigest()[:16]
    print(f"{key.upper()}: {len(glb):,} bytes | hash={h} | verts={len(SPECS[key]['rooms'])*SPECS[key]['stories']*24} | file={path}")

print("Done.")
