"""Standard layouts made by a few interior-design habits: the fallback when the AI gives no usable layout.

Every piece is placed with check_alternative (backend/app/layout.py) as the judge, so a rule layout obeys the same
limits as an AI one. The habits: the bed's head against a quiet wall with bedside tables either side; the sofa
against a wall facing the TV unit, the coffee table between them and armchairs beside; the desk at a window with
its chair; kitchen fixtures in a row from a corner, turning the corner when the wall is full; bath and shower in
corners; the dining table in the middle; everything else against the free walls. The rules know nothing of the
brief; they are a safe default, not a design.

A piece "against a wall" has its back to it: north rotation 0, south 180, west 270, east 90.
"""

from collections import Counter
from dataclasses import replace

from app.catalog import FURNITURE_BY_TYPE
from app.layout import LayoutError, Room, check_alternative

SIDES = ("north", "east", "south", "west")
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
ROTATION = {"north": 0, "south": 180, "west": 270, "east": 90}
STEP_CM = 10
BEDS = ("double-bed", "single-bed")
KITCHEN_ORDER = ("sink", "kitchen-counter", "stove", "fridge")  # sink and worktop together, then round the corner
WET = ("bathtub", "shower", "toilet", "vanity")


class _Planner:
    def __init__(self, room: Room, variant: int):
        self.room, self.variant, self.placed = room, variant, []

    def length(self, side: str) -> float:
        return self.room.width if side in ("north", "south") else self.room.depth

    def pose(self, ref: str, kind: str, side: str, t: float, off: float = 0, facing: str | None = None) -> dict:
        """A piece with its back to `side`, centred `t` cm along it, `off` cm out from the wall."""
        d, r = FURNITURE_BY_TYPE[kind]["d"], self.room
        x, y = {
            "north": (t, d / 2 + off),
            "south": (t, r.depth - d / 2 - off),
            "west": (d / 2 + off, t),
            "east": (r.width - d / 2 - off, t),
        }[side]
        return {"ref": ref, "type": kind, "x": x, "y": y, "rotation": ROTATION[facing or side]}

    def put(self, item: dict) -> bool:
        """Keeps the piece if the layout so far, with it, passes the real check."""
        items = [*self.placed, item]
        partial = replace(
            self.room,
            movable={i["ref"]: self.room.movable[i["ref"]] for i in items if i["ref"]},
            new=Counter(i["type"] for i in items if not i["ref"]),
        )
        try:
            check_alternative(partial, items)
        except LayoutError:
            return False
        self.placed.append(item)
        return True

    def along_wall(self, ref: str, kind: str, sides, centre: float | None = None, off: float = 0, from_corner: bool = False):
        """Against the first wall in `sides` with room, as near `centre` (or the wall's start) as possible."""
        w = FURNITURE_BY_TYPE[kind]["w"]
        for side in sides:
            length = self.length(side)
            target = centre if centre is not None else (w / 2 if from_corner else length / 2)
            for t in sorted(range(int(w / 2), int(length - w / 2) + 1, STEP_CM), key=lambda v: abs(v - target)):
                if self.put(self.pose(ref, kind, side, t, off)):
                    return side, t
        return None, None

    def has(self, side: str, kind: str) -> bool:
        return any(o["side"] == side and o["type"] == kind for o in self.room.openings)

    def ranked(self, avoid_window: bool = False) -> list[str]:
        """Walls for a big piece: no door first, then (if asked) no window, then the longest.
        The second variant leads with the next-best wall, so the two layouts differ."""
        order = sorted(SIDES, key=lambda s: (self.has(s, "door"), avoid_window and self.has(s, "window"), -self.length(s)))
        return order[1:] + order[:1] if self.variant else order

    def window_walls(self) -> list[str]:
        return [s for s in SIDES if self.has(s, "window")] + [s for s in SIDES if not self.has(s, "window")]


def rule_layout(room: Room, variant: int) -> list[dict] | None:
    """A standard layout (room-local pieces, as check_alternative returns them), or None if the rules cannot fit
    every requested piece. `variant` 0 and 1 start from different walls."""
    p = _Planner(room, variant)
    todo = [(piece["id"], piece["type"]) for piece in room.movable.values()] + [("", t) for t, n in room.new.items() for _ in range(n)]

    def take(kinds, limit=None) -> list[tuple[str, str]]:
        """Removes and returns the pieces of these kinds still to place, at most `limit` of them."""
        found = [item for item in todo if item[1] in kinds][:limit]
        for item in found:
            todo.remove(item)
        return found

    def later(item):  # a companion piece that did not fit by its partner is placed with the rest
        todo.append(item)

    for ref, kind in take(BEDS):
        side, t = p.along_wall(ref, kind, p.ranked(avoid_window=True))
        if side is None:
            return None
        bed_w = FURNITURE_BY_TYPE[kind]["w"]
        for (tref, tkind), sign in zip(take(("bedside-table",), 2), (-1, 1)):
            if not p.put(p.pose(tref, tkind, side, t + sign * (bed_w / 2 + FURNITURE_BY_TYPE[tkind]["w"] / 2 + 5))):
                later((tref, tkind))

    for ref, kind in take(("sofa",)):
        side, t = p.along_wall(ref, kind, p.ranked())
        if side is None:
            return None
        gap = FURNITURE_BY_TYPE[kind]["d"] + 45  # sofa depth plus legroom to the coffee table
        for tref, tkind in take(("tv-unit",), 1):
            if p.along_wall(tref, tkind, [OPPOSITE[side]], centre=t)[0] is None:
                later((tref, tkind))
        for cref, ckind in take(("coffee-table",), 1):
            if not p.put(p.pose(cref, ckind, side, t, off=gap, facing=side)):
                later((cref, ckind))
        across = [s for s in SIDES if s not in (side, OPPOSITE[side])]
        for (aref, akind), sign in zip(take(("armchair",), 2), (1, -1)):
            near = gap + FURNITURE_BY_TYPE[akind]["d"] / 2  # level with the coffee table, from the sofa's wall
            centre = near if side in ("north", "west") else p.length(across[0]) - near
            if p.along_wall(aref, akind, across[::sign], centre=centre)[0] is None:
                later((aref, akind))

    for ref, kind in take(("desk",)):
        side, t = p.along_wall(ref, kind, p.window_walls())
        if side is None:
            later((ref, kind))
            continue
        for cref, ckind in take(("chair",), 1):
            if not p.put(p.pose(cref, ckind, side, t, off=FURNITURE_BY_TYPE[kind]["d"] + 5, facing=OPPOSITE[side])):
                later((cref, ckind))

    row = take(KITCHEN_ORDER)
    if row:
        side = p.ranked()[0]
        corner_wall = "west" if side in ("north", "south") else "north"
        cursor = 0
        for ref, kind in sorted(row, key=lambda item: KITCHEN_ORDER.index(item[1])):
            w = FURNITURE_BY_TYPE[kind]["w"]
            if p.put(p.pose(ref, kind, side, cursor + w / 2)):
                cursor += w
                continue
            start = w / 2 if side in ("north", "west") else p.length(corner_wall) - w / 2
            if p.along_wall(ref, kind, [corner_wall], centre=start)[0] is None:
                later((ref, kind))

    for ref, kind in sorted(take(WET), key=lambda item: WET.index(item[1])):
        if p.along_wall(ref, kind, p.ranked(), from_corner=kind in ("bathtub", "shower"))[0] is None:
            return None

    for ref, kind in take(("dining-table",)):
        r, spec = p.room, FURNITURE_BY_TYPE[kind]
        if not p.put({"ref": ref, "type": kind, "x": r.width / 2, "y": r.depth / 2, "rotation": 0}):
            later((ref, kind))
            continue
        seats = [(r.width / 2 + dx, r.depth / 2 + sy * (spec["d"] / 2 + 30), 180 if sy < 0 else 0) for dx in (-40, 40) for sy in (-1, 1)]
        for (cref, ckind), (x, y, rotation) in zip(take(("chair",), len(seats)), seats):
            if not p.put({"ref": cref, "type": ckind, "x": x, "y": y, "rotation": rotation}):
                later((cref, ckind))

    todo.sort(key=lambda item: -(FURNITURE_BY_TYPE[item[1]]["w"] * FURNITURE_BY_TYPE[item[1]]["d"]))
    for ref, kind in todo:
        if p.along_wall(ref, kind, p.ranked(avoid_window=kind == "wardrobe"))[0] is None:
            if p.along_wall(ref, kind, SIDES, off=60)[0] is None:  # a second row, leaving a walkway by the wall
                return None
    try:
        return check_alternative(room, p.placed)
    except LayoutError:
        return None
