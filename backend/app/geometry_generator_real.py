"""
Room-Based Geometry Generator
==============================
Generates GLB from spec["rooms"] list.

Pipeline:
  spec["rooms"]  →  for room in rooms: create_room_mesh(room)
                 →  pack all meshes into a single GLB

Each room mesh = 4 walls + floor + ceiling (6 quads = 12 triangles).
Rooms are laid out in a grid derived from spec["room_dimensions"]
and spec["dimensions"] (total footprint).

No slabs. No dummy meshes. No automotive/electronics geometry.
"""

import json
import logging
import math
import struct
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Vertex = Tuple[float, float, float]
Face = List[int]


# ---------------------------------------------------------------------------
# GLB packing helpers
# ---------------------------------------------------------------------------


def _pack_glb(vertices: List[Vertex], faces: List[Face]) -> bytes:
    """Pack vertices + triangle faces into a valid GLB 2.0 binary."""
    if not vertices or not faces:
        raise ValueError("Cannot pack empty geometry")

    # ── normals ──────────────────────────────────────────────────────────────
    normals = _calculate_normals(vertices, faces)

    # ── flatten index list ───────────────────────────────────────────────────
    flat_indices: List[int] = []
    for face in faces:
        flat_indices.extend(face)

    n_verts = len(vertices)
    n_indices = len(flat_indices)

    # ── binary buffers ───────────────────────────────────────────────────────
    vert_buf = b"".join(struct.pack("<fff", *v) for v in vertices)
    normal_buf = b"".join(struct.pack("<fff", *n) for n in normals)
    idx_buf = b"".join(struct.pack("<H", i) for i in flat_indices)

    # Pad index buffer to 4-byte boundary
    idx_pad = (4 - len(idx_buf) % 4) % 4
    idx_buf += b"\x00" * idx_pad

    bin_data = vert_buf + normal_buf + idx_buf

    # ── byte offsets ─────────────────────────────────────────────────────────
    off_verts = 0
    off_normals = len(vert_buf)
    off_idx = len(vert_buf) + len(normal_buf)

    gltf = {
        "asset": {"version": "2.0", "generator": "BHIV-RoomGeometry"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [
            {
                "name": "rooms",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1},
                        "indices": 2,
                        "mode": 4,  # TRIANGLES
                    }
                ],
            }
        ],
        "accessors": [
            {  # 0 — positions
                "bufferView": 0,
                "componentType": 5126,
                "count": n_verts,
                "type": "VEC3",
            },
            {  # 1 — normals
                "bufferView": 1,
                "componentType": 5126,
                "count": n_verts,
                "type": "VEC3",
            },
            {  # 2 — indices
                "bufferView": 2,
                "componentType": 5123,
                "count": n_indices,
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": off_verts, "byteLength": len(vert_buf)},
            {"buffer": 0, "byteOffset": off_normals, "byteLength": len(normal_buf)},
            {"buffer": 0, "byteOffset": off_idx, "byteLength": len(idx_buf)},
        ],
        "buffers": [{"byteLength": len(bin_data)}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - len(json_bytes) % 4) % 4
    json_bytes += b" " * json_pad

    bin_pad = (4 - len(bin_data) % 4) % 4
    bin_data += b"\x00" * bin_pad

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_data)

    return (
        b"glTF"
        + struct.pack("<II", 2, total)
        + struct.pack("<I", len(json_bytes))
        + b"JSON"
        + json_bytes
        + struct.pack("<I", len(bin_data))
        + b"BIN\x00"
        + bin_data
    )


def _calculate_normals(vertices: List[Vertex], faces: List[Face]) -> List[Vertex]:
    """Per-vertex normals accumulated from face normals."""
    normals = [[0.0, 0.0, 0.0] for _ in vertices]

    for face in faces:
        if len(face) < 3:
            continue
        v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        for idx in face:
            normals[idx][0] += nx
            normals[idx][1] += ny
            normals[idx][2] += nz

    result: List[Vertex] = []
    for n in normals:
        mag = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        result.append((n[0] / mag, n[1] / mag, n[2] / mag) if mag > 0 else (0.0, 0.0, 1.0))
    return result


# ---------------------------------------------------------------------------
# Room mesh builder
# ---------------------------------------------------------------------------


def create_room_mesh(
    room_name: str,
    x: float,
    y: float,  # bottom-left corner in world space
    w: float,
    l: float,
    h: float,  # width (X), length (Y), height (Z)
    wall_thickness: float = 0.15,
) -> Tuple[List[Vertex], List[Face]]:
    """
    Build a single room mesh: floor + ceiling + 4 walls.

    Coordinate system:
      X → width  (east)
      Y → length (north)
      Z → height (up)

    Returns (vertices, faces) with faces as triangles.
    All indices are LOCAL (0-based) — caller must offset.
    """
    verts: List[Vertex] = []
    faces: List[Face] = []

    def _quad(a: Vertex, b: Vertex, c: Vertex, d: Vertex) -> None:
        """Add a quad (a,b,c,d) as two triangles."""
        base = len(verts)
        verts.extend([a, b, c, d])
        faces.append([base, base + 1, base + 2])
        faces.append([base, base + 2, base + 3])

    # ── Floor ────────────────────────────────────────────────────────────────
    _quad(
        (x, y, 0),
        (x + w, y, 0),
        (x + w, y + l, 0),
        (x, y + l, 0),
    )

    # ── Ceiling ──────────────────────────────────────────────────────────────
    _quad(
        (x, y + l, h),
        (x + w, y + l, h),
        (x + w, y, h),
        (x, y, h),
    )

    t = wall_thickness

    # ── South wall (y-face, facing inward = +Y normal) ───────────────────────
    _quad(
        (x, y, 0),
        (x, y, h),
        (x + w, y, h),
        (x + w, y, 0),
    )

    # ── North wall ───────────────────────────────────────────────────────────
    _quad(
        (x + w, y + l, 0),
        (x + w, y + l, h),
        (x, y + l, h),
        (x, y + l, 0),
    )

    # ── West wall ────────────────────────────────────────────────────────────
    _quad(
        (x, y + l, 0),
        (x, y + l, h),
        (x, y, h),
        (x, y, 0),
    )

    # ── East wall ────────────────────────────────────────────────────────────
    _quad(
        (x + w, y, 0),
        (x + w, y, h),
        (x + w, y + l, h),
        (x + w, y + l, 0),
    )

    logger.debug(
        "Room '%s' mesh: origin=(%.2f,%.2f) size=%.2fx%.2fx%.2f " "verts=%d faces=%d",
        room_name,
        x,
        y,
        w,
        l,
        h,
        len(verts),
        len(faces),
    )
    return verts, faces


# ---------------------------------------------------------------------------
# Room dimension resolver
# ---------------------------------------------------------------------------

# Default room dimensions (meters) when not in spec
_ROOM_DEFAULTS: Dict[str, Tuple[float, float, float]] = {
    "master_bedroom": (4.0, 4.5, 2.8),
    "bedroom": (3.5, 4.0, 2.7),
    "hall": (4.5, 5.5, 2.8),
    "kitchen": (3.0, 4.0, 2.7),
    "dining": (3.5, 4.0, 2.7),
    "bathroom": (2.0, 2.5, 2.4),
    "master_bathroom": (2.5, 3.0, 2.4),
    "common_bathroom": (1.8, 2.2, 2.4),
    "balcony": (1.5, 3.5, 2.4),
    "study": (3.0, 3.5, 2.7),
    "pooja_room": (2.0, 2.5, 2.7),
    "garage": (6.0, 6.0, 2.5),
    "terrace": (8.0, 10.0, 0.3),
    "home_theatre": (5.0, 6.0, 2.8),
    "jacuzzi_deck": (4.0, 5.0, 0.5),
    "garden": (6.0, 8.0, 0.1),
}


def _resolve_room_dims(
    room_name: str,
    spec_room_dimensions: Dict[str, Any],
    floor_height: float,
) -> Tuple[float, float, float]:
    """
    Resolve (width, length, height) for a room.
    Priority: spec room_dimensions > canonical defaults > generic fallback.
    """
    # Strip numeric suffix: "bedroom_2" → "bedroom"
    base = room_name.rstrip("_0123456789")
    # Also try without trailing digit: "bedroom_2" → "bedroom"
    parts = room_name.rsplit("_", 1)
    base_alt = parts[0] if len(parts) == 2 and parts[1].isdigit() else room_name

    # 1. From spec room_dimensions (keyed by exact name or base)
    for key in (room_name, base_alt, base):
        rd = spec_room_dimensions.get(key)
        if rd and isinstance(rd, dict):
            w = float(rd.get("width_m", rd.get("width", 0)) or 0)
            l = float(rd.get("length_m", rd.get("length", 0)) or 0)
            h = float(rd.get("height_m", rd.get("height", floor_height)) or floor_height)
            if w > 0 and l > 0:
                return w, l, h

    # 2. Canonical defaults
    for key in (room_name, base_alt, base):
        if key in _ROOM_DEFAULTS:
            w, l, h = _ROOM_DEFAULTS[key]
            return w, l, floor_height if floor_height != 2.7 else h

    # 3. Generic fallback
    return 3.5, 4.0, floor_height


# ---------------------------------------------------------------------------
# Layout engine — grid packing
# ---------------------------------------------------------------------------


def _layout_rooms(
    rooms: List[str],
    spec_room_dimensions: Dict[str, Any],
    total_width: float,
    floor_height: float,
    gap: float = 0.15,  # wall thickness between rooms
) -> List[Tuple[str, float, float, float, float, float]]:
    """
    Pack rooms into a grid layout within total_width.
    Returns list of (room_name, x, y, w, l, h).
    """
    layout: List[Tuple[str, float, float, float, float, float]] = []
    cursor_x = 0.0
    cursor_y = 0.0
    row_max_l = 0.0

    for room_name in rooms:
        w, l, h = _resolve_room_dims(room_name, spec_room_dimensions, floor_height)

        # Wrap to next row if room doesn't fit
        if cursor_x + w > total_width + 0.01 and cursor_x > 0:
            cursor_x = 0.0
            cursor_y += row_max_l + gap
            row_max_l = 0.0

        layout.append((room_name, cursor_x, cursor_y, w, l, h))
        cursor_x += w + gap
        row_max_l = max(row_max_l, l)

    return layout


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_real_glb(spec_json: Dict[str, Any]) -> bytes:
    """
    Generate a GLB from spec_json["rooms"].

    For every room in spec["rooms"]:
        create_room_mesh(room)  →  add to scene

    Falls back to a single bounding-box room if rooms list is empty.
    """
    rooms: List[str] = spec_json.get("rooms") or []
    dimensions = spec_json.get("dimensions") or {}
    room_dimensions = spec_json.get("room_dimensions") or {}
    stories = int(spec_json.get("stories") or 1)

    total_w = float(dimensions.get("width", 10.0) or 10.0)
    total_l = float(dimensions.get("length", 10.0) or 10.0)
    floor_h = float(dimensions.get("height", 2.8) or 2.8) / max(stories, 1)

    logger.info(
        "generate_real_glb: %d rooms, footprint=%.1fx%.1f, floor_h=%.1f, stories=%d",
        len(rooms),
        total_w,
        total_l,
        floor_h,
        stories,
    )

    # ── No rooms → hard fail, no silent fallback ─────────────────────────────
    if not rooms:
        raise ValueError("Geometry generation failed: spec has no rooms defined")

    # ── Layout rooms ─────────────────────────────────────────────────────────
    layout = _layout_rooms(rooms, room_dimensions, total_w, floor_h)

    # ── Build combined mesh ───────────────────────────────────────────────────
    all_verts: List[Vertex] = []
    all_faces: List[Face] = []

    for story in range(stories):
        z_offset = story * (floor_h + 0.15)  # 0.15 = floor slab thickness

        for room_name, rx, ry, rw, rl, rh in layout:
            room_verts, room_faces = create_room_mesh(
                room_name,
                x=rx,
                y=ry,
                w=rw,
                l=rl,
                h=rh,
            )

            # Apply story Z offset
            room_verts = [(vx, vy, vz + z_offset) for vx, vy, vz in room_verts]

            # Offset face indices to global vertex list
            base = len(all_verts)
            all_verts.extend(room_verts)
            all_faces.extend([f[0] + base, f[1] + base, f[2] + base] for f in room_faces)

    logger.info(
        "Geometry built: %d rooms x %d stories = %d verts, %d faces",
        len(rooms),
        stories,
        len(all_verts),
        len(all_faces),
    )

    return _pack_glb(all_verts, all_faces)
