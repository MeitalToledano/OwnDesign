// "Suggest a layout" for the selected room: the client confirms the furniture list, the AI returns up to three
// arrangements, shown as thumbnails and as a dashed preview on the canvas. The plan changes only on Apply.
import { api } from "../api.js";
import { FURNITURE, FURNITURE_BY_TYPE, REVIEW_NOTE } from "../catalog.js";
import * as P from "../plan.js";
import { planThumbnail } from "../thumbnail.js";
import { h, toast } from "../ui.js";

const MAX_PIECES = 20; // the backend's limit (backend/app/schemas.py)
const label = (type) => FURNITURE_BY_TYPE.get(type)?.label ?? type;

export function createLayoutPanel({ editor, projectId, onBusy, onChange }) {
  const node = h("section", { class: "layout-panel stack", "aria-label": "Suggest a layout", tabindex: -1 });
  let catalog = null; // the pending or finished GET /v1/catalog, fetched once
  let defaults = {}; // room type -> [{type, count}]: the usual pieces a new list starts with
  let s = null; // { roomId, keep, existing: Map<id, kept>, counts: Map<type, n>, phase, alternatives, chosen }

  const room = () => editor.plan.rooms.find((r) => r.id === s?.roomId);
  const inRoom = () => P.roomFurniture(editor.plan, s.roomId);
  const kept = () => [...s.existing].filter(([, on]) => on).map(([id]) => id);
  const total = () => kept().length + [...s.counts.values()].reduce((sum, n) => sum + n, 0);

  function fresh(roomId) {
    const plan = editor.plan;
    const pieces = P.roomFurniture(plan, roomId);
    const type = plan.rooms.find((r) => r.id === roomId)?.type;
    // The starting list is the room type's usual pieces, minus what the room already has.
    const counts = new Map();
    for (const { type: kind, count } of defaults[type] ?? []) {
      const missing = count - pieces.filter((piece) => piece.type === kind).length;
      if (missing > 0) counts.set(kind, missing);
    }
    const existing = new Map(pieces.map((piece) => [piece.id, true]));
    return { roomId, type, keep: true, existing, counts, pick: FURNITURE[0].type, phase: "list", alternatives: [], chosen: 0 };
  }

  // When the room's furniture or type changes under the list (an applied layout, an undo, a piece dragged in or
  // out, a new room type), the list starts over from the room as it now is, so it never offers what it has.
  function sync() {
    const ids = inRoom().map((piece) => piece.id);
    const same = room().type === s.type && ids.length === s.existing.size && ids.every((id) => s.existing.has(id));
    if (!same) s = { ...fresh(s.roomId), keep: s.keep };
  }

  function nextPlan(alternative) {
    const remove = [...s.existing].filter(([, on]) => !on).map(([id]) => id);
    return P.applyLayout(editor.plan, { remove, items: alternative.items });
  }

  function update(changes) {
    s = { ...s, ...changes };
    draw();
    onChange();
  }

  async function suggest() {
    const body = {
      room_id: s.roomId,
      keep_existing: s.keep,
      existing: kept(),
      new: [...s.counts].filter(([, n]) => n > 0).map(([type, count]) => ({ type, count })),
      geometry: editor.plan,
    };
    const asked = editor.plan;
    update({ phase: "loading" });
    onBusy(true);
    try {
      const { alternatives } = await api(`/v1/projects/${encodeURIComponent(projectId)}/layout-suggestions`, { method: "POST", body });
      // The inspector stays usable meanwhile (a version could be loaded): never preview onto a different plan.
      if (editor.plan !== asked) {
        update({ phase: "list" });
        return toast("The plan changed while the suggestions were being made. Please ask again.", "error");
      }
      update({ phase: "results", alternatives, chosen: 0 });
    } catch (error) {
      update({ phase: "list" });
      toast(error.message, "error");
    } finally {
      onBusy(false);
    }
  }

  function apply() {
    const alternative = s.alternatives[s.chosen];
    editor.commit(nextPlan(alternative)); // the room's furniture changed, so the list starts over (sync)
    toast(`Applied “${alternative.name}”. Undo to go back, or save the plan to keep it.`);
  }

  function listView() {
    sync();
    const pieces = inRoom();
    const counter = h("span", { class: "code", id: "layout-count" });
    const go = h("button", { type: "button", class: "primary", "data-focus": "suggest", onclick: suggest }, h("span", { class: "icon", "aria-hidden": "true" }, "auto_awesome"), "Suggest layouts");
    const hint = h("p", { class: "muted small" }, "Add a piece, or let the AI move the existing ones.");
    // Typing a count updates only these three, never the whole panel: a redraw between a button's mousedown
    // and its click would swallow the click (type a count, then press "Suggest layouts" straight away).
    const refresh = () => {
      const count = total();
      const nothingToArrange = s.keep && [...s.counts.values()].every((n) => n === 0);
      counter.textContent = `${count} / ${MAX_PIECES} pieces`;
      counter.classList.toggle("error", count > MAX_PIECES);
      go.disabled = count === 0 || count > MAX_PIECES || nothingToArrange;
      hint.hidden = !(nothingToArrange && count > 0);
    };
    const typeCount = (type, input) => {
      const n = Math.max(0, Math.min(MAX_PIECES, Math.round(Number(input.value)) || 0));
      s.counts = new Map(s.counts).set(type, n); // a row at 0 stays until removed; it adds nothing
      refresh();
      onChange();
      return n;
    };
    const remove = (type) => {
      const counts = new Map(s.counts);
      counts.delete(type);
      update({ counts });
    };
    const picker = h("select", { "aria-label": "Furniture to add", "data-focus": "pick", onchange: (event) => (s.pick = event.target.value) },
      FURNITURE.map((item) => h("option", { value: item.type, selected: item.type === s.pick }, `${item.label} (${item.w}×${item.d})`)));
    const addPiece = () => {
      const counts = new Map(s.counts);
      counts.set(s.pick, (counts.get(s.pick) ?? 0) + 1);
      update({ counts });
    };
    refresh();
    return [
      h("p", { class: "muted small" }, "Choose the furniture for this room. The AI suggests where to put it; nothing changes until you apply a suggestion."),
      h("div", { class: "stack-tight" },
        h("span", { class: "label" }, "Already in the room"),
        pieces.length === 0 && h("p", { class: "muted small" }, "Nothing yet."),
        pieces.map((piece) =>
          h("label", { class: "check" },
            h("input", { type: "checkbox", "data-focus": `existing:${piece.id}`, checked: s.existing.get(piece.id), onchange: (event) => update({ existing: new Map(s.existing).set(piece.id, event.target.checked) }) }),
            label(piece.type),
            h("span", { class: "chip" }, "existing"),
          ),
        ),
        pieces.length > 0 && h("p", { class: "muted small" }, "Untick a piece to take it out of the room when you apply."),
      ),
      h("div", { class: "stack-tight" },
        h("span", { class: "label" }, "To add"),
        s.counts.size === 0 && h("p", { class: "muted small" }, "Nothing to add."),
        [...s.counts].map(([type, n]) =>
          h("div", { class: "piece" },
            h("span", { class: "grow" }, label(type)),
            h("input", {
              type: "number", "data-focus": `count:${type}`, min: 0, max: MAX_PIECES, value: n, inputMode: "numeric", "aria-label": `How many: ${label(type)}`,
              oninput: (event) => typeCount(type, event.target),
              onchange: (event) => (event.target.value = typeCount(type, event.target)), // show the clamped value
            }),
            h("button", { type: "button", "data-focus": `remove:${type}`, "aria-label": `Remove ${label(type)}`, onclick: () => remove(type) }, h("span", { class: "icon", "aria-hidden": "true" }, "close")),
          ),
        ),
        h("div", { class: "piece" }, picker, h("button", { type: "button", "data-focus": "add", onclick: addPiece }, "Add")),
      ),
      h("fieldset", { class: "stack-tight" },
        h("legend", { class: "label" }, "Pieces already in the room"),
        h("label", { class: "check" }, h("input", { type: "radio", name: "layout-keep", "data-focus": "keep", checked: s.keep, onchange: () => update({ keep: true }) }), "Keep them where they are"),
        h("label", { class: "check" }, h("input", { type: "radio", name: "layout-keep", "data-focus": "move", checked: !s.keep, onchange: () => update({ keep: false }) }), "Let the AI move them"),
      ),
      h("div", { class: "row between" }, counter, go),
      hint,
    ];
  }

  function resultsView() {
    const walls = editor.plan.walls.filter((wall) => wall.roomId === s.roomId);
    const alternative = s.alternatives[s.chosen];
    const review = P.roomFurniture(nextPlan(alternative), s.roomId).some((item) => FURNITURE_BY_TYPE.get(item.type)?.review);
    return [
      h("p", { class: "muted small" }, `${s.alternatives.length} suggestion${s.alternatives.length === 1 ? "" : "s"}. The chosen one is drawn dashed on the plan.`),
      h("div", { class: "alts", role: "group", "aria-label": "Layout suggestions" },
        s.alternatives.map((alt, i) => {
          const next = nextPlan(alt);
          const preview = { walls, furniture: P.roomFurniture(next, s.roomId) };
          return h("button", { type: "button", class: "alt", "data-focus": `alt:${i}`, "aria-pressed": String(i === s.chosen), onclick: () => update({ chosen: i }) },
            planThumbnail(preview, `Preview of ${alt.name}`),
            h("strong", {}, alt.name),
            // Made by the backend's standard rules because the AI gave nothing usable (or is not set up).
            alt.source === "rules" && h("span", { class: "chip caution" }, "Standard rules"),
            alt.reason && h("span", { class: "muted small" }, alt.reason),
          );
        }),
      ),
      review && h("p", { class: "note" }, REVIEW_NOTE),
      h("div", { class: "row between" },
        h("button", { type: "button", "data-focus": "again", onclick: () => update({ phase: "list" }) }, "Try again"),
        h("div", { class: "row" },
          h("button", { type: "button", onclick: () => update({ phase: "list", alternatives: [] }) }, "Cancel"),
          h("button", { type: "button", class: "primary", onclick: apply }, "Apply"),
        ),
      ),
    ];
  }

  function draw() {
    if (!s || !room()) return node.replaceChildren();
    const body =
      s.phase === "loading"
        ? [h("p", { class: "muted small", role: "status" }, "Arranging the room. This can take up to a minute.")]
        : s.phase === "results"
          ? resultsView()
          : listView();
    // The panel is rebuilt on every change. Focus goes back to the same control, so the next key press reaches it
    // and not the editor's shortcuts (Backspace would otherwise delete the selected room).
    const focused = node.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    node.replaceChildren(h("h3", { class: "label accent" }, "Suggest a layout"), ...body.flat().filter(Boolean));
    if (focused) (node.querySelector(`[data-focus="${CSS.escape(focused)}"]`) ?? node).focus(); // gone (removed): the panel itself
  }

  return {
    node,
    // Called when a room is selected: keeps the list if it is the same room, starts a new one otherwise.
    async open(roomId) {
      // Without the starting lists (catalog unreachable) the list simply starts empty.
      catalog ??= api("/v1/catalog").then((data) => data.room_defaults ?? {}).catch(() => ({}));
      defaults = await catalog;
      if (s?.roomId !== roomId) s = fresh(roomId);
      draw();
    },
    // The plan changed (an edit, undo, a loaded version): suggestions made for the old plan are dropped.
    planChanged() {
      if (s?.phase === "results") update({ phase: "list", alternatives: [] });
      else if (s?.phase === "list") draw(); // the room's furniture may have changed (see sync)
    },
    // Pieces of the chosen suggestion, to draw as a dashed preview while `roomId` is selected.
    ghost(roomId) {
      return s?.phase === "results" && s.roomId === roomId ? s.alternatives[s.chosen].items : null;
    },
  };
}
