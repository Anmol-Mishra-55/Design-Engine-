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


# ── Furniture helpers ────────────────────────────────────────────────────────


def _add_box(m: Mesh, x: float, y: float, z: float, bw: float, bl: float, bh: float) -> None:
    x1, y1, z1 = x + bw, y + bl, z + bh
    m.add_quad((x, y, z), (x1, y, z), (x1, y1, z), (x, y1, z))
    m.add_quad((x, y1, z1), (x1, y1, z1), (x1, y, z1), (x, y, z1))
    m.add_quad((x, y, z), (x, y, z1), (x1, y, z1), (x1, y, z))
    m.add_quad((x1, y1, z), (x1, y1, z1), (x, y1, z1), (x, y1, z))
    m.add_quad((x, y1, z), (x, y1, z1), (x, y, z1), (x, y, z))
    m.add_quad((x1, y, z), (x1, y, z1), (x1, y1, z1), (x1, y1, z))


def _room_base_type(name: str) -> str:
    key = name.split("_s")[0]
    parts = key.rsplit("_", 1)
    return parts[0] if len(parts) == 2 and parts[1].isdigit() else key


def _add_furniture(m: Mesh, rt: str, x: float, y: float, w: float, l: float, z: float) -> None:
    p = WALL_T + 0.1  # inner padding from wall face

    # ── Bedrooms ──────────────────────────────────────────────────────────────
    if rt in ("master_bedroom", "bedroom", "bedroom_2", "bedroom_3", "bedroom_4", "bedroom_5"):
        # Bed against north wall, centred
        bw, bl = min(1.6, w - 2 * p), min(2.0, l * 0.5)
        bx, by = x + (w - bw) / 2, y + l - p - bl
        _add_box(m, bx, by, z, bw, bl, 0.5)  # mattress
        _add_box(m, bx, by + bl - 0.15, z + 0.5, bw, 0.1, 0.55)  # headboard
        _add_box(m, bx + 0.1, by + bl - 0.35, z + 0.5, 0.5, 0.3, 0.12)  # pillow
        # Bedside table
        if bx - x - p > 0.4:
            _add_box(m, bx - p - 0.45, by + bl - 0.5, z, 0.45, 0.45, 0.55)
        # Wardrobe against west wall
        _add_box(m, x + p, y + p, z, min(1.2, w * 0.3), 0.6, 2.0)

    # ── Living / Hall ─────────────────────────────────────────────────────────
    elif rt in ("hall", "living", "living_room"):
        sw = min(2.2, w - 2 * p)
        # 3-seater sofa against south wall
        _add_box(m, x + (w - sw) / 2, y + p, z, sw, 0.9, 0.85)
        # Coffee table in centre
        _add_box(m, x + (w - 1.0) / 2, y + l * 0.38, z, 1.0, 0.55, 0.42)
        # TV unit against north wall
        tw = min(1.6, w - 2 * p)
        _add_box(m, x + (w - tw) / 2, y + l - p - 0.45, z, tw, 0.45, 0.5)
        # TV panel on top
        _add_box(m, x + (w - tw * 0.7) / 2, y + l - p - 0.42, z + 0.5, tw * 0.7, 0.08, 0.55)
        # Side chair
        _add_box(m, x + p, y + l * 0.35, z, 0.55, 0.55, 0.9)

    # ── Kitchen ───────────────────────────────────────────────────────────────
    elif rt == "kitchen":
        # Base counter along south wall
        _add_box(m, x + p, y + p, z, w - 2 * p, 0.6, 0.9)
        # Side counter along west wall
        _add_box(m, x + p, y + p + 0.6, z, 0.6, min(l * 0.4, l - 2 * p - 0.6), 0.9)
        # Overhead cabinet above base counter
        _add_box(m, x + p, y + p, z + 1.4, w - 2 * p, 0.35, 0.65)
        # Refrigerator box in corner
        _add_box(m, x + w - p - 0.7, y + p, z, 0.7, 0.7, 1.8)

    # ── Dining ────────────────────────────────────────────────────────────────
    elif rt in ("dining", "dining_room"):
        tw, tl = min(1.4, w - 2 * p), min(0.85, l * 0.4)
        tx, ty = x + (w - tw) / 2, y + (l - tl) / 2
        _add_box(m, tx, ty, z, tw, tl, 0.75)  # table
        # 4 chairs around table
        for cx, cy in [
            (tx - 0.55, ty + (tl - 0.45) / 2),
            (tx + tw + 0.1, ty + (tl - 0.45) / 2),
            (tx + (tw - 0.45) / 2, ty - 0.55),
            (tx + (tw - 0.45) / 2, ty + tl + 0.1),
        ]:
            _add_box(m, cx, cy, z, 0.45, 0.45, 0.9)

    # ── Bathrooms ─────────────────────────────────────────────────────────────
    elif rt in ("bathroom", "bathroom_2", "bathroom_3", "bathroom_4", "master_bathroom", "common_bathroom", "toilet"):
        # Toilet in near corner
        _add_box(m, x + p, y + p, z, 0.38, 0.65, 0.42)  # bowl
        _add_box(m, x + p, y + p + 0.45, z + 0.3, 0.38, 0.2, 0.12)  # cistern
        # Sink/vanity
        _add_box(m, x + p, y + l - p - 0.45, z, 0.5, 0.45, 0.85)
        # Shower tray in far corner (only if room wide enough)
        if w > 1.5 and l > 2.0:
            _add_box(m, x + w - p - 0.9, y + p, z, 0.9, 0.9, 0.05)

    # ── Study / Home Office ───────────────────────────────────────────────────
    elif rt == "study":
        dw = min(1.4, w - 2 * p)
        # Desk against north wall
        _add_box(m, x + (w - dw) / 2, y + l - p - 0.65, z, dw, 0.65, 0.75)
        # Monitor on desk
        _add_box(m, x + (w - 0.5) / 2, y + l - p - 0.6, z + 0.75, 0.5, 0.08, 0.4)
        # Chair in front of desk
        _add_box(m, x + (w - 0.55) / 2, y + l - p - 1.3, z, 0.55, 0.55, 0.9)
        # Bookshelf against east wall
        _add_box(m, x + w - p - 0.3, y + p, z, 0.3, min(1.2, l - 2 * p), 1.9)

    # ── Pooja Room ────────────────────────────────────────────────────────────
    elif rt == "pooja_room":
        pw = min(0.9, w - 2 * p)
        # Altar shelf against north wall
        _add_box(m, x + (w - pw) / 2, y + l - p - 0.4, z + 0.8, pw, 0.3, 0.05)
        # Platform/mandir base
        _add_box(m, x + (w - pw) / 2, y + l - p - 0.4, z, pw, 0.4, 0.8)
        # Prayer mat (flat)
        mw = min(0.6, w - 2 * p)
        _add_box(m, x + (w - mw) / 2, y + p, z, mw, 0.9, 0.03)

    # ── Balconies ─────────────────────────────────────────────────────────────
    elif rt in ("balcony", "balcony_1", "balcony_2", "balcony_3"):
        # Small bistro table
        _add_box(m, x + (w - 0.6) / 2, y + (l - 0.6) / 2, z, 0.6, 0.6, 0.72)
        # Two chairs on either side
        if w > 1.0:
            _add_box(m, x + p, y + (l - 0.45) / 2, z, 0.45, 0.45, 0.85)
            _add_box(m, x + w - p - 0.45, y + (l - 0.45) / 2, z, 0.45, 0.45, 0.85)
        # Planter box along railing
        _add_box(m, x + p, y + l - p - 0.25, z, w - 2 * p, 0.25, 0.35)

    # ── Garage ────────────────────────────────────────────────────────────────
    elif rt == "garage":
        # Car silhouette
        cw, cl = min(2.0, w - 2 * p), min(4.5, l - 2 * p)
        _add_box(m, x + (w - cw) / 2, y + p, z, cw, cl, 1.5)
        # Workbench along side wall
        _add_box(m, x + p, y + p, z, 0.6, min(1.5, l * 0.3), 0.9)

    # ── Home Theatre ─────────────────────────────────────────────────────────
    elif rt == "home_theatre":
        # Screen wall
        sw = min(w - 2 * p, 3.0)
        _add_box(m, x + (w - sw) / 2, y + l - p - 0.15, z + 0.6, sw, 0.1, 1.4)
        # Rows of seats (2 rows × 3 seats)
        seat_w = min((w - 2 * p) / 3, 0.6)
        for row, ry in enumerate([y + l * 0.35, y + l * 0.6]):
            for col in range(3):
                sx = x + p + col * (seat_w + 0.1)
                _add_box(m, sx, ry, z, seat_w, 0.55, 0.9)

    # ── Jacuzzi Deck ─────────────────────────────────────────────────────────
    elif rt == "jacuzzi_deck":
        # Jacuzzi tub centred
        jw, jl = min(1.8, w - 2 * p), min(1.8, l * 0.45)
        _add_box(m, x + (w - jw) / 2, y + (l - jl) / 2, z, jw, jl, 0.65)
        # Deck lounger
        _add_box(m, x + p, y + p, z, 0.7, min(1.9, l - 2 * p), 0.35)

    # ── Terrace ───────────────────────────────────────────────────────────────
    elif rt == "terrace":
        # Outdoor seating set
        _add_box(m, x + p, y + p, z, min(2.0, w * 0.35), 0.9, 0.85)  # sofa
        _add_box(m, x + p + 0.5, y + p + 1.1, z, 1.0, 0.6, 0.42)  # table
        # Planter boxes along perimeter
        _add_box(m, x + p, y + l - p - 0.3, z, w - 2 * p, 0.3, 0.4)
        _add_box(m, x + w - p - 0.3, y + p, z, 0.3, l - 2 * p, 0.4)

    # ── Garden ────────────────────────────────────────────────────────────────
    elif rt == "garden":
        # Lawn area (flat green slab)
        lw, ll = max(w - 2 * p - 1.0, 1.0), max(l - 2 * p - 1.0, 1.0)
        _add_box(m, x + (w - lw) / 2, y + (l - ll) / 2, z, lw, ll, 0.05)
        # Garden bench
        _add_box(m, x + p, y + l - p - 0.5, z, min(1.4, w * 0.3), 0.5, 0.45)
        # Tree stumps (2 planters)
        _add_box(m, x + p + 0.5, y + p + 0.5, z, 0.5, 0.5, 0.4)
        _add_box(m, x + w - p - 1.0, y + p + 0.5, z, 0.5, 0.5, 0.4)

    # ── Store / Utility ───────────────────────────────────────────────────────
    elif rt in ("store", "utility"):
        # Shelving units along walls
        _add_box(m, x + p, y + p, z, 0.4, min(l - 2 * p, 1.5), 1.8)
        _add_box(m, x + w - p - 0.4, y + p, z, 0.4, min(l - 2 * p, 1.5), 1.8)

    # ── Passage / Corridor ────────────────────────────────────────────────────
    elif rt in ("passage", "corridor"):
        # Slim console table against wall
        _add_box(m, x + p, y + (l - 0.8) / 2, z, min(0.3, w * 0.25), 0.8, 0.85)


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

    # Furniture
    _add_furniture(m, _room_base_type(name), x, y, w, l, z0)

    return m


# ── GLB packer ────────────────────────────────────────────────────────────────

# Per-room-type base colors [R, G, B] in linear space (approx)
_ROOM_COLORS: Dict[str, List[float]] = {
    "master_bedroom": [0.85, 0.70, 0.70],
    "bedroom": [0.80, 0.75, 0.90],
    "bedroom_2": [0.75, 0.80, 0.90],
    "bedroom_3": [0.70, 0.85, 0.90],
    "bedroom_4": [0.70, 0.85, 0.85],
    "bedroom_5": [0.70, 0.80, 0.85],
    "hall": [0.95, 0.90, 0.75],
    "living": [0.95, 0.90, 0.75],
    "living_room": [0.95, 0.90, 0.75],
    "kitchen": [0.80, 0.95, 0.80],
    "dining": [0.95, 0.85, 0.70],
    "dining_room": [0.95, 0.85, 0.70],
    "bathroom": [0.70, 0.85, 0.95],
    "master_bathroom": [0.65, 0.80, 0.95],
    "common_bathroom": [0.70, 0.85, 0.95],
    "toilet": [0.75, 0.88, 0.95],
    "balcony": [0.75, 0.95, 0.80],
    "study": [0.90, 0.85, 0.70],
    "pooja_room": [0.95, 0.88, 0.65],
    "garage": [0.80, 0.80, 0.80],
    "passage": [0.90, 0.90, 0.85],
    "corridor": [0.90, 0.90, 0.85],
    "store": [0.85, 0.82, 0.78],
    "utility": [0.82, 0.85, 0.78],
}
_DEFAULT_COLOR = [0.88, 0.88, 0.88]


def _room_color(name: str) -> List[float]:
    """Return RGBA color for a room by matching its base type."""
    key = name.split("_s")[0]  # strip story suffix
    parts = key.rsplit("_", 1)
    candidates = [key, parts[0] if len(parts) == 2 and parts[1].isdigit() else key]
    for c in candidates:
        if c in _ROOM_COLORS:
            return _ROOM_COLORS[c] + [1.0]
    # try prefix match
    for k, v in _ROOM_COLORS.items():
        if key.startswith(k):
            return v + [1.0]
    return _DEFAULT_COLOR + [1.0]


def _swap_yz(v: Vertex) -> Vertex:
    """Convert from Z-up (XYZ) to Y-up (XZY) for glTF standard orientation."""
    x, y, z = v
    return (x, z, -y)


def _normals_for_mesh(m: Mesh) -> List[Vertex]:
    # compute normals in original space then swap
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
        raw = (n[0] / mag, n[1] / mag, n[2] / mag) if mag > 0 else (0.0, 0.0, 1.0)
        result.append(_swap_yz(raw))
    return result


def _pad4(b: bytes) -> bytes:
    r = len(b) % 4
    return b + b"\x00" * ((4 - r) % 4)


def pack_glb_multi_mesh(meshes: List[Mesh]) -> bytes:
    """
    Pack named Mesh objects into a single GLB 2.0 file.
    - Y-up orientation (swap Y↔Z so floor lies on XZ plane)
    - Per-room colored PBR materials
    """
    if not meshes:
        raise ValueError("No meshes to pack")

    bin_chunks: List[bytes] = []
    buffer_views = []
    accessors = []
    gltf_meshes = []
    gltf_materials = []
    nodes = []
    offset = 0

    for m in meshes:
        if not m.verts or not m.tris:
            continue

        # Apply Y-up swap to all vertices
        verts_yup = [_swap_yz(v) for v in m.verts]
        norms = _normals_for_mesh(m)

        pos_buf = _pad4(b"".join(struct.pack("<fff", *v) for v in verts_yup))
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

        # Compute POSITION min/max for accessor (required by spec)
        xs = [v[0] for v in verts_yup]
        ys = [v[1] for v in verts_yup]
        zs = [v[2] for v in verts_yup]

        acc_pos = len(accessors)
        accessors.append(
            {
                "bufferView": bv_pos,
                "componentType": 5126,
                "count": len(verts_yup),
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )
        acc_nor = len(accessors)
        accessors.append({"bufferView": bv_nor, "componentType": 5126, "count": len(verts_yup), "type": "VEC3"})
        acc_idx = len(accessors)
        accessors.append({"bufferView": bv_idx, "componentType": 5125, "count": len(m.tris) * 3, "type": "SCALAR"})

        # Material
        mat_idx = len(gltf_materials)
        rgba = _room_color(m.name)
        gltf_materials.append(
            {
                "name": f"{m.name}_mat",
                "pbrMetallicRoughness": {
                    "baseColorFactor": rgba,
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.8,
                },
                "doubleSided": True,
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
                        "material": mat_idx,
                    }
                ],
            }
        )
        nodes.append({"mesh": mesh_idx, "name": m.name})

    if not gltf_meshes:
        raise ValueError("All meshes were empty")

    bin_data = b"".join(bin_chunks)

    gltf = {
        "asset": {"version": "2.0", "generator": "BHIV-RoomGeometry-v4"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": gltf_meshes,
        "materials": gltf_materials,
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
