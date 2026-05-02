"""
Room-Based Geometry Generator
==============================
Each room = separate GLB mesh node (named).
Walls have real thickness (WALL_T = 0.2 m).
Adjacent rooms share a wall with a door gap cut out.
Rooms are separated by wall thickness so partitions are visible.

Pipeline:
  spec["rooms"]  →  layout_rooms()
                 →  for each room: build_room_node()
                 →  pack_glb_multi_mesh()
"""

import json
import logging
import math
import struct
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WALL_T = 0.2  # wall thickness in metres
DOOR_W = 0.9  # door opening width in metres
DOOR_H = 2.1  # door opening height in metres
GAP = WALL_T  # gap between room origins = wall thickness

Vertex = Tuple[float, float, float]
Triangle = Tuple[int, int, int]


# ---------------------------------------------------------------------------
# Per-mesh geometry container
# ---------------------------------------------------------------------------
class Mesh:
    def __init__(self, name: str):
        self.name = name
        self.verts: List[Vertex] = []
        self.tris: List[Triangle] = []

    def add_quad(self, a: Vertex, b: Vertex, c: Vertex, d: Vertex) -> None:
        """Add a quad as two CCW triangles (a,b,c) + (a,c,d)."""
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
        Build a wall panel from (x0,y0)→(x1,y1) with thickness WALL_T.
        normal_out points away from the room interior.
        If door=True, cut a door-sized gap in the centre of the wall.
        """
        nx, ny = normal_out
        tx, ty = WALL_T * nx, WALL_T * ny  # thickness vector

        # inner face (facing room)
        ix0, iy0 = x0, y0
        ix1, iy1 = x1, y1
        # outer face (offset by thickness)
        ox0, oy0 = x0 + tx, y0 + ty
        ox1, oy1 = x1 + tx, y1 + ty

        if not door:
            # inner face
            self.add_quad(
                (ix0, iy0, z_bot),
                (ix1, iy1, z_bot),
                (ix1, iy1, z_top),
                (ix0, iy0, z_top),
            )
            # outer face (reversed winding)
            self.add_quad(
                (ox1, oy1, z_bot),
                (ox0, oy0, z_bot),
                (ox0, oy0, z_top),
                (ox1, oy1, z_top),
            )
            # top cap
            self.add_quad(
                (ix0, iy0, z_top),
                (ix1, iy1, z_top),
                (ox1, oy1, z_top),
                (ox0, oy0, z_top),
            )
            # left cap
            self.add_quad(
                (ox0, oy0, z_bot),
                (ix0, iy0, z_bot),
                (ix0, iy0, z_top),
                (ox0, oy0, z_top),
            )
            # right cap
            self.add_quad(
                (ix1, iy1, z_bot),
                (ox1, oy1, z_bot),
                (ox1, oy1, z_top),
                (ix1, iy1, z_top),
            )
        else:
            # Wall length along its axis
            length = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
            if length < 1e-6:
                return
            # unit vector along wall
            ux = (x1 - x0) / length
            uy = (y1 - y0) / length

            door_start = max(0.0, (length - DOOR_W) / 2)
            door_end = door_start + DOOR_W

            # Segment A: left of door
            if door_start > 0.01:
                ax0, ay0 = x0, y0
                ax1, ay1 = x0 + ux * door_start, y0 + uy * door_start
                oax0, oay0 = ax0 + tx, ay0 + ty
                oax1, oay1 = ax1 + tx, ay1 + ty
                self._wall_segment(ax0, ay0, ax1, ay1, oax0, oay0, oax1, oay1, z_bot, z_top)

            # Segment B: above door (full height minus door height)
            if DOOR_H < z_top - z_bot:
                bx0 = x0 + ux * door_start
                by0 = y0 + uy * door_start
                bx1 = x0 + ux * door_end
                by1 = y0 + uy * door_end
                obx0, oby0 = bx0 + tx, by0 + ty
                obx1, oby1 = bx1 + tx, by1 + ty
                self._wall_segment(
                    bx0,
                    by0,
                    bx1,
                    by1,
                    obx0,
                    oby0,
                    obx1,
                    oby1,
                    z_bot + DOOR_H,
                    z_top,
                )

            # Segment C: right of door
            if door_end < length - 0.01:
                cx0 = x0 + ux * door_end
                cy0 = y0 + uy * door_end
                cx1, cy1 = x1, y1
                ocx0, ocy0 = cx0 + tx, cy0 + ty
                ocx1, ocy1 = cx1 + tx, cy1 + ty
                self._wall_segment(cx0, cy0, cx1, cy1, ocx0, ocy0, ocx1, ocy1, z_bot, z_top)

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
        """Render one rectangular wall segment (inner + outer + caps)."""
        self.add_quad(
            (ix0, iy0, z_bot),
            (ix1, iy1, z_bot),
            (ix1, iy1, z_top),
            (ix0, iy0, z_top),
        )
        self.add_quad(
            (ox1, oy1, z_bot),
            (ox0, oy0, z_bot),
            (ox0, oy0, z_top),
            (ox1, oy1, z_top),
        )
        self.add_quad(
            (ix0, iy0, z_top),
            (ix1, iy1, z_top),
            (ox1, oy1, z_top),
            (ox0, oy0, z_top),
        )
        self.add_quad(
            (ox0, oy0, z_bot),
            (ix0, iy0, z_bot),
            (ix0, iy0, z_top),
            (ox0, oy0, z_top),
        )
        self.add_quad(
            (ix1, iy1, z_bot),
            (ox1, oy1, z_bot),
            (ox1, oy1, z_top),
            (ix1, iy1, z_top),
        )


# ---------------------------------------------------------------------------
# Build one room's full geometry
# ---------------------------------------------------------------------------
def build_room_mesh(
    name: str,
    x: float,
    y: float,  # inner bottom-left corner
    w: float,
    l: float,  # inner width (X) and length (Y)
    h: float,  # floor-to-ceiling height
    z: float = 0.0,  # Z offset for multi-storey
    door_south: bool = False,
    door_north: bool = False,
    door_west: bool = False,
    door_east: bool = False,
) -> Mesh:
    """
    Build a room with:
    - Floor slab
    - Ceiling slab
    - 4 thick walls (each with optional door gap)
    """
    m = Mesh(name)
    z0 = z
    z1 = z + h

    # ── Floor ────────────────────────────────────────────────────────────────
    m.add_quad(
        (x, y, z0),
        (x + w, y, z0),
        (x + w, y + l, z0),
        (x, y + l, z0),
    )

    # ── Ceiling ──────────────────────────────────────────────────────────────
    m.add_quad(
        (x, y + l, z1),
        (x + w, y + l, z1),
        (x + w, y, z1),
        (x, y, z1),
    )

    # ── South wall (y = y, normal = -Y) ──────────────────────────────────────
    m.add_thick_wall(x, y, x + w, y, z0, z1, (0.0, -1.0), door=door_south)

    # ── North wall (y = y+l, normal = +Y) ────────────────────────────────────
    m.add_thick_wall(x + w, y + l, x, y + l, z0, z1, (0.0, 1.0), door=door_north)

    # ── West wall (x = x, normal = -X) ───────────────────────────────────────
    m.add_thick_wall(x, y + l, x, y, z0, z1, (-1.0, 0.0), door=door_west)

    # ── East wall (x = x+w, normal = +X) ─────────────────────────────────────
    m.add_thick_wall(x + w, y, x + w, y + l, z0, z1, (1.0, 0.0), door=door_east)

    return m


# ---------------------------------------------------------------------------
# GLB packer — multi-mesh, one node per room
# ---------------------------------------------------------------------------
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


def pack_glb_multi_mesh(meshes: List[Mesh]) -> bytes:
    """
    Pack a list of named Mesh objects into a single GLB 2.0 file.
    Each mesh becomes its own node so viewers show separate rooms.
    Uses uint32 indices to handle large vertex counts.
    """
    if not meshes:
        raise ValueError("No meshes to pack")

    # ── Build binary buffer ──────────────────────────────────────────────────
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

        pos_buf = b"".join(struct.pack("<fff", *v) for v in m.verts)
        nor_buf = b"".join(struct.pack("<fff", *n) for n in norms)
        idx_buf = b"".join(struct.pack("<I", i) for tri in m.tris for i in tri)

        # pad each buffer to 4-byte boundary
        def _pad4(b: bytes) -> bytes:
            r = len(b) % 4
            return b + b"\x00" * ((4 - r) % 4)

        pos_buf = _pad4(pos_buf)
        nor_buf = _pad4(nor_buf)
        idx_buf = _pad4(idx_buf)

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
        accessors.append(
            {
                "bufferView": bv_pos,
                "componentType": 5126,
                "count": len(m.verts),
                "type": "VEC3",
            }
        )
        acc_nor = len(accessors)
        accessors.append(
            {
                "bufferView": bv_nor,
                "componentType": 5126,
                "count": len(m.verts),
                "type": "VEC3",
            }
        )
        acc_idx = len(accessors)
        accessors.append(
            {
                "bufferView": bv_idx,
                "componentType": 5125,  # UNSIGNED_INT
                "count": len(m.tris) * 3,
                "type": "SCALAR",
            }
        )

        mesh_idx = len(gltf_meshes)
        gltf_meshes.append(
            {
                "name": m.name,
                "primitives": [
                    {
                        "attributes": {"POSITION": acc_pos, "NORMAL": acc_nor},
                        "indices": acc_idx,
                        "mode": 4,
                    }
                ],
            }
        )
        node_idx = len(nodes)
        nodes.append({"mesh": mesh_idx, "name": m.name})

    if not gltf_meshes:
        raise ValueError("All meshes were empty")

    bin_data = b"".join(bin_chunks)

    gltf = {
        "asset": {"version": "2.0", "generator": "BHIV-RoomGeometry-v2"},
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


# ---------------------------------------------------------------------------
# Room dimension resolver
# ---------------------------------------------------------------------------
_ROOM_DEFAULTS: Dict[str, Tuple[float, float, float]] = {
    "master_bedroom": (4.0, 4.5, 2.8),
    "bedroom": (3.5, 4.0, 2.7),
    "hall": (4.5, 5.5, 2.8),
    "living": (4.5, 5.5, 2.8),
    "living_room": (4.5, 5.5, 2.8),
    "kitchen": (3.0, 4.0, 2.7),
    "dining": (3.5, 4.0, 2.7),
    "dining_room": (3.5, 4.0, 2.7),
    "bathroom": (2.0, 2.5, 2.4),
    "master_bathroom": (2.5, 3.0, 2.4),
    "common_bathroom": (1.8, 2.2, 2.4),
    "toilet": (1.5, 2.0, 2.4),
    "balcony": (1.5, 3.5, 2.4),
    "study": (3.0, 3.5, 2.7),
    "pooja_room": (2.0, 2.5, 2.7),
    "garage": (6.0, 6.0, 2.5),
    "terrace": (8.0, 10.0, 0.3),
    "home_theatre": (5.0, 6.0, 2.8),
    "passage": (1.2, 3.0, 2.7),
    "corridor": (1.2, 4.0, 2.7),
    "store": (2.0, 2.0, 2.4),
    "utility": (2.0, 2.5, 2.4),
}


def _resolve_room_dims(
    room_name: str,
    spec_room_dimensions: Dict[str, Any],
    floor_height: float,
) -> Tuple[float, float, float]:
    base = room_name.rstrip("_0123456789")
    parts = room_name.rsplit("_", 1)
    base_alt = parts[0] if len(parts) == 2 and parts[1].isdigit() else room_name

    for key in (room_name, base_alt, base):
        rd = spec_room_dimensions.get(key)
        if rd and isinstance(rd, dict):
            w = float(rd.get("width_m", rd.get("width", 0)) or 0)
            l = float(rd.get("length_m", rd.get("length", 0)) or 0)
            h = float(rd.get("height_m", rd.get("height", floor_height)) or floor_height)
            if w > 0 and l > 0:
                return w, l, h

    for key in (room_name, base_alt, base):
        if key in _ROOM_DEFAULTS:
            dw, dl, dh = _ROOM_DEFAULTS[key]
            return dw, dl, floor_height if floor_height != 2.7 else dh

    return 3.5, 4.0, floor_height


# ---------------------------------------------------------------------------
# Layout engine — row-based packing with adjacency tracking
# ---------------------------------------------------------------------------
def _layout_rooms(
    rooms: List[str],
    spec_room_dimensions: Dict[str, Any],
    total_width: float,
    floor_height: float,
) -> List[Tuple[str, float, float, float, float, float]]:
    """
    Pack rooms left-to-right, wrapping to next row.
    Rooms are separated by GAP (= WALL_T) so shared walls are visible.
    Returns list of (name, x, y, w, l, h) — all inner dimensions.
    """
    layout: List[Tuple[str, float, float, float, float, float]] = []
    cursor_x = 0.0
    cursor_y = 0.0
    row_max_l = 0.0

    for room_name in rooms:
        w, l, h = _resolve_room_dims(room_name, spec_room_dimensions, floor_height)

        if cursor_x + w > total_width + 0.01 and cursor_x > 0:
            cursor_x = 0.0
            cursor_y += row_max_l + GAP
            row_max_l = 0.0

        layout.append((room_name, cursor_x, cursor_y, w, l, h))
        cursor_x += w + GAP
        row_max_l = max(row_max_l, l)

    return layout


def _compute_adjacency(layout: List[Tuple[str, float, float, float, float, float]]) -> Dict[int, Dict[str, bool]]:
    """
    For each room index, determine which walls are shared with a neighbour.
    Returns {room_idx: {south, north, west, east}} booleans.
    """
    adj: Dict[int, Dict[str, bool]] = {
        i: {"south": False, "north": False, "west": False, "east": False} for i in range(len(layout))
    }
    tol = GAP + 0.05  # tolerance for adjacency detection

    for i, (_, xi, yi, wi, li, _hi) in enumerate(layout):
        for j, (_, xj, yj, wj, lj, _hj) in enumerate(layout):
            if i == j:
                continue
            # Room j is directly east of room i?
            if abs((xi + wi + GAP) - xj) < tol:
                # Y ranges overlap?
                if yi < yj + lj and yi + li > yj:
                    adj[i]["east"] = True
                    adj[j]["west"] = True
            # Room j is directly north of room i?
            if abs((yi + li + GAP) - yj) < tol:
                if xi < xj + wj and xi + wi > xj:
                    adj[i]["north"] = True
                    adj[j]["south"] = True

    return adj


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def generate_real_glb(spec_json: Dict[str, Any]) -> bytes:
    """
    Generate a GLB from spec_json["rooms"].

    Each room becomes a separate named mesh node.
    Walls are thick (WALL_T = 0.2 m).
    Adjacent rooms get a door gap in the shared wall.
    """
    rooms: List[str] = spec_json.get("rooms") or []
    dimensions = spec_json.get("dimensions") or {}
    room_dimensions = spec_json.get("room_dimensions") or {}
    stories = int(spec_json.get("stories") or 1)

    total_w = float(dimensions.get("width", 12.0) or 12.0)
    total_l = float(dimensions.get("length", 10.0) or 10.0)
    floor_h = float(dimensions.get("height", 2.8) or 2.8) / max(stories, 1)

    if not rooms:
        raise ValueError("Geometry generation failed: spec has no rooms defined")

    logger.info(
        "generate_real_glb: %d rooms, footprint=%.1fx%.1f, floor_h=%.1f, stories=%d",
        len(rooms),
        total_w,
        total_l,
        floor_h,
        stories,
    )

    layout = _layout_rooms(rooms, room_dimensions, total_w, floor_h)
    adjacency = _compute_adjacency(layout)

    all_meshes: List[Mesh] = []

    for story in range(stories):
        z_offset = story * (floor_h + WALL_T)

        for idx, (room_name, rx, ry, rw, rl, rh) in enumerate(layout):
            adj = adjacency[idx]
            node_name = f"{room_name}_s{story}" if stories > 1 else room_name

            mesh = build_room_mesh(
                name=node_name,
                x=rx,
                y=ry,
                w=rw,
                l=rl,
                h=rh,
                z=z_offset,
                door_south=adj["south"],
                door_north=adj["north"],
                door_west=adj["west"],
                door_east=adj["east"],
            )
            all_meshes.append(mesh)

    logger.info(
        "Geometry built: %d meshes (%d rooms x %d stories)",
        len(all_meshes),
        len(rooms),
        stories,
    )

    return pack_glb_multi_mesh(all_meshes)
