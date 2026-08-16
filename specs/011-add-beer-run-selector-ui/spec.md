# Spec 011: Add Beer-Run Selector UI And Public Discovery

**Feature Branch**: `codex/011-add-beer-run-selector-ui`

**Created**: 2026-08-11

**Status**: Draft

## Overview

The browser currently resolves BeerRunJPN as a temporary in-memory default even though the scoped leaderboard, entry, and map APIs already accept any authorized beer-run ID. This feature replaces that bridge with one global current-run control above the tabs, allowing authenticated users to switch among their member runs and allowing any visitor to find and view public runs without downloading the entire public catalog.

The selected run controls Ranking, Map, the map user filter, and member-authorized Log Drink behavior. BeerRunJPN remains the initial anonymous and no-preference default, while Wrapped remains unchanged until its dedicated scope work.

## Goals

- Make the selected beer-run visible as global application context above the tab navigation.
- Let authenticated users switch among runs where they are owners or members.
- Let authenticated and logged-out visitors find public runs through bounded server-side search instead of loading every public run.
- Persist an authenticated user's selected run safely per stable user ID and validate it before reuse.
- Refresh leaderboard, map, filters, and write affordances consistently when the run or identity changes.
- Prevent stale private data and out-of-order responses from appearing after run switches, logout, session rejection, or access loss.
- Preserve the existing lightweight FastAPI, SQLite, vanilla JavaScript, and no-build architecture.

## Confirmed Decisions

- **Global placement:** The current-run control is full-width and sits between the main header and tab navigation. It is not part of the Ranking tab.
- **Picker interaction:** The control is a button that opens an accessible run-picker dialog or mobile sheet. A native `<select>` is not used because the picker must support grouped member runs, metadata, public search, loading, empty, and error states.
- **Member and public separation:** “My runs” contains only runs where the authenticated caller has an `owner` or `member` role, including public runs they have joined. Other public runs are discovered through search and are never loaded as one unbounded selector list.
- **Anonymous default:** A logged-out page load resolves and selects the public BeerRunJPN row. Anonymous selections of other public runs are session-only and reset to BeerRunJPN after a page reload.
- **Authenticated persistence:** The selected run ID is stored in a user-specific local-storage key based on the stable `/api/me` user ID. The browser stores no run name, visibility, role, or private data in that key.
- **One selected-run context:** Ranking, Map, the map user filter, and Log Drink all use the same selected run. Authenticated public viewers who are not members may read a public run but cannot see or use Log Drink for it.
- **Public discovery scale:** Public search is server-side, case-insensitive, prefix-based, and capped at 20 results. The user narrows the query rather than paging through an entire catalog.
- **API compatibility:** `GET /api/beer-runs` without query parameters retains the Spec 006 response shape and all-visible behavior. New query modes are additive, and the new frontend does not call the unbounded mode during normal startup or selection.
- **Visibility policy:** Public readability depends only on persisted `BeerRun.is_public`; BeerRunJPN receives no name-based authorization exception. Its name is used only to choose the product's default run.
- **Wrapped boundary:** `/wrapped` and the Wrapped tab/link do not change with selection. Task 16 owns scoping or hiding Wrapped.
- **Create and join boundary:** Users with no memberships see explanatory create/join guidance, but Tasks 12 and 13 own functional create and invite/join controls. This feature does not add dead buttons.

---

## Feature 1: Bounded Beer-Run Listing And Public Search

**Who & why:** A user may belong to a few runs while the service contains thousands of public runs. The browser needs a small member list and targeted public discovery without downloading, rendering, or scanning the complete public catalog.

### Functional Requirements

#### FR-1.1: Preserve The Existing Unfiltered List Contract

`GET /api/beer-runs` with no selector query parameters MUST retain the Spec 006 behavior and response shape: authenticated callers receive every public run plus their private member runs, logged-out callers receive public runs only, and each item contains `id`, `name`, `is_public`, `created_at`, `member_count`, and `current_user_role`. Existing consumers and tests MUST continue to work unchanged.

**Verify:** Run the existing beer-run CRUD tests and confirm no-query requests return the same visibility sets, ordering, fields, roles, and status codes as before this feature.

#### FR-1.2: List Only The Authenticated User's Member Runs

`GET /api/beer-runs?view=mine` MUST return only runs for which the valid authenticated caller has an `owner` or `member` membership, regardless of whether each run is public or private. Results MUST use the existing `BeerRunResponse` object shape, appear in case-insensitive name order with ID as a deterministic tie-breaker, and include the caller's non-null role. A caller with no memberships receives `200 OK` and `[]`; a missing, invalid, expired, or deleted-user token receives the shared `401 Unauthorized` response.

**Verify:** With private memberships, public memberships, public non-memberships, no memberships, missing authentication, and invalid authentication, confirm only genuine member runs are returned and every successful item has `current_user_role` equal to `owner` or `member`.

#### FR-1.3: Resolve A Public Run By Exact Name

`GET /api/beer-runs?view=public&name={name}` MUST perform a trimmed, case-insensitive exact-name lookup among public runs only. It MUST return the existing array shape containing one matching run or `[]`; private runs with the same requested name MUST not be disclosed. This mode is used to discover BeerRunJPN's database ID without assuming a fixed ID or downloading the public catalog.

**Verify:** Query BeerRunJPN with canonical and varied casing and confirm one public result; query a private run and an unknown name and confirm each returns `200 OK` with `[]`.

#### FR-1.4: Search Public Runs With A Bounded Prefix Query

`GET /api/beer-runs?view=public&q={query}&limit={limit}` MUST search only public run names using a trimmed, case-insensitive prefix match. `q` MUST be 2–64 characters, `%` and `_` MUST be treated as literal characters rather than wildcard syntax, `limit` MUST default to 20 and accept only 1–20, and results MUST be ordered by case-insensitive name then ID. The endpoint MUST return at most `limit` existing `BeerRunResponse` objects and MUST never return a private run.

**Verify:** Seed more than 20 matching public runs plus matching private runs; confirm deterministic prefix results contain at most the requested limit, contain no private runs, and treat `%` and `_` literally.

#### FR-1.5: Reject Invalid Selector Query Combinations

The `view` value MUST be either `mine` or `public` when present. `view=public` MUST include exactly one of `name` or `q`; `limit` is valid only with `q`; `view=mine` MUST reject `name`, `q`, and `limit`; `name` and `q` MUST be mutually exclusive; and search fields without `view` MUST be rejected. Invalid values, lengths, limits, or combinations MUST return FastAPI's normal sanitized `422 Unprocessable Entity` response without querying or disclosing run data.

**Verify:** Exercise every invalid combination and boundary and confirm `422` responses contain no SQL, table names, token data, or private-run information.

#### FR-1.6: Keep Public Search Metadata Caller-Aware

Public exact and prefix searches MAY receive a valid bearer token. When the authenticated caller is a member of a matching public run, `current_user_role` MUST contain their actual role; otherwise it MUST be `null`. An invalid token MUST be treated as logged out for public search, matching the existing optional-authentication read semantics.

**Verify:** Search the same public run as its owner, a member, an authenticated non-member, a logged-out caller, and a caller with an invalid token; confirm identical public visibility with caller-appropriate roles.

### Architectural Requirements

#### AR-1.1: Extend The Existing Direct Router

The additive query modes MUST remain in `beer_run_routes.py` on the existing `GET /api/beer-runs` route and reuse `auth.get_current_user`, `models.BeerRun`, `models.BeerRunMember`, and the existing `schemas.BeerRunResponse`. Do not add a service layer, new route family, frontend framework, or dependency.

#### AR-1.2: Filter And Bound In SQL

Membership filtering, public visibility, exact/prefix name filtering, deterministic ordering, and limits MUST be applied in SQL before rows reach Python. Response metadata MUST be produced with a bounded query count that does not grow one query per returned run; do not lazily load each result's full membership collection merely to calculate `member_count` or `current_user_role`.

#### AR-1.3: Reuse Existing Indexes Before Adding Schema

The implementation MUST use the existing NOCASE beer-run name index, public-visibility index, and membership indexes. Focused tests or query-plan inspection MUST demonstrate acceptable indexed behavior; no migration is part of this specification unless implementation evidence proves an additional index is required and the user approves that scope separately.

---

## Feature 2: Global Current-Run Control And Picker

**Who & why:** Visitors need to understand which trip the page represents before interpreting a ranking or map. Participants also need one predictable place to switch context without separately configuring the Ranking and Map tabs.

### Functional Requirements

#### FR-2.1: Show The Current Run Above The Tabs

After identity and default-selection resolution, the page MUST show a full-width current-run trigger between `.main-header` and `.tabs`. It MUST display the selected run's name plus a text visibility label (`Public` or `Private`); authenticated members MUST additionally see `Owner` or `Member`. The same selected run MUST remain visible while switching among the in-page Ranking, Map, and Log Drink tabs. The existing Wrapped link continues navigating away to `/wrapped` and does not consume selected-run state.

**Verify:** Select public, private-owner, and private-member runs on desktop and mobile, switch through every visible tab, and confirm the trigger remains in place with accurate non-color-only metadata.

#### FR-2.2: Provide An Accessible Run Picker

Activating the current-run trigger MUST open a dialog or mobile sheet titled “Choose a run.” Authenticated users MUST see a “My runs” section populated only from `view=mine`; all users MUST receive a labeled “Search public runs” form. Each run MUST be a real button with its name, visibility, role when present, and selected state; the same run ID MUST never appear twice in the rendered picker. When the current selection is a public non-member run that is absent from both My Runs and the active search results, the picker MUST show it once as the current public run so the selected state remains understandable.

**Verify:** Open the picker as logged out, as a user with private and public memberships, and as a user whose public membership also matches search; confirm correct sections, metadata, activation, and ID-based de-duplication.

#### FR-2.3: Search Public Runs On Explicit Input

The picker MUST NOT fetch public search results until the trimmed query has at least two characters. Submitting or changing a valid query MUST call the bounded `view=public&q=...&limit=20` mode and display only the returned results. When 20 results are returned, the UI MUST explain that only the first 20 are shown and ask the user to keep typing to narrow the search; it MUST NOT offer an action that loads the entire catalog.

**Verify:** Inspect network traffic while opening the picker and entering zero, one, two, and several characters; confirm no unbounded request occurs and at most 20 public results are rendered.

#### FR-2.4: Define Picker Loading, Empty, And Error States

While identity/default resolution is pending, the trigger MUST show “Loading runs…” and remain disabled. A user with no memberships MUST see “You don't belong to any runs yet” and create/join guidance while BeerRunJPN remains available as the current public view. Public search with no matches MUST say `No public runs match “{query}”`; a search network/server failure MUST preserve the current selection and show an inline retry action without closing the picker.

**Verify:** Simulate delayed startup, no memberships, no public matches, and a failed search; confirm each state is distinct, readable, retryable where applicable, and never represented by a broken or empty control.

#### FR-2.5: Handle Long Names And Small Screens

Names up to the server's 64-character limit MUST not overflow the 500px app container, obscure the auth control, or make picker rows untappable. Visible truncation MAY be used, but the complete name MUST remain available to assistive technology and in the picker's accessible name.

**Verify:** Use a 64-character run name at desktop width and at 390×844; confirm the header, trigger, tabs, dialog, metadata, and touch targets remain usable without horizontal scrolling.

### Architectural Requirements

#### AR-2.1: Put Substantial Selector Behavior In A Separate Module

Add a focused vanilla ES module such as `static/js/modules/beer-runs.js` for run-picker rendering, interaction, storage-key helpers, and picker-local state. Keep network requests in `static/js/modules/api.js`, token/auth primitives in `static/js/modules/auth.js`, generic rendering in `static/js/modules/ui.js`, map behavior in `static/js/modules/map.js`, and cross-feature orchestration in `static/js/app.js`. Do not make `app.js` or `auth.js` the home of the entire selector implementation.

#### AR-2.2: Use Safe DOM Rendering

Run names and search text MUST be rendered through text-safe DOM APIs rather than interpolated into executable HTML or inline handlers. Server-side name validation is not a substitute for correct browser escaping.

#### AR-2.3: Update Static Asset Cache Busting

Any changed JavaScript or CSS asset MUST receive the relevant cache-busting updates in `templates/index.html` and in ES-module import query strings from `static/js/app.js`, following `repository_rules.md`.

---

## Feature 3: Selection, Persistence, And Write Affordances

**Who & why:** A returning participant expects the app to reopen the same authorized trip, but one person's private choice must never influence another account or the logged-out page on a shared device. The selected run must also clearly determine whether drink logging is allowed.

### Functional Requirements

#### FR-3.1: Select One Run As Global Application Context

Selecting a picker row MUST close the picker, update the trigger, set one selected run object/ID/role as application context, reset the map user filter to “All Users,” close run-specific detail surfaces, and start a run-scoped refresh. Ranking, Map, user filtering, user-history data, and any entry submission MUST all use that same selected run ID.

**Verify:** Switch between two runs with distinct entrants and markers, inspect every scoped request URL, open user/map details, and submit an entry as a member; confirm no read, filter, detail, or write uses the previous or a different run ID.

#### FR-3.2: Gate Log Drink By Selected-Run Membership

Log Drink MUST be visible and usable only when the browser has a valid authenticated session and the selected run's `current_user_role` is `owner` or `member`. Selecting a public run as an authenticated non-member MUST hide the Log Drink tab; if Log Drink was active, the app MUST return to Ranking before changing context. The backend's existing member-only authorization remains authoritative and MUST not be weakened.

**Verify:** View the same public run as its member and as an authenticated non-member; confirm only the member sees Log Drink and that direct unauthorized submission still receives the existing concealed member-access failure.

#### FR-3.3: Persist Selection Per Authenticated User ID

After `/api/me` confirms an authenticated identity, selection MUST persist only the run ID under `beerRunJpn.selectedRun.user.{user_id}`. Startup MUST never infer the user ID from the username, decode the JWT for application state, or read another user's key. A public run selected by an authenticated non-member MAY be persisted under that user's key; anonymous public selections MUST remain in memory only.

**Verify:** Have two accounts select different private/public runs in the same browser, reload and alternate logins, and confirm each valid session restores only its own selected run while logged-out reload starts from BeerRunJPN.

#### FR-3.4: Validate A Stored Selection Before Rendering It

The browser MUST validate a stored run ID against current server authorization before displaying its name or requesting its trip data. A stored member-run ID MAY be validated through the fresh `view=mine` result; another stored ID MUST be validated through `GET /api/beer-runs/{beer_run_id}`. A missing, private-inaccessible, deleted, or newly unavailable selection MUST be removed from that user's storage, announced as unavailable, and replaced by public BeerRunJPN when it can be resolved.

**Verify:** Restore valid private, valid public non-member, deleted, membership-removed, and privatized selections; confirm only currently visible runs render and invalid IDs are removed before fallback data loads.

#### FR-3.5: Choose BeerRunJPN When No Preference Exists

When there is no valid authenticated preference, or when the caller is logged out, the browser MUST resolve public BeerRunJPN with the exact-name public query and select its returned ID. It MUST never hard-code a database ID or silently select an arbitrary public run. If BeerRunJPN cannot be resolved because of a transient failure, the app MUST offer retry; if it is genuinely unavailable, the app MUST show a distinct no-current-run state.

**Verify:** Use different database IDs for BeerRunJPN, no stored preference, a failed discovery request, and a missing/private BeerRunJPN row; confirm ID-independent resolution, retry behavior, and no arbitrary fallback.

#### FR-3.6: Preserve Login, Signup, Logout, And Rejected-Session Semantics

Successful login and signup MUST resolve the `/api/me` identity and then restore that user's valid selection or BeerRunJPN. Logout and rejected-session handling MUST immediately invalidate active selected-run state and all in-flight work, clear private rendered state, hide member-only controls, and resolve anonymous BeerRunJPN. A non-401 session-validation failure MUST retain the token and avoid treating the user as safely logged out, matching Spec 010.

**Verify:** Exercise login, signup, explicit logout, rejected token, and transient `/api/me` failure during active private-run requests; confirm selection, token, controls, fallback, and rendered-data behavior match the specified identity state.

### Architectural Requirements

#### AR-3.1: Treat Server Authorization As The Source Of Truth

Local storage and `current_user_role` control restoration and affordances only. Every leaderboard, entry read, detail lookup, public search, and entry write MUST continue relying on the existing server visibility/member dependencies from `permissions.py` and the scoped routes in `main.py`.

#### AR-3.2: Consume The Stable `/api/me` Identity

`validateStoredSession()` or its replacement MUST retain the existing `{id, username}` `/api/me` response sufficiently to derive the current user's storage key. The `access_token` key, ID-based JWT contract, and forced re-login behavior for rejected tokens remain unchanged.

---

## Feature 4: Atomic Refresh, Access-Loss Recovery, And Race Safety

**Who & why:** Run switching, polling, map activation, filtering, and authentication can produce overlapping requests. Users must never see one run's private leaderboard, entries, names, or locations under another run or after access has been lost.

### Functional Requirements

#### FR-4.1: Clear Cross-Run Content Before Loading A New Run

When the selected run changes, the browser MUST clear the previous leaderboard and in-memory arrays, map markers and highlights, user-filter options, user-history modal, and drink-detail sheet before displaying the new run as active. It MUST then show run-specific loading states until both leaderboard and entries requests for the new run succeed. A failed new-run load MUST not restore or relabel the previous run's content.

**Verify:** Switch from a populated private run to a delayed, empty, and failing public run; confirm no previous participant, total, marker, filter, modal, image, or detail appears under the new run's name.

#### FR-4.2: Commit Leaderboard And Entry Results As One Run Snapshot

Leaderboard and entries/map results for a refresh MUST be accepted and rendered together only when both requests succeed for the same selected run and identity generation. The UI MUST never combine a new leaderboard with old entries or vice versa. A selected run with successful empty arrays MUST render “No drinks logged in this run yet” and an empty map as normal content rather than an error.

**Verify:** Delay and fail each half of the paired request independently and return empty arrays for both; confirm only coherent same-run snapshots render and the empty state is normal.

#### FR-4.3: Suppress Stale Run And Identity Responses

Every run-data and public-search request MUST capture the run/search identity and current authentication generation. Login, signup, logout, rejected-session handling, and run selection MUST invalidate older work. A response MUST update state or DOM only if its captured generation and selected run or search query still match at completion; aborting requests MAY supplement but MUST NOT replace stale-result checks.

**Verify:** Force slow A then fast B run loads, slow old then fast new searches, and logout/login during private refresh; confirm only the latest matching operation can render.

#### FR-4.4: Recover From Mid-Session Access Loss Without Leaking State

If either scoped read returns the existing concealed `404` because the run was deleted, privatized, or membership was removed, the browser MUST immediately clear all state listed in FR-4.1, remove the invalid persisted selection, show a concise unavailable notice, refresh selectable/member runs, and fall back once to public BeerRunJPN when available. It MUST not retry the inaccessible run indefinitely or choose another arbitrary public run.

**Verify:** Remove membership, privatize a selected public run for a non-member, and delete a selected run during active use; confirm one bounded recovery, sanitized messaging, complete state clearing, and correct fallback.

#### FR-4.5: Preserve Same-Run Data During Transient Failures Only

A network or non-authorization server failure while refreshing the currently rendered run MAY retain that same run's last known-good coherent snapshot and existing retry-oriented sync status. This retention MUST NOT apply during a run switch, identity transition, or access-loss response, where old content must already have been cleared.

**Verify:** Compare a periodic same-run network failure with a failed run switch and logout during refresh; confirm only the first case retains previously rendered data.

#### FR-4.6: Reset Filtering Before Fetching A New Run

Changing the selected run MUST set the map user filter to “All Users” before requesting entries for the new run. The browser MUST not send a username carried from the previous run in the first new-run entries request.

**Verify:** Select a user filter in Run A, switch to Run B where that user is absent, and confirm the first Run B entries URL has no username filter and all Run B markers can render.

### Architectural Requirements

#### AR-4.1: Keep Refresh Coordination Centralized

`static/js/app.js` MUST remain responsible for cross-module selection/auth generation, paired data refresh, and stale-result acceptance. `static/js/modules/api.js` MUST accept request cancellation signals where needed, while selector rendering and picker-local search state stay in the dedicated beer-run module.

#### AR-4.2: Provide Complete Map And Detail Clearing

`static/js/modules/map.js` MUST expose focused clearing behavior that removes marker layers, entry-ID lookup state, highlights, open popups, and the detail sheet without recreating the Leaflet map. Existing touch-friendly map interactions and marker behavior must remain intact after a subsequent successful load.

---

## Feature 5: Accessible And Mobile-First Interaction

**Who & why:** BeerRunJPN is used on phones during trips, often with touch input and changing connectivity. The picker must remain understandable and operable by keyboard, touch, and assistive technology without crowding the existing header or tabs.

### Functional Requirements

#### FR-5.1: Support Keyboard And Dialog Focus Behavior

The trigger MUST expose `aria-haspopup="dialog"`, current `aria-expanded`, and an accessible name containing the selected run. The picker MUST have dialog semantics and an accessible heading, move focus to a useful first control when opened, contain focus while modal, close on Escape and its real `<button>` close control, and return focus to the trigger when closed.

**Verify:** Complete open, search, selection, close, Escape, and reopen flows using only the keyboard and confirm focus never becomes lost behind the modal.

#### FR-5.2: Announce Search And Selection Status

Public search MUST have a visible label and a polite live region for loading, result counts, no matches, and errors. Selection completion, inaccessible-selection fallback, and no-current-run states MUST be announced without unexpectedly moving focus. The selected run row MUST expose `aria-current="true"` or an equivalent programmatic state.

**Verify:** Inspect accessibility state and live announcements for successful search, no results, failure, selection, and fallback while confirming focus stays on the user's current task.

#### FR-5.3: Preserve Touch-Friendly Layout

The trigger, picker rows, search action, retry action, and close control MUST provide at least 44×44 CSS-pixel touch targets. The picker MUST fit within mobile safe areas, remain scrollable without moving the page behind it, and coexist with the existing 500px container, segmented tabs, sync bar, map, and auth controls.

**Verify:** At 390×844 and a representative desktop viewport, operate every control by touch/click and confirm no overlap, clipped content, inaccessible action, background scroll leak, or horizontal page scroll.

### Architectural Requirements

#### AR-5.1: Reuse Visual Language, Not Inaccessible Markup

The picker MAY reuse the existing glass-card/modal visual language from `static/css/style.css` and `static/css/auth.css`, but it MUST use semantic buttons and complete dialog behavior rather than copying the current non-button close `<span>` pattern.

---

## Data And API Requirements

- No database table, column, relationship, migration, or persisted runtime-data change is required.
- The existing `BeerRunResponse` remains the response item for legacy lists, member lists, exact public lookup, public prefix search, detail, create, and update.
- Browser persistence contains only a run ID in `beerRunJpn.selectedRun.user.{user_id}`; it contains no token, username, run name, visibility, role, membership, leaderboard, entry, image, or location data.
- Public search parameters are treated as untrusted input, validated by FastAPI/Pydantic-compatible constraints, escaped for literal prefix matching, and applied only to `is_public = true` rows.
- Protected runtime files and data—including `boozerun.db`, uploads, `users.json`, and caches—must not be changed during implementation or verification without explicit authorization.

## Integration Points

| Area | Existing boundary | Required interaction |
|------|-------------------|----------------------|
| Beer-run API | `beer_run_routes.py` | Add compatible `view=mine`, exact public, and bounded public-prefix query modes with efficient metadata. |
| Schemas | `schemas.py` | Reuse `BeerRunResponse`; add query validation types only if they clarify the direct route. |
| Models/indexes | `models.py`, migrations 002 and 005 | Reuse public, membership, and NOCASE name indexes; no planned migration. |
| Authorization | `auth.py`, `permissions.py` | Preserve optional identity for public reads and shared 401/404 member policies. |
| Scoped trip data | `main.py`, Spec 009 | Continue using selected-ID leaderboard, entries, filter, and member-only entry routes. |
| API client | `static/js/modules/api.js` | Add bounded member/public query helpers, detail validation, and cancellation support without changing normalized result semantics. |
| Selector module | `static/js/modules/beer-runs.js` (new) | Own picker DOM behavior, rendering, search state, de-duplication, accessibility, and per-user storage helpers. |
| App orchestration | `static/js/app.js` | Own selected global context, identity/run generations, atomic refresh, fallback, and cross-module resets. |
| Auth UI | `static/js/modules/auth.js` | Preserve token/session behavior while allowing selected-role-aware Log Drink visibility. |
| Ranking/general UI | `static/js/modules/ui.js` | Render run-specific loading/empty/error states without mixing data snapshots. |
| Map | `static/js/modules/map.js` | Clear run-specific markers, lookups, highlights, popups, and detail state on transitions. |
| Markup/styles | `templates/index.html`, `static/css/style.css`, `static/css/auth.css` | Add the global trigger and accessible mobile picker using existing visual language. |
| Backend tests | `tests/test_beer_run_crud.py`, `tests/conftest.py` | Extend visibility fixtures for bounded member/public listing, validation, scale, and query-count coverage. |
| Scoped regressions | `tests/test_scoped_routes.py` | Preserve cross-run read/write isolation, empty-run behavior, and authorization responses. |
| Living guidance | `repository_rules.md` | Replace obsolete implicit-BeerRunJPN frontend wording with selected-run behavior and its verification requirements. |

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 009: Scope Entries And Leaderboard API | **Extends** — replaces its temporary in-memory BeerRunJPN resolver while preserving scoped read/write contracts | FR-3.1, FR-4.1 through FR-4.6, AR-3.1, AR-4.1 |
| Spec 006: Add Beer-Run CRUD API | **Modifies** — adds bounded query modes while preserving its unfiltered list and `BeerRunResponse` contracts | FR-1.1 through FR-1.6, AR-1.1 through AR-1.3 |
| Spec 010: Update Frontend Auth And Signup | **Extends** — consumes stable `/api/me` identity and preserves shared login/signup/logout refresh behavior and module boundaries | FR-3.3, FR-3.6, AR-2.1, AR-3.2 |
| Spec 007: Centralize Beer-Run Authorization | **Depends on** — public reads and member-only writes continue using persisted visibility and shared concealed-access policies | FR-1.3, FR-1.4, FR-3.2, FR-4.4, AR-3.1 |
| Spec 004: Harden Auth Tokens | **References** — user-specific persistence relies on stable ID-based authenticated identity and rejected-token handling | FR-3.3, FR-3.6, AR-3.2 |

## Constraints

- Keep FastAPI, SQLAlchemy, SQLite, Pydantic, vanilla ES modules, static HTML/CSS, Leaflet, and the no-build deployment model.
- Add no application dependency, SPA framework, frontend build system, or broad abstraction layer.
- Preserve existing successful beer-run, leaderboard, entry-list, entry-create, login, signup, and `/api/me` response shapes.
- Preserve public read and member-only write authorization; UI affordances never replace server enforcement.
- Preserve geolocation as user-triggerable and the existing touch-friendly map/detail behavior.
- Use isolated test/browser data only. Never mutate live `boozerun.db`, uploads, `users.json`, or caches without explicit authorization.
- Update relevant JavaScript/CSS cache-busting query strings when deployed assets change.
- Run focused backend tests and the complete `uv --cache-dir .uv-cache run pytest` suite for implementation.
- Inspect desktop and mobile-sized views in the Codex in-app browser, including access-loss/logout scenarios and browser console/network behavior.

## Failure Modes And Recovery

- **Initial identity validation is transiently unavailable:** retain the token, show the existing validation-failed/login prompt behavior, and do not restore a private selection under an unverified identity.
- **Member-list request fails:** keep any already validated current selection and show a retryable picker error; do not replace it with an arbitrary run.
- **Default exact lookup fails transiently:** show a retryable no-current-run loading/error state; do not invent or cache an ID.
- **Default genuinely missing or private:** show BeerRunJPN unavailable and no current run; do not leak a private row or select another public run.
- **Public search fails:** preserve the current run and previous coherent trip data; show an inline search retry state.
- **Stored run is inaccessible:** remove only the current user's invalid selection key, clear run-specific data, announce the loss, and fall back once to public BeerRunJPN.
- **Selected run loses access mid-session:** invalidate old requests and rendered data before fallback; never leave private names, totals, entries, images, locations, filters, modals, or markers visible.
- **Run switch data fails:** keep the new selection and show its loading/error state without restoring old-run content beneath the new name.
- **Same-run refresh fails transiently:** retain the last coherent snapshot for that same run and identity and expose retry status.
- **Responses complete out of order:** stale generation/query/run responses are ignored even if cancellation did not prevent completion.
- **Selected public run is read-only:** hide Log Drink for non-members and rely on server member authorization for direct requests.

## Security And Privacy Review

- Anonymous and public-search queries return only persisted public runs. Private runs remain concealed with existing 404 semantics.
- Authenticated member listing requires a valid token and returns only that user's memberships.
- User-specific storage prevents one account's private run ID from becoming another account's restored selection. The ID is still reauthorized before use.
- Run IDs and roles are not authorization credentials; all scoped data and writes remain server-authorized.
- Logout, rejected sessions, and access loss clear every private rendered/state surface before public fallback.
- Search text and returned names are rendered safely and are not inserted into executable HTML or inline JavaScript.
- Tokens, run data, search queries, and storage contents are not logged as diagnostic payloads.
- Existing static uploaded-image URL limitations documented by Spec 009 are unchanged; this feature does not claim authenticated private-media delivery.

## Performance Impact

- Normal anonymous startup adds one bounded exact public lookup before the existing paired scoped data requests.
- Normal authenticated startup uses `/api/me`, one membership-only list, at most one detail validation for a stored public non-member selection, and the existing paired scoped data requests.
- Opening the picker does not download public runs. Public search occurs only for a valid explicit query and returns at most 20 rows.
- Filter, visibility, ordering, and limits are applied in SQLite. Response metadata query count must remain bounded independently of result count.
- Existing indexes are expected to cover member lookup, public filtering, and NOCASE prefix lookup; no schema migration is planned.
- Request generations and optional cancellation bound stale browser work and prevent obsolete responses from causing extra rendering.

## Verification Strategy

1. Extend `tests/test_beer_run_crud.py` with `view=mine`, exact public lookup, prefix search, limit, literal wildcard, validation-combination, optional-auth role, deterministic ordering, and concealed-private tests.
2. Seed more than 20 matching public runs and matching private runs in the isolated database; prove the bounded search returns at most 20 public rows and the browser never calls the unfiltered catalog endpoint.
3. Instrument focused backend tests to confirm filtered list/search query count does not grow per returned run and inspect SQLite query plans for existing index use.
4. Run existing `tests/test_scoped_routes.py` to preserve run-isolated leaderboards, entries, filters, public/private reads, member-only writes, and empty-run behavior.
5. Run the complete `uv --cache-dir .uv-cache run pytest` suite against the isolated database.
6. In an isolated running app, verify anonymous startup, BeerRunJPN default discovery, public search, selection, Ranking/Map switching, refresh, and anonymous reload reset.
7. With two authenticated users and multiple public/private memberships, verify My Runs grouping, de-duplication, role/visibility labels, per-user restore, public non-member selection, Log Drink gating, and selected-run writes.
8. Verify populated-to-populated, populated-to-empty, populated-to-failing, deleted, privatized, and membership-lost transitions clear and reload every state surface correctly.
9. Force overlapping A→B selections, old/new searches, periodic/manual refresh, map activation, filter changes, logout, rejected session, and login; confirm stale responses never render.
10. Inspect network requests to confirm no unbounded `GET /api/beer-runs` call occurs in normal browser flows, every trip-data URL contains the selected run ID, bearer headers match identity state, and retries are bounded.
11. Inspect the browser console for errors and sensitive diagnostic payloads.
12. Verify keyboard dialog behavior, screen-reader names/live states, 44px touch targets, long names, and layout on desktop and at 390×844 using the Codex in-app browser.
13. Verify access loss/logout explicitly clears leaderboard HTML/state, entries, filter options, markers, highlights, popups, user-history modal, and drink-detail sheet before BeerRunJPN appears.
14. Run `git diff --check` and inspect `git status --short`; confirm only intended source/spec/guidance files changed and protected runtime data remains untouched.

## Rollout And Rollback

1. Implement and test the additive query modes while preserving the legacy no-query behavior.
2. Add the selector module, markup/styles, selected-run orchestration, race safeguards, and map/detail clearing against isolated data.
3. Update cache-busting references and `repository_rules.md` in the same change.
4. Run focused and full pytest gates, then complete desktop/mobile browser, network, console, auth-transition, and access-loss verification.
5. Deploy backend and static assets together so the new frontend never targets a backend lacking bounded query modes.
6. No database migration or live-data transformation is required.
7. Roll back backend query additions and frontend assets together if necessary. Existing runs, memberships, entries, uploads, schema, and legacy no-query API remain valid.

## Out Of Scope

- Creating, renaming, changing visibility, deleting, leaving, favoriting, or managing a beer-run in the selector.
- Functional create-run controls; Task 12 owns them.
- Invite preview, acceptance, join controls, or invite-code persistence; Task 13 owns them.
- General public catalog browsing, popularity/recommendation feeds, recent-run history, favorites, arbitrary sorting, substring/fuzzy search, or loading every public run.
- Pagination beyond the bounded first 20 prefix results; users narrow the search in this release.
- Separate view and write run selections; one selected run is intentionally the global context.
- Changing scoped leaderboard, entry-list, or member-only entry-create response contracts.
- Scoping, relabeling, or hiding `/wrapped`; Task 16 owns Wrapped behavior.
- Database schema/index migrations unless separate implementation evidence and user approval expand the scope.
- Authenticated delivery or relocation of private-run images beneath `/static/uploads`.
- Automated browser-framework adoption; manual in-app browser verification remains required unless an existing suitable harness is discovered during implementation.

## Assumptions And Risks

- **Assumption:** Most users belong to a manageable number of member runs. Public-run scale is addressed now; pagination of a user's own memberships can be specified later if real usage requires it.
- **Assumption:** BeerRunJPN normally exists and is public. Existing CRUD can make it unavailable, so this spec retains an explicit no-current-run state rather than an authorization exception.
- **Risk:** A global control above all tabs may suggest Wrapped is selected-run aware even though Task 16 is deferred. The implementation and user guidance must avoid claiming that Wrapped changes with selection.
- **Risk:** Prefix search favors scalable indexed lookup over fuzzy discovery; users must know the beginning of a run name and may need to narrow broad matches.
- **Risk:** The existing run response builder may perform per-run membership loads. AR-1.2 requires bounded metadata retrieval for the new query modes and focused evidence before implementation is considered complete.
- **Risk:** Existing frontend refresh paths overlap and currently retain stale state in some access-loss cases. Feature 4 makes race and privacy corrections part of the selector's required scope rather than optional hardening.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Features 1–5 define API, picker, selection, persistence, refresh, accessibility, and explicit Out Of Scope boundaries with a Verify line for every FR.
- [x] **Testing strategy** — Verification Strategy covers focused API tests, scale/query checks, scoped regressions, full pytest, and isolated desktop/mobile browser scenarios.
- [x] **Existing patterns** — AR-1.1, AR-2.1, AR-3.1, AR-4.1, Integration Points, and Related Specs tie the design to current routers, permissions, scoped APIs, frontend modules, map behavior, and auth flow.
- [x] **Dependencies** — Constraints and AR-1.1 require the existing stack with no new library, framework, build system, or service layer.
- [x] **Architecture & interfaces** — Feature 1 defines exact additive query contracts; Features 2–4 and Integration Points define browser state, module ownership, persistence, and selected-run consumers.
- [x] **Error handling & failure modes** — FR-1.5, FR-2.4, FR-3.4 through FR-3.6, Feature 4, and Failure Modes And Recovery cover invalid input, transient failures, missing defaults, access loss, and stale responses.
- [x] **Security review** — FR-1.2 through FR-1.6, FR-3.2 through FR-3.6, AR-2.2, AR-3.1, and Security And Privacy Review cover authorization, private-run concealment, identity-safe storage, XSS-safe rendering, and logout clearing.
- [x] **Performance impact** — FR-1.4, AR-1.2, AR-1.3, Performance Impact, and Verification Strategy require bounded public results, SQL filtering, bounded metadata queries, and index evidence.
- [x] **Rollout & migration** — Data And API Requirements and Rollout And Rollback define no planned migration, paired backend/static deployment, cache busting, runtime-data protection, and reversible asset/API rollout.
- [x] **Assumptions & risks** — Confirmed Decisions resolves the major UX and scope choices; Assumptions And Risks records member-list scale, default availability, Wrapped signaling, search tradeoffs, and existing race complexity.
