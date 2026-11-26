# Decisions

Each line: the decision, who made it, why. Dates are in [log.md](log.md).

## By the user

- **Phase 1 first**, later phases afterwards.
- **AI through OpenAI API calls.** This overrides the PRD's "no paid API" constraint. The PRD text has not been updated.
- **English-only UI** (left to right).
- **Cloud Supabase**, in a new organisation created for this product.
- **UI follows the Stitch project** "AI Interior Design Platform" ([design.md](design.md)).
- **GitHub repository is public.** The user chose to publish with the existing commit author address.
- **Stitch screens for later phases stay as references** in `design/stitch/`; the two that match Phase 1 (client portal, studio dashboard) are built with real data only.
- **Working rules** in `CLAUDE.md`: plan first, Fable 5.2, three kinds of tests, security review at every stage, commit per finished piece of code, subagents for specialist work, memory in `wiki/`.

- **Furniture-layout suggestions pulled forward** (2026-11-26). The PRD lists automated design proposals as
  post-MVP; the user chose to build them now, with approval before anything changes. One room per request,
  2–3 alternatives shown as thumbnails plus a dashed preview, the client chooses the furniture list (prefilled
  by room type) and whether existing pieces may move. Rooms are picked from the plan; uploading a plan for AI
  conversion was rejected (excluded by the PRD, accuracy risk). A draft PR without the feasibility check, for
  the manager's review, because no keys were available on this machine.

- **Standard rules as the layout fallback** (2026-11-26). After trying the demo, the user chose option 1 of three
  (fallback; the hybrid "AI picks anchors, code places" and rules-only were the others): the rules answer when the
  AI gives nothing usable, and alone when there is no key.

## By Claude (open to change)

- **Layout suggestions:** 10 requests per user per day; not offered to guests; based on the editor's current
  (possibly unsaved) plan; a room is its walls' bounding rectangle; 90 cm clear in front of doors; the model
  places pieces and deterministic code checks them (the planned fallback, if the model proves weak: the model
  picks anchors and code computes positions).

- **FastAPI**, managed with `uv`; **no-build frontend** with plain ES modules. Smallest stack that meets the PRD's "Python backend, HTML/CSS frontend".
- **All writes go through the backend with the service key; users have SELECT only.** The approved plan limited the service key to three operations. Widened so geometry validation and the audit trail cannot be bypassed through the Supabase Data API ([architecture.md](architecture.md)).
- **One JSON document per plan version**, in centimetres. The current plan is the latest version; no separate floor-plan table.
- **supabase-js is vendored**, not loaded from a CDN, with a `script-src 'self'` policy. Came out of the security review.
- **Product name "ATELIER"** in the UI, taken from Stitch. The PRD leaves the name undecided.
- **Phase 2 data model:** the brief is one JSON document per project; finishes and the moodboard are saved as a whole set (delete then insert, not atomic, saving again recovers).
- **Consultant memory policy** (PRD 5.4 leaves it open): messages are stored per project and user, private to that user, capped at 30 a day per user. A failed OpenAI call still uses a slot because it may have been billed.
- **Images go through the backend**, not directly to storage, so type, size, count and access are checked in one place.
- **Later-phase widgets shown in Stitch are left out** (AI advisor, credits, budget, compliance badges) so the UI shows no fake data.
