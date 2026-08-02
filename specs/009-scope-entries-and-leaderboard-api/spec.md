# Spec 009: Scope Entries and Leaderboard API by Beer-Run

## Overview

Entry listing, entry creation, and leaderboard reads currently use global-looking routes that implicitly select the seeded `BeerRunJPN` row. This feature replaces those routes with beer-run-ID-scoped APIs, applies the shared visibility and membership policies from Spec 007, and updates the existing browser UI to call the new routes while continuing to display `BeerRunJPN` as its temporary fixed default.

The feature is an API and compatibility transition, not the run-selector feature. The browser resolves the visible `BeerRunJPN` row through the existing beer-run list API, keeps its ID only for the current page session, and sends that ID with every leaderboard, entry-list, and entry-create request. Later selector work will replace that default-ID choice without changing the scoped endpoint contracts introduced here.

## Goals

- Ensure entry reads, entry writes, username filters, and leaderboard totals cannot cross beer-run boundaries.
- Apply the shared `is_public` read policy and member-only write policy consistently to all scoped routes.
- Preserve the current BeerRunJPN browser experience while removing the old unscoped route paths.
- Preserve successful entry, leaderboard, and creation response shapes so existing rendering and form behavior remain stable.
- Define focused authorization, isolation, failure, performance, and browser verification requirements.

## Specification Decisions

- Public read access follows Spec 007: every run with `is_public = true` is publicly readable. The mutable name `BeerRunJPN` has no authorization meaning.
- A leaderboard contains only current run members who have at least one entry assigned to that same run. Members with zero scoped entries do not receive a zero-total row.
- The old `/api/leaderboard`, `GET /api/entries`, and `POST /api/entries` routes are removed in the same deployment unit that updates the repository frontend to the scoped routes.
- Until run selection is implemented, the browser resolves the visible run named `BeerRunJPN` through `GET /api/beer-runs` and uses its ID for all current trip data calls. A logged-out caller can discover it only while it is public; an authenticated member can continue using it if it becomes private. The browser does not hard-code a database ID.
- No database schema change, migration, persisted run selection, or new dependency is required.

---

## Feature 1: Read Entries and Leaderboards Within One Beer-Run

**Who & why:** Logged-out visitors and trip participants need the map and leaderboard to represent exactly one visible beer-run. A caller viewing one run must never receive another run's locations, user-filter results, entries, or totals, even when the same user participates in both runs.

### Functional Requirements

#### FR-1.1: Add the Scoped Leaderboard Route

The system MUST expose `GET /api/beer-runs/{beer_run_id}/leaderboard`. A successful response MUST be a JSON array whose objects contain exactly `username`, `total_liters`, and `total_alcohol`, preserving the current value meanings and JSON types. Totals MUST include only entries whose `beer_run_id` equals the requested path ID.

**Verify:** Create entries for the same user in two runs, request each run's leaderboard, and confirm each response contains only the totals calculated from that run's entries and retains the three-field response shape.

#### FR-1.2: Include Entrants Only

The leaderboard MUST include a user only when that user has both a current membership in the requested run and at least one entry assigned to that run. A member with zero scoped entries MUST be absent, so a newly created run with only its owner membership returns `[]`. An entry owned by a user who lacks membership in that run MUST NOT create a leaderboard row or contribute to another member's totals.

**Verify:** Request a run containing a zero-entry owner, a member with an entry, and an inconsistent non-member-owned entry; confirm only the member entrant appears and a membership-only run returns an empty array.

#### FR-1.3: Preserve Leaderboard Ranking

Leaderboard rows MUST be ordered by `total_alcohol` from highest to lowest, preserving the current ranking metric. No cross-run entry may influence row inclusion, totals, or ordering. The API does not guarantee relative ordering for exact `total_alcohol` ties.

**Verify:** Seed entrants whose requested-run alcohol totals have a known order plus larger entries in another run, then confirm the scoped response remains ordered only by the requested-run totals.

#### FR-1.4: Add the Scoped Entry-List Route

The system MUST expose `GET /api/beer-runs/{beer_run_id}/entries`. A successful response MUST contain only entries whose `beer_run_id` equals the requested path ID, ordered by timestamp newest first. Entries with `beer_run_id = NULL` MUST be excluded from every scoped response. Each entry object MUST preserve the current twelve fields: `id`, `username`, `drink_type`, `abv`, `quantity`, `brand`, `latitude`, `longitude`, `image_path`, `timestamp`, `timezone`, and `timezone_code`; it MUST NOT add `beer_run_id` to the public response.

Run assignment is authoritative for the entry list: a legacy or inconsistent entry assigned to the requested run remains visible even if its owner no longer has a membership. FR-1.2 independently excludes that owner from the entrant-only leaderboard, so such a marker may not have a corresponding leaderboard/filter row; repairing inconsistent data is outside this feature.

**Verify:** Seed entries in two runs plus one unassigned entry and one requested-run entry owned by a non-member; confirm the requested-run entries remain visible, the other-run and unassigned entries are excluded, results appear newest first, and every object has exactly the established twelve fields.

#### FR-1.5: Keep Username Filtering Inside the Requested Run

The scoped entry-list route MUST continue to accept the optional `username` query parameter. Filtering MUST combine the requested `beer_run_id` and the username identity, using the existing case-insensitive username semantics; it MUST never search entries from another run. An omitted or empty username returns all readable entries for the selected run, and no match returns `[]`.

**Verify:** Give one user entries in two runs and query Run A with that username in canonical and case-varied forms; confirm only Run A entries are returned and an unknown username returns an empty array.

#### FR-1.6: Authorize Reads Through Persisted Visibility

Both scoped GET routes MUST use the shared public-read policy from `permissions.py`. Any caller may read a run with `is_public = true`, including a logged-out caller, an invalid-token caller treated as logged out, and an authenticated non-member. A private run is readable only by an authenticated owner or member.

**Verify:** Exercise both GET routes against an arbitrarily named public run and a private run as logged-out, invalid-token, owner, member, and authenticated non-member callers and confirm the Spec 007 visibility matrix.

#### FR-1.7: Conceal Inaccessible Private Runs

A missing run and a private run that the caller cannot read MUST both return `404 Not Found` with detail `Beer-run not found`. Read authorization MUST NOT use or special-case the run name, and MUST NOT reveal whether a private run exists.

**Verify:** Compare both scoped GET responses for a missing ID and an inaccessible private-run ID and confirm identical status and detail with no entry, member, or visibility disclosure.

### Architectural Requirements

#### AR-1.1: Consume the Shared Read Access Result

The scoped GET routes MUST consume `permissions.authorize_public_read` through FastAPI dependency injection and use the authorized `PublicReadAccess.beer_run` as their run identity. They MUST NOT reload the run to make a second authorization decision or reproduce visibility logic inline.

#### AR-1.2: Scope Queries in SQLite

Entry selection and leaderboard aggregation MUST apply the requested run ID in the database query. The leaderboard MUST NOT load every entry relationship for each user and filter other runs in Python. The implementation MUST use the existing membership and entry indexes without introducing an N+1 query per leaderboard row. Focused verification MUST show that query count does not grow with the number of leaderboard rows and that the migrated isolated database query plan uses the run-scope index rather than scanning unrelated entries.

#### AR-1.3: Reuse Existing Response Contracts

The implementation MUST make the scoped response contracts explicit by reusing `schemas.Entry` and `schemas.LeaderboardUser` or by declaring equivalent response models with exactly the same JSON output. Timestamp serialization MUST remain compatible with the current ISO-formatted response consumed by `static/js`.

### Feature Validation

Test empty runs, overlapping users across two runs, entrants and zero-entry members, unassigned entries, inconsistent non-member-owned entries, username filters, exact response fields, timestamp ordering, ranking, bounded query count, run-index query planning, arbitrary public-run names, private membership, missing runs, negative IDs, non-integer IDs, and invalid tokens. All database setup must use the isolated test override; non-integer path IDs retain FastAPI's standard `422` validation response, while a valid but missing integer follows FR-1.7.

---

## Feature 2: Create an Entry in One Authorized Beer-Run

**Who & why:** Authenticated participants need every submitted drink to be written to the run they are actively viewing. The server, not a caller-supplied form field, must bind the entry to the authorized path run so a client cannot write into another trip.

### Functional Requirements

#### FR-2.1: Add the Scoped Entry-Create Route

The system MUST expose `POST /api/beer-runs/{beer_run_id}/entries`. It MUST accept the same multipart form fields and optional image upload as the current `POST /api/entries` route: required `drink_type`, `abv`, `quantity`, `latitude`, and `longitude`; optional `brand`, `client_timestamp`, `client_timezone`, `client_timezone_code`, and `image`. Existing parsing, numeric acceptance, image normalization, timestamp fallback, and field-validation behavior remain in force; this feature adds no new drink, coordinate, ABV, or quantity ranges. With otherwise authorized access, missing or malformed required form fields retain FastAPI's standard `422` validation response.

**Verify:** Submit the existing browser form payload, with and without a valid image, to the scoped route and confirm both requests are accepted without adding a run field to the multipart body.

#### FR-2.2: Require Membership for Every Write

The create route MUST require a valid bearer-authenticated user who is an owner or member of the path run. Public visibility MUST NOT permit an authenticated non-member to write. Missing or invalid authentication MUST return `401 Unauthorized` with detail `Could not validate credentials` and `WWW-Authenticate: Bearer`; after authentication succeeds, a missing run or non-member target MUST return the shared concealed `404 Beer-run not found` response.

**Verify:** Exercise owner, member, authenticated non-member, logged-out, and invalid-token creation against public, private, and missing runs and confirm the shared member-access status, detail, and header contract.

#### FR-2.3: Bind the Entry to the Authorized Path Run

A successful create MUST set `user_id` from the authenticated user and `beer_run_id` from the authorized path run. The accepted multipart contract MUST NOT define `user_id`, `username`, or `beer_run_id`; if a caller submits extra fields with those names, they have no effect and MUST NOT override either server-derived identity. Creating an entry in Run A MUST change only Run A's entry list and leaderboard, and the scoped route MUST never create an entry with `beer_run_id = NULL`.

**Verify:** Submit an entry to Run A as a user who also belongs to Run B while spoofing `user_id`, `username`, and Run B's `beer_run_id`; confirm the extra fields have no effect, the row has the authenticated caller's ID and Run A ID, the run ID is non-null, and neither Run B endpoint changes.

#### FR-2.4: Preserve the Successful Create Response

A successful create MUST continue to return `200 OK` with exactly `{"status": "success", "entry_id": <integer>}`. The existing UI must not need a new response parser for this transition.

**Verify:** Create an entry through the scoped route and assert the status code, exact response keys and values, and persisted row ID.

#### FR-2.5: Authorize Before Processing Uploads

Authentication, run lookup, and membership authorization MUST complete before the request creates an entry row or writes an uploaded image. A denied request MUST create neither database state nor a new upload file.

**Verify:** Submit a valid image as a logged-out caller and authenticated non-member and confirm the response follows FR-2.2 while isolated entry counts and the test upload directory remain unchanged.

#### FR-2.6: Sanitize Create Failures

Image-processing or pre-commit persistence failures MUST return `500` with exactly `{"detail": "Unable to create entry"}` and MUST NOT expose exception strings, local filesystem paths, SQL text, credentials, tokens, or other server internals. The database session MUST roll back and no entry row may remain. Because current timestamp-based filenames cannot prove exclusive file ownership, this feature MUST NOT delete a possibly pre-existing upload during failure cleanup; collision-safe attribution and reliable orphan cleanup remain deferred to Task 15.

**Verify:** Force image and pre-commit database failures and confirm the exact sanitized detail, transaction rollback, no new entry, no deletion of pre-existing files, and no raw exception or path in the response.

### Architectural Requirements

#### AR-2.1: Consume Shared Member Access

The create route MUST consume `permissions.authorize_member_access` and use its `MemberAccess.beer_run` and authenticated membership result. It MUST NOT repeat token validation, membership queries, or authorization error construction inside the route.

#### AR-2.2: Preserve Direct Entry and Image Architecture

Entry creation and the current Pillow-based normalization remain within the compact route/helper structure owned by `main.py`; no service layer, queue, background worker, or storage abstraction is introduced. Shared internal helpers may be used to keep serialization and creation behavior consistent, but they must not weaken authorization ordering.

#### AR-2.3: Do Not Expand Upload Migration Scope

This feature MUST preserve existing image-path values and current upload-directory compatibility. Collision-safe run folders, UUID filenames, and migration of existing upload paths remain owned by Task 15 and MUST NOT be partially implemented here.

#### AR-2.4: Make Commit the Final Failure Boundary

All fallible database refreshes and response-value preparation MUST occur before the final commit or be removed when their output is unnecessary. The route MUST NOT call `db.refresh` or perform fallible response preparation after commit. Once commit succeeds, it MUST return the successful FR-2.4 response and MUST NOT report a rollback-style `500` that cannot undo the committed row.

#### AR-2.5: Isolate Upload Tests

Production uploads MUST continue to default to `static/uploads`, but entry creation MUST expose a narrow internal upload-location or image-writer seam that focused tests can redirect or monkeypatch to a `tmp_path`. Tests MUST NOT create, overwrite, inspect, or delete files in the repository's real `static/uploads` directory.

### Feature Validation

Test owner/member success in public and private runs, non-member denial in both visibility modes, missing/invalid authentication, missing run concealment, negative and non-integer path IDs, cross-run isolation, spoofed identity/run fields, exact response shape, multipart validation, timestamps/timezones, valid and invalid images, authorization-before-file-write, sanitized failures, pre-commit rollback, post-commit success finality, and the absence of any cleanup deletion. Redirect or mock every image write through the isolated test seam from AR-2.5; same-path overwrite risk remains explicitly deferred to Task 15.

---

## Feature 3: Keep the Existing Browser on BeerRunJPN Through Scoped Calls

**Who & why:** Current users should see the same BeerRunJPN leaderboard, map, filters, and entry form immediately after the API paths change. They should not have to select a run until the dedicated selector work ships, and the transition must not hard-code a database ID that differs across installations.

### Functional Requirements

#### FR-3.1: Resolve the Default Run ID Through the Existing API

On initial page setup, the browser MUST call `GET /api/beer-runs` and identify the visible run whose case-insensitive name is `BeerRunJPN`. It MUST retain the returned `id` and `current_user_role` as the current page's temporary default access state. The run-list request MUST include the stored bearer token when available so an authenticated member can continue to resolve BeerRunJPN if it becomes private; a logged-out caller can resolve only the public row returned by the existing list policy. The browser MUST NOT assume that the database ID is `1`, include a run ID in HTML, or persist this transitional default in local storage.

**Verify:** Seed BeerRunJPN with a non-default database ID, load the app logged out and as a member and authenticated non-member, and confirm trip-data calls use the returned ID while the in-memory role matches the list response.

#### FR-3.2: Send the Default ID With Every Trip-Data Call

The frontend API helpers and orchestration MUST call only:

- `GET /api/beer-runs/{beer_run_id}/leaderboard`
- `GET /api/beer-runs/{beer_run_id}/entries`
- `POST /api/beer-runs/{beer_run_id}/entries`

Entry filters MUST remain query parameters on the scoped entry URL. Entry creation MUST continue to send the stored bearer token. Scoped GET helpers MUST support sending the bearer token when one is available so their contract also works for later private-run selection, while public BeerRunJPN remains readable without a token.

**Verify:** Inspect browser network requests during initial refresh, username filtering, manual refresh, periodic refresh, login, and entry submission and confirm every trip-data URL contains the resolved BeerRunJPN ID and no request uses an old route.

#### FR-3.3: Preserve Current Visible Behavior

After default-run resolution succeeds, the leaderboard, user filter, map markers, user-history modal, refresh controls, login/logout behavior, geolocation flow, image upload, and post-submit refresh MUST continue to work as they do now. An authenticated caller whose resolved `current_user_role` is neither `owner` nor `member` may continue reading a public BeerRunJPN, but the submit handler MUST block before making a create request and show `You are not a member of BeerRunJPN.` Login, logout, and every successful default re-resolution MUST refresh the stored role. This feature MUST add no run selector, create-run UI, invite UI, or selected-run persistence.

**Verify:** Exercise the existing primary browser flows on desktop and a mobile-sized viewport and confirm members can display and write BeerRunJPN data, authenticated non-members can display public data but receive the local membership message without a POST, and no layout regression or console error occurs.

#### FR-3.4: Handle an Unavailable Default Safely

If `/api/beer-runs` fails or no visible `BeerRunJPN` row is returned, the browser MUST NOT fall back to another run, invent an ID, call an unscoped route, or enable entry submission without a target. It MUST keep trip data empty and disable submission. The existing sync-status surface MUST say `BeerRunJPN is not available` after a successful list without the run, or `Connection unavailable; retrying` after a network or server failure. Manual refresh, login/logout state changes, and the existing 30-second refresh cycle MUST retry default discovery while no run ID is available; recovery MUST proceed automatically once discovery succeeds.

**Verify:** Test a failed run-list request and a successful list without BeerRunJPN; confirm no trip-data or create request is made, no other run is selected, submission is blocked, the exact appropriate message appears, manual/periodic discovery retries occur, and later success restores normal refresh and submission.

#### FR-3.5: Handle Scoped Request Failures Without Corrupting UI State

Frontend API helpers MUST distinguish successful array data from non-OK HTTP and network failures and MUST never return an error object to leaderboard or entry renderers as if it were an array. After a scoped GET network or `5xx` failure, the browser MUST retain the resolved run ID and last successfully rendered data, show `Connection unavailable; retrying`, and retry on manual or periodic refresh. After a scoped GET `404`, it MUST clear the run ID, re-run default discovery once, and retry the read once only if BeerRunJPN resolves to an accessible ID; otherwise it enters FR-3.4's unavailable state.

A create `401` MUST retain the existing rejected-session behavior. After a create `404`, the browser MUST re-fetch visible runs without automatically resubmitting the form: if BeerRunJPN remains visible, it retains the read ID, refreshes `current_user_role`, and blocks later creates when the role is absent; if it is no longer visible, it enters FR-3.4's unavailable state. A network or `5xx` failure MUST retain the current run state and form data for an explicit user retry. No failure path may start an unbounded immediate retry loop or erase last-known-good rendered data for a merely transient failure.

**Verify:** After a successful load, simulate scoped GET network, `500`, and `404` responses plus create `401`, `404`, network, and `500` responses; confirm renderers never receive error objects, access state/messages/retries follow this requirement, a still-public non-member run remains readable but not writable, and entry submission is never replayed automatically.

#### FR-3.6: Remove the Old Route Contract

The application MUST remove `GET /api/leaderboard`, `GET /api/entries`, and `POST /api/entries`. Repository frontend code and automated tests MUST have no remaining dependency on those paths. Requests to them after deployment MUST receive the normal FastAPI not-found response rather than default-run data.

**Verify:** Search source and tests for old path usage, then request all three old method/path combinations and confirm they return `404` while the equivalent scoped calls succeed.

### Architectural Requirements

#### AR-3.1: Preserve Frontend Module Boundaries

`static/js/modules/api.js` MUST own the beer-run list request, scoped request construction, optional read authorization headers, and success-versus-failure response handling. `static/js/app.js` MUST own choosing and holding the temporary default run ID and role plus coordinating discovery, refresh, recovery, and submission. Authentication state remains in `static/js/modules/auth.js`; rendering and map responsibilities remain in their existing modules. The availability messages in FR-3.4 and FR-3.5 MUST use the existing sync-status element, while the non-member write block uses the existing alert pattern, so this feature requires no new layout or CSS.

#### AR-3.2: Make the Later Selector a State Substitution

Frontend request helpers MUST require a beer-run ID rather than internally searching for BeerRunJPN. Only application orchestration may resolve the temporary default. Later Tasks 11 and 14 must be able to replace that ID source with selected-run state without changing the scoped URL, response, filter, upload, or authorization contracts.

#### AR-3.3: Update Static Cache Busting

Every changed deployed JavaScript module and importing module MUST receive the relevant cache-busting query-string updates in module imports and `templates/index.html`, following `repository_rules.md`. This reduces stale-module use but cannot refresh HTML that a client has already cached; the remaining stale-client `404` risk must stay explicit in rollout reporting.

### Feature Validation

Inspect the running app on desktop and a mobile-sized viewport. Cover logged-out public viewing, logged-in public/private BeerRunJPN resolution, username filtering, periodic/manual refresh, entry submission, default-run discovery with a non-fixed ID, missing default, initial and mid-session failures, bounded recovery, browser network URLs, console output, and cache-busted asset loading. Non-fixed IDs, missing defaults, private defaults, and forced failures MUST use a disposable database and isolated upload root configured before the test app starts; browser verification MUST NOT rename, privatize, delete, or otherwise mutate the protected runtime BeerRunJPN row.

---

## Data Requirements

- `Entry.beer_run_id` remains the persisted scope for every scoped entry. The existing nullable column is unchanged: legacy `NULL` rows are excluded from scoped reads and leaderboard calculations, and the scoped POST always writes a non-null path-run ID. A non-null migration or legacy-data repair is outside this feature.
- `BeerRun.is_public` remains the sole public-read authorization flag.
- `BeerRunMember(beer_run_id, user_id)` remains the sole membership input for private reads, writes, and leaderboard eligibility.
- `User.username` retains its existing case-insensitive identity semantics.
- Existing entry, user, run, membership, invite, and image-path data are unchanged; no migration or backfill is required.
- No selected-run preference is persisted by this feature.

## Integration Points

- `main.py`: replace the three default-run entry/leaderboard routes with scoped routes while preserving serialization, timestamp parsing, and image normalization; provide the narrow isolated-upload test seam and final commit boundary.
- `permissions.py`: consume `authorize_public_read`, `authorize_member_access`, typed access results, and shared 401/404 errors unchanged.
- `models.py`: use the existing `BeerRun`, `BeerRunMember`, `Entry`, and `User` relationships and indexes; no model change is expected.
- `schemas.py`: reuse or enforce the existing `Entry` and `LeaderboardUser` response shapes; no new run field is added.
- `beer_run_routes.py`: existing `GET /api/beer-runs` supplies the temporary default run ID and retains its general visibility semantics.
- `static/js/modules/api.js`: request visible beer-runs, construct scoped leaderboard, entry-list, and entry-create requests, support bearer headers for scoped reads, and keep non-OK responses out of data render paths.
- `static/js/app.js`: resolve and retain the in-memory BeerRunJPN ID, gate refresh/submission on it, coordinate bounded recovery, update the existing sync-status message, and pass the ID to API helpers.
- `templates/index.html` and JavaScript module imports: update cache-busting versions for changed browser assets.
- `tests/conftest.py`: reuse isolated database setup and the owner/member/non-member public/private run fixture.
- Focused scoped-route tests: cover isolation, response shapes, authorization, entrant semantics, filtering, creation, uploads, rollback, and old-route removal.
- `tests/test_main.py` and `tests/test_auth.py`: migrate existing callers and compatibility assertions from old routes to the scoped contract where applicable.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 007: Centralize Beer-Run Authorization | **Depends on** - scoped reads and writes consume its general `is_public`, member-only, typed-result, and concealed-error contracts | FR-1.6, FR-1.7, FR-2.2, AR-1.1, AR-2.1 |
| Spec 006: Add Beer-Run CRUD API | **Modifies** - uses its visible beer-run list and arbitrary-public-run semantics while superseding its temporary constraint that the old entry and leaderboard paths remain unchanged | FR-3.1, FR-3.4, FR-3.6 |
| Spec 003: Backfill Existing Trip | **Modifies** - replaces its temporary implicit BeerRunJPN entry and leaderboard routes with explicit scoped APIs while preserving the visible default-trip experience | FR-3.1 through FR-3.6 |
| Spec 002: Add Beer-Run Schema | **Depends on** - uses its entry scope, membership uniqueness, visibility flag, relationships, and indexes without another migration | FR-1.1 through FR-2.3, AR-1.2 |
| Spec 004: Harden Auth Tokens | **References** - continues to derive entry ownership and optional read identity from its ID-based bearer tokens | FR-1.6, FR-2.2, FR-2.3 |

This spec supersedes Task 14's original bullets that introduce scoped URL construction, make API helpers accept a run ID, add read bearer headers, refresh after creation, and remove old endpoint usage. Release 1 Task 11 and the remaining Task 14 work will later **modify** Feature 3 by adding selector UI and persistent selected-run state, replacing the temporary BeerRunJPN choice, clearing or prompting for inaccessible saved selections, blocking submission when no selected run exists, and refreshing on run changes. Task 13's later invite-acceptance flow must refresh selected-run membership metadata before enabling entry creation. Those later tasks must preserve the scoped API contracts and helper inputs defined here.

## Constraints

- Keep the lightweight FastAPI, direct SQLAlchemy, SQLite, vanilla JavaScript, and no-build-step architecture.
- Deploy the backend route replacement and frontend caller update as one atomic application release; either half alone is incompatible.
- Preserve the successful public response shapes and multipart form contract.
- Do not add libraries, a service layer, a frontend framework, or a database migration.
- Do not migrate, delete, reset, overwrite, or test against live `boozerun.db`, uploads, `users.json`, caches, or other protected runtime data.
- Use the isolated test database and AR-2.5 upload seam for automated tests. Forced browser states must run against a disposable app/database/upload-root configuration, never protected runtime state.
- Use `uv --cache-dir .uv-cache run pytest` for full automated verification.
- Update cache-busting query strings and inspect the running browser UI because deployed JavaScript behavior changes.

## Failure Modes and Recovery

- **Public scoped read:** succeeds without authentication for any `is_public = true` run.
- **Private scoped read:** succeeds for owners/members; missing, invalid, or absent usable identity and authenticated non-members receive concealed `404 Beer-run not found`.
- **Scoped create authentication:** missing or invalid bearer identity returns the shared `401` and bearer challenge before upload processing.
- **Scoped create membership:** authenticated non-member or missing target run returns concealed `404` before upload processing, even when the run is public.
- **No entries or entrants:** return `[]`, not `404`, `null`, or an object wrapper.
- **Unknown username:** return `[]` within the authorized run.
- **Image failure:** return exact sanitized detail `Unable to create entry`, persist no entry, and never delete a possibly pre-existing timestamp-path upload.
- **Pre-commit database failure:** roll back and return the same sanitized `500`; no partial entry remains, unrelated database data is untouched, and cleanup does not delete any upload path. A same-path overwrite remains possible under the preserved timestamp naming. A committed entry is final and must not subsequently be reported as rolled back.
- **Default discovery failure:** do not select another run; block trip requests and writes, show the FR-3.4 status, and retry discovery through manual/login/periodic triggers.
- **Mid-session scoped GET failure:** retain last-known-good data for transient failures; clear and re-resolve once for `404`; never render an error body as trip data.
- **Scoped create failure:** keep existing `401` session handling, re-resolve without auto-resubmission after `404`, and preserve the user's form for explicit retry after network/`5xx` failure.
- **Removed route request:** return the normal application `404`; never redirect silently to BeerRunJPN.
- **Rollback:** restore the old frontend callers and old backend routes together. No database or uploaded-file rollback is required because this feature changes neither schema nor existing data paths.

## Security and Privacy Boundaries

- Authorization decisions use persisted run visibility and membership only; neither path ownership claims, usernames, frontend state, nor the literal name `BeerRunJPN` authorizes access.
- The server derives entry ownership from the bearer-authenticated user and run scope from the authorized path parameter.
- Concealed private-run `404` responses prevent existence disclosure through the scoped APIs.
- Username filtering is always conjoined with the authorized run ID and cannot enumerate entries in another run.
- Error responses must not expose raw exception strings, SQL, local paths, credentials, tokens, or image internals.
- This feature protects entry metadata and leaderboard data returned by APIs. Existing files under `/static/uploads` remain publicly addressable when their URL is known because `/static` is mounted without per-run authorization. Task 15 changes organization and collision safety but does not add private-media authorization; authenticated media delivery requires a separate specification.

## Performance Impact

- Entry reads use the existing `Entry.beer_run_id` index and bounded optional username join.
- Leaderboard inclusion and totals are computed with run-scoped membership/entry queries or aggregation, avoiding per-member relationship loads and reads of entries from other runs.
- Normal browser startup adds one existing `GET /api/beer-runs` request before initial trip-data refresh. The ID is reused in memory, so later refreshes do not list runs unless the ID is unavailable or a scoped `404` triggers one bounded re-resolution.
- No background work, polling interval change, unbounded cross-run scan, migration, or additional runtime service is introduced.

## Rollout and Migration

1. Add the scoped GET and POST routes, shared run-scoped query behavior, focused tests, and sanitized failure handling.
2. Update the browser API helpers and application orchestration to resolve BeerRunJPN and use the scoped routes.
3. Remove the three old route handlers and migrate all repository tests and frontend callers in the same change.
4. Update JavaScript cache-busting query strings so deployed clients do not retain old endpoint calls.
5. Run focused route/auth/upload tests and the complete `uv --cache-dir .uv-cache run pytest` suite against isolated data.
6. Inspect the running app on desktop and mobile-sized viewports, including network calls and console output.
7. Deploy backend and static assets together. No database migration or live runtime-data change is part of this rollout.
8. Roll back backend and frontend assets together if necessary; existing entries, runs, memberships, uploads, and database schema remain valid.

## Out of Scope

- A run selector, persistent selected-run ID, switching between runs, create-run UI, invite UI, automatic selection after invite acceptance, or clearing/prompting for an inaccessible persisted selection. Task 11 and the remaining Task 14 work own selected-run state; Tasks 12 and 13 own create/invite UI.
- Allowing the transitional UI to fall back to an arbitrary public run when BeerRunJPN is unavailable.
- Changing beer-run CRUD, visibility, ownership, membership, invite, signup, login, or JWT semantics.
- Adding `beer_run_id` to entry or leaderboard response objects or changing successful status codes.
- Member removal, ownership transfer, a non-null `Entry.beer_run_id` migration, or automatic repair of unassigned or inconsistent legacy membership/entry data.
- Collision-safe upload names, reliable orphan-file attribution/cleanup, run-specific upload directories, or existing file/path migration; Task 15 owns these changes.
- Authenticated delivery or relocation of private-run images already reachable beneath `/static/uploads`.
- Scoping or hiding `/wrapped`; Task 16 owns Wrapped visibility.
- Rate limiting, pagination, date ranges, search beyond the existing username filter, or a general analytics/query layer.

## Validation Strategy

1. Add focused scoped-route tests using two runs and overlapping users to prove entry, filter, creation, and leaderboard isolation.
2. Test entrants-only behavior, including zero-entry members, an empty newly created run, unassigned entries, and an inconsistent non-member-owned entry whose marker remains listed but whose owner is absent from the leaderboard.
3. Test exact entry and leaderboard response shapes, timestamp ordering, alcohol ranking, empty arrays, case-insensitive username filtering, non-integer path validation, and valid-but-missing integer IDs.
4. Exercise both GET routes across public/private/missing runs with owner, member, non-member, logged-out, missing-token, and invalid-token callers.
5. Exercise POST across the same identities and visibility modes, asserting the exact shared 401/404 contracts and absence of denied side effects.
6. Verify successful multipart entry creation, ignored spoofed identity/run fields, authenticated user binding, non-null path-run binding, image normalization, timestamp/timezone preservation, and exact `200` response.
7. Through the AR-2.5 test seam, force image and pre-commit persistence failures; confirm exact sanitized errors, rollback before commit, no cleanup deletion, and documented same-path overwrite risk. Inspect the success path to confirm no `db.refresh` or fallible response preparation occurs after commit and a successful commit returns FR-2.4.
8. Confirm all old route method/path combinations return `404` and repository source/tests no longer call them.
9. Run the complete pytest suite using `uv --cache-dir .uv-cache run pytest`; confirm tests use only isolated databases and upload paths and do not touch live `boozerun.db`.
10. Use a disposable browser-test database and upload root to inspect desktop and mobile-sized views for non-fixed-ID BeerRunJPN discovery, logged-in private-default discovery, leaderboard/map rendering, user filters, refresh behavior, login/logout, entry submission, missing default, and initial/mid-session failure recovery.
11. Inspect browser network requests to confirm the resolved run ID is present in every trip-data URL, read bearer headers behave correctly, retries are bounded, failed submissions are not replayed, old paths are absent, changed assets are cache-busted, and the console has no errors.
12. Instrument or inspect focused leaderboard SQL to confirm bounded query count and run-scope index use on the migrated isolated database.
13. Run `git diff --check` and inspect `git status --short` to confirm only intended source/spec changes exist and protected runtime data remains untouched.

## Assumptions and Risks

- **Confirmed decision:** General `is_public` semantics from Spec 007 supersede Task 09's original BeerRunJPN-only public-read wording.
- **Confirmed decision:** Leaderboards contain entrants only; membership without a scoped entry does not create a zero-total row.
- **Confirmed decision:** The current frontend migrates immediately to scoped routes but remains temporarily bound to BeerRunJPN without selection or persistence.
- **Assumption:** The seeded BeerRunJPN row is normally present and public during this transition. Existing CRUD permits an owner to rename, privatize, or delete it; an authenticated member may still resolve it while private, while other callers enter the explicit unavailable state rather than selecting a different run.
- **Assumption:** Valid application-created entries belong to users who are members of their run. The current schema cannot enforce that cross-table invariant; tests define conservative leaderboard behavior for inconsistent data without adding repair logic.
- **Risk:** Removing old routes requires backend and static assets to deploy atomically and cache busting to work; otherwise stale clients receive `404` until refreshed.
- **Risk:** Private entry metadata is access-controlled, but a previously learned static image URL remains retrievable without membership. This limitation must not be described as full private-media protection.
- **Risk:** Existing timestamp-only upload filenames remain collision-prone, can overwrite a pre-existing same-second path, and prevent reliable failed-request orphan cleanup until Task 15; Task 09 never deletes an ambiguously owned path but cannot guarantee preservation when the attempted request path already exists.
- **Risk:** Entrants-only leaderboards intentionally change the current zero-total-member display. The later UI must treat `[]` as the normal empty state for a new run.
- **Risk:** Adding a bearer header to scoped GETs can trigger browser preflight only for cross-origin deployments; the current same-origin frontend does not introduce that condition.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Goals, Specification Decisions, Features 1-3, Constraints, and Out of Scope define the scoped APIs, transitional frontend, removal boundary, and exact acceptance conditions.
- [x] **Testing strategy** - Feature Validation sections and Validation Strategy cover isolated database/upload/browser state, authorization, responses, entrant semantics, bounded SQL, uploads, commit boundaries, old-route removal, full pytest, and browser checks.
- [x] **Existing patterns** - AR-1.1, AR-2.1, AR-2.2, AR-3.1, and Integration Points reference shared permissions, direct `main.py` behavior, current frontend modules, schemas, and isolated fixtures.
- [x] **Dependencies** - Specification Decisions and Constraints confirm existing FastAPI, SQLAlchemy, Pillow, and vanilla JavaScript capabilities are sufficient and no new library is introduced.
- [x] **Architecture & interfaces** - Every endpoint, method, path, input, successful output, policy dependency, query boundary, frontend caller, runtime recovery rule, and later selector seam is defined in Features 1-3 and the Integration Points.
- [x] **Error handling & failure modes** - FR-1.7, FR-2.2, FR-2.5, FR-2.6, FR-3.4 through FR-3.6, AR-2.4, and Failure Modes define concealed authorization, discovery and mid-session recovery, removed routes, exact sanitized failures, commit finality, and file preservation.
- [x] **Security review** - FR-1.5 through FR-1.7, FR-2.2 through FR-2.6, Security and Privacy Boundaries, and Assumptions and Risks assess auth, membership, input identity, cross-run exposure, exception leakage, and public static media.
- [x] **Performance impact** - AR-1.2, Performance Impact, and Validation Strategy item 12 require indexed run-scoped queries, bounded query count, no cross-run relationship loads, and bounded transitional browser requests/retries.
- [x] **Rollout & migration** - Data Requirements, Constraints, Failure Modes, and Rollout and Migration define no schema change, isolated verification, atomic backend/frontend deployment, cache busting, runtime-data preservation, and paired rollback.
- [x] **Assumptions & risks** - Specification Decisions and Assumptions and Risks record public visibility, entrants-only semantics, default-run availability, schema invariants, static-media exposure, upload collisions, and stale-client risk.
