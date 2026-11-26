# Security

Sources: `supabase/migrations/`, `backend/app/main.py`, `backend/tests/test_api.py`, commit `f4ed029`.

## Tenant isolation

- A studio member sees the studio's projects. A client sees only their own. Enforced by RLS policies.
- Proven by tests through the API and directly against the Supabase Data API: no reading another
  studio's data, no direct writes, nothing visible to an anonymous caller.

## Controls in place

- JWT checked on every protected route; anonymous sign-ins are rejected.
- Strict input schemas: unknown fields rejected, numbers bounded, ids unique, openings must fit their wall.
- Request bodies capped at 2 MB by counting received bytes, so chunked uploads are capped too.
- Per-account quotas on projects and versions.
- Suspended studios cannot be written to.
- Invite tokens are random; the public invite lookup never returns the email.
- supabase-js is served from `frontend/vendor/`; every page has `script-src 'self'`.
- The DOM builder writes text nodes only, so plan and project names cannot inject markup.
- Secrets only in git-ignored files. History was scanned before the repository was published.

## Review of Phase 1

Independent security review and code review. No critical or high security finding. Fixed: CDN script
without integrity, chunked-body bypass of the size cap, account flooding, a race allowing two owned
studios, writes to suspended studios, sequence grants.

Not fixed, by decision: see [open-items.md](open-items.md).

## Review of the client portal and studio dashboard

No finding. The studio activity endpoint answers 403 to anyone who is not a member of an active
studio with that id, whether or not the studio exists, and returns no actor ids, tokens or emails.
A client's plan is drawn as SVG in the designer's browser from values the backend schema bounds as
finite numbers and fixed literals.

## Review of Phase 2 (backend)

`security-review` and a security-reviewer agent on the local commits. Fixed: a suspended studio could still
write design data; parallel uploads could pass the 30-image limit (now a database trigger); the consultant's
daily cap could be bypassed (empty answers, parallel calls, many projects) and is now reserved atomically per
user before the paid call; project text sent to OpenAI could pose as instructions (now an escaped,
untrusted input item). Checked, no finding: tenant isolation of every new table and route, upload byte
checks, signed URLs, no IDOR through asset or room ids. Not fixed: see the Phase 2 gaps in
[open-items.md](open-items.md). The Phase 2 frontend had a code review (fixed: expiring image links,
duplicate chat message after a failed answer, unvalidated `?project=`); a security review of the frontend
commits is still to do.

## Review of layout suggestions (2026-11-26)

`security-review` on the branch's commits: no finding. Checked: the endpoint's access check and that service-key
calls use only the checked project id and the token's user id; the new table's RLS (own rows only), grants
(SELECT for users) and the SECURITY DEFINER function (fixed SQL, empty search path, service role only); no
string-built SQL; model output re-validated and shown as text only; logs hold error types only. A code review
found and led to fixes for: focus loss in the panel that let Backspace delete the selected room, doors in a
neighbour's shared wall being ignored, silent SDK retries, a slot used up when the brief read failed.

## Every stage

Run the `security-review` skill on the branch's local commits before pushing (`CLAUDE.md`, step 7), and add
the outcome here and to [log.md](log.md).
