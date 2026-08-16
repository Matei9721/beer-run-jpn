# Spec 013: Add Invite UI And Accept Flow

**Feature Branch**: `spec/013-add-invite-ui-and-accept-flow`

**Created**: 2026-08-13

**Status**: Draft

## Overview

The permanent invite API already lets an owner create one reusable link, lets
any code holder preview the target run, and lets an authenticated account join.
The browser does not expose any of those capabilities, so owners and recipients
still need manual API calls.

This feature adds an owner-only invite action to the selected-run picker and a
focused `?invite=<code>` landing flow. Recipients see the target run before
joining, can continue through the existing login or signup modal, and after a
successful idempotent acceptance see the joined run added to My runs and
selected as the global Ranking, Map, filter, and Log Drink context.

## Goals

- Let an owner create or retrieve and copy the selected run's permanent invite.
- Keep navigation-only run sharing visibly distinct from membership-granting
  invite links.
- Preview a valid public or private invite before any acceptance request.
- Let logged-out recipients log in or sign up and resume an explicitly requested
  join without losing the invite.
- Add the accepted run to My runs, persist it, select it globally, and refresh
  its scoped trip data.
- Prevent stale identity responses and invite-bearing URLs from leaking into the
  wrong account, ordinary share links, logs, or browser storage.
- Preserve the existing lightweight static frontend and server API contracts.

## Drafted Decisions

- **Owner presentation:** An `Invite people` action appears beside the selected
  run summary only when `current_user_role === "owner"`. It opens an invite
  subview inside the existing run-picker sheet; it is not another stacked modal.
- **Recipient presentation:** A root-page `?invite=<code>` URL opens a focused,
  accessible invite dialog/mobile sheet above the normal page. Invite handling
  takes priority over the instructions and Wrapped-ended startup notices so
  top-level dialogs never stack.
- **Consent:** Loading an invite URL never joins automatically. Every recipient
  first sees the run name and deliberately activates `Join run`, `Log in to
  join`, or `Sign up to join`.
- **Post-auth continuation:** Choosing a login/signup-to-join action records an
  in-memory acceptance intent. A successful shared auth flow resumes acceptance
  automatically only after `/api/me` confirms that identity. Merely loading an
  invite while already logged in, or logging in from the header without choosing
  a join action, does not auto-accept.
- **Auth cancellation:** Closing the auth modal cancels automatic continuation
  and returns to the invite preview. The code remains in the URL/in memory so the
  recipient may choose again; credentials and form values are still cleared by
  the existing auth behavior.
- **Link controls:** The owner view always shows a read-only absolute invite URL
  and a Copy action. A native Share action may also be exposed when supported;
  clipboard failure falls back to the existing explicit copy prompt pattern.
- **Successful acceptance:** The committed `BeerRunResponse` is immediately
  upserted into My runs and selected through the existing global run transition.
  The browser then performs one bounded `view=mine` refresh to reconcile the
  authoritative membership list.
- **URL cleanup:** Successful acceptance replaces `invite` with
  `run=<accepted_id>` using `history.replaceState`. Explicit invite dismissal
  removes only `invite`. Unrelated query parameters are preserved.
- **Secret lifetime:** The invite code exists only in the incoming URL, the
  owner-visible link, and short-lived in-memory flow state. It is never copied
  into localStorage, sessionStorage, app diagnostics, rendered errors, or the
  selected-run storage key.

---

## Feature 1: Owner Invite Link Creation And Sharing

**Who & why:** A run owner needs a phone-friendly way to retrieve the one
permanent invite and send it through any channel. A normal member or public
viewer must not be given a misleading control that the server will reject.

### Functional Requirements

#### FR-1.1: Show A Distinct Owner-Only Invite Action

After `/api/me` and the selected run are resolved, the picker MUST show an
`Invite people` action only when the selected run's authoritative
`current_user_role` is `owner`. It MUST be hidden for members, authenticated
non-members, logged-out visitors, validating/validation-failed identities, and
runs with no current owner role. The existing `Share link` action remains a
navigation link for people who already have read access and MUST be labeled and
described separately from an invite that grants membership.

**Verify:** Open the same public and private run as owner, member, authenticated
non-member, logged-out visitor, and validating/rejected identity; confirm only
the confirmed owner sees an activatable invite action and all callers still
receive server-enforced authorization on direct requests.

#### FR-1.2: Create Or Retrieve The Selected Run's Permanent Invite

Activating `Invite people` MUST open an invite subview for the currently selected
run and, on an explicit generate/retrieve action, send one bodyless authenticated
`POST /api/beer-runs/{beer_run_id}/invites`. The request MUST capture the selected
run ID, confirmed user ID, bearer token, and application context generation.
While pending, repeat activation MUST be disabled and a non-color-only progress
state MUST be announced.

**Verify:** Delay the request and click/tap/press the action repeatedly; confirm
one POST targets the selected run ID with the current bearer token and only one
result is handled.

#### FR-1.3: Validate And Display A Copyable Absolute Link

A successful `201` or `200` response MUST be accepted only when it contains the
Spec 008 fields `code`, `invite_url`, `beer_run_id`, `beer_run_name`, and
`created_at`; the run ID MUST match the captured selected run, and `invite_url`
MUST be the Spec 008 root-relative shape `/?invite=<code>` with one matching
invite value, no other query fields, and no fragment. The browser MUST resolve
that validated path against `window.location.origin` and display the resulting
absolute URL in a labeled read-only field with a Copy action. It MUST NOT
construct an invite by modifying the current page URL.

**Verify:** Return normal `201` and repeat `200` responses plus mismatched IDs,
origins, paths, codes, and missing fields; confirm only valid same-origin results
are displayed and both successful calls show the same permanent link.

#### FR-1.4: Copy Or Share Without Losing The Link

Copy MUST write the displayed absolute link through the Clipboard API and
announce success without moving focus. If clipboard writing is unavailable or
fails, the browser MUST offer the existing explicit copy prompt containing the
same link. When `navigator.share` is available, a Share action MUST send the run
name and exact invite URL; user cancellation is silent, while other failures
leave the visible link and Copy action usable.

**Verify:** Exercise native share success/cancel/failure, clipboard success, and
clipboard denial; confirm the shared/copied value is the displayed invite URL,
the permanent link remains visible, and no code is written to the console.

#### FR-1.5: Handle Owner Request Failures Safely

A `401` MUST use the existing rejected-session flow. A `403` MUST remove the
owner-only affordance after current-run/identity reconciliation and show a safe
access-changed message. A `404` MUST use the existing selected-run access-loss
recovery. A `500`, malformed success, or network failure MUST keep the previous
selected run and show a retryable generic error without displaying raw response
data. Because create-or-retrieve is idempotent, an intentional Retry may send one
new POST; the browser MUST NOT retry automatically.

**Verify:** Force each status, malformed JSON/shape, offline behavior, logout,
and ownership loss while pending; confirm no stale link renders, private trip
state follows existing recovery rules, and retries occur only by user action.

### Architectural Requirements

#### AR-1.1: Preserve Server Ownership As Authority

Owner-role rendering is an affordance only. `POST
/api/beer-runs/{beer_run_id}/invites` remains protected by
`permissions.authorize_owner_access`; the frontend MUST NOT infer ownership from
member count, roster order, run visibility, name, or browser storage.

---

## Feature 2: Invite URL Preview And Explicit Join Intent

**Who & why:** A recipient may receive a link to a private run from an unfamiliar
channel. They need to know which run the invitation targets before signing in or
changing membership, without receiving private trip details.

### Functional Requirements

#### FR-2.1: Recognize One Root-Page Invite Parameter

On the normal index page, the browser MUST inspect the query string for exactly
one non-empty `invite` value without adding a server route or SPA router. It MUST
preserve the exact decoded value in ephemeral flow state and pass an encoded
path segment to `GET /api/invites/{code}`. Missing `invite` means no invite flow;
empty or duplicate invite parameters MUST produce the same generic unavailable
state as an invalid code and MUST never trigger acceptance.

**Verify:** Load URLs with a valid code, encoded value, empty value, duplicated
parameter, unrelated parameters, and no invite; confirm only an unambiguous
value is previewed and no acceptance request occurs during page load.

#### FR-2.2: Preview Only The API's Minimal Run Identity

A successful preview MUST render the returned `beer_run_name` in a focused
invite dialog titled `Join a beer run` and retain `beer_run_id` only for response
validation. The dialog MUST explain that joining adds the current account as a
member. It MUST NOT infer or display visibility, owner, roster, member count,
entries, map data, or whether the current account already belongs to the run.
Run names and status text MUST use text-safe DOM APIs.

**Verify:** Preview valid public and private invites as logged-out, member,
owner, and non-member callers; confirm every preview exposes only the same run
name and join explanation before acceptance.

#### FR-2.3: Require A Deliberate Join Action

An authenticated recipient MUST see a `Join run` action. A logged-out recipient
MUST see distinct `Log in to join` and `Sign up to join` actions that open the
corresponding mode of the existing auth modal. Page load, preview completion,
stored-session restoration, ordinary header login, and switching auth modes MUST
NOT by themselves send an acceptance request.

**Verify:** Load a valid invite in every identity state and inspect network
traffic before activating a join action; confirm preview is the only invite
request and the chosen auth action opens the correct existing form.

#### FR-2.4: Prioritize Invite UI Without Stacking Dialogs

Invite preview/loading/error UI MUST take priority over the instructions and
Wrapped-ended startup notices. Opening login/signup from the invite MUST hide or
suspend the invite dialog before showing the auth modal. Closing auth MUST return
to the same preview with no stacked backdrops; successful authentication may
continue according to FR-3.1. The invite dialog MUST not disrupt the global run
selected behind it until acceptance succeeds.

**Verify:** Use fresh storage that would normally show both startup notices,
then open and close login/signup from an invite; confirm one top-level dialog at
a time, stable background run context, and predictable focus return.

#### FR-2.5: Make Invalid And Failed Preview States Retryable Or Dismissible

A preview `404`, malformed success, empty/duplicate parameter, or unavailable
target MUST show one generic `Invite not found or no longer available` state
without target metadata. A network or non-404 server failure MUST show a
distinct connection/server message with Retry. Explicit dismissal through
Close, Escape, or backdrop MUST remove only the `invite` query parameter with
`history.replaceState`, clear pending intent and code state, and then allow
normal startup notices. Retry MUST remain bounded to one request per action.

**Verify:** Exercise malformed, unknown, case-changed, deleted-run, malformed
success, offline, `500`, Retry, and every dismissal path; confirm uniform
invalid copy, no metadata leak, URL cleanup, and no automatic request loop.

### Architectural Requirements

#### AR-2.1: Reuse The Index Page Instead Of Adding Routing Infrastructure

The existing root route in `main.py` continues serving `templates/index.html`.
Invite handling is query-driven browser state; do not add a new server-rendered
page, client router, SPA framework, or duplicate application bootstrap.

---

## Feature 3: Authentication Continuation, Acceptance, And Selection

**Who & why:** A recipient should be able to move from an invite into the
existing login or signup flow and land in the joined run without copying codes,
reopening links, or seeing another account's stale result.

### Functional Requirements

#### FR-3.1: Resume Only A User-Initiated Join After Authentication

When a logged-out recipient activates `Log in to join` or `Sign up to join`, the
browser MUST record an in-memory pending intent bound to the current invite.
After the existing shared `handleAuthenticated` path stores the token, resolves
`/api/me`, and establishes the confirmed identity, it MUST resume one acceptance
attempt for that same invite. Closing auth, failed auth, changing the invite URL,
explicitly dismissing the invite, or merely authenticating through the header
MUST clear or avoid that automatic continuation.

**Verify:** Complete login and signup from their invite actions, cancel and
retry auth, fail credentials, log in from the header, and change/dismiss the
invite; confirm automatic acceptance occurs exactly once only for the two
explicit join continuations.

#### FR-3.2: Accept With The Confirmed Identity And Prevent Repeat Taps

An acceptance attempt MUST send one bodyless `POST /api/invites/{code}/accept`
with the current bearer token and an encoded code path. It MUST capture the
previewed run ID, confirmed user ID, token, and context generation, disable join
actions, and announce progress. Logout, rejected-session handling, account
change, invite dismissal, or a newer invite flow MUST abort when possible and
always invalidate the old result before it can update DOM, picker state,
storage, or selected run.

**Verify:** Double-activate Join, delay acceptance through logout/account switch,
and replace the invite while pending; confirm at most one POST per attempt and
no old response changes the new identity or flow.

#### FR-3.3: Validate The Accepted Run Response

A `200` acceptance response MUST contain the existing `BeerRunResponse` fields
`id`, `name`, `is_public`, `created_at`, `member_count`, and
`current_user_role`. The ID MUST match the previewed `beer_run_id`, and the role
MUST be `member` or the preserved `owner`. Missing, contradictory, or otherwise
malformed success data MUST not enter My runs, storage, or global selection and
MUST produce a safe retry/reconciliation state.

**Verify:** Return new-member, existing-member, and existing-owner responses plus
wrong-ID, missing-field, null-role, and unexpected-role responses; confirm only
valid matching responses proceed and owner is never displayed as demoted.

#### FR-3.4: Add, Select, Persist, And Refresh The Joined Run

After a valid committed response, the picker MUST upsert the run by immutable ID
into its local My runs list, preserving case-insensitive name ordering and
preventing duplicates. The app MUST then select it through the existing
`setCurrentRun` / `selectRun` transition with authenticated persistence, close
the invite dialog, clear the previous run's leaderboard, entries, filter, map,
details, and user history, and request the accepted run's scoped data. It MUST
also make one bounded authenticated `GET /api/beer-runs?view=mine` refresh and
replace picker memberships only if the response still matches the same identity
and generation.

**Verify:** Accept from populated public/private runs as a new member, existing
member, and owner; confirm one ordered My runs row, the user-scoped selected ID,
correct trigger/Log Drink role, cleared old surfaces, and only accepted-run
scoped requests.

#### FR-3.5: Preserve Success If Membership Refresh Fails

The valid acceptance response is authoritative evidence of a committed
membership. If the following My runs refresh has a non-authentication network or
server failure, the browser MUST keep the locally upserted accepted run selected,
show a retryable list-refresh notice, and MUST NOT claim acceptance failed or
automatically POST again. A `401` still invokes rejected-session handling and
clears private state. A later normal initialization or picker refresh may
reconcile the full list.

**Verify:** Return a valid acceptance followed by failed/offline `view=mine`;
confirm the joined run remains selected and visible once, with a refresh notice
and no second accept request.

#### FR-3.6: Reconcile An Ambiguous Acceptance Result

If the acceptance POST has a network failure or malformed success after the
server may have committed, the browser MUST perform at most one authenticated
`view=mine` reconciliation for the same identity. If that list contains the
previewed run ID with role `member` or `owner`, treat it as successful using
that run response. Otherwise retain the preview and offer an intentional Retry;
the idempotent backend remains responsible for preventing duplicate membership.

**Verify:** Simulate commit-then-lost-response, failure-before-commit, malformed
success with committed membership, and failed reconciliation; confirm only a
server-confirmed membership is selected and retries are never automatic.

#### FR-3.7: Normalize The URL After Success

Before revealing the accepted run as the stable landing state, the browser MUST
use `history.replaceState` to remove every `invite` parameter and set exactly one
`run=<accepted_id>` parameter while preserving unrelated non-invite parameters.
Reload MUST therefore validate/open the accepted run through the existing run
deep-link behavior and MUST NOT preview or re-accept the invitation.

**Verify:** Accept from URLs containing invite plus unrelated parameters and an
existing run value; confirm the final URL contains no invite code, contains the
accepted run ID once, preserves unrelated parameters, and reload makes no invite
request.

### Architectural Requirements

#### AR-3.1: Reuse One Shared Authentication And Selection Path

Login and signup success MUST continue converging through the existing
`handleAuthenticated` / `establishAuthenticatedContext` behavior. Invite
continuation is a post-auth hook on that shared path, not a second token,
identity, default-run, or refresh implementation. Acceptance success MUST reuse
the existing picker upsert, selected-run persistence, trip-state clearing, and
paired scoped refresh boundaries.

---

## Feature 4: Module Boundaries, URL Safety, Accessibility, And Mobile Behavior

**Who & why:** Invite handling crosses query state, auth, a bearer capability,
the run picker, and global selection. Keeping those responsibilities explicit
prevents a convenient flow from becoming a secret leak or an unmaintainable
addition to `app.js` and `auth.js`.

### Functional Requirements

#### FR-4.1: Prevent Invite Codes From Entering Ordinary Share URLs

Every non-invite run share URL, including the existing `shareUrlForRun`, MUST
remove all `invite` parameters before adding `run=<id>`. It MUST never start from
an unfiltered current query string that can carry the invite bearer capability
into `navigator.share`, clipboard, or prompt output. Owner invite URLs MUST be
built only from the validated API `invite_url` against the current origin.

**Verify:** Open `/?invite=<code>&run=<other>&x=1`, use ordinary Share link and
owner Invite people, and confirm the first output contains `run=<selected>&x=1`
with no invite while the second contains only the validated invite URL.

#### FR-4.2: Keep Invite Data Ephemeral And Text-Safe

The browser MUST NOT persist invite codes, invite URLs, preview names, pending
acceptance intent, or acceptance responses in localStorage or sessionStorage.
The selected-run key continues storing only an accepted run ID. Invite codes,
tokens, request bodies, raw response bodies, and full invite URLs MUST NOT be
written to application console messages or rendered errors. Run names and known
status text MUST be assigned using text-safe DOM APIs.

**Verify:** Complete successful and failed owner/recipient flows, inspect storage,
DOM errors, and console output, and confirm only the allowed owner link field and
address bar contain the invite URL/code.

#### FR-4.3: Provide Complete Dialog And Focus Behavior

The invite landing UI MUST use dialog semantics, an accessible heading, real
button controls, focus containment, Escape/backdrop/Close dismissal, and focus
return to a logical origin. Owner invite controls MUST remain inside the existing
picker focus trap; Back returns to the owner action and closing the picker returns
to the global run trigger. Status/loading/copy/success announcements are polite;
action failures are assertive without unexpectedly moving focus.

**Verify:** Complete owner copy/share, recipient preview, auth handoff, retry,
acceptance, and dismissal using keyboard and assistive-technology inspection;
confirm one focus trap at a time and reliable focus restoration.

#### FR-4.4: Remain Usable At Mobile Widths And With Long Names

At 390x844 and comparable phone viewports, invite sheets, a 64-character run
name, the read-only absolute link, errors, and actions MUST fit without horizontal
page scrolling or obscured controls. Long URLs MAY scroll within their field or
wrap without expanding the page. Every interactive target MUST be at least
44x44 CSS pixels and the background MUST not scroll while a dialog is open.

**Verify:** Inspect short/long run names and URLs plus loading, invalid, network,
auth, and success states at desktop and 390x844; confirm readable content,
reachable controls, safe areas, touch targets, and no overflow.

### Architectural Requirements

#### AR-4.1: Put Substantial Invite Behavior In A Focused Module

Add a focused vanilla ES module such as `static/js/modules/invites.js` for invite
query parsing, response validation, owner/recipient rendering, copy/share state,
pending intent, and invite-local focus/error state. Keep network calls in
`static/js/modules/api.js`, token/auth primitives in
`static/js/modules/auth.js`, picker-local selected-run integration in
`static/js/modules/beer-runs.js`, and cross-feature identity/generation/selection
orchestration in `static/js/app.js`. Do not put the entire flow in `app.js`,
`auth.js`, or generic `ui.js`.

#### AR-4.2: Normalize Invite API Results In `api.js`

Add create/retrieve, preview, and accept helpers that distinguish success data,
HTTP status, sanitized detail when appropriate, network failure, and abort using
the module's existing normalized-result pattern. Each helper MUST accept an
`AbortSignal` where the flow can become stale, encode path segments, send no
request body, and never log codes, URLs, tokens, or raw responses.

#### AR-4.3: Update Static Asset Cache Busting

Every changed deployed JavaScript or CSS asset MUST receive the relevant
cache-busting update in `templates/index.html`, and changed/new ES-module imports
MUST receive updated query strings in `static/js/app.js`, following
`repository_rules.md`.

## Data And API Requirements

- No database model, schema, migration, backend route, runtime-data
  transformation, or upload change is required.
- Consume the implemented Spec 008 contracts without changing their shapes:
  - Owner: bodyless `POST /api/beer-runs/{id}/invites`; first `201`, later `200`;
    `{code, invite_url, beer_run_id, beer_run_name, created_at}`.
  - Preview: anonymous `GET /api/invites/{code}`; `200` with exactly
    `{beer_run_id, beer_run_name}`; uniform invalid `404`.
  - Accept: bodyless authenticated `POST /api/invites/{code}/accept`; `200`
    `BeerRunResponse`; idempotent and role-preserving; auth-first `401` and
    authenticated invalid `404`.
- The only persistent browser result of success is the existing authenticated
  selected-run ID. Invite state remains URL/in-memory only.
- Protected runtime data, including `boozerun.db`, uploads, `users.json`, and
  caches, MUST NOT be changed during implementation or verification without
  explicit authorization.

## Integration Points

| Area | Existing boundary | Required interaction |
|------|-------------------|----------------------|
| Invite API | `invite_routes.py`, `schemas.py`, Spec 008 | Consume permanent create/retrieve, minimal preview, and idempotent accept contracts without backend changes. |
| API client | `static/js/modules/api.js` | Add normalized, cancellable invite helpers with encoded path values and no request bodies. |
| Invite feature module | `static/js/modules/invites.js` (new) | Own URL parsing, response validation, owner/recipient views, copy/share, pending intent, and invite-local accessibility. |
| Run picker | `static/js/modules/beer-runs.js` | Gate the owner action, host its owner subview, and upsert/reconcile accepted memberships. |
| Auth UI | `static/js/modules/auth.js`, `static/js/modules/signup.js` | Reuse login/signup modes, token storage, error behavior, and form reset; expose only a focused mode/open/close continuation seam if needed. |
| App orchestration | `static/js/app.js` | Bind invite work to identity/context generations, schedule startup dialogs, handle rejected sessions, refresh My runs, and select/persist accepted runs. |
| Global run state | `static/js/app.js`, `static/js/modules/map.js`, `static/js/modules/ui.js` | Reuse complete old-run clearing and paired accepted-run refresh. |
| Markup/styles | `templates/index.html`, `static/css/style.css`, `static/css/auth.css` | Add semantic owner/recipient invite surfaces using the current picker/modal visual language and mobile safe areas. |
| Backend regressions | `tests/test_invites.py`, `tests/conftest.py` | Preserve exact invite authorization, disclosure, idempotency, response, concurrency, and rollback behavior. |

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 008: Add Invite Code API | **Depends on** - supplies every invite endpoint, response, authorization, privacy, permanence, and idempotency contract consumed here | FR-1.2 through FR-1.5, FR-2.1 through FR-2.5, FR-3.2 through FR-3.6, AR-4.2 |
| Spec 012: Add Create Beer-Run UI | **Extends** - adds the deferred owner invite and join flow while reusing picker subviews, response validation, My runs upsert, race binding, and mobile behavior | FR-1.1 through FR-1.5, FR-3.3 through FR-4.4, AR-4.1 |
| Spec 011: Add Beer-Run Selector UI And Public Discovery | **Extends** - replaces deferred join guidance and reuses global selection, user-scoped persistence, bounded My runs, stale clearing, and run deep links | FR-3.4 through FR-3.7, FR-4.1, AR-3.1 |
| Spec 010: Update Frontend Auth And Signup | **Extends** - adds an explicit invite continuation to the shared login/signup success path without changing auth contracts | FR-2.3, FR-2.4, FR-3.1, AR-3.1 |
| Spec 007: Centralize Beer-Run Authorization | **References** - UI visibility never replaces server owner authentication or accepted-run authorization | FR-1.1, FR-1.5, AR-1.1 |
| Spec 004: Harden Auth Tokens | **References** - continuation and stale checks rely on confirmed stable user-ID identity and rejected-token handling | FR-3.1, FR-3.2, AR-3.1 |

## Constraints

- Keep FastAPI, SQLite, static HTML/CSS, vanilla ES modules, Leaflet, and the
  no-build deployment model.
- Add no frontend framework, build system, client router, external dependency,
  email/SMS integration, or service layer.
- Preserve all Spec 008 endpoint shapes, statuses, authentication order,
  permanent-code behavior, and minimal preview disclosure.
- Preserve the global selected-run context and server-authorized public/member/
  owner boundaries; invite possession grants only the existing preview/join
  capability.
- Use isolated test/browser data only. Never generate an invite against or add a
  membership to live `boozerun.db` during verification without explicit
  authorization.
- Update relevant JavaScript/CSS cache-busting query strings for every changed
  static asset.
- Run focused invite regressions and full pytest, then inspect desktop and
  mobile browser behavior including logout/access-loss scenarios.

## Failure Modes And Recovery

- **Invalid or unavailable preview:** show one generic invalid state with no run
  metadata; permit dismissal but not acceptance.
- **Transient preview failure:** retain the code only in URL/in-memory and offer
  a deliberate bounded Retry.
- **Owner role changes before request:** server `403` wins; reconcile the
  selected run and remove the stale action.
- **Selected run is deleted/inaccessible:** reuse complete access-loss clearing
  and default-run recovery.
- **Rejected token during invite create/accept:** remove the token, clear private
  state, keep the invite preview available, and require fresh explicit auth
  continuation; never retry with the rejected credential.
- **Auth is cancelled or fails:** return to preview without accepting; preserve
  the invite link until explicit invite dismissal.
- **Acceptance returns invalid invite:** show the same unavailable state and do
  not add/select a run.
- **Acceptance result is ambiguous:** reconcile once through bounded My runs;
  select only confirmed membership, otherwise offer deliberate idempotent Retry.
- **My runs refresh fails after confirmed acceptance:** keep the locally upserted
  joined run selected and expose a list-refresh notice.
- **Identity or invite changes while work is pending:** abort when possible and
  ignore the stale result unconditionally.
- **Copy/share capability fails:** keep the visible read-only owner link and
  fallback copy prompt available.
- **Invite is dismissed or accepted:** scrub `invite` from the current URL and
  clear all pending code/intent state.

## Security And Privacy Review

- A permanent invite is a bearer capability. The owner-visible link and incoming
  URL necessarily contain the raw code; possession plus an authenticated account
  is sufficient to join until the run is deleted.
- Public preview intentionally reveals only run ID and current name to a code
  holder, including for private runs. The browser must not enrich that response
  before membership exists.
- Owner action visibility is not authorization. The backend remains authoritative
  for owner create/retrieve and authenticated acceptance.
- Successful auth alone is not consent to join. Automatic continuation is
  permitted only after the recipient explicitly chose a login/signup-to-join
  action for the same in-memory invite.
- Codes are never persisted outside their existing server storage and URL
  surfaces, never included in ordinary run-share links, and removed from the
  current address after success/dismissal.
- URL query codes may already appear in browser history, reverse-proxy logs, and
  access logs before client cleanup. Deployment logs remain sensitive; eliminating
  that exposure requires a different API contract outside this feature.
- Stale-result guards prevent one user's acceptance response or private run name
  from appearing under another account or after logout.
- All server-returned names and messages are rendered through text-safe APIs; raw
  error bodies, tokens, codes, and request payloads are not logged.

## Performance Impact

- A page without `invite` adds no invite request or rendering work.
- An invite landing page adds one explicit indexed preview request.
- Owner link retrieval adds one POST only when requested; later retrieval reuses
  the same server row.
- Successful acceptance adds one POST, one bounded `view=mine` reconciliation,
  and the existing paired scoped leaderboard/entries refresh for the selected
  run.
- Retry and ambiguous-result reconciliation are user-triggered or capped at one;
  no polling, background catalog load, or unbounded public-run request is added.

## Verification Strategy

1. Run existing `tests/test_invites.py` to preserve exact owner creation,
   anonymous preview, authenticated acceptance, idempotency, role preservation,
   invalid-code, concurrency, deletion, and sanitized-failure contracts.
2. Run relevant auth, beer-run CRUD, selector/scoped-route, and permission tests
   when implementation touches their shared behavior.
3. Parse every changed/new JavaScript ES module and run `git diff --check`.
4. Run the complete `uv --cache-dir .uv-cache run pytest` suite against the
   isolated test database.
5. In an isolated local app, verify owner first/repeat invite retrieval, absolute
   link display, Copy, native Share when available, clipboard fallback, and clear
   distinction from ordinary Share link.
6. Verify member, non-member, logged-out, validating, and rejected identities do
   not see an owner invite control; inspect direct API responses to confirm server
   enforcement remains unchanged.
7. Verify public/private invite previews, long names, invalid/malformed/duplicate/
   deleted codes, offline/server failures, retry, and explicit dismissal.
8. Verify already-authenticated new-member, existing-member, and owner acceptance;
   confirm idempotent roles, My runs upsert/refresh, selection, persistence, URL
   normalization, scoped requests, and complete old-state clearing.
9. Verify logged-out Login to join and Sign up to join, including failed auth,
   switching modes, closing/reopening auth, and successful single continuation.
10. Confirm ordinary header login never auto-accepts, loading/reloading a link
    never auto-accepts, and explicit auth cancellation returns to preview.
11. Force commit-then-lost accept response, failed My runs reconciliation,
    malformed success, `401`, logout, account switch, invite replacement, and
    delayed responses; confirm bounded recovery and stale-result suppression.
12. From an invite-bearing page, use ordinary Share link and confirm no invite
    code appears in its native-share, clipboard, or prompt output. Confirm accept
    and dismissal scrub the current URL as specified.
13. Inspect localStorage, sessionStorage, address bar, DOM, console, request URLs,
    and rendered errors for unintended invite/token/private-data persistence or
    disclosure.
14. Verify keyboard-only focus, announcements, Escape/backdrop/Close behavior,
    one-dialog-at-a-time auth handoff, 44px targets, safe areas, and layouts on
    desktop and at 390x844 using the Codex in-app browser.
15. Inspect `git status --short` and confirm only intended source/spec files
    changed and protected runtime data was not modified.

## Rollout And Rollback

1. Add normalized invite API helpers and the focused invite-flow module against
   the already deployed Spec 008 backend.
2. Add owner picker markup, recipient invite dialog, auth-continuation seam,
   responsive styles, and cache-busting updates.
3. Connect accepted responses to existing My runs upsert/reconciliation,
   selected-run persistence, state clearing, and scoped refresh.
4. Add ordinary-share query scrubbing and post-invite history normalization.
5. Complete focused/full regression checks and isolated desktop/mobile browser,
   network, storage, console, auth-transition, and access-loss verification.
6. Deploy the static assets together. No migration, backend route deployment,
   live-data transformation, or runtime invite generation is part of rollout.
7. Roll back by reverting the invite UI/module/API helpers and asset versions
   together. Invites and memberships already created through the valid backend
   remain unchanged and MUST NOT be deleted during rollback.

## Out Of Scope

- Invite expiration, revocation, rotation, replacement, labels, audit history,
  one-time use, maximum uses, or usage counters.
- Per-recipient username/email invitations, email/SMS delivery, QR codes, contact
  selection, or a general sharing service.
- Bypassing the existing signup code or automatically creating an account.
- Automatically accepting merely because an invite URL or valid stored session
  exists.
- Promoting invited users to owner, changing roles, removing members, leaving a
  run, transferring ownership, or broader run management.
- Changing the Spec 008 database model, migrations, endpoints, response shapes,
  authorization order, or permanent-code lifecycle.
- Adding a client router, separate invite page, frontend framework, build step,
  or automated browser framework where none currently exists.
- Loading an unbounded public catalog or changing global run-search behavior.
- Scoping or changing `/wrapped`; Task 16 owns Wrapped behavior.

## Assumptions And Risks

- **Assumption:** Spec 008's invite API and Specs 010-012's auth, picker, My runs,
  selection, and state-clearing behavior are deployed together before this UI.
- **Assumption:** The phrase `Log in to join` or `Sign up to join` communicates
  both authentication and consent clearly enough to resume acceptance after
  successful identity confirmation.
- **Assumption:** Keeping recipient invite state in the URL/in memory is adequate;
  reloading during auth returns to preview and requires a new explicit join
  action rather than persisting hidden continuation state.
- **Risk:** Permanent links cannot be revoked without deleting the run under the
  current API contract. The UI must not imply expiration, recipient targeting,
  or owner control that does not exist.
- **Risk:** `history.replaceState` limits continued exposure but cannot erase a
  link from external messages, previously recorded history/logs, or clipboard.
- **Risk:** Auth, startup notices, run initialization, invite preview, and
  acceptance can overlap. One-dialog scheduling plus identity/invite generations
  are required to keep focus, privacy, and selected state coherent.
- **Risk:** A committed acceptance followed by a lost response can look like a
  failure. One bounded My runs reconciliation distinguishes confirmed membership
  before offering an idempotent manual Retry.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Features 1-4 define owner retrieval,
  recipient preview, consent, auth continuation, acceptance, selection, URL
  cleanup, accessibility, and explicit Out Of Scope boundaries with a Verify
  line for every FR.
- [x] **Testing strategy** - Verification Strategy covers focused invite and
  shared regressions, full pytest, module parsing, desktop/mobile browser flows,
  network/storage/console review, races, and access loss.
- [x] **Existing patterns** - AR-1.1, AR-2.1, AR-3.1, AR-4.1, Integration Points,
  and Related Specs tie the plan to the current API, picker, auth, My runs,
  selection, stale-generation, and state-clearing paths.
- [x] **Dependencies** - Constraints and Out Of Scope require only existing
  browser capabilities and project modules; no new library, service, router,
  framework, or build step is introduced.
- [x] **Architecture & interfaces** - Features 1-4, Data And API Requirements,
  and Integration Points define exact API consumption, response validation,
  module ownership, persistence, dialog, and global-selection interfaces.
- [x] **Error handling & failure modes** - FR-1.5, FR-2.5, FR-3.3 through FR-3.6,
  and Failure Modes And Recovery cover invalid codes, auth, authorization,
  malformed responses, network ambiguity, stale identities, and refresh failure.
- [x] **Security review** - FR-1.1, FR-2.2, FR-2.3, FR-3.1, FR-3.2, FR-4.1,
  FR-4.2, and Security And Privacy Review cover consent, server authority,
  minimal disclosure, bearer-code handling, query scrubbing, and cross-account
  isolation.
- [x] **Performance impact** - Performance Impact and FR-3.4 through FR-3.6 bound
  normal work to preview/create/accept, one member-list reconciliation, and the
  existing scoped refresh without polling or unbounded catalog requests.
- [x] **Rollout & migration** - Data And API Requirements and Rollout And Rollback
  specify a static-only deployment, cache busting, no live migration/data change,
  and preservation of valid invites/memberships during rollback.
- [x] **Assumptions & risks** - Drafted Decisions and Assumptions And Risks record
  the UX choices, consent semantics, ephemeral continuation, permanent-link
  limitation, URL exposure, startup-dialog races, and ambiguous POST recovery.
