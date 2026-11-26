import assert from "node:assert/strict";
import { test } from "node:test";

import * as P from "../js/plan.js";

const deepFreeze = (value) => {
  if (value && typeof value === "object") Object.values(value).forEach(deepFreeze);
  return Object.freeze(value);
};

const twoRooms = () =>
  deepFreeze(
    P.fromRooms([
      { name: "Living room", type: "living", width: 500, length: 400 },
      { name: "Bedroom", type: "bedroom", width: 350, length: 300 },
    ]),
  );

test("wizard rooms become four tagged walls each, with the entered dimensions", () => {
  const plan = twoRooms();
  assert.equal(plan.schema, 1);
  assert.equal(plan.units, "cm");
  assert.deepEqual(plan.rooms.map((r) => r.name), ["Living room", "Bedroom"]);
  assert.equal(plan.walls.length, 8);
  const [living, bedroom] = plan.rooms.map((room) => P.roomBox(plan, room.id));
  assert.deepEqual([living.w, living.h], [500, 400]);
  assert.deepEqual([bedroom.w, bedroom.h], [350, 300]);
  assert.equal(bedroom.x, living.x + living.w, "rooms are laid out side by side");
  assert.equal(new Set(plan.walls.map((w) => w.id)).size, 8);
});

test("a wizard room can come with a door and a window on chosen sides", () => {
  const plan = P.fromRooms([
    { name: "Bedroom", type: "bedroom", width: 400, length: 300, openings: [{ type: "door", side: "south", at: 0.25 }, { type: "window", side: "north", at: 0.5 }] },
    { name: "Store", type: "other", width: 200, length: 200 },
  ]);
  const [north, , south] = plan.walls;
  const door = plan.openings.find((o) => o.type === "door");
  const window = plan.openings.find((o) => o.type === "window");
  assert.equal(plan.openings.length, 2, "a room without openings gets none");
  assert.equal(door.wallId, south.id);
  assert.equal(door.offset, 400 * 0.25 - 40, "centred a quarter along the wall");
  assert.equal(window.wallId, north.id);
  assert.equal(window.offset + window.width / 2, 200);
});

test("an opening wider than a short wizard wall is clamped to fit", () => {
  const plan = P.fromRooms([{ name: "Closet", type: "other", width: 60, length: 60, openings: [{ type: "window", side: "north", at: 0.5 }] }]);
  const [opening] = plan.openings;
  assert.equal(opening.width, 60);
  assert.equal(opening.offset, 0);
});

test("room furniture is what stands inside the room's walls", () => {
  let plan = twoRooms();
  plan = P.addFurniture(plan, { type: "sofa", w: 200, d: 90 }, 250, 200); // living room
  plan = P.addFurniture(plan, { type: "double-bed", w: 160, d: 200 }, 650, 150); // bedroom
  const [living, bedroom] = plan.rooms;
  assert.deepEqual(P.roomFurniture(plan, living.id).map((f) => f.type), ["sofa"]);
  assert.deepEqual(P.roomFurniture(plan, bedroom.id).map((f) => f.type), ["double-bed"]);
  assert.deepEqual(P.roomFurniture(plan, "missing"), []);
});

test("applying a layout moves, adds and removes furniture without touching other rooms", () => {
  let plan = twoRooms();
  plan = P.addFurniture(plan, { type: "sofa", w: 200, d: 90 }, 250, 200);
  plan = P.addFurniture(plan, { type: "chair", w: 45, d: 45 }, 100, 100);
  plan = deepFreeze(P.addFurniture(plan, { type: "double-bed", w: 160, d: 200 }, 650, 150));
  const [sofa, chair, bed] = plan.furniture;
  const next = P.applyLayout(plan, {
    remove: [chair.id],
    items: [
      { id: sofa.id, type: "sofa", x: 300, y: 330, w: 200, d: 90, rotation: 180 },
      { type: "tv-unit", x: 250, y: 40, w: 160, d: 45, rotation: 0 },
      { id: "not-there", type: "sofa", x: 0, y: 0, w: 1, d: 1, rotation: 0 },
    ],
  });
  assert.deepEqual(next.furniture.map((f) => f.type), ["sofa", "double-bed", "tv-unit"]);
  assert.deepEqual(next.furniture[0], { ...sofa, x: 300, y: 330, rotation: 180 });
  assert.equal(next.furniture[1], bed, "a piece in another room is the same object");
  assert.ok(next.furniture[2].id && next.furniture[2].id !== sofa.id);
  assert.notEqual(next, plan);
  // Undo after applying returns exactly the plan before it.
  const h = P.history.undo(P.history.push(P.history.start(plan), next));
  assert.equal(h.present, plan);
});

test("an empty layout changes nothing but what it removes", () => {
  const plan = deepFreeze(P.addFurniture(twoRooms(), { type: "sofa", w: 200, d: 90 }, 250, 200));
  assert.deepEqual(P.applyLayout(plan, { items: [] }).furniture, plan.furniture);
  assert.deepEqual(P.applyLayout(plan, { remove: [plan.furniture[0].id], items: [] }).furniture, []);
});

test("rooms wrap onto a new row instead of forming one endless strip", () => {
  const plan = P.fromRooms(Array.from({ length: 6 }, (_, i) => ({ name: `R${i}`, type: "other", width: 500, length: 400 })));
  const ys = new Set(plan.rooms.map((room) => P.roomBox(plan, room.id).y));
  assert.ok(ys.size > 1);
});

test("an opening is centred where it was dropped and clamped inside its wall", () => {
  const plan = twoRooms();
  const wall = plan.walls[0];
  const centred = P.addOpening(plan, wall.id, "door", 250);
  assert.deepEqual(
    centred.openings.map(({ wallId, type, offset, width }) => ({ wallId, type, offset, width })),
    [{ wallId: wall.id, type: "door", offset: 210, width: 80 }],
  );
  const atEnd = P.addOpening(plan, wall.id, "window", 9999);
  assert.equal(atEnd.openings[0].offset + atEnd.openings[0].width, P.wallLength(wall));
});

test("moving a room moves its walls and keeps its openings attached", () => {
  const start = twoRooms();
  const room = start.rooms[0];
  const withDoor = deepFreeze(P.addOpening(start, start.walls[0].id, "door", 100));
  const moved = P.translate(withDoor, "rooms", room.id, 30, -20);
  const before = P.roomBox(withDoor, room.id);
  const after = P.roomBox(moved, room.id);
  assert.deepEqual([after.x - before.x, after.y - before.y, after.w, after.h], [30, -20, before.w, before.h]);
  assert.deepEqual(moved.openings, withDoor.openings);
  assert.deepEqual(P.roomBox(moved, start.rooms[1].id), P.roomBox(start, start.rooms[1].id), "other rooms stay put");
});

test("shortening a wall keeps its openings inside it", () => {
  const start = twoRooms();
  const wall = start.walls[0];
  const withWindow = deepFreeze(P.addOpening(start, wall.id, "window", 440));
  const shorter = P.setWallLength(withWindow, wall.id, 200);
  const [opening] = shorter.openings;
  assert.equal(P.wallLength(shorter.walls[0]), 200);
  assert.ok(opening.offset >= 0 && opening.offset + opening.width <= 200);
});

test("a wall cannot be shrunk to nothing", () => {
  const plan = twoRooms();
  const wall = plan.walls[0];
  assert.equal(P.moveWallEnd(plan, wall.id, 2, wall.x1, wall.y1), plan);
  assert.equal(P.setWallLength(plan, wall.id, 0), plan);
});

test("removing a wall removes its openings; removing a room removes its walls", () => {
  const start = twoRooms();
  const withDoor = deepFreeze(P.addOpening(start, start.walls[0].id, "door", 100));
  assert.equal(P.remove(withDoor, "walls", start.walls[0].id).openings.length, 0);
  const withoutRoom = P.remove(withDoor, "rooms", start.rooms[0].id);
  assert.equal(withoutRoom.rooms.length, 1);
  assert.equal(withoutRoom.walls.length, 4);
  assert.equal(withoutRoom.openings.length, 0);
});

test("furniture can be added, patched and rotated without negative angles", () => {
  const start = twoRooms();
  const placed = deepFreeze(P.addFurniture(start, { type: "sofa", w: 200, d: 90 }, 123, 77));
  const [sofa] = placed.furniture;
  assert.deepEqual({ ...sofa, id: null }, { id: null, type: "sofa", x: 120, y: 80, w: 200, d: 90, rotation: 0 });
  const rotated = P.patch(placed, "furniture", sofa.id, { rotation: -90 });
  assert.equal(rotated.furniture[0].rotation, 270);
  assert.equal(P.patch(placed, "furniture", sofa.id, { w: -5 }).furniture[0].w, 200, "invalid sizes are ignored");
});

test("nearest wall is found within reach and ignored beyond it", () => {
  const plan = twoRooms();
  const top = plan.walls[0];
  const hit = P.nearestWall(plan, { x: top.x1 + 100, y: top.y1 + 12 }, 30);
  assert.equal(hit.wall.id, top.id);
  assert.equal(Math.round(hit.along), 100);
  assert.equal(P.nearestWall(plan, { x: top.x1 + 100, y: top.y1 - 500 }, 30), null);
});

test("history undoes and redoes, and a new change clears redo", () => {
  const a = twoRooms();
  const b = P.addFurniture(a, { type: "chair", w: 45, d: 45 }, 0, 0);
  const c = P.addFurniture(b, { type: "chair", w: 45, d: 45 }, 100, 0);
  let h = P.history.push(P.history.push(P.history.start(a), b), c);
  h = P.history.undo(h);
  assert.equal(h.present, b);
  h = P.history.undo(P.history.undo(h));
  assert.equal(h.present, a, "undo past the start is a no-op");
  h = P.history.redo(h);
  assert.equal(h.present, b);
  h = P.history.push(h, a);
  assert.equal(P.history.redo(h).present, a, "redo is cleared by a new change");
});

test("duplicating furniture makes an offset copy with its own id", () => {
  const placed = deepFreeze(P.addFurniture(twoRooms(), { type: "sofa", w: 200, d: 90 }, 100, 100));
  const [original, copy] = P.duplicateFurniture(placed, placed.furniture[0].id).furniture;
  assert.notEqual(copy.id, original.id);
  assert.deepEqual({ ...copy, id: original.id }, { ...original, x: 120, y: 120 });
});

test("areas are reported in square metres and stored plans are recognised", () => {
  const plan = twoRooms();
  assert.equal(P.planArea(plan), 20 + 10.5);
  assert.equal(P.metres(455), "4.55");
  assert.ok(P.isPlan(plan));
  assert.ok(!P.isPlan({ schema: 1, rooms: [] }));
  assert.ok(!P.isPlan(null));
});

test("a room disappears with its last wall, and a zero move changes nothing", () => {
  const start = twoRooms();
  const room = start.rooms[0];
  const stripped = start.walls.filter((wall) => wall.roomId === room.id).reduce((plan, wall) => P.remove(plan, "walls", wall.id), start);
  assert.deepEqual(stripped.rooms.map((r) => r.id), [start.rooms[1].id]);
  assert.equal(P.remove(start, "walls", start.walls[0].id).rooms.length, 2, "a room with walls left stays");
  assert.equal(P.translate(start, "rooms", room.id, 0, 0), start);
});
