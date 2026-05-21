"""
Room-Based Geometry Generator — Phase 2
=========================================
Each room = enclosed volume (floor + ceiling + 4 thick walls).
Walls have real thickness (WALL_T = 0.2 m).
Adjacent rooms share a wall with exactly one door gap.
Rooms are positioned in a grid layout with wall-thickness separation.

Rules enforced:
  - Bedroom ≠ Hall ≠ Kitchen (different dimensions, visually separable)
  - Rooms positioned by row-based layout with GAP = WALL_T between them
  - Adjacency from spec_json["adjacency"] drives door placement
  - No dummy mesh — raises ValueError if rooms list is empty

Pipeline:
  spec["rooms"] + spec["adjacency"]
      → _layout_rooms()        — assign (x, y, w, l, h) per room
      → _compute_doors()       — door flags from adjacency + spatial proximity
      → build_room_mesh()      — floor + ceiling + 4 thick walls per room
      → pack_glb_multi_mesh()  — one GLB node per room
"""

import json
import logging
import math
import struct
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
WALL_T = 0.25  # wall thickness in metres (visible at normal scale)
DOOR_W = 0.9  # door opening width in metres
DOOR_H = 2.1  # door opening height in metres
GAP = WALL_T  # gap between adjacent room origins = one shared wall thickness

Vertex = Tuple[float, float, float]
Triangle = Tuple[int, int, int]


# ── Room dimension defaults (w, l, h) in metres ──────────────────────────────
_ROOM_DEFAULTS: Dict[str, Tuple[float, float, float]] = {
    "master_bedroom": (4.2, 4.8, 2.8),
    "bedroom": (3.6, 4.2, 2.7),
    "bedroom_2": (3.2, 3.8, 2.7),
    "bedroom_3": (3.0, 3.5, 2.7),
    "bedroom_4": (3.0, 3.5, 2.7),
    "bedroom_5": (3.0, 3.5, 2.7),
    "hall": (5.0, 6.0, 3.0),
    "living": (5.0, 6.0, 3.0),
    "living_room": (5.0, 6.0, 3.0),
    "kitchen": (3.0, 4.0, 2.7),
    "dining": (3.6, 4.2, 2.7),
    "dining_room": (3.6, 4.2, 2.7),
    "bathroom": (2.0, 2.5, 2.4),
    "bathroom_2": (1.8, 2.2, 2.4),
    "bathroom_3": (1.8, 2.2, 2.4),
    "bathroom_4": (1.8, 2.2, 2.4),
    "master_bathroom": (2.5, 3.0, 2.4),
    "common_bathroom": (1.8, 2.2, 2.4),
    "toilet": (1.5, 2.0, 2.4),
    "balcony": (1.5, 3.5, 2.4),
    "balcony_1": (1.5, 4.0, 2.4),
    "balcony_2": (1.2, 3.0, 2.4),
    "balcony_3": (1.2, 3.0, 2.4),
    "study": (3.0, 3.5, 2.7),
    "pooja_room": (2.0, 2.5, 2.7),
    "garage": (6.0, 6.0, 2.5),
    "terrace": (8.0, 10.0, 0.3),
    "home_theatre": (5.0, 6.0, 2.8),
    "jacuzzi_deck": (5.0, 6.0, 2.4),
    "passage": (1.5, 3.5, 2.7),
    "corridor": (1.5, 4.5, 2.7),
    "store": (2.0, 2.0, 2.4),
    "utility": (2.0, 2.5, 2.4),
    "garden": (8.0, 10.0, 0.3),
}


def _resolve_room_dims(
    room_name: str,
    spec_room_dimensions: Dict[str, Any],
    floor_height: float,
) -> Tuple[float, float, float]:
    """Resolve (w, l, h) for a room: spec overrides > defaults > fallback."""
    # Build lookup candidates: exact name, then strip trailing _N suffix, then base type
    parts = room_name.rsplit("_", 1)
    numeric_suffix = len(parts) == 2 and parts[1].isdigit()
    base_no_num = parts[0] if numeric_suffix else room_name
    # Also try stripping the number to get generic base (e.g. balcony_1 -> balcony)
    base_type = base_no_num.rsplit("_", 1)[0] if "_" in base_no_num else base_no_num

    candidates = [room_name, base_no_num, base_type]

    # 1. Try spec room_dimensions (exact match or suffix-stripped)
    for key in candidates:
        rd = spec_room_dimensions.get(key)
        if rd and isinstance(rd, dict):
            w = float(rd.get("width_m", rd.get("width", 0)) or 0)
            l = float(rd.get("length_m", rd.get("length", 0)) or 0)
            h = float(rd.get("height_m", rd.get("height", floor_height)) or floor_height)
            if w > 0 and l > 0:
                return w, l, max(h, 2.2)

    # 2. Fall back to hardcoded defaults
    for key in candidates:
        if key in _ROOM_DEFAULTS:
            dw, dl, dh = _ROOM_DEFAULTS[key]
            return dw, dl, floor_height if floor_height != 2.7 else dh

    return 3.5, 4.0, floor_height


# ── Layout engine ─────────────────────────────────────────────────────────────


def _layout_rooms(
    rooms: List[str],
    spec_room_dimensions: Dict[str, Any],
    total_width: float,
    floor_height: float,
) -> List[Tuple[str, float, float, float, float, float]]:
    """
    Pack rooms left-to-right, wrapping to next row when width exceeded.
    Rooms are separated by GAP so shared walls are physically distinct.
    Returns list of (name, x, y, w, l, h) — inner dimensions.

    Phase 2 fix: use max(total_width, widest_room * 1.5) so rooms never
    all collapse into a single column.
    """
    if not rooms:
        return []

    # Compute per-room dims first so we can set a sensible row width
    dims = [_resolve_room_dims(r, spec_room_dimensions, floor_height) for r in rooms]
    max_w = max(d[0] for d in dims)
    total_room_w = sum(d[0] for d in dims) + GAP * (len(dims) - 1)
    # Row width: use total_width but ensure at least 2 rooms wide
    row_width = max(total_width, max_w * 2.0 + GAP, total_room_w / max(math.ceil(len(dims) / 3), 1))

    layout: List[Tuple[str, float, float, float, float, float]] = []
    cursor_x = 0.0
    cursor_y = 0.0
    row_max_l = 0.0

    for room_name, (w, l, h) in zip(rooms, dims):
        # Wrap to next row if this room doesn't fit
        if cursor_x > 0 and cursor_x + w > row_width + 0.01:
            cursor_x = 0.0
            cursor_y += row_max_l + GAP
            row_max_l = 0.0

        layout.append((room_name, cursor_x, cursor_y, w, l, h))
        cursor_x += w + GAP
        row_max_l = max(row_max_l, l)

    return layout


# ── Door placement ────────────────────────────────────────────────────────────


def _compute_doors(
    layout: List[Tuple[str, float, float, float, float, float]],
    adjacency_spec: Dict[str, Any],
) -> Dict[int, Dict[str, bool]]:
    """
    Determine which walls get a door gap.

    Two sources:
      1. spec_json["adjacency"] — explicit adjacency pairs from BHK definition
      2. Spatial proximity — rooms that are physically touching (GAP apart)

    Returns {room_idx: {south, north, west, east}} booleans.
    """
    n = len(layout)
    doors: Dict[int, Dict[str, bool]] = {
        i: {"south": False, "north": False, "west": False, "east": False} for i in range(n)
    }

    # Build name → index map
    name_to_idx: Dict[str, int] = {}
    for i, (name, *_) in enumerate(layout):
        # strip _1/_2 suffix for adjacency lookup
        base = name.rsplit("_", 1)[0] if name.rsplit("_", 1)[-1].isdigit() else name
        name_to_idx[name] = i
        name_to_idx[base] = i  # allow base name lookup

    # 1. Spatial adjacency — rooms touching within tolerance
    tol = GAP * 1.5
    for i, (_, xi, yi, wi, li, _hi) in enumerate(layout):
        for j, (_, xj, yj, wj, lj, _hj) in enumerate(layout):
            if i >= j:
                continue
            # j is east of i?
            if abs((xi + wi + GAP) - xj) < tol and yi < yj + lj and yi + li > yj:
                doors[i]["east"] = True
                doors[j]["west"] = True
            # j is north of i?
            if abs((yi + li + GAP) - yj) < tol and xi < xj + wj and xi + wi > xj:
                doors[i]["north"] = True
                doors[j]["south"] = True

    # 2. Explicit adjacency from spec — add doors even if not spatially touching
    # adjacency_spec can be {"bedroom": ["hall"], "kitchen": ["dining"]} etc.
    if isinstance(adjacency_spec, dict):
        for room_a, neighbours in adjacency_spec.items():
            if not isinstance(neighbours, list):
                continue
            idx_a = name_to_idx.get(room_a)
            if idx_a is None:
                continue
            for room_b in neighbours:
                idx_b = name_to_idx.get(room_b)
                if idx_b is None:
                    continue
                # Determine relative direction and add door on the closer wall
                _, xa, ya, wa, la, _ = layout[idx_a]
                _, xb, yb, wb, lb, _ = layout[idx_b]
                cx_a, cy_a = xa + wa / 2, ya + la / 2
                cx_b, cy_b = xb + wb / 2, yb + lb / 2
                dx, dy = cx_b - cx_a, cy_b - cy_a
                if abs(dx) >= abs(dy):
                    if dx > 0:
                        doors[idx_a]["east"] = True
                        doors[idx_b]["west"] = True
                    else:
                        doors[idx_a]["west"] = True
                        doors[idx_b]["east"] = True
                else:
                    if dy > 0:
                        doors[idx_a]["north"] = True
                        doors[idx_b]["south"] = True
                    else:
                        doors[idx_a]["south"] = True
                        doors[idx_b]["north"] = True

    return doors


# ── Mesh container ────────────────────────────────────────────────────────────


class Mesh:
    def __init__(self, name: str):
        self.name = name
        self.verts: List[Vertex] = []
        self.tris: List[Triangle] = []

    def add_quad(self, a: Vertex, b: Vertex, c: Vertex, d: Vertex) -> None:
        base = len(self.verts)
        self.verts += [a, b, c, d]
        self.tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]

    def add_thick_wall(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        z_bot: float,
        z_top: float,
        normal_out: Tuple[float, float],
        door: bool = False,
    ) -> None:
        """
        Build a wall panel (x0,y0)→(x1,y1) with thickness WALL_T.
        normal_out points away from the room interior.
        door=True cuts a centred door gap.
        """
        nx, ny = normal_out
        tx, ty = WALL_T * nx, WALL_T * ny

        ix0, iy0 = x0, y0
        ix1, iy1 = x1, y1
        ox0, oy0 = x0 + tx, y0 + ty
        ox1, oy1 = x1 + tx, y1 + ty

        if not door:
            self._wall_segment(ix0, iy0, ix1, iy1, ox0, oy0, ox1, oy1, z_bot, z_top)
        else:
            length = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            if length < 1e-6:
                return
            ux = (x1 - x0) / length
            uy = (y1 - y0) / length

            door_start = max(0.0, (length - DOOR_W) / 2)
            door_end = door_start + DOOR_W

            # Left segment
            if door_start > 0.01:
                ax0, ay0 = x0, y0
                ax1, ay1 = x0 + ux * door_start, y0 + uy * door_start
                self._wall_segment(ax0, ay0, ax1, ay1, ax0 + tx, ay0 + ty, ax1 + tx, ay1 + ty, z_bot, z_top)

            # Above-door segment
            if DOOR_H < z_top - z_bot:
                bx0 = x0 + ux * door_start
                by0 = y0 + uy * door_start
                bx1 = x0 + ux * door_end
                by1 = y0 + uy * door_end
                self._wall_segment(bx0, by0, bx1, by1, bx0 + tx, by0 + ty, bx1 + tx, by1 + ty, z_bot + DOOR_H, z_top)

            # Right segment
            if door_end < length - 0.01:
                cx0 = x0 + ux * door_end
                cy0 = y0 + uy * door_end
                self._wall_segment(cx0, cy0, x1, y1, cx0 + tx, cy0 + ty, ox1, oy1, z_bot, z_top)

    def _wall_segment(
        self,
        ix0: float,
        iy0: float,
        ix1: float,
        iy1: float,
        ox0: float,
        oy0: float,
        ox1: float,
        oy1: float,
        z_bot: float,
        z_top: float,
    ) -> None:
        # inner face
        self.add_quad((ix0, iy0, z_bot), (ix1, iy1, z_bot), (ix1, iy1, z_top), (ix0, iy0, z_top))
        # outer face (reversed winding)
        self.add_quad((ox1, oy1, z_bot), (ox0, oy0, z_bot), (ox0, oy0, z_top), (ox1, oy1, z_top))
        # top cap
        self.add_quad((ix0, iy0, z_top), (ix1, iy1, z_top), (ox1, oy1, z_top), (ox0, oy0, z_top))
        # left cap
        self.add_quad((ox0, oy0, z_bot), (ix0, iy0, z_bot), (ix0, iy0, z_top), (ox0, oy0, z_top))
        # right cap
        self.add_quad((ix1, iy1, z_bot), (ox1, oy1, z_bot), (ox1, oy1, z_top), (ix1, iy1, z_top))


# ── Build one room ────────────────────────────────────────────────────────────


def build_room_mesh(
    name: str,
    x: float,
    y: float,
    w: float,
    l: float,
    h: float,
    z: float = 0.0,
    door_south: bool = False,
    door_north: bool = False,
    door_west: bool = False,
    door_east: bool = False,
) -> Mesh:
    """
    Build one room: floor + ceiling + 4 thick walls with optional door gaps.
    Phase 2: each room is a fully enclosed volume, not a plane.
    """
    m = Mesh(name)
    z0, z1 = z, z + h

    # Floor
    m.add_quad((x, y, z0), (x + w, y, z0), (x + w, y + l, z0), (x, y + l, z0))
    # Ceiling
    m.add_quad((x, y + l, z1), (x + w, y + l, z1), (x + w, y, z1), (x, y, z1))

    # South wall (y=y, normal=-Y)
    m.add_thick_wall(x, y, x + w, y, z0, z1, (0.0, -1.0), door=door_south)
    # North wall (y=y+l, normal=+Y)
    m.add_thick_wall(x + w, y + l, x, y + l, z0, z1, (0.0, 1.0), door=door_north)
    # West wall (x=x, normal=-X)
    m.add_thick_wall(x, y + l, x, y, z0, z1, (-1.0, 0.0), door=door_west)
    # East wall (x=x+w, normal=+X)
    m.add_thick_wall(x + w, y, x + w, y + l, z0, z1, (1.0, 0.0), door=door_east)

    return m


# ── GLB packer ────────────────────────────────────────────────────────────────


def _normals_for_mesh(m: Mesh) -> List[Vertex]:
    normals = [[0.0, 0.0, 0.0] for _ in m.verts]
    for tri in m.tris:
        v0, v1, v2 = m.verts[tri[0]], m.verts[tri[1]], m.verts[tri[2]]
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        for idx in tri:
            normals[idx][0] += nx
            normals[idx][1] += ny
            normals[idx][2] += nz
    result: List[Vertex] = []
    for n in normals:
        mag = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
        result.append((n[0] / mag, n[1] / mag, n[2] / mag) if mag > 0 else (0.0, 0.0, 1.0))
    return result


def _pad4(b: bytes) -> bytes:
    r = len(b) % 4
    return b + b"\x00" * ((4 - r) % 4)


def pack_glb_multi_mesh(meshes: List[Mesh]) -> bytes:
    """
    Pack named Mesh objects into a single GLB 2.0 file.
    Each mesh = its own node → viewers show separate rooms.
    """
    if not meshes:
        raise ValueError("No meshes to pack")

    bin_chunks: List[bytes] = []
    buffer_views = []
    accessors = []
    gltf_meshes = []
    nodes = []
    offset = 0

    for m in meshes:
        if not m.verts or not m.tris:
            continue

        norms = _normals_for_mesh(m)

        pos_buf = _pad4(b"".join(struct.pack("<fff", *v) for v in m.verts))
        nor_buf = _pad4(b"".join(struct.pack("<fff", *n) for n in norms))
        idx_buf = _pad4(b"".join(struct.pack("<I", i) for tri in m.tris for i in tri))

        bv_pos = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(pos_buf)})
        offset += len(pos_buf)
        bin_chunks.append(pos_buf)

        bv_nor = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(nor_buf)})
        offset += len(nor_buf)
        bin_chunks.append(nor_buf)

        bv_idx = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(idx_buf)})
        offset += len(idx_buf)
        bin_chunks.append(idx_buf)

        acc_pos = len(accessors)
        accessors.append({"bufferView": bv_pos, "componentType": 5126, "count": len(m.verts), "type": "VEC3"})
        acc_nor = len(accessors)
        accessors.append({"bufferView": bv_nor, "componentType": 5126, "count": len(m.verts), "type": "VEC3"})
        acc_idx = len(accessors)
        accessors.append({"bufferView": bv_idx, "componentType": 5125, "count": len(m.tris) * 3, "type": "SCALAR"})

        mesh_idx = len(gltf_meshes)
        gltf_meshes.append(
            {
                "name": m.name,
                "primitives": [{"attributes": {"POSITION": acc_pos, "NORMAL": acc_nor}, "indices": acc_idx, "mode": 4}],
            }
        )
        nodes.append({"mesh": mesh_idx, "name": m.name})

    if not gltf_meshes:
        raise ValueError("All meshes were empty")

    bin_data = b"".join(bin_chunks)

    gltf = {
        "asset": {"version": "2.0", "generator": "BHIV-RoomGeometry-v3"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": gltf_meshes,
        "accessors": accessors,
        "bufferViews": buffer_views,
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


# ── Main entry point ──────────────────────────────────────────────────────────


def generate_real_glb(spec_json: Dict[str, Any]) -> bytes:
    """
    Generate a GLB from spec_json["rooms"].

    Phase 2 guarantees:
      - Each room = enclosed volume (floor + ceiling + 4 thick walls)
      - Walls have real thickness (WALL_T = 0.25 m)
      - Rooms are spatially separated (GAP = WALL_T between them)
      - Adjacent rooms (from spec adjacency + spatial proximity) get door gaps
      - Bedroom ≠ Hall ≠ Kitchen — different dimensions, different positions
      - Raises ValueError if rooms list is empty (no dummy mesh)
    """
    rooms: List[str] = spec_json.get("rooms") or []
    dimensions = spec_json.get("dimensions") or {}
    room_dims = spec_json.get("room_dimensions") or {}
    adjacency_spec = spec_json.get("adjacency") or {}
    stories = int(spec_json.get("stories") or 1)

    total_w = float(dimensions.get("width", 12.0) or 12.0)
    floor_h = float(dimensions.get("height", 2.8) or 2.8) / max(stories, 1)

    if not rooms:
        raise ValueError("Geometry generation failed: spec has no rooms defined")

    logger.info(
        "generate_real_glb: %d rooms, footprint=%.1fx%.1f, floor_h=%.1f, stories=%d",
        len(rooms),
        total_w,
        float(dimensions.get("length", 10.0) or 10.0),
        floor_h,
        stories,
    )

    layout = _layout_rooms(rooms, room_dims, total_w, floor_h)
    door_map = _compute_doors(layout, adjacency_spec)
    all_meshes: List[Mesh] = []

    for story in range(stories):
        z_offset = story * (floor_h + WALL_T)
        for idx, (room_name, rx, ry, rw, rl, rh) in enumerate(layout):
            d = door_map[idx]
            node_name = f"{room_name}_s{story}" if stories > 1 else room_name
            mesh = build_room_mesh(
                name=node_name,
                x=rx,
                y=ry,
                w=rw,
                l=rl,
                h=rh,
                z=z_offset,
                door_south=d["south"],
                door_north=d["north"],
                door_west=d["west"],
                door_east=d["east"],
            )
            all_meshes.append(mesh)

    logger.info("Geometry built: %d meshes (%d rooms x %d stories)", len(all_meshes), len(rooms), stories)
    return pack_glb_multi_mesh(all_meshes)
