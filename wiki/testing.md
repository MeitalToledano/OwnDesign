# Testing

Sources: `backend/tests/`, `frontend/tests/`.

```sh
cd backend  && uv run pytest     # unit + integration (real dev Supabase) + browser E2E
cd frontend && npm test          # plan logic, node --test
```

First E2E run needs `uv run playwright install chromium`. Integration and E2E tests are skipped when
`backend/.env` is missing. They create users at `*@owndesign-test.example.com` and delete them afterwards.

## Suites

| File | Kind | Covers |
|---|---|---|
| `backend/tests/test_geometry.py` | unit, edge | geometry validation: bounds, duplicates, openings outside walls |
| `backend/tests/test_api.py` | integration, edge | auth, studios, invites, projects, versions, isolation, quotas, 413 on chunked upload, studio activity (members only) |
| `backend/tests/test_e2e.py` | end to end, edge | client journey (portal, wizard, editor, sign-up, save, reload); designer journey (studio dashboard metrics, invite, project cards, search, activity, edit a client's project); portal entry points (personal invite, blank canvas, invalid links, markup and long names) |
| `frontend/tests/plan.test.js` | unit | plan functions: add, move, remove, undo, rooms from the wizard |
| `frontend/tests/studio.test.js` | unit, edge | dashboard metrics, activity sentences, project filter |

## Required after every change

End to end, regression (both full suites) and edge cases for the change (`CLAUDE.md`, step 5).

## Last result

2026-11-23: backend 94 passed (incl. 3 browser journeys), frontend 31 passed. New files:
`backend/tests/test_design.py` (brief, finishes, uploads, moodboard, isolation, quota, suspended studio) and
`test_consultant.py` (fake OpenAI client: context, privacy, cap, failure, injection, tag escaping);
`frontend/tests/design-logic.test.js`. `backend/tests/test_e2e_design.py` (6 browser tests: client journey for brief, finishes and moodboard with
reload; designer sees the client's data; client-side rejections, markup stays text; stranger and signed-out
visitor; consultant page limits) passes together with `test_e2e.py` (9 browser tests in all). No chat message
reaches OpenAI in the suite; the real call was checked by hand once.

2026-11-26 (layout suggestions, on a machine without keys): backend 62 passed, 64 skipped (everything that
needs Supabase), with `test_consultant.py` and `test_layout_api.py` left out because they cannot be collected
without `.env` ([open-items.md](open-items.md)). Frontend 36 passed. New: `backend/tests/test_layout.py` (room,
answer checks, request schema, catalog drift; no network), `backend/tests/test_layout_api.py` (fake OpenAI:
plan coordinates, privacy, isolation, 422/502/503, parallel cap, suspended studio) and a browser journey in
`test_e2e_design.py` (suggestion answered in the browser). The editor UI was also driven headless against a
faked backend: list, preview, apply, undo, cancel, keyboard focus.

## Local setup notes

`backend/.env` needs `ALLOWED_ORIGINS` to include both `http://localhost:5500` and `http://127.0.0.1:5500` (the
journeys use the second). A system-level `OPENAI_API_KEY` overrides the one in `.env`; unset it before starting the backend.

## Not covered

Real touch devices (pinch zoom), browsers other than Chromium, screen readers, load, a studio with
many projects, a clean clone on another machine.

## Gotchas

- Every run of the backend suite deletes all `*@owndesign-test.example.com` accounts and their studios.
  Do not run it while someone is checking pages by hand with such accounts.
- Playwright matches accessible names by substring. A second link containing "Start designing" or a
  second heading containing the studio name breaks the journeys.
