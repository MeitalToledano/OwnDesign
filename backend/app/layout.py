"""Furniture-layout suggestions: the room a model is asked to furnish, and the deterministic check of its answer.

Coordinates exchanged with the model are room-local: centimetres from the inside top-left corner of the room
(inside the walls), x to the right (east), y downward (south). A room is the bounding rectangle of its walls.
That is exact for wizard rooms (four straight walls) and only an approximation once walls are moved or angled;
upgrade when rooms get real outlines. Door clearance is checked for walls parallel to the axes only, for the
same reason.
"""

import math
from collections import Counter
from dataclasses import dataclass

from app.catalog import FURNITURE_BY_TYPE
from app.schemas import Geometry

ROTATIONS = (0, 90, 180, 270)
DOOR_CLEARANCE_CM = 90  # kept free in front of every door, across its full width
EPS = 0.5  # cm: touching edges and rounding are not overlaps


class LayoutError(ValueError):
    """A request or an answer that cannot be laid out. The message is safe to show to the user."""


@dataclass(frozen=True)
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def overlaps(self, other: "Rect") -> bool:
        return self.x0 < other.x1 - EPS and other.x0 < self.x1 - EPS and self.y0 < other.y1 - EPS and other.y0 < self.y1 - EPS

    def within(self, width: float, depth: float) -> bool:
        return self.x0 >= -EPS and self.y0 >= -EPS and self.x1 <= width + EPS and self.y1 <= depth + EPS


def footprint(x: float, y: float, w: float, d: float, rotation: float) -> Rect:
    """The axis-aligned rectangle an item centred at (x, y) covers, for any rotation."""
    angle = math.radians(rotation)
    cos, sin = abs(math.cos(angle)), abs(math.sin(angle))
    half_x = (w * cos + d * sin) / 2
    half_y = (w * sin + d * cos) / 2
    return Rect(x - half_x, y - half_y, x + half_x, y + half_y)


@dataclass(frozen=True)
class Room:
    """What a suggestion for one room is checked against. Every position here is room-local."""

    name: str
    type: str
    origin: tuple[float, float]  # plan position of the room-local (0, 0)
    width: float
    depth: float
    openings: list[dict]  # {type, side, from, to}: along the side, from the room's west or north corner
    door_zones: list[Rect]
    fixed: list[dict]  # existing pieces that stay where they are: {id, type, x, y, w, d, rotation}
    movable: dict[str, dict]  # existing pieces the model places again: id -> {id, type, w, d}
    new: Counter  # catalog type -> how many to add


def _side(wall, box: tuple[float, float, float, float]) -> str | None:
    min_x, min_y, max_x, max_y = box
    if abs(wall.y1 - wall.y2) < EPS:
        return "north" if abs(wall.y1 - min_y) <= abs(wall.y1 - max_y) else "south"
    if abs(wall.x1 - wall.x2) < EPS:
        return "west" if abs(wall.x1 - min_x) <= abs(wall.x1 - max_x) else "east"
    return None


def room_for(geometry: Geometry, room_id: str, existing: list[str], keep_existing: bool, new: Counter) -> Room:
    """The room to furnish. `existing`: ids of the room's current pieces the client keeps in the request."""
    room = next((r for r in geometry.rooms if r.id == room_id), None)
    walls = [wall for wall in geometry.walls if wall.roomId == room_id]
    if room is None or not walls:
        raise LayoutError("The room is not part of the plan")
    xs = [x for wall in walls for x in (wall.x1, wall.x2)]
    ys = [y for wall in walls for y in (wall.y1, wall.y2)]
    box = (min(xs), min(ys), max(xs), max(ys))
    inset = max(wall.thickness for wall in walls) / 2
    origin = (box[0] + inset, box[1] + inset)
    width, depth = box[2] - box[0] - 2 * inset, box[3] - box[1] - 2 * inset
    if width <= 0 or depth <= 0:
        raise LayoutError("The room is too small to furnish")

    # The same membership rule as roomFurniture in frontend/js/plan.js: the centre is inside the walls' box.
    in_room = {f.id: f for f in geometry.furniture if box[0] <= f.x <= box[2] and box[1] <= f.y <= box[3]}
    if len(set(existing)) != len(existing) or any(item_id not in in_room for item_id in existing):
        raise LayoutError("A furniture item is not in this room")

    def local(item) -> dict:
        return {"id": item.id, "type": item.type, "x": item.x - origin[0], "y": item.y - origin[1], "w": item.w, "d": item.d, "rotation": item.rotation}

    openings, zones = [], []
    by_id = {wall.id: wall for wall in walls}
    for opening in geometry.openings:
        wall = by_id.get(opening.wallId)
        side = wall and _side(wall, box)
        if side is None:
            continue
        # Positions along the side, measured from its west (north/south sides) or north (east/west sides) end.
        length = wall.length
        ux, uy = (wall.x2 - wall.x1) / length, (wall.y2 - wall.y1) / length
        ends = [(wall.x1 + ux * t, wall.y1 + uy * t) for t in (opening.offset, opening.offset + opening.width)]
        along = sorted(x - origin[0] for x, _ in ends) if side in ("north", "south") else sorted(y - origin[1] for _, y in ends)
        start, end = max(along[0], 0), min(along[1], width if side in ("north", "south") else depth)
        if end <= start:
            continue
        openings.append({"type": opening.type, "side": side, "from": round(start), "to": round(end)})
        if opening.type == "door":
            zones.append(
                {
                    "north": Rect(start, 0, end, DOOR_CLEARANCE_CM),
                    "south": Rect(start, depth - DOOR_CLEARANCE_CM, end, depth),
                    "west": Rect(0, start, DOOR_CLEARANCE_CM, end),
                    "east": Rect(width - DOOR_CLEARANCE_CM, start, width, end),
                }[side]
            )

    kept = [in_room[item_id] for item_id in existing]
    return Room(
        name=room.name,
        type=room.type,
        origin=origin,
        width=width,
        depth=depth,
        openings=openings,
        door_zones=zones,
        fixed=[local(item) for item in kept] if keep_existing else [],
        movable={} if keep_existing else {item.id: {"id": item.id, "type": item.type, "w": item.w, "d": item.d} for item in kept},
        new=new,
    )


def check_alternative(room: Room, items: list[dict]) -> list[dict]:
    """Checks one answer: {ref, type, x, y, rotation} per piece, ref = an existing id or "" for a new piece.

    Returns the placed pieces in room-local positions, or raises LayoutError naming the first problem.
    The answer must place exactly what was asked: every movable piece once, and the new pieces by type and count.
    """
    placed: list[tuple[Rect, dict]] = []
    obstacles = [footprint(f["x"], f["y"], f["w"], f["d"], f["rotation"]) for f in room.fixed]
    moved: set[str] = set()
    added: Counter = Counter()
    for item in items:
        if not isinstance(item, dict):
            raise LayoutError("The answer has an invalid piece")
        ref = item.get("ref") or ""
        if ref:
            spec = room.movable.get(ref)
            if spec is None or ref in moved:
                raise LayoutError("The answer moves a piece that was not asked for")
            moved.add(ref)
        else:
            spec = FURNITURE_BY_TYPE.get(item.get("type"))
            if spec is None:
                raise LayoutError("The answer uses furniture that is not in the catalog")
            added[spec["type"]] += 1
        x, y, rotation = item.get("x"), item.get("y"), item.get("rotation")
        if rotation not in ROTATIONS or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
            raise LayoutError("The answer has an invalid position or rotation")
        x, y = round(x), round(y)  # checked as it will be stored, so rounding cannot create an overlap
        rect = footprint(x, y, spec["w"], spec["d"], rotation)
        if not rect.within(room.width, room.depth):
            raise LayoutError("A piece does not fit inside the room")
        if any(rect.overlaps(zone) for zone in room.door_zones):
            raise LayoutError("A piece blocks a door")
        if any(rect.overlaps(other) for other in obstacles + [r for r, _ in placed]):
            raise LayoutError("Two pieces overlap")
        piece = {"type": spec["type"], "x": x, "y": y, "w": spec["w"], "d": spec["d"], "rotation": rotation}
        placed.append((rect, {"id": ref, **piece} if ref else piece))
    if moved != set(room.movable) or added != room.new:
        raise LayoutError("The answer does not place exactly the requested furniture")
    return [piece for _, piece in placed]


def to_plan(room: Room, pieces: list[dict]) -> list[dict]:
    """Room-local pieces back in plan coordinates, rounded to whole centimetres."""
    ox, oy = room.origin
    return [{**piece, "x": round(piece["x"] + ox), "y": round(piece["y"] + oy)} for piece in pieces]
