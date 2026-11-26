"""Layout suggestion logic: the room handed to the model and the checks on its answer. No network, no database."""

import re
from collections import Counter
from pathlib import Path

import pytest

from app.catalog import FURNITURE, ROOM_DEFAULTS
from app.layout import DOOR_CLEARANCE_CM, LayoutError, check_alternative, footprint, room_for, to_plan
from app.schemas import Geometry

CATALOG_JS = Path(__file__).resolve().parents[2] / "frontend" / "js" / "catalog.js"


def bedroom(furniture=(), openings=None, size=(420, 370)):
    """A wizard-style room: 20 cm walls on the centre lines 0..W x 0..H, so the inside is (W-20) x (H-20)."""
    w, h = size
    walls = [
        {"id": "n", "x1": 0, "y1": 0, "x2": w, "y2": 0},
        {"id": "e", "x1": w, "y1": 0, "x2": w, "y2": h},
        {"id": "s", "x1": w, "y1": h, "x2": 0, "y2": h},
        {"id": "w", "x1": 0, "y1": h, "x2": 0, "y2": 0},
    ]
    if openings is None:  # a door at the south-west corner area, a window in the middle of the north wall
        openings = [{"id": "o1", "wallId": "s", "type": "door", "offset": w - 130, "width": 80}, {"id": "o2", "wallId": "n", "type": "window", "offset": 150, "width": 120}]
    return Geometry.model_validate(
        {
            "schema": 1,
            "units": "cm",
            "rooms": [{"id": "r1", "name": "Bedroom", "type": "bedroom"}, {"id": "r2", "name": "Empty", "type": "other"}],
            "walls": [{**wall, "thickness": 20, "kind": "exterior", "roomId": "r1"} for wall in walls],
            "openings": openings,
            "furniture": list(furniture),
        }
    )


BED = {"id": "bed", "type": "double-bed", "x": 210, "y": 120, "w": 160, "d": 200, "rotation": 0}
OUTSIDE = {"id": "far", "type": "sofa", "x": 2000, "y": 2000, "w": 200, "d": 90, "rotation": 0}


def room(geometry=None, existing=(), keep=True, new=None):
    return room_for(geometry or bedroom([BED, OUTSIDE]), "r1", list(existing), keep, Counter(new or {}))


def piece(type_, x, y, rotation=0, ref=""):
    return {"ref": ref, "type": type_, "x": x, "y": y, "rotation": rotation}


# ---- the room ----------------------------------------------------------------------------------------------------


def test_room_is_the_inside_of_its_walls_with_its_openings():
    r = room()
    assert (r.width, r.depth, r.origin) == (400, 350, (10, 10))
    assert r.openings == [{"type": "door", "side": "south", "from": 40, "to": 120}, {"type": "window", "side": "north", "from": 140, "to": 260}]
    assert len(r.door_zones) == 1
    zone = r.door_zones[0]
    assert (zone.x0, zone.x1, zone.y1 - zone.y0, zone.y1) == (40, 120, DOOR_CLEARANCE_CM, 350)


def test_a_room_without_openings_has_no_door_zone():
    r = room(bedroom(openings=[]))
    assert r.openings == [] and r.door_zones == []


def test_kept_pieces_are_fixed_and_moved_pieces_are_movable():
    kept = room(existing=["bed"], keep=True)
    assert [f["id"] for f in kept.fixed] == ["bed"] and kept.movable == {}
    assert (kept.fixed[0]["x"], kept.fixed[0]["y"]) == (200, 110), "positions are room-local"
    moving = room(existing=["bed"], keep=False)
    assert moving.fixed == [] and list(moving.movable) == ["bed"]
    assert room(existing=[]).fixed == [], "a piece the client unticked is not an obstacle"


@pytest.mark.parametrize(
    "room_id, existing",
    [("missing", []), ("r2", []), ("r1", ["far"]), ("r1", ["nope"]), ("r1", ["bed", "bed"])],
    ids=["unknown room", "room without walls", "piece in another room", "unknown piece", "piece twice"],
)
def test_bad_requests_are_refused(room_id, existing):
    with pytest.raises(LayoutError):
        room_for(bedroom([BED, OUTSIDE]), room_id, existing, True, Counter())


def test_a_room_thinner_than_its_walls_cannot_be_furnished():
    with pytest.raises(LayoutError, match="too small"):
        room(bedroom(openings=[], size=(15, 300)))


# ---- the answer --------------------------------------------------------------------------------------------------


def test_a_good_answer_passes_and_converts_back_to_the_plan():
    r = room(existing=["bed"], keep=False, new={"bedside-table": 2, "wardrobe": 1})
    answer = [
        piece("double-bed", 200, 110, ref="bed"),
        piece("bedside-table", 95, 30),
        piece("bedside-table", 305, 30),
        piece("wardrobe", 370, 200, rotation=90),
    ]
    placed = check_alternative(r, answer)
    assert placed[0] == {"id": "bed", "type": "double-bed", "x": 200, "y": 110, "w": 160, "d": 200, "rotation": 0}
    assert placed[3]["w"] == 180 and placed[3]["d"] == 60, "sizes come from the catalog, not the model"
    assert to_plan(r, placed)[0]["x"] == 210 and to_plan(r, placed)[0]["y"] == 120


@pytest.mark.parametrize(
    "answer, problem",
    [
        ([piece("wardrobe", 395, 200)], "inside the room"),  # sticks out of the east wall
        ([piece("wardrobe", 130, 300)], "blocks a door"),  # in front of the door
        ([piece("wardrobe", 200, 100)], "overlap"),  # on the kept bed
        ([piece("wardrobe", 300, 300, rotation=45)], "rotation"),
        ([piece("wardrobe", float("nan"), 300)], "position"),
        ([piece("throne", 300, 300)], "catalog"),
        ([piece("double-bed", 200, 110, ref="bed")], "not asked for"),  # the bed is kept, not movable
        ([], "exactly the requested"),  # the wardrobe is missing
        ([piece("wardrobe", 370, 200, 90), piece("wardrobe", 220, 260)], "exactly the requested"),  # one too many
    ],
)
def test_bad_answers_are_refused(answer, problem):
    r = room(existing=["bed"], keep=True, new={"wardrobe": 1})
    with pytest.raises(LayoutError, match=problem):
        check_alternative(r, answer)


def test_two_new_pieces_may_not_overlap_each_other_but_may_touch():
    r = room(bedroom(openings=[]), new={"chair": 2})
    assert len(check_alternative(r, [piece("chair", 100, 100), piece("chair", 145, 100)])) == 2  # edges touch
    with pytest.raises(LayoutError, match="overlap"):
        check_alternative(r, [piece("chair", 100, 100), piece("chair", 130, 100)])


def test_a_moved_piece_is_placed_once_and_must_be_placed():
    r = room(existing=["bed"], keep=False)
    with pytest.raises(LayoutError):
        check_alternative(r, [piece("double-bed", 200, 110, ref="bed"), piece("double-bed", 200, 110, ref="bed")])
    with pytest.raises(LayoutError, match="exactly the requested"):
        check_alternative(r, [])


def test_nothing_fits_in_the_smallest_room():
    r = room(bedroom(openings=[], size=(80, 80)), new={"double-bed": 1})
    with pytest.raises(LayoutError, match="inside the room"):
        check_alternative(r, [piece("double-bed", 30, 30)])


def test_the_largest_request_is_checked_piece_by_piece():
    big = bedroom(openings=[], size=(2020, 2020))
    r = room(big, new={"chair": 20})
    answer = [piece("chair", 50 + 100 * (i % 10), 50 + 100 * (i // 10)) for i in range(20)]
    assert len(check_alternative(r, answer)) == 20


def test_footprint_turns_with_the_piece():
    sides = lambda r: [round(v, 6) for v in (r.x0, r.y0, r.x1, r.y1)]  # noqa: E731
    assert sides(footprint(0, 0, 200, 90, 0)) == sides(footprint(0, 0, 200, 90, 180)) == [-100, -45, 100, 45]
    turned = footprint(0, 0, 200, 90, 90)
    assert (round(turned.x1 - turned.x0), round(turned.y1 - turned.y0)) == (90, 200)


# ---- the catalog -------------------------------------------------------------------------------------------------


def test_backend_furniture_matches_the_editor_catalog():
    """The editor (frontend/js/catalog.js) and the layout check must agree on every piece and its size."""
    entries = re.findall(r'\{ type: "([a-z0-9-]+)", label: "[^"]+", group: "[^"]+", w: (\d+), d: (\d+)(, review: true)? \}', CATALOG_JS.read_text())
    frontend = [(t, int(w), int(d), bool(review)) for t, w, d, review in entries]
    backend = [(f["type"], f["w"], f["d"], bool(f.get("review"))) for f in FURNITURE]
    assert frontend == backend


def test_room_defaults_use_catalog_furniture():
    types = {f["type"] for f in FURNITURE}
    assert all(t in types and 1 <= n <= 10 for items in ROOM_DEFAULTS.values() for t, n in items)
