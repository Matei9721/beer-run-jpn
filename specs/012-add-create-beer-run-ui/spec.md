# Spec 012: Add Create Beer-Run UI

**Feature Branch**: `codex/012-add-create-beer-run-ui`

**Created**: 2026-08-13

**Status**: Draft

## Overview

Authenticated users can already create a beer-run through `POST /api/beer-runs`, but the browser exposes no creation flow. This feature adds a mobile-first create mode to the existing global run picker, validates the run name, lets the creator choose public or private visibility, adds the authoritative response to My runs, and selects it as the global Ranking, Map, filter, and Log Drink context. Authorized viewers can also inspect the selected run's member roster.

Creation must preserve the selector's authentication, privacy, persistence, stale-response, and state-clearing guarantees. A logged-out visitor can continue browsing public runs but cannot enter a partial or broken create flow.

## Goals

- Let any authenticated user create a private beer-run from the existing run picker.
- Let the creator choose public or private visibility, defaulting to private.
- Match the server's complete beer-run name policy before submission while keeping the server authoritative.
- Make the returned owner run immediately visible in My runs and select it without an unbounded catalog request.
- Replace the prior run's Ranking and Map content with clear empty states for the new run.
- Handle duplicate names, validation failures, rejected sessions, network failures, and identity changes without losing private-state isolation.
- Preserve the existing vanilla JavaScript module boundaries, accessible picker behavior, and mobile layout.
- Show member usernames and roles to the same callers authorized to read the run.

## Drafted Decisions

- **Presentation:** “Create run” opens a create subview inside the existing run-picker sheet. It does not open a second stacked modal.
- **Availability:** The action is shown only after an authenticated identity is confirmed. It remains available when the user has no memberships or is viewing a public run as a non-member.
- **Privacy:** The form offers a public/private choice and defaults to private. The request sends the selected `is_public` value; server authorization remains authoritative.
- **Roster visibility:** `GET /api/beer-runs/{id}/members` uses the existing public-read policy. Public-run rosters are visible to any public reader; private-run rosters are visible only to members.
- **Successful completion:** The picker closes after success, the created run is selected and persisted for that authenticated user, and the page shows that run's empty Ranking and Map states.
- **Membership update:** The `201` response is the authoritative new My runs item. The browser upserts it by immutable run ID and does not require a second catalog request before selection.
- **Validation:** Client validation mirrors the existing trimmed 3–64 character ASCII allowlist. Server validation and case-insensitive uniqueness remain authoritative.
- **Logged-out treatment:** Logged-out visitors do not see a non-functional Create run action. Login/signup behavior remains owned by Spec 010; this feature does not add a create-specific authentication prompt.
- **Invite boundary:** The authenticated zero-memberships state presents functional Create run guidance only. Joining through an invite remains Task 13 / a later spec.

---

## Feature 1: Authenticated Create Entry Point And Form

**Who & why:** A signed-in participant who wants to start a new trip currently has to call the API manually. They need a clear creation action in the same place where runs are selected, including when they do not yet belong to any run.

### Functional Requirements

#### FR-1.1: Show Create Run To Every Authenticated User

After `/api/me` confirms the current identity, the run picker MUST show a clearly labeled `Create run` action in or immediately beside the My runs section. Its visibility MUST depend on authenticated identity, not on membership in the selected run; an authenticated non-member viewing a public run and an authenticated user with zero memberships MUST both be able to open it. Logged-out, validating, validation-failed, and rejected-session states MUST not expose an activatable create form.

**Verify:** Open the picker while logged out, while authentication is pending, as an authenticated public non-member, as a member, and as a user with zero memberships; confirm only confirmed authenticated states can activate Create run.

#### FR-1.2: Open A Create Subview In The Existing Picker

Activating Create run MUST switch the existing picker sheet to a creation subview titled `Create a run`. The subview MUST contain one labeled name field, concise name guidance, an inline error/status region, a submit action, and a cancel/back action. It MUST not stack another modal or dialog over the picker, and opening it MUST focus the name field.

**Verify:** Activate Create run on desktop and mobile; confirm the existing picker remains the sole dialog, the name field receives focus, all controls have accessible names, and there is no nested backdrop or focus trap.

#### FR-1.3: Cancel Without Changing Run Context

Cancel/back, the picker close control, backdrop dismissal, and Escape MUST leave the current selected run, persisted selection, My runs list, leaderboard, entries, map, filter, and Log Drink availability unchanged. Returning from the create subview to the run list MUST clear create-only input and errors unless a submission is still resolving.

**Verify:** Enter invalid and valid names, then cancel through each supported dismissal path; confirm no request is sent, no trip state changes, and reopening starts with a clean form.

#### FR-1.4: Replace The Zero-Membership Dead End

When an authenticated user has no member runs, My runs MUST explain that no runs have been created or joined yet and present the functional Create run action. It MUST not retain the current dead-end instruction `Create or join a run to add it here` unless every named action in that message is functional in the current release.

**Verify:** Sign in with an account that has no memberships and confirm the picker provides a working create path without presenting a non-functional join control.

### Architectural Requirements

#### AR-1.1: Extend The Existing Picker Module

Picker-local create rendering, form mode, focus handling, inline status, and My runs insertion MUST remain in `static/js/modules/beer-runs.js` or a small dedicated create-run module owned by it. `static/js/app.js` remains responsible only for authenticated identity, generation/race checks, selected-run orchestration, persistence, and scoped refresh. Do not place the entire create form implementation in `app.js`, `auth.js`, or generic `ui.js`.

#### AR-1.2: Preserve Semantic And Text-Safe Rendering

The form MUST use semantic form, label, input, button, status, and alert behavior. User-provided and server-returned run names and error text MUST be assigned through text-safe DOM APIs; no value may be interpolated into executable HTML or inline handlers.

---

## Feature 2: Name Validation And Visibility-Aware Create Request

**Who & why:** A creator needs immediate, understandable feedback, while the browser must not invent looser rules than the API or hide the server's supported public/private choice.

### Functional Requirements

#### FR-2.1: Validate The Complete Name Policy Locally

Before sending a request, the browser MUST trim leading and trailing whitespace and require the result to be 3–64 characters matching the server's ASCII allowlist: letters, digits, spaces, `_`, and `-`. Empty-after-trim, 1–2 character, 65+ character, punctuation outside the allowlist, and non-ASCII names MUST show a specific inline validation error and MUST send no request. The trimmed value is the value submitted.

**Verify:** Exercise the 3- and 64-character valid boundaries plus blank, 2-character, 65-character, punctuation, and non-ASCII inputs; confirm valid values submit trimmed text and invalid values make no network request.

#### FR-2.2: Create With Explicit Visibility

Submitting a valid form MUST call `POST /api/beer-runs` with `Content-Type: application/json`, the current bearer token, and a body containing the trimmed `name` and the selected boolean `is_public`. The form MUST default to private and clearly label the public option as readable by anyone. The server remains authoritative for the final persisted visibility.

**Verify:** Inspect private and public create requests and confirm the current bearer token is present, the trimmed name is sent, the selected boolean is serialized correctly, and the returned run displays the same visibility.

#### FR-2.3: Prevent Duplicate Submissions

While one create request is pending, the form MUST disable its submit action, expose a non-color-only progress state, and ignore additional submit attempts. The name and cancel/close semantics MUST remain coherent; a response MUST be handled at most once.

**Verify:** Double-click, press Enter repeatedly, and activate submit through keyboard and touch during a delayed request; confirm only one POST occurs and only one run/list/selection transition is processed.

#### FR-2.4: Render Safe Server And Network Failures Inline

A case-insensitive duplicate-name `409` MUST keep the form open and say that the name is already in use without disclosing whether the conflicting run is public, private, or owned by someone else. A server `422` MUST show a sanitized name-validation message. A sanitized `500` or definite non-authentication failure MUST show a retryable generic error. A network failure MUST say that the result may be unknown and MUST not automatically repeat the POST. In every retryable case, preserve the entered name, re-enable submit only when safe, and leave the selected run and trip data unchanged.

**Verify:** Force 409, 422, 500, offline/network interruption, and malformed error bodies; confirm safe inline copy, retained input, no private disclosure, no automatic duplicate POST, and no change to the selected run.

#### FR-2.5: Reconcile An Ambiguous Network Result Before Retrying

When the POST has an indeterminate network outcome, the browser MUST perform at most one authenticated `GET /api/beer-runs?view=mine` reconciliation before allowing the same name to be resubmitted. If a previously absent owner run with the submitted normalized name appears, treat that returned run as the successful creation result. If no such run appears or reconciliation also fails, keep the form open, explain that My runs should be checked before retrying, and do not select an unverified run.

**Verify:** Simulate a server commit followed by a lost POST response and confirm reconciliation finds and selects the new owner run without a second POST; simulate failure before commit and confirm no run is invented or automatically retried.

### Architectural Requirements

#### AR-2.1: Keep The Network Contract In `api.js`

Add the create request helper to `static/js/modules/api.js`. It MUST distinguish success data, HTTP status, sanitized API detail, network failure, and abort without requiring picker DOM code to call `fetch` directly. It MUST not log bearer tokens, request bodies, run names, raw response bodies, or database details.

#### AR-2.2: Reuse Or Isolate Validation Logic

Client validation MUST be DOM-independent and reusable from the picker submit path. If the validation and error mapping are substantial, keep them in a focused module following the precedent of `static/js/modules/signup.js`; do not turn `static/js/modules/ui.js` into feature-specific business logic.

---

## Feature 3: Immediate Selection And Empty Run State

**Who & why:** After creating a run, its owner wants to start using it immediately and must not mistake the previous trip's ranking or markers for data in the new run.

### Functional Requirements

#### FR-3.1: Trust And Validate The Successful Response Shape

On `201 Created`, the browser MUST require the existing `BeerRunResponse` fields and accept the returned run as the authoritative created item only when it has a numeric ID, the selected `is_public` value, `current_user_role: "owner"`, and the expected name. An unexpected success shape MUST be treated as a safe server failure: do not insert or select it, retain the current run, and offer recovery through a fresh My runs request.

**Verify:** Return a normal create response and responses missing or contradicting required fields; confirm only the valid private owner response enters My runs and becomes selected.

#### FR-3.2: Upsert The Created Run Into My Runs

The picker MUST insert or replace the valid response by immutable run ID in its local My runs state and render it using the existing member-run row. The resulting list MUST remain in the selector's case-insensitive name order with ID tie-breaking and MUST contain no duplicate ID. The response's `member_count: 1`, owner role, selected visibility, and canonical trimmed name MUST be shown without a required unbounded list fetch.

**Verify:** Create public and private runs whose names sort before, between, and after existing member runs; confirm one correctly ordered owner row with accurate visibility appears immediately each time.

#### FR-3.3: Select Through The Existing Global Transition

After the local membership upsert, the app MUST select the returned run through the same `setCurrentRun` / `selectRun` orchestration used by normal picker choices. Selection MUST persist the ID under `beerRunJpn.selectedRun.user.{user_id}`, update the trigger and owner write affordances, close/reset the picker, clear prior run state, and issue scoped leaderboard and entries requests for the new ID. No separate creation-only selected-run state is permitted.

**Verify:** Create from a populated public or private run and inspect storage, trigger metadata, Log Drink visibility, request URLs, and in-memory/rendered state; confirm every surface transitions to the returned ID through one selection path.

#### FR-3.4: Show Explicit Empty Ranking And Map States

When the new run's scoped leaderboard and entries both return `200 []`, Ranking MUST display `No drinks logged in this run yet.` and the Map MUST contain no markers, highlights, popups, detail sheet, or prior user filter. The Map view MUST also expose a visible or assistive status equivalent to `No mapped drinks in this run yet.` so an empty map is distinguishable from a loading or failed map. Empty-state rendering MUST occur only after both scoped requests for the selected run succeed.

**Verify:** Create a run while the previous run has leaderboard rows, a selected user filter, markers, an open popup/detail sheet, and user history; confirm all old content clears before the new run's explicit empty states appear.

#### FR-3.5: Preserve The New Selection Across Reload

After successful creation and selection, reloading under the same authenticated user MUST restore the created run through the existing validated user-scoped selection behavior. Logged-out reload and another authenticated user MUST not restore or display that private run.

**Verify:** Create and reload as the owner, then log out and sign in as a different user; confirm only the owner restores the new private run.

### Architectural Requirements

#### AR-3.1: Reuse Existing State Clearing And Refresh Generations

Creation success MUST reuse `clearTripState`, map state clearing, user-modal/detail clearing, selected-run persistence, paired scoped refresh, and stale-result guards already orchestrated by `static/js/app.js`. Do not directly render an empty result merely because creation succeeded; the server's scoped `200 []` responses establish the empty snapshot.

#### AR-3.2: Keep My Runs Ownership Coherent

The run-picker module MUST expose a focused membership upsert or equivalent state update rather than duplicating an independently mutable My runs array throughout `app.js`. `initializeRunContext` may still replace the full list from `view=mine`, but a later reconciliation response MUST not override a newer creation, identity, or selection generation.

---

## Feature 4: Session, Race, Accessibility, And Mobile Safety

**Who & why:** Creation is an authenticated write that may complete slowly on a phone. A logout, account switch, closed picker, or delayed response must not select one person's private run under another identity or leave the interface inaccessible.

### Functional Requirements

#### FR-4.1: Bind Submission To The Confirmed Identity

Each create attempt MUST capture the confirmed user ID, token/session context, and application context generation that initiated it. If logout, rejected-session handling, login as another user, or another identity transition occurs before completion, abort the request when possible and ignore its eventual response. A run that the server may have created for the original user MUST never be inserted, persisted, or selected under the new or anonymous identity.

**Verify:** Delay creation, then log out and log in as another account before resolving the response; confirm no private run name, row, storage value, selected context, or scoped request appears for the wrong identity.

#### FR-4.2: Route Create 401 Through Rejected-Session Handling

A create response of `401 Unauthorized` MUST invoke the existing rejected-session flow: remove the invalid token, invalidate in-flight context, clear private rendered state, hide authenticated controls, show the login prompt, and resolve the anonymous BeerRunJPN fallback. The form MUST not remain available behind the prompt and MUST not retry automatically.

**Verify:** Expire or revoke the token immediately before submit and confirm the standard forced re-login and private-state clearing behavior occurs once.

#### FR-4.3: Preserve Picker Keyboard And Focus Behavior

The create subview MUST remain inside the picker's existing focus containment. Tab and Shift+Tab MUST cycle through visible create controls; Escape MUST close the picker; cancel/back MUST return focus to the Create run action; and any picker close, including successful creation, MUST return focus to the global run trigger. Validation and request failures MUST use an assertive alert, while pending and success states MUST use a polite live region without moving focus unexpectedly.

**Verify:** Complete success, validation error, server error, cancel, and close flows using only the keyboard and a screen reader inspection; confirm logical focus order and announced state changes.

#### FR-4.4: Remain Touch-Friendly At Small Widths

At 390×844 and comparable mobile viewports, the name field, guidance, errors, and actions MUST fit within the existing bottom sheet without horizontal scrolling or obscuring the picker close control. Touch targets MUST be at least 44×44 CSS pixels. Compact back/cancel controls MUST override the global full-width button style only where the layout requires it.

**Verify:** Inspect short, 64-character, validation-error, pending, and duplicate-name states at 390×844; confirm readable copy, visible controls, 44px targets, and no horizontal overflow.

### Architectural Requirements

#### AR-4.1: Update Static Asset Cache Busting

Every changed deployed JavaScript or CSS asset MUST receive the relevant cache-busting update in `templates/index.html`, and changed ES-module dependencies MUST receive updated import query strings in `static/js/app.js`, following `repository_rules.md`.

---

## Feature 5: Authorized Member Roster

**Who & why:** A member count does not tell a viewer who is participating in the selected run. The picker should expose the roster without creating a separate privacy policy.

### Functional Requirements

#### FR-5.1: Read Members Through The Existing Run Authorization

`GET /api/beer-runs/{beer_run_id}/members` MUST use the same public-read policy as run detail: any caller may read a public run's roster, while a private run's roster is limited to authenticated members. Missing runs and inaccessible private runs MUST return the shared `404 Beer-run not found` response. Invalid bearer credentials on a public run retain the existing optional-authentication public-read behavior.

**Verify:** Fetch a public roster logged out and as an authenticated non-member; fetch a private roster as a member, non-member, and logged-out caller; confirm only authorized cases return members.

#### FR-5.2: Return Safe, Deterministic Member Metadata

Successful roster responses MUST be JSON arrays of `{user_id, username, role}` objects ordered case-insensitively by username with user ID tie-breaking. The response MUST not include passwords, tokens, invite codes, entry data, or private account fields.

**Verify:** Confirm owner/member roles and usernames are present, ordering is deterministic, and no credential or entry fields appear.

#### FR-5.3: Render The Roster In The Run Picker

When the picker is open for a selected run, it MUST load and display the authorized roster with usernames and human-readable roles. Loading, empty, error, selection changes, logout, and stale-response states MUST be announced safely and MUST never display a prior run's members under a new run name. The roster MUST remain text-safe and fit the existing mobile sheet.

**Verify:** Open public and private runs with different rosters, switch rapidly, log out, simulate a failed roster request, and inspect desktop plus 390×844 layouts for correct isolation and no overflow.

### Architectural Requirements

#### AR-5.1: Keep Roster Authorization Server-Side

The browser MUST treat roster data as untrusted display data and MUST not infer membership from `member_count`, leaderboard rows, or local state. The API helper belongs in `static/js/modules/api.js`; picker rendering belongs in `static/js/modules/beer-runs.js`; authorization remains in `permissions.py`.

## Data And API Requirements

- No database model, schema, migration, runtime-data transformation, or upload change is required. Additive backend route and response-schema work is required for the authorized member roster.
- `POST /api/beer-runs` remains the existing Spec 006 contract:
  - Request: `{"name": <trimmed string>, "is_public": <boolean>}` with bearer authentication.
  - Success: `201` and `BeerRunResponse` containing `id`, `name`, `is_public`, `created_at`, `member_count`, and `current_user_role`.
  - Authentication failure: `401` through the shared credential response.
  - Invalid name/body: `422`.
  - Global case-insensitive duplicate name: `409`.
  - Sanitized unexpected persistence failure: `500`.
- `GET /api/beer-runs/{beer_run_id}/members` returns an authorized roster array of `{user_id, username, role}` objects.
- The create UI MUST not weaken server validation, uniqueness, authentication, transactionality, or owner-membership creation.
- Form input and errors are ephemeral. The feature adds no browser persistence beyond the existing user-scoped selected run ID.
- Protected runtime data—including `boozerun.db`, uploads, `users.json`, and caches—must not be changed during implementation or verification without explicit authorization.

## Integration Points

| Area | Existing boundary | Required interaction |
|------|-------------------|----------------------|
| Create and roster API | `beer_run_routes.py`, `schemas.py`, `permissions.py` | Consume the authenticated visibility-aware create contract and add an authorized member-roster response using shared public-read policy. |
| API client | `static/js/modules/api.js` | Add the JSON create helper with normalized success, status, detail, network, and abort outcomes. |
| Picker state/UI | `static/js/modules/beer-runs.js` | Own authenticated action visibility, create subview, focus/status behavior, validation integration, and My runs upsert. |
| Optional validation module | `static/js/modules/signup.js` pattern | Keep nontrivial create validation/error mapping DOM-independent if extraction improves module size. |
| App orchestration | `static/js/app.js` | Bind attempts to identity/context generations, handle 401, select/persist the response, and run the existing paired refresh. |
| Generic empty states | `static/js/modules/ui.js` | Render the run-specific empty Ranking message without owning create or roster behavior. |
| Map state | `static/js/modules/map.js` | Preserve complete run-state clearing and expose an empty-map status after a successful empty snapshot. |
| Markup/styles | `templates/index.html`, `static/css/style.css` | Add semantic create markup and responsive picker-subview styles using the current visual language. |
| Backend regression tests | `tests/test_beer_run_crud.py`, `tests/test_scoped_routes.py` | Preserve create/private-owner, validation, duplicate, auth, scoped-empty, and cross-run isolation contracts. |

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 011: Add Beer-Run Selector UI | **Extends** — replaces its deferred create guidance with a functional create mode while reusing global selection, persistence, refresh, and picker accessibility | FR-1.1 through FR-1.4, FR-3.2 through FR-4.4, AR-1.1, AR-3.1, AR-3.2 |
| Spec 006: Add Beer-Run CRUD API | **Depends on** — consumes its existing visibility-aware create endpoint, name policy, owner membership, response shape, and error statuses | FR-2.1 through FR-3.2, AR-2.1 |
| Spec 010: Update Frontend Auth And Signup | **References** — preserves confirmed `/api/me` identity, bearer storage, login/signup/logout, rejected-session behavior, and frontend module boundaries | FR-1.1, FR-4.1, FR-4.2 |
| Spec 009: Scope Entries And Leaderboard API | **References** — validates the created run through its existing empty scoped leaderboard and entry responses | FR-3.3, FR-3.4, AR-3.1 |
| Spec 007: Centralize Beer-Run Authorization | **References** — server authentication and membership authorization remain authoritative despite UI affordances | FR-1.1, FR-4.2 |

## Constraints

- Keep FastAPI, SQLite, static HTML/CSS, vanilla ES modules, Leaflet, and the no-build deployment model.
- Add no frontend framework, build system, external dependency, or service layer. Visibility selection and roster display are limited to this run-picker flow; broader run-management settings remain out of scope.
- Preserve all existing beer-run API response shapes and status semantics.
- Preserve the global current-run context across Ranking, Map, filter, and Log Drink.
- Keep public readability based only on persisted `BeerRun.is_public`; never special-case authorization by the BeerRunJPN name.
- Use isolated browser/test data only. Never create a run in live `boozerun.db` during verification without explicit authorization.
- Update relevant cache-busting query strings for every changed static asset.
- Run full pytest regression checks and inspect desktop plus mobile-sized browser behavior during implementation.

## Failure Modes And Recovery

- **Local validation fails:** keep the create subview open, focus or associate the error with the name field, and send no request.
- **Duplicate name:** retain input and show a non-disclosing in-use message; do not search for or expose the conflicting run.
- **Server validation differs:** render a sanitized server validation message; the server wins and no run is selected.
- **Definite server failure:** keep the prior selected run and coherent trip snapshot, then allow an intentional retry.
- **Indeterminate network result:** do not repeat automatically; reconcile My runs once as defined by FR-2.5.
- **Malformed 201 response:** do not insert or select it; reconcile through authenticated My runs.
- **401 or rejected identity:** run the existing forced re-login and anonymous fallback flow.
- **Logout/account change while pending:** abort or ignore the old result and clear create state before rendering the new identity.
- **Scoped empty refresh fails:** retain the newly selected run but show its run-specific loading/error state; never restore old-run data beneath its name.
- **My runs reconciliation completes late:** ignore it when its identity or context generation is stale.

## Security And Privacy Review

- Create is an authenticated write and always relies on the server's bearer validation; UI visibility is only an affordance.
- The UI defaults to private, clearly labels public visibility, and sends only the selected boolean; the server remains authoritative.
- Member usernames and roles are disclosed only through the authorized roster endpoint: public-run readers and private-run members may see them.
- Global case-insensitive name conflicts are reported without revealing the conflicting run's visibility, owner, membership, or ID.
- A response is bound to the initiating stable user ID and cannot populate another user's picker or storage.
- Run IDs and returned roles are not credentials; subsequent reads and writes remain server-authorized.
- Names and errors use text-safe rendering, and no token, request body, run name, raw error body, or private response is written to the console.
- Logout, rejected sessions, and stale completions cannot leave a private created-run name or old trip data visible.

## Performance Impact

- Normal page startup and picker opening add no create-related request.
- A successful create uses one POST plus the existing paired scoped leaderboard/entries refresh.
- The authoritative `201` response avoids an immediate unbounded beer-run list request.
- Only an indeterminate network outcome adds one bounded authenticated `view=mine` reconciliation.
- Local validation, pending-state locking, and generation checks prevent unnecessary duplicate writes and stale rendering.

## Verification Strategy

1. Run existing focused create tests in `tests/test_beer_run_crud.py` for private default, owner membership, trimming, validation boundaries, duplicate names, authentication, and sanitized failure behavior.
2. Run existing scoped-route tests proving a new authorized run returns `200 []` for leaderboard and entries and remains isolated from other runs.
3. If a suitable JavaScript test harness is discovered during implementation, add focused tests for validation, normalized error mapping, membership upsert, and stale identity results; do not introduce a new framework solely for this feature.
4. Parse all changed JavaScript modules and run `git diff --check`.
5. Run the complete `uv --cache-dir .uv-cache run pytest` suite against the isolated test database.
6. In an isolated local app, create public and private runs from populated public-member, private-owner, public-non-member, and zero-memberships contexts; confirm the owner response appears once, is selected, and persists for the creator.
7. Inspect requests to confirm one private POST, then only the new run ID in leaderboard/entry calls, with no unbounded catalog fetch.
8. Confirm prior leaderboard rows, user filter, markers, highlights, popups, detail sheet, and user history clear before the new empty Ranking and Map states render.
9. Exercise blank, short, long, punctuation, non-ASCII, duplicate, server-validation, sanitized 500, malformed success, offline, and commit-then-lost-response scenarios.
10. Delay the request and test repeat submit, picker close, logout, rejected token, and account switch; confirm no stale private state or wrong-user selection.
11. Verify logged-out users cannot open the create subview and authenticated public non-members still can.
12. Verify keyboard-only focus, Escape, cancel/back, announcements, touch targets, 64-character names, and error/pending layouts on desktop and at 390×844 in the Codex in-app browser.
13. Inspect browser console and storage for errors, tokens, request bodies, raw responses, wrong-user keys, or private stale data.
14. Inspect `git status --short` and confirm only intended source/spec files changed and no protected runtime data was modified.

## Rollout And Rollback

1. Add the API helper and DOM-independent validation/error mapping against the already deployed backend contract.
2. Add the picker create subview, authenticated availability, My runs upsert, and responsive styles.
3. Connect success and failure outcomes to existing identity, selection, persistence, clearing, and refresh orchestration.
4. Add explicit empty Ranking/Map status rendering and cache-busting updates.
5. Complete focused/full regression checks and desktop/mobile browser verification using isolated data.
6. Deploy the backend roster route and static assets together. No database migration or live-data transformation is required.
7. Roll back by reverting the roster route and create UI/helper/static-asset versions together. Runs already created through the valid API remain intact and MUST NOT be deleted during rollback.

## Out Of Scope

- Renaming, deleting, leaving, transferring ownership of, or otherwise managing a run after creation.
- Invite generation, preview, acceptance, or join UI; Task 13 owns those flows.
- Automatically creating a run during signup or login.
- Adding participants during creation.
- Changing backend create validation, uniqueness, transactionality, authorization, or migrations.
- Loading the full public run catalog or changing public-search behavior.
- Scoping or changing `/wrapped`; Task 16 owns Wrapped behavior.
- Automated browser-framework adoption when no suitable harness already exists.

## Assumptions And Risks

- **Assumption:** The existing deployed backend includes Spec 006's create contract and Spec 011's bounded My runs and selected-run behavior.
- **Assumption:** A valid `201` response is sufficient to update My runs immediately because creation and owner membership commit atomically.
- **Assumption:** Closing the picker after success is clearer than leaving the create form or selected row open while Ranking and Map refresh behind it.
- **Risk:** A POST response can be lost after the server commits. FR-2.5 uses one My runs reconciliation to avoid accidental duplicate retries.
- **Risk:** The current `.auth-restricted` class reflects write access to the selected run rather than general authentication. The Create run action must use confirmed identity instead of that class.
- **Risk:** The current leaderboard copy and marker-only map do not fully distinguish empty from loading/failure. FR-3.4 makes explicit run-specific empty states part of this feature.
- **Risk:** Picker-local My runs state and initialization results can race. AR-3.2 and FR-4.1 require identity/context generation checks before applying either result.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Features 1–5 define authenticated entry, visibility-aware creation, validation, submission, selection, roster, empty states, race handling, accessibility, and explicit Out Of Scope boundaries with a Verify line for every FR.
- [x] **Testing strategy** — Verification Strategy covers existing focused backend contracts, scoped-empty regressions, full pytest, JavaScript parsing, isolated desktop/mobile browser checks, network inspection, and race scenarios.
- [x] **Existing patterns** — AR-1.1, AR-2.1, AR-3.1, AR-3.2, Integration Points, and Related Specs tie the feature to the implemented picker, API module, auth flow, selected-run orchestration, and scoped refresh.
- [x] **Dependencies** — Constraints and Out Of Scope require the existing stack and explicitly reject a new framework, build system, external library, or backend dependency.
- [x] **Architecture & interfaces** — Data And API Requirements and Features 1–5 define the exact request/response contract, module ownership, picker state, application orchestration, persistence, roster, and empty-state interfaces.
- [x] **Error handling & failure modes** — FR-2.3 through FR-2.5, FR-3.1, FR-4.1, FR-4.2, and Failure Modes And Recovery cover validation, duplicates, malformed responses, server/network failures, ambiguous commits, rejected sessions, and stale results.
- [x] **Security review** — FR-1.1, FR-2.2, FR-2.4, FR-4.1, FR-4.2, FR-5.1, AR-1.2, and Security And Privacy Review cover authenticated writes, authorized roster disclosure, safe rendering, logging, and cross-identity isolation.
- [x] **Performance impact** — Performance Impact and FR-2.3/FR-2.5 bound normal creation to one POST plus scoped reads and allow only one bounded reconciliation after an indeterminate outcome.
- [x] **Rollout & migration** — Data And API Requirements and Rollout And Rollback specify no schema/live-data change, static-asset cache busting, paired asset deployment, and preservation of already created runs during rollback.
- [x] **Assumptions & risks** — Drafted Decisions and Assumptions And Risks identify the same-sheet UX, authenticated availability, response authority, ambiguous network commits, auth-class mismatch, empty-state gap, and picker-state races.
