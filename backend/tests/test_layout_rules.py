"""Standard layout rules (the fallback when the AI gives nothing usable). No network, no database."""

import time
from collections import Counter

import pytest

from app.catalog import ROOM_DEFAULTS
from app.layout import check_alternative, footprint, room_for
from app.layout_rules import rule_layout
from tests.test_layout import BED, bedroom


def room(geometry=None, existing=(), keep=True, new=None):
    return room_for(geometry or bedroom(), "r1", list(existing), keep, Counter(new or {}))


def by_type(pieces, kind):
    return [p for p in pieces if p["type"] == kind]


@pytest.mark.parametrize("room_type", sorted(t for t, items in ROOM_DEFAULTS.items() if items))
@pytest.mark.parametrize("variant", [0, 1])
def test_every_room_types_starting_list_gets_a_valid_layout(room_type, variant):
    geometry = bedroom().model_copy(update={"rooms": [r.model_copy(update={"type": room_type}) if r.id == "r1" else r for r in bedroom().rooms]})
    r = room(geometry, new=dict(ROOM_DEFAULTS[room_type]))
    pieces = rule_layout(r, variant)
    assert pieces is not None
    assert check_alternative(r, [{"ref": p.get("id", ""), **p} for p in pieces]) == pieces, "the real check accepts it unchanged"


def test_bed_has_its_head_on_a_wall_without_a_door_and_tables_beside_it():
    pieces = rule_layout(room(new={"double-bed": 1, "bedside-table": 2, "wardrobe": 1}), 0)
    bed = by_type(pieces, "double-bed")[0]
    tables = by_type(pieces, "bedside-table")
    bed_box = footprint(bed["x"], bed["y"], bed["w"], bed["d"], bed["rotation"])
    assert bed["rotation"] != 180, "the door is on the south wall"
    for table in tables:
        box = footprint(table["x"], table["y"], table["w"], table["d"], table["rotation"])
        assert table["rotation"] == bed["rotation"], "the tables stand against the same wall"
        assert min(abs(box.x1 - bed_box.x0), abs(bed_box.x1 - box.x0), abs(box.y1 - bed_box.y0), abs(bed_box.y1 - box.y0)) <= 10


def test_the_two_variants_differ():
    r = room(new={"double-bed": 1, "wardrobe": 1})
    assert rule_layout(r, 0) != rule_layout(r, 1)


def test_kept_pieces_stay_and_moved_pieces_are_placed():
    kept = rule_layout(room(bedroom([BED]), existing=["bed"], keep=True, new={"wardrobe": 1}), 0)
    assert [p["type"] for p in kept] == ["wardrobe"], "the kept bed is not returned or moved"
    moved = rule_layout(room(bedroom([BED]), existing=["bed"], keep=False, new={"bedside-table": 2}), 0)
    assert [p.get("id") for p in moved if p["type"] == "double-bed"] == ["bed"]


def test_extra_companion_pieces_are_placed_too():
    """A desk takes one chair and a bed two tables; the extra chairs and tables still get a place."""
    big = bedroom(openings=[], size=(820, 620))
    pieces = rule_layout(room(big, new={"desk": 1, "chair": 3, "double-bed": 1, "bedside-table": 3}), 0)
    assert pieces is not None
    assert Counter(p["type"] for p in pieces) == Counter({"chair": 3, "bedside-table": 3, "desk": 1, "double-bed": 1})


def test_an_existing_piece_keeps_its_own_size_even_if_not_in_the_catalog():
    """The editor accepts any piece type and size; moving one must neither crash nor resize it."""
    piano = {"id": "piano", "type": "grand-piano", "x": 200, "y": 200, "w": 150, "d": 150, "rotation": 0}
    wide_bed = {**BED, "w": 180}
    pieces = rule_layout(room(bedroom([piano, wide_bed]), existing=["piano", "bed"], keep=False), 0)
    assert pieces is not None
    assert {p["id"]: (p["w"], p["d"]) for p in pieces} == {"piano": (150, 150), "bed": (180, 200)}


def test_too_much_furniture_gives_none():
    assert rule_layout(room(new={"double-bed": 4}), 0) is None
    assert rule_layout(room(bedroom(openings=[], size=(80, 80)), new={"chair": 1}), 0) is not None
    assert rule_layout(room(bedroom(openings=[], size=(80, 80)), new={"wardrobe": 1}), 0) is None


def test_the_largest_request_finishes_quickly():
    r = room(bedroom(openings=[], size=(1020, 820)), new={"chair": 12, "desk": 4, "armchair": 4})
    started = time.monotonic()
    pieces = rule_layout(r, 0)
    assert pieces is not None and len(pieces) == 20
    assert time.monotonic() - started < 5
