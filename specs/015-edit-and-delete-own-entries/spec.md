# Spec 015: Edit And Delete Own Entries

## Overview

Authenticated beer-run members need to correct or permanently remove entries
they created without gaining authority over another participant's data. This
feature adds owner-and-run-scoped entry mutation APIs, explicit and safe photo
operations, and a mobile-friendly browser workflow that refreshes the selected
run coherently without allowing stale mutation responses to repaint a new run
or identity.

The feature preserves the existing twelve-field entry response, leaderboard
calculation, run-selection model, image normalization, and compact FastAPI plus
vanilla-JavaScript architecture. It requires no database migration or new
dependency.

## Goals

- Let an authenticated owner or member edit and delete only entries whose
  `user_id` is their own and whose `beer_run_id` is the authorized path run.
- Keep entry identity, ownership, run assignment, and original timestamp
  immutable.
- Define unambiguous keep, replace, and remove operations for entry photos.
- Remove only canonical, confined, unshared files that can be proven to belong
  to the mutated entry, without deleting legacy or unrelated media.
- Refresh entries, markers, user history, and leaderboard as one coherent
  selected-run snapshot after a successful mutation.
- Prevent late mutation responses from changing UI belonging to a different
  run, user, token, or entry interaction.

## Specification Decisions

- `PATCH /api/beer-runs/{beer_run_id}/entries/{entry_id}` accepts
  `multipart/form-data` so scalar edits and an optional replacement image share
  one authenticated request. It is a partial update: omitted editable fields
  retain their stored values.
- `DELETE /api/beer-runs/{beer_run_id}/entries/{entry_id}` returns a compact
  JSON success body consistent with the repository's existing delete route.
- Both routes consume `permissions.authorize_member_access`. Run ownership does
  not grant authority over another user's entry.
- After run membership is authorized, missing entries, entries in another run,
  and entries owned by another user all return the same `404 Entry not found`
  response.
- PATCH returns the existing twelve-field `schemas.Entry` representation. The
  public entry shape does not gain `user_id`, `beer_run_id`, or a caller-relative
  ownership flag.
- The browser uses exact equality between the canonical `entry.username` and
  `/api/me` `currentUser.username` only to decide whether to show an affordance.
  The backend's ID-based authorization remains authoritative.
- The only removable persisted photo is an unshared, forward-slash canonical
  path of the exact shape
  `static/uploads/beer_runs/{authorized_run_id}/{canonical_uuid}.jpg` whose
  resolved physical target remains inside the configured upload root. Legacy,
  malformed, cross-run, symlink-escaping, outside-root, and still-shared paths
  are never unlinked by these routes.
- Database commit precedes cleanup of the old photo. A cleanup failure after a
  successful commit may leave an orphan, but it does not turn a completed
  mutation into a reported failure that could be retried unsafely.
- The existing Log Drink form becomes a reusable create/edit surface. Edit and
  create must consume one shared field-normalization and validation path.

---

## Feature 1: Authorize And Address Entry Mutations

**Who & why:** A participant may need to fix a typo, correct a location, or
remove an accidental drink. They need predictable self-service access, while
other participants—including the run owner—must be unable to infer or mutate an
entry through guessed run and entry IDs.

### Functional Requirements

#### FR-1.1: Add The Scoped PATCH Route

The system MUST expose
`PATCH /api/beer-runs/{beer_run_id}/entries/{entry_id}` and require a valid
bearer-authenticated owner or member of the path run. The request MUST use
`multipart/form-data` and the editable-field and photo contracts in Feature 2.
A successful request MUST return `200 OK` with the updated entry serialized
through the existing `schemas.Entry` response model.

**Verify:** Patch an owned entry in a public and a private run as an ordinary
member and as a run owner, and confirm `200` plus the existing entry shape and
the requested persisted changes.

#### FR-1.2: Add The Scoped DELETE Route

The system MUST expose
`DELETE /api/beer-runs/{beer_run_id}/entries/{entry_id}` and require the same
authenticated membership and entry ownership as PATCH. A successful deletion
MUST return `200 OK` with exactly
`{"status": "deleted", "entry_id": <deleted_entry_id>}`. Repeating the request
after deletion MUST follow the concealed entry-not-found behavior in FR-1.4.

**Verify:** Delete an owned entry, assert the exact success response and absence
of the row, then repeat the request and confirm the entry-not-found response.

#### FR-1.3: Preserve Shared Run Authorization Ordering

Both routes MUST consume `permissions.authorize_member_access` before looking
up or mutating an entry or writing a file. Missing or invalid authentication
MUST return `401` with detail `Could not validate credentials` and
`WWW-Authenticate: Bearer`. After authentication succeeds, a missing run or a
run in which the caller is not a member MUST return the existing concealed
`404` with detail `Beer-run not found`, regardless of public visibility.

**Verify:** Exercise logged-out, invalid-token, authenticated non-member,
member, and owner callers against public, private, and missing runs and confirm
the existing member-access matrix and absence of database or file side effects
for every denied request.

#### FR-1.4: Conceal Entry Existence And Ownership

After member access to the path run succeeds, the target lookup MUST require
the entry ID, the authorized run ID, and the authenticated member's user ID in
one ownership-scoped condition. A missing entry, negative entry ID, entry from
another run, or entry owned by another user MUST return identical `404 Not
Found` responses with exactly `{"detail": "Entry not found"}`. A run owner MUST
receive this same response for another member's entry rather than an elevated
permission or owner-specific error.

**Verify:** As both an ordinary member and a run owner, compare the status and
body for missing, negative, wrong-run, and other-user entry IDs and confirm no
response or side effect distinguishes the cases.

#### FR-1.5: Keep Identity, Scope, And Timestamp Immutable

PATCH MUST never change `Entry.id`, `Entry.user_id`, `Entry.beer_run_id`, or the
original `Entry.timestamp`. These names, `username`, `client_timestamp`, and
`image_path` are not accepted mutable fields; extra multipart fields with those
names have no effect and do not count as an edit. The authenticated user and
authorized path run remain the sole sources of ownership and scope.

**Verify:** Submit spoofed IDs, username, timestamp, client timestamp, and image
path alongside a valid edit and confirm the valid field changes while all four
immutable stored values and the photo reference remain unchanged; submit only
immutable fields and confirm the empty-edit validation from FR-2.3.

### Architectural Requirements

#### AR-1.1: Reuse The Shared Member Access Result

The routes MUST use the `permissions.MemberAccess.beer_run` and
`MemberAccess.membership` resolved by `authorize_member_access`. They MUST NOT
repeat token validation, reload the run for a second authorization decision,
use `authorize_owner_access`, or base permission on public visibility, mutable
run names, usernames, or frontend state.

#### AR-1.2: Keep Entry Mutations Beside Existing Scoped Routes

The mutation routes and their narrow image/path helpers remain in the compact
`main.py` boundary beside `get_scoped_entries` and `create_scoped_entry` unless
their final size clearly justifies a similarly focused module. No service
layer, storage abstraction, background worker, or frontend framework is added.

#### AR-1.3: Preserve Path Validation Behavior

Non-integer run or entry path parameters retain FastAPI's standard `422`
validation response. Valid integer IDs proceed through the authorization and
concealment ordering defined above.

---

## Feature 2: Edit Mutable Entry Fields And Choose A Photo Operation

**Who & why:** Entry owners need to correct the information they originally
entered without reconstructing the entry, changing its historical logging
time, or accidentally losing its current photo. Callers also need an explicit
contract for clearing optional values and changing a photo.

### Functional Requirements

#### FR-2.1: Accept Only The Editable Scalar Fields

PATCH MAY contain `drink_type`, `abv`, `quantity`, `brand`, `latitude`,
`longitude`, `client_timezone`, and `client_timezone_code`. Omitted fields MUST
retain their stored values. Present `brand`, `client_timezone`, and
`client_timezone_code` fields with an empty value MUST clear the corresponding
stored optional value to `NULL`; absence and explicit empty input therefore
have different meanings.

The accepted numeric and text rules MUST remain the same as the existing entry
creation form and FastAPI parsing behavior; this feature MUST NOT introduce a
new ABV, quantity, coordinate, or string-length policy only for edits.

**Verify:** Patch each editable field alone, patch several together, clear each
optional field explicitly, and omit fields with known values; confirm only the
present editable fields change and create/edit accept the same value classes.

#### FR-2.2: Keep Coordinates And Browser Timezone Coherent

`latitude` and `longitude` MUST either both be present or both be absent in a
partial PATCH; supplying only one MUST return `422` without changing the row.
`client_timezone` and `client_timezone_code` map to the existing stored
`timezone` and `timezone_code` columns. Changing location or timezone metadata
MUST NOT alter the original timestamp.

**Verify:** Submit both coordinates, each coordinate alone, timezone values,
and cleared timezone values and confirm pair validation, correct persistence,
and byte-for-byte-equivalent timestamp serialization before and after.

#### FR-2.3: Reject Empty Or Invalid Edit Contracts

A PATCH that contains no editable scalar field and no effective photo change
MUST return `422 Unprocessable Entity` and leave the row and filesystem
unchanged. Malformed editable values under the existing create/FastAPI parsing
rules, an unknown photo operation, and contradictory photo inputs described in
FR-2.4 MUST also return `422`. All contract validation that can occur before
image processing MUST complete before allocating a replacement file.

**Verify:** Submit an empty form, immutable-only fields, malformed values under
the existing parsing rules, an unknown photo action, and every contradictory
photo combination; confirm `422`, no row change, and no new or removed file.

#### FR-2.4: Define Keep, Replace, And Remove Photo Operations

PATCH MAY contain `photo_action` with exactly one of `keep`, `replace`, or
`remove`; omission means `keep`.

- `keep` retains the stored `image_path` and MUST reject a non-empty `image`
  upload.
- `replace` requires one non-empty `image` upload, normalizes it through the
  existing Pillow pipeline, and stores a new server-generated canonical path.
- `remove` sets `image_path` to `NULL` and MUST reject a non-empty `image`
  upload.

A blank filename or zero-byte upload counts as no replacement image. The
client filename and any client-supplied `image_path` MUST never determine a
physical or stored path.

**Verify:** Exercise omitted/default keep, explicit keep, replace, and remove
for entries with and without existing photos; also exercise empty uploads and
invalid combinations and confirm the exact retained, new, or null reference.

#### FR-2.5: Preserve Existing Image Normalization

A replacement image MUST use `write_upload_image` or an equivalent reuse of the
current behavior: server-generated canonical UUID JPEG name, exclusive
non-overwriting allocation, EXIF orientation, RGB conversion when needed,
longest edge capped at 1080 pixels, JPEG quality 85 with optimization, and a
path under the authorized run ID. Invalid image content or image processing,
allocation, or write failure MUST return `500` with exactly
`{"detail": "Unable to update entry"}` and leave the entry unchanged.

**Verify:** Replace with supported images, an EXIF-rotated image, hostile client
filenames, invalid bytes, allocation exhaustion, and forced writer failures;
confirm normalization and the exact sanitized failure behavior.

#### FR-2.6: Return The Existing Entry Contract

Successful PATCH responses MUST contain exactly the existing twelve fields:
`id`, `username`, `drink_type`, `abv`, `quantity`, `brand`, `latitude`,
`longitude`, `image_path`, `timestamp`, `timezone`, and `timezone_code`.
`image_path` separator normalization MUST remain response-only, and no user ID,
run ID, role, or ownership flag is added.

**Verify:** Compare GET and PATCH representations of the same entry and confirm
the exact field set, JSON types, timestamp compatibility, username, and
forward-slash image response while the stored path is not response-mutated.

### Architectural Requirements

#### AR-2.1: Distinguish Omitted And Explicitly Cleared Fields

The PATCH request boundary MUST preserve multipart field presence so omitted
optional fields can remain unchanged while explicit empty optional fields can
be cleared. It MUST NOT collapse those two states before applying the partial
update.

#### AR-2.2: Share Create And Edit Field Rules

The browser's current custom drink type, custom quantity, required-field,
location, and timezone logic in `static/js/app.js` and
`static/js/modules/ui.js` MUST be factored into one focused entry-form boundary
used by both create and edit modes. Backend create behavior remains unchanged;
the refactor MUST NOT add edit-only validation that rejects values the create
flow still accepts.

#### AR-2.3: Prepare The PATCH Response Before Final Commit

All fallible database flushes and response-value preparation MUST occur before
the final commit. Once commit succeeds, the route MUST return the prepared
successful response even if later old-file cleanup fails; it MUST NOT perform a
fallible refresh or report rollback-style failure after committed state can no
longer be undone.

---

## Feature 3: Preserve Photo And Database Consistency

**Who & why:** Uploaded drink photos are user data and some legacy or migrated
rows can share a physical file. An entry owner needs replacement and deletion
to clean up safely without a failed transaction breaking the old image or one
entry deleting media still used by another.

### Functional Requirements

#### FR-3.1: Roll Back Replacement Before Commit

For `photo_action=replace`, the system MUST allocate and normalize the new
request-owned upload before changing the stored pointer. If validation,
database flush, response preparation, or commit fails, the transaction MUST
roll back, the old entry and photo reference MUST remain intact, and the system
MUST attempt to remove only the newly allocated request-owned file. The failure
MUST return exactly `{"detail": "Unable to update entry"}` without exception,
SQL, UUID, token, credential, or filesystem details.

**Verify:** Force each pre-commit failure after a replacement file exists and
confirm the old row/path/file remain, the new file is removed when the
filesystem permits, sentinel files are untouched, and the response is exact
and sanitized.

#### FR-3.2: Commit Before Removing An Old Photo

For replace, remove, and entry deletion, the database pointer change or row
deletion MUST commit before the old physical file is considered for cleanup.
A failed update or delete commit MUST leave the old file present and the entry
still pointing to it. A delete persistence failure MUST return `500` with
exactly `{"detail": "Unable to delete entry"}`.

**Verify:** Force PATCH and DELETE commit failures for photographed entries and
confirm rollback preserves both row and old file, no success response is
reported, and each route returns its exact sanitized detail.

#### FR-3.3: Prove A Persisted Path Is Safe To Unlink

After a successful commit, old-file cleanup MAY target a path only when all of
the following are true:

- the stored value already uses forward slashes and exactly matches
  `static/uploads/beer_runs/{authorized_run_id}/{canonical_uuid}.jpg`;
- the run segment equals the authorized route run and every filename component
  is server-canonical;
- resolving the physical target and configured `UPLOAD_ROOT` proves the target
  remains inside the upload root and does not escape through traversal or a
  symlink;
- the target is a file rather than a directory; and
- no remaining `Entry.image_path`, compared with separator normalization only
  for this reference check, points to the same managed file.

If any condition fails, the database mutation remains successful but the file
MUST be retained.

**Verify:** Exercise canonical owned, flat legacy, backslash legacy, malformed,
absolute, traversal, wrong-run, directory, symlink-escaping, missing, and shared
paths and confirm only an unshared canonical same-run file is eligible for
unlinking.

#### FR-3.4: Never Delete Unrelated Or Shared Media

Cleanup MUST target at most the one eligible old file from the mutated entry.
It MUST never remove a whole run directory, a legacy rollback copy, a
pre-existing replacement candidate, a file referenced by another entry, or any
other upload. A missing eligible file is an idempotent cleanup success.

**Verify:** Place unrelated sentinels in the upload root and run directory,
create two entries referencing one canonical file, and perform replace, remove,
and delete; confirm shared and sentinel files remain and a uniquely referenced
eligible old file is removed.

#### FR-3.5: Treat Post-Commit Cleanup Failure As An Orphan

If unlinking an eligible old file fails after the database commit, PATCH and
DELETE MUST still return their successful response and MUST NOT restore an old
database pointer, delete the new replacement, expose a path, or invite an
automatic client retry. The old file may remain as an unreferenced orphan for
later operator review.

**Verify:** Force old-file unlink failure after successful replace, remove, and
delete commits and confirm the new database state and success response remain
final while the old file is left untouched.

### Architectural Requirements

#### AR-3.1: Reuse Proven Upload Confinement Rules

Persisted-path eligibility MUST reuse or match the normalization and resolved
root-confinement protections already established by
`scripts/migrate_upload_paths.py`, tightened to the canonical same-run UUID JPEG
shape required here. Client strings MUST never be joined directly to form a
cleanup target.

#### AR-3.2: Keep Request-Owned And Persisted Cleanup Separate

`_OwnedUpload` and `_cleanup_owned_upload_safely` continue to represent files
created exclusively by the current request. Cleanup of an old persisted path
requires the additional validation and remaining-reference checks in FR-3.3;
the code MUST NOT treat an arbitrary `Entry.image_path` as an `_OwnedUpload`.

#### AR-3.3: Use Isolated Filesystem Seams

All automated photo tests MUST redirect `main.UPLOAD_ROOT` and any corresponding
path root to a temporary directory. Tests MUST NOT inspect, create, overwrite,
or delete files in the repository's real `static/uploads` directory.

---

## Feature 4: Provide An Explicit Create/Edit/Delete Browser Workflow

**Who & why:** Mobile participants need to correct an entry at the moment they
notice a mistake, using the same familiar controls they used to log it. Actions
must be discoverable for their own selected drink, absent for everyone else's,
and safe against accidental repeated or unconfirmed deletion.

### Functional Requirements

#### FR-4.1: Show Actions Only For The Current User's Selected Entry

The drink detail sheet MUST show semantic Edit and Delete buttons only when a
valid authenticated user is present, the selected entry belongs to the current
selected run, the user remains an owner or member of that run, and
`entry.username` exactly equals the canonical `currentUser.username` returned
by `/api/me`. The actions MUST be hidden immediately on logout, rejected
session, run switch, or detail clearing. Direct API requests remain subject to
the server's ID-based checks regardless of button visibility.

**Verify:** Open own and other-user entries as a member and run owner, then
switch runs, log out, and expire the session; confirm actions appear only for
the current user's own current-run entry and disappear immediately on every
context invalidation.

#### FR-4.2: Reuse The Entry Form In Explicit Edit Mode

Choosing Edit MUST activate the existing Log Drink form in a visibly distinct
edit mode, identify that an existing drink is being edited, prefill drink type,
brand, ABV, quantity, and saved coordinates, and provide Save Changes and Cancel
actions. Values not present in configured drink or quantity options MUST use
the existing Other/Custom controls. The original timestamp MUST not be shown as
editable or replaced during save.

**Verify:** Edit entries containing configured and custom values, optional
fields, and coordinates; confirm correct prefilling, visible mode/action copy,
no timestamp control, and a PATCH rather than POST on Save Changes.

#### FR-4.3: Preserve Location And Timezone Unless Re-Pinned

Entering edit mode MUST preserve the stored latitude, longitude, timezone, and
timezone code by default. If the user explicitly pins a new location, the edit
payload MUST send the new coordinate pair and the browser's current timezone
and timezone code using the shared form helpers. Merely editing another field
MUST NOT silently replace location or timezone metadata.

**Verify:** Change only brand and confirm location/timezone are unchanged, then
re-pin and confirm coordinates and browser timezone metadata update together
while timestamp remains fixed.

#### FR-4.4: Make Photo Intent Explicit In Edit Mode

Edit mode MUST show the current-photo state and mutually exclusive Keep,
Replace, and Remove choices. Keep is the initial choice and sends no image.
Replace reveals the file input and requires a selected non-empty file. Remove
requires no file. An entry without a current photo MUST not offer a misleading
Keep-current-photo state; its valid choices are no photo and Replace.

**Verify:** Enter edit mode for entries with and without photos, exercise all
choices, cancel and reopen, and confirm visible state and multipart payloads
match the selected operation without retaining a stale file input.

#### FR-4.5: Cancel Edit Without A Mutation

Cancel MUST make no network request, discard edit-only state and file input,
restore the form to normal Log Drink create mode, and return focus to a useful
originating control when the same run and entry context still exists. A later
create submission MUST not retain the edited entry ID or photo action.

**Verify:** Change every edit control, select a replacement file, cancel, and
submit a new entry; confirm no PATCH occurred on cancel and the POST contains no
stale entry or photo-operation state.

#### FR-4.6: Confirm Deletion And Block Duplicate Submission

Delete MUST open an accessible confirmation dialog that identifies the drink
being removed and states that deletion is permanent. No DELETE request is sent
until the user activates the explicit confirm button. While PATCH or DELETE is
pending, all controls capable of repeating or conflicting with that mutation
MUST be disabled and expose a clear pending status; cancel is unavailable after
the confirmed request has begun.

**Verify:** Cancel deletion, confirm deletion, and rapidly activate mutation
controls by pointer and keyboard; confirm cancel sends no request and each
confirmed operation sends at most one request while pending.

#### FR-4.7: Refresh Every Affected Surface After Success

For a successful mutation whose captured run and identity are still current,
the app MUST close the stale drink detail and delete confirmation, restore the
form to create mode, and invoke the existing paired selected-run refresh. The
accepted refresh MUST update `currentEntries`, markers and entry lookup,
leaderboard totals/order, user filter options, and the selected user's history
without a page reload. If that user's history was open, it MUST be rerendered
from the refreshed snapshot or closed with a concise empty/unavailable notice
when the user no longer has a leaderboard row.

**Verify:** Edit quantity/ABV/location/photo and delete an entry while history
and detail surfaces are exercised; confirm all listed surfaces reflect one
fresh snapshot immediately and no full-page reload occurs.

### Architectural Requirements

#### AR-4.1: Add A Focused Entry-Management Module

A focused module under `static/js/modules/` MUST own edit/delete interaction
state, shared create/edit form normalization, photo-choice UI, confirmation,
pending state, and local error/status rendering. `static/js/modules/api.js`
owns network helpers, `static/js/modules/map.js` owns marker/detail rendering,
`static/js/modules/ui.js` owns generic rendering helpers, and
`static/js/app.js` remains the orchestrator for authenticated identity,
selected-run context, paired refresh, and stale-result acceptance.

#### AR-4.2: Inject Actions Into Detail Rendering

The map module MUST receive the selected entry's action availability and
callbacks through a focused interface rather than trusting inline serialized
HTML or a client-controlled owner ID. The current entry response may be used to
render details, but it MUST NOT be treated as server authorization.

#### AR-4.3: Preserve The Existing Create Flow

Refactoring the form MUST preserve authenticated member-only creation, custom
drink and quantity behavior, geolocation, client timestamp/timezone submission,
photo upload, pending-state protection, success/error copy, and same-run refresh
unless a requirement above explicitly distinguishes edit mode.

---

## Feature 5: Guard Mutations Against Stale Context And Failures

**Who & why:** A phone user can switch runs, log out, lose membership, or trigger
a refresh while a mutation is in flight. The server operation may already have
completed, but an old response must never close, overwrite, or repopulate UI
for a new identity or selected run.

### Functional Requirements

#### FR-5.1: Bind Every Mutation To A Context Snapshot

Before PATCH or DELETE, the browser MUST capture the current user ID, bearer
token, context generation, selected run ID, entry ID, and a mutation generation.
A completion may update DOM or in-memory state only if every captured identity,
run, entry-interaction, and generation value still matches. Aborting the fetch
MAY reduce work but MUST NOT replace the completion-time stale check.

**Verify:** Delay mutation responses while switching runs, logging out and back
in, opening another entry, and starting a newer interaction; confirm no late
result changes the new context.

#### FR-5.2: Invalidate Pending Mutation UI On Run Or Identity Change

Run selection, login, signup, logout, rejected-session handling, and complete
trip-state clearing MUST cancel or invalidate mutation work, close entry-owned
dialogs and edit mode, clear pending flags, and restore the form to create mode
before displaying another context. A server mutation that completed despite
client cancellation MUST not trigger a stale refresh or success message.

**Verify:** Start edit and delete operations, perform each run/identity
transition, and confirm immediate UI clearing plus absence of old-run refresh,
success copy, detail, form values, or history in the new context.

#### FR-5.3: Normalize Mutation API Results Without Automatic Retry

The API module's PATCH and DELETE helpers MUST accept a bearer token and
optional abort signal and return normalized success, HTTP error, network error,
and aborted results including only the sanitized status/detail needed by the
orchestrator. Mutations MUST never be automatically retried because the first
request may have committed despite a lost response.

**Verify:** Simulate success, `401`, both `404` details, `422`, `500`, offline,
lost response after commit, and abort; confirm normalized handling and exactly
one request per explicit user submission.

#### FR-5.4: Handle Current-Context Errors Safely

When the mutation snapshot is still current:

- `401` MUST use the existing rejected-session flow.
- `404 Beer-run not found` MUST use the existing selected-run access-loss
  recovery.
- `404 Entry not found` MUST close stale entry UI, announce that the entry is no
  longer available, and refresh the still-selected run rather than assuming the
  run is inaccessible.
- `422`, `500`, and network failures MUST show a concise readable error and
  preserve editable values when retry is safe.

After any non-stale completion, pending controls MUST return to a usable state.
No response body, exception, token, filesystem path, SQL, or raw multipart data
may be written to the visible UI or console.

**Verify:** Exercise every listed response while the context remains current
and after it becomes stale; confirm the correct recovery, preserved retryable
input, re-enabled controls, and absence of sensitive diagnostics.

#### FR-5.5: Preserve Coherent Paired Refresh Semantics

Post-mutation refresh MUST continue accepting leaderboard and entry-list data
together only when both requests succeed for the same selected run, identity,
and refresh generation. A mutation completion MUST NOT directly splice its
response into `currentEntries`, markers, history, or leaderboard before that
coherent refresh succeeds.

**Verify:** Delay or fail each half of the post-mutation paired refresh and
confirm the app never combines patched/deleted entries with old leaderboard or
marker/history state and never renders results under a different run.

### Architectural Requirements

#### AR-5.1: Keep Mutation And Refresh Lifecycles Distinct

`static/js/app.js` MUST coordinate a dedicated mutation controller/generation
separately from its existing `refreshController` and `refreshGeneration`.
Starting or cancelling a data refresh alone MUST NOT accidentally authorize a
stale mutation completion, while run and identity invalidation MUST invalidate
both lifecycles.

#### AR-5.2: Preserve Existing Access-Loss Clearing

Mutation recovery MUST reuse `clearTripState`, `recoverFromAccessLoss`,
`mapMod.clearRunState`, and `ui.clearUserModal` or equivalent complete clearing
behavior. It MUST NOT create a second fallback-selection or partial-clearing
path.

---

## Data Requirements

- No database schema or migration change is required. `Entry` already stores
  every editable and immutable value needed by this feature.
- PATCH may update only `drink_type`, `abv`, `quantity`, `brand`, `latitude`,
  `longitude`, `timezone`, `timezone_code`, and `image_path` under the contracts
  above.
- DELETE removes exactly the authorized owned `Entry` row. It does not delete a
  user, membership, beer-run, invite, or another entry.
- Leaderboard totals remain derived from persisted `quantity` and `abv`; no
  cached total is introduced.
- Persisted image paths remain app-relative strings. New replacement uploads
  use the Spec 014 canonical run-ID/UUID JPEG shape.
- Runtime database files and real uploads are protected user data and are not
  migration or test fixtures.

## API Contract Summary

| Method and path | Request | Success | Relevant failures |
|---|---|---|---|
| `PATCH /api/beer-runs/{beer_run_id}/entries/{entry_id}` | Authenticated multipart partial edit; optional `photo_action` | `200`, exact `schemas.Entry` shape | `401` auth; `404 Beer-run not found`; `404 Entry not found`; `422` contract; `500 Unable to update entry` |
| `DELETE /api/beer-runs/{beer_run_id}/entries/{entry_id}` | Authenticated, no request body | `200 {"status":"deleted","entry_id":id}` | `401` auth; `404 Beer-run not found`; `404 Entry not found`; `500 Unable to delete entry` |

## Integration Points

| Area | Existing boundary | Required integration |
|---|---|---|
| Authorization | `permissions.py: authorize_member_access` | Reuse authenticated run membership, then scope entry lookup by entry/run/user IDs. |
| Entry routes and serialization | `main.py: get_scoped_entries`, `create_scoped_entry`, `normalize_image_path_for_response` | Add PATCH/DELETE beside scoped routes and preserve the current entry response. |
| Image allocation | `main.py: _OwnedUpload`, `write_upload_image`, `_cleanup_owned_upload_safely` | Reuse request-owned replacement allocation; add stricter persisted-old-path cleanup. |
| Persisted path safety | `scripts/migrate_upload_paths.py` normalization and confinement helpers/patterns | Reuse proven path rejection concepts plus canonical run and remaining-reference checks. |
| API client | `static/js/modules/api.js` | Add abortable, bearer-authenticated, normalized PATCH and DELETE helpers. |
| Context orchestration | `static/js/app.js` | Supply identity/run snapshots, invalidate mutation state, and invoke paired refresh. |
| Detail and map | `static/js/modules/map.js` | Render selected-entry ownership actions through injected state/callbacks and clear them with run state. |
| Form and history | `static/js/modules/ui.js`, `templates/index.html` | Share create/edit field behavior and refresh or close stale history. |
| Styling and caching | `static/css/style.css`, `templates/index.html`, imports in `static/js/app.js` | Add touch-friendly edit/confirmation states and increment all affected cache-busting query strings. |
| Tests | `tests/conftest.py`, `tests/test_scoped_routes.py`, upload migration tests | Reuse isolated auth/run fixtures, temporary upload roots, response-shape checks, and failure injection. |

## Related Specs

| Spec | Relationship | Affected Requirements |
|---|---|---|
| Spec 007: Centralize Beer-Run Authorization | **Depends on** — supplies the shared authenticated member policy and concealment ordering | FR-1.3, AR-1.1 |
| Spec 009: Scope Entries and Leaderboard API by Beer-Run | **Extends** — adds scoped PATCH/DELETE while preserving scoped GET/POST, entry response, and leaderboard contracts | FR-1.1 through FR-1.5, FR-2.6, FR-4.7, FR-5.5 |
| Spec 011: Add Beer-Run Selector UI | **Extends** — binds entry mutations to the established selected-run, identity-generation, clearing, and paired-refresh lifecycle | FR-4.1, FR-4.7, Feature 5 |
| Spec 014: Organize Upload Paths By Beer-Run | **Extends** — applies canonical request-owned uploads to replacement and adds safe persisted-photo cleanup previously outside that spec | FR-2.4, FR-2.5, Feature 3 |

## Failure Modes And Recovery

- Authorization denial occurs before entry lookup and file allocation and uses
  the shared `401`/run-`404` contracts.
- Entry absence, wrong scope, or wrong owner uses one entry-level `404` and no
  side effect.
- Contract validation failure returns `422` before replacement allocation when
  possible and leaves edit mode usable.
- Replacement processing failure removes only the newly allocated file and
  leaves the original row and photo untouched.
- PATCH or DELETE persistence failure rolls back before old-file cleanup and
  returns only its sanitized route-specific `500` detail.
- Post-commit old-file cleanup failure leaves an orphan and still returns
  success; it never rolls back or restores stale pointers.
- A lost success response is not retried automatically. The user may explicitly
  refresh to reconcile server state.
- A stale response has no UI effect. Current-context `401`, run `404`, and entry
  `404` use the distinct recovery paths defined in FR-5.4.
- A failed paired refresh retains only the existing same-run last-known-good
  behavior from Spec 011; it never relabels or restores data across a context
  transition.

## Performance Impact

- Each mutation performs bounded authorization and one ownership-scoped entry
  lookup. Persisted-photo deletion adds one bounded remaining-reference query.
- Successful browser mutations reuse the existing two-request paired refresh;
  no polling interval, new background work, or client cache is added.
- Photo normalization retains the current 1080-pixel bound and synchronous
  behavior suitable for the app's current small-trip workload.
- Whole-run entry scans, recursive upload-directory scans, and N+1 user or
  leaderboard queries are not permitted for a single mutation.

## Testing And Verification Strategy

1. Add focused API tests, preferably in `tests/test_entry_mutations.py` or a
   clearly separated section of `tests/test_scoped_routes.py`, using the
   existing isolated database override and owner/member/non-member fixtures.
2. Cover PATCH and DELETE success for ordinary members and owners in public and
   private runs, plus logged-out, invalid-token, non-member, missing-run,
   missing-entry, negative-ID, wrong-run, other-user, and owner-overreach cases.
3. Assert immutable ID, user, run, and timestamp behavior; partial fields;
   optional clears; coordinate pairing; empty PATCH; immutable-only payloads;
   spoofed fields; multipart validation; exact success/error bodies; and the
   exact twelve-field PATCH response.
4. Verify leaderboard totals and ordering before and after quantity/ABV edits
   and deletion, and verify scoped GET ordering/serialization after edits.
5. Redirect every upload operation to `tmp_path`. Cover keep, replace, remove,
   no-current-photo, invalid/empty image, normalization, hostile filename,
   UUID collision, writer failure, database flush/commit failure, new-file
   cleanup failure, old-file cleanup failure, and final-commit response
   behavior.
6. Cover legacy flat/backslash paths, malformed and outside-root paths,
   traversal, wrong-run canonical paths, directory targets, symlink escape,
   missing files, unrelated sentinels, and two entries sharing a canonical
   file. Confirm only one unshared eligible same-run canonical file is removed.
7. Run `uv --cache-dir .uv-cache run pytest` and confirm no test points at or
   mutates `boozerun.db`, `users.json`, or real `static/uploads`.
8. Syntax-check every changed JavaScript module with the repository's available
   Node runtime, then inspect the running app with the Codex in-app browser at a
   representative desktop viewport and 390x844.
9. In isolated browser data, verify own/other-user action visibility; edit
   prefill; configured/custom inputs; re-pin behavior; photo keep/replace/remove;
   cancel; accessible delete confirmation; pending controls; error recovery;
   keyboard flow; 44x44 touch targets; and no horizontal overflow.
10. Delay PATCH, DELETE, leaderboard, and entry-list responses while rapidly
    switching runs, changing entries, logging out/in, and losing access. Inspect
    network and console output to confirm one mutation request, no stale repaint,
    coherent paired refresh, and no sensitive diagnostics.
11. Run `git diff --check` and inspect `git status --short`; confirm only intended
    source/spec assets changed and all affected static cache-busting query
    strings were incremented.

## Rollout And Rollback

- Ship backend routes, frontend helpers/module/UI, styles, tests, and cache-bust
  updates in one deployment unit so controls never target unavailable routes.
- No schema migration, upload-path migration, Wrapped regeneration, or runtime
  data rewrite is part of rollout.
- Before deployment, back up runtime database and uploads through the existing
  operator process; implementation verification itself uses only disposable
  database and upload roots.
- Rollback removes the new routes and frontend controls together. Rows retained
  by PATCH and rows removed by a completed DELETE are user mutations and are not
  automatically reversed by code rollback; retained orphan files are safe to
  leave for later operator review.

## Constraints

- Keep the existing FastAPI, SQLAlchemy, SQLite, Pillow, static HTML/CSS, and
  vanilla ES-module architecture with no frontend build step or new dependency.
- Preserve the exact successful GET entry, POST entry, leaderboard, auth,
  beer-run, and selected-run contracts except for the two new routes explicitly
  defined here.
- Preserve mobile-first touch behavior, user-triggered geolocation, map/detail
  behavior, periodic refresh, and server-side image normalization.
- Use bearer authentication for all writes; frontend ownership visibility is
  never an authorization boundary.
- Update cache-busting query strings for every changed deployed JavaScript or
  CSS asset and importing module.
- Never mutate live `boozerun.db`, backups, `users.json`, real uploads, or local
  caches during implementation or verification without explicit authorization.

## Out Of Scope

- Editing or deleting another user's entry, including by a run owner.
- Reassigning an entry to another user or beer-run.
- Changing an entry's original timestamp.
- Bulk entry edit/delete, undo, soft delete, trash, audit history, or version
  conflict UI.
- New entry-field range rules or a broader create-form redesign.
- Publicly exposing entry owner IDs or adding an ownership flag to entry
  responses.
- General orphan discovery/cleanup, deleting legacy rollback copies, recursive
  run-directory cleanup, or modifying the upload-path migration.
- Authenticated private-media delivery or changing the `/static` media boundary.
- Beer-run, membership, ownership-transfer, or account deletion behavior owned
  by later Release 2 tasks.
- Wrapped regeneration or historical recap correction after an entry mutation.

## Assumptions And Risks

- **Assumption:** `/api/me` and entry serialization return the same canonical
  stored username, so exact username equality is sufficient for affordance
  visibility while the server continues authorizing by numeric user ID.
- **Assumption:** The current permissive entry value rules are intentional for
  this task; a consistent create-and-edit validation policy can be specified
  separately if product limits are desired.
- **Risk:** SQLite and the filesystem cannot commit atomically. Commit-first old
  cleanup protects live references at the cost of a possible orphan after
  cleanup failure; FR-3.5 makes that tradeoff explicit.
- **Risk:** Concurrent successful replacements can be last-write-wins and may
  leave a superseded new upload orphaned. The routes must never delete a file
  still referenced by a row; optimistic versioning and general orphan cleanup
  remain outside this feature.
- **Risk:** Username comparison controls only UI visibility. Any frontend bug or
  modified client can still issue a request, so FR-1.4's server-side
  entry/run/user predicate is the security boundary.
- **Risk:** The current form is partially assembled and validated across HTML,
  `ui.js`, and `app.js`. AR-2.2 requires a focused shared boundary to prevent
  create/edit behavior from drifting during the refactor.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Goals, Specification Decisions, Features
  1-5, Constraints, and Out Of Scope define exact shipped and excluded behavior.
- [x] **Testing strategy** — Testing And Verification Strategy covers API,
  filesystem, leaderboard, JavaScript syntax, desktop/mobile browser, races,
  and repository hygiene.
- [x] **Existing patterns** — Architectural requirements and Integration Points
  tie the proposal to current scoped routes, shared permissions, upload helpers,
  paired refresh, map clearing, and form modules.
- [N/A] **Dependencies** — the specification explicitly adds no external
  library, framework, build step, or schema dependency.
- [x] **Architecture & interfaces** — API Contract Summary, Data Requirements,
  Integration Points, and AR-1.1 through AR-5.2 define route, module, data, and
  transaction boundaries.
- [x] **Error handling & failure modes** — FR-1.3, FR-1.4, FR-2.3, Feature 3,
  Feature 5, and Failure Modes And Recovery define validation, rollback,
  cleanup, access loss, network, and stale-result behavior.
- [x] **Security review** — FR-1.3 through FR-1.5, FR-3.3 through FR-3.4,
  FR-4.1, and FR-5.4 cover authentication, authorization, concealment,
  immutable fields, filesystem confinement, shared references, and data
  exposure.
- [x] **Performance impact** — Performance Impact bounds route queries, refresh
  requests, image work, and prohibited scans/N+1 behavior.
- [x] **Rollout & migration** — Data Requirements and Rollout And Rollback state
  that no migration is needed and define atomic deployment, backup, and rollback
  expectations.
- [x] **Assumptions & risks** — Assumptions And Risks records username-affordance,
  validation, filesystem transaction, concurrency, and form-refactor risks.
