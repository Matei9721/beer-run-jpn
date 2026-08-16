# Spec 014: Organize Upload Paths By Beer-Run

## Overview

New entry photos must receive collision-safe, server-generated paths beneath the
authorized beer-run's stable numeric ID. A dedicated, retry-safe migration must
copy every eligible legacy entry image into that same canonical structure and
update its database reference only after verification, while retaining the flat
source as a rollback copy and preserving old static URLs.

## Goals

- Prevent concurrent or same-second image uploads from overwriting one another.
- Organize every new image beneath the immutable ID of the beer-run that owns the
  entry.
- Migrate active legacy image references into the same run-ID/UUID path format
  used by new uploads without risking the only copy of an existing photo.
- Preserve original upload files as rollback copies, image normalization, API
  response shapes, old static URLs, and browser rendering behavior.
- Make a newly written file attributable to one request so failed entry creation
  can clean up only that request's file.

## Specification Decisions

- New stored paths use the exact app-relative shape
  `static/uploads/beer_runs/{beer_run_id}/{uuid}.jpg`, with forward slashes, no
  leading slash, a canonical UUID-based basename, and the existing normalized
  JPEG extension.
- `{beer_run_id}` comes only from the run resolved by
  `permissions.authorize_member_access`; the current selected run is already
  carried in the scoped request URL. There is no implicit BeerRunJPN exception,
  form-supplied run ID, or run-name lookup for upload placement.
- UUID naming must be paired with non-overwriting destination allocation. UUID
  probability alone is not accepted as proof that an existing file cannot be
  replaced.
- Every eligible legacy `Entry.image_path` is migrated to the canonical nested
  format by a dedicated operator-invoked file/data migration. The migration
  copies and verifies before rewriting a row, never overwrites a destination,
  and is safe to resume or rerun.
- Legacy source files are retained after successful migration as rollback and
  old-URL compatibility copies. A completed migration has no eligible legacy
  path left in `Entry.image_path`, even though the unreferenced flat source file
  remains on disk.
- A file uniquely created by a request is targeted for removal if image
  processing or pre-commit entry persistence fails. General orphan cleanup,
  run-directory deletion, and historical-file relocation remain out of scope.
- Run-specific folders organize media but do not authorize it. The existing
  unauthenticated `/static` media boundary is unchanged.
- Python's standard UUID, hashing, copy, and filesystem capabilities are
  sufficient; no new package or database schema change is required.

---

## Feature 1: Create Collision-Safe Run-Scoped Uploads

**Who & why:** Trip participants may submit photos nearly simultaneously from
multiple phones. Each successful submission needs its own durable image, stored
under the run the server authorized, without one upload replacing another or a
run rename breaking its URL.

### Functional Requirements

#### FR-1.1: Derive The Folder From The Authorized Run

When `POST /api/beer-runs/{beer_run_id}/entries` accepts a non-empty image, the
system MUST place the normalized file beneath
`static/uploads/beer_runs/{authorized_run_id}/`. The ID MUST be the numeric ID
from `MemberAccess.beer_run`, not an original filename, multipart field, run
name, current username, timestamp, or other caller-controlled value. Renaming a
beer-run MUST NOT change or invalidate paths already stored for that run.

**Verify:** Upload to two differently named runs, including one that is renamed
after upload, and confirm each path contains only its authorized numeric run ID
as the folder segment and every image remains retrievable after the rename.

#### FR-1.2: Use UUID-Based JPEG Names

Every new upload MUST receive a server-generated canonical UUID-based basename
and `.jpg` extension, producing the exact relative shape
`static/uploads/beer_runs/{beer_run_id}/{uuid}.jpg`. The original client
filename and extension MUST NOT appear in or influence the stored filesystem
path.

**Verify:** Submit images with identical, Unicode, nested, absolute-looking, and
path-traversal-style client filenames and confirm all stored names match the
canonical UUID JPEG shape and contain none of the submitted filename text.

#### FR-1.3: Never Replace An Existing Destination

Creating a new upload MUST use non-overwriting destination allocation. If a
generated candidate already exists, the existing file MUST remain byte-for-byte
unchanged and the request MUST select another UUID candidate; retries MUST be
bounded, and exhaustion MUST fail through FR-2.3 without creating an entry.
Two authorized uploads performed during the same second MUST receive distinct
paths and preserve both normalized files.

**Verify:** Freeze time for two uploads and separately force the first UUID
candidate to identify an existing sentinel file; confirm the two successful
paths differ, both new files exist, the sentinel is unchanged, and forced retry
exhaustion creates no entry or overwritten file.

#### FR-1.4: Create Missing Run Directories Lazily

The run-specific destination directory MUST be created before its first file is
written, including any missing parent directories. Repeated and concurrent
creation attempts for the same valid run MUST be safe and MUST NOT require
pre-creating a directory for every run at startup.

**Verify:** Start with an isolated upload root containing no `beer_runs` tree,
perform first uploads for the same run through independent requests, and confirm
the required directory is created once logically and both files are preserved.

#### FR-1.5: Preserve Existing Image Normalization

New run-scoped uploads MUST retain the current Pillow behavior in `main.py`:
apply EXIF orientation, convert formats that require RGB conversion, restrict
the longest edge to 1080 pixels, and store an optimized JPEG. This feature MUST
NOT change which multipart fields are accepted or the behavior of an entry with
no non-empty image.

**Verify:** Run the existing image-normalization and multipart tests against the
new destination scheme, including an image requiring orientation/conversion, an
oversized image, no image, and an empty image body, and confirm prior output and
entry behavior remains intact.

### Architectural Requirements

#### AR-1.1: Keep The Direct Image-Writer Boundary

Image normalization and persistence remain in the compact helper/route boundary
in `main.py`. The internal writer MUST accept the authorized run context and
retain a redirectable upload-root or writer seam so focused tests exercise the
real naming, directory, normalization, and collision logic entirely beneath
`tmp_path`; no storage service, queue, background worker, or broad abstraction
layer is introduced.

#### AR-1.2: Use Stable Filesystem Components

Only the server-derived integer beer-run ID, a canonical server-generated UUID,
and the fixed `.jpg` extension may form new relative path components. Filesystem
joins used for writing MUST remain confined beneath the configured upload root,
while the value persisted in `Entry.image_path` MUST use the canonical
forward-slash app-relative representation from Specification Decisions.

#### AR-1.3: Preserve Authorization Ordering

`create_scoped_entry` MUST continue consuming
`permissions.authorize_member_access` before reading or writing an upload. An
unauthenticated caller, non-member, concealed missing run, or invalid path ID
MUST cause no upload-directory or file side effect.

### Feature Validation

Use isolated filesystem and database fixtures to cover two same-second uploads,
forced UUID candidate collision, bounded retry exhaustion, first-use directory
creation, two different runs, run rename stability, hostile original filenames,
JPEG normalization, no/empty image behavior, and authorization before any
filesystem side effect. Tests must inspect actual file contents and paths rather
than mocking away the path writer.

---

## Feature 2: Preserve Compatibility And Clean Up Failed Writes

**Who & why:** Existing BeerRunJPN photos are irreplaceable runtime data, and
current browser/API consumers already understand their flat stored paths. The
maintainer needs the safer scheme to coexist with those files while a failed new
entry cannot delete older media or leave an avoidable request-owned orphan.

### Functional Requirements

#### FR-2.1: Preserve Old URLs And Source Copies During Migration

The migration MUST copy rather than destructively move each eligible legacy
source. After the corresponding database reference becomes canonical, the
original flat file MUST remain byte-for-byte unchanged and servable at its old
`/static/uploads/...` URL as a rollback copy. Both the retained flat URL and the
new nested URL MUST render through the current map popup and detail sheet; only
the nested destination becomes the entry's active `image_path`.

**Verify:** Migrate an isolated flat legacy photo and confirm the row now holds
the canonical nested path, source and destination both exist with identical
bytes, both URLs return the image, and the scoped UI renders the canonical URL.

#### FR-2.2: Normalize Entry API Path Separators

Every successful scoped entry-list response MUST return a non-null `image_path`
with forward slashes, regardless of the separators stored in the database. This
normalization MUST be response-only for legacy values and MUST preserve the
exact twelve-field entry response contract from Spec 009; the successful create
response MUST remain exactly `200 {"status": "success", "entry_id": <integer>}`.

**Verify:** Read entries whose database values contain legacy backslashes, flat
forward-slash paths, and new nested paths; confirm all returned `image_path`
values use forward slashes, stored legacy values are unchanged, the entry field
set is unchanged, and the create response gains no new field.

#### FR-2.3: Preserve Sanitized Upload Failures

Invalid image data, directory/allocation failure, UUID retry exhaustion, image
processing failure, and pre-commit persistence failure MUST return `500` with
exactly `{"detail": "Unable to create entry"}`. Responses MUST NOT expose UUID
candidates, local paths, exception text, SQL, credentials, tokens, or other
server internals, and the database transaction MUST leave no new entry row.

**Verify:** Force each failure category and confirm the exact response, absence
of a new row, and absence of internal details in the response body.

#### FR-2.4: Remove Only The Failed Request's New File

If a request has exclusively created a destination but image processing or
entry persistence fails before commit, the system MUST attempt to remove that
request-owned file, including any partial output; when the filesystem accepts
the removal, no request-owned orphan may remain. Cleanup MUST never target a
candidate that pre-existed the request, a legacy path, another request's file,
or a whole run directory. A cleanup failure MUST NOT replace the sanitized
original API error with raw filesystem details; once the database commit
succeeds, later response handling MUST NOT delete the committed entry's file.

**Verify:** Force an image-processing failure after destination allocation and a
database failure after a valid file write; confirm each request-owned file is
removed, sentinel/legacy/concurrent files and the run directory remain, the API
error stays sanitized if cleanup itself fails, and a committed success retains
its file.

#### FR-2.5: Keep Nested Paths Compatible With Wrapped Generation

The existing Wrapped path normalization, existence checks, and public URL
generation MUST continue to accept both legacy flat paths and new nested paths.
This feature does not otherwise change Wrapped selection, content, or generated
data.

**Verify:** Build Wrapped data from an isolated database/root containing one
valid legacy flat path and one valid new nested path and confirm both become
forward-slash `/static/...` image URLs without changing unrelated Wrapped output.

### Architectural Requirements

#### AR-2.1: Normalize At Storage And Serialization Boundaries

New `Entry.image_path` values MUST be stored canonically. Before a legacy row is
migrated, separator normalization is performed only in the entry response
serializer; migration later replaces the stored legacy value through Feature 3.
The frontend's defensive separator replacement in
`static/js/modules/map.js` may remain, but correctness MUST NOT depend on a
Windows-specific path reaching the browser.

#### AR-2.2: Limit Cleanup To Proven Request Ownership

Cleanup is permitted only for a path whose exclusive creation was confirmed for
the active request. Cleanup MUST be a targeted single-file operation and MUST
retain Spec 009's commit-finality rule: commit is the last fallible database
boundary, and no rollback-style error may be reported after a successful commit.

#### AR-2.3: Keep Legacy Reads During A Partial Migration

Entry serialization, static serving, and browser rendering MUST continue to
accept flat and nested paths while the explicit migration is pending, partially
complete, being retried, or rolled back at the code level. Compatibility MUST
not depend on all rows being migrated in one uninterrupted run.

### Feature Validation

Exercise flat and nested paths through scoped entry reads, `/static` retrieval,
map popup/detail rendering, and Wrapped generation before, during, and after the
migration. Force image and database failures at each ownership boundary to prove
request-owned cleanup and unrelated file preservation. All automated filesystem
work must use a disposable upload root; browser verification must use disposable
data and must not create or alter live uploads.

---

## Feature 3: Migrate Existing Entry Images Safely

**Who & why:** The app owner wants BeerRunJPN and every other run to use one
active upload-path format, including historical entries. Those photos are
irreplaceable, so migration must be explicit, independently testable, resumable,
and incapable of rewriting a row before a verified destination exists.

### Functional Requirements

#### FR-3.1: Provide An Explicit Upload Migration Command

The system MUST provide a dedicated operator-invoked command that accepts an
explicit SQLite database and upload root, validates database readiness, and
migrates eligible legacy image references. It MUST NOT run automatically during
application import, startup, normal schema migration, entry reads, or entry
writes. The command MUST support a read-only preflight mode that reports planned,
already canonical, missing, invalid, conflicting, and migratable counts without
creating files or changing database rows.

**Verify:** Run preflight against a representative isolated database/tree and
confirm the report is accurate while file hashes and database contents remain
unchanged; then confirm ordinary app startup performs no migration side effect.

#### FR-3.2: Define Eligible Legacy Rows Conservatively

An eligible row MUST have a non-null legacy `image_path`, a valid non-null
`beer_run_id`, and a normalized source path that resolves to a non-empty regular
file within the configured `static/uploads` root. Already canonical nested paths
and null image paths MUST be skipped. Missing files, paths outside the upload
root, directories, empty files, invalid run assignments, and malformed paths
MUST be reported as unresolved and MUST NOT be copied or rewritten.

**Verify:** Preflight and apply a fixture containing each eligible, canonical,
null, missing, outside-root, directory, empty, invalid-run, and malformed case;
confirm only the eligible rows and files change and the command exits nonzero
while any unresolved case remains.

#### FR-3.3: Assign A Stable Canonical Destination

Each distinct pair of authorized `beer_run_id` and normalized legacy source
path MUST map deterministically to one canonical UUID-shaped destination under
`static/uploads/beer_runs/{beer_run_id}/`. Entries in the same run that share a
legacy source MUST share the same destination; references to that source from
different runs MUST receive destinations beneath their respective run IDs. The
mapping MUST remain identical across machines and reruns for the same run ID and
normalized source path, and MUST NOT include a run name or client filename.

**Verify:** Generate plans repeatedly and from two isolated copies of the same
fixture, including duplicate references within one run and across two runs;
confirm stable UUID-shaped destinations, within-run reuse, and cross-run folder
separation.

#### FR-3.4: Copy Without Overwriting And Verify Before Rewrite

For each eligible source, the migration MUST create the destination without
overwriting any existing file, copy the source bytes without re-encoding, and
verify source and destination content and non-empty size before changing any
`Entry.image_path`. If the deterministic destination already exists with
identical verified content, it MUST be safely reused. If it contains different
content or cannot be verified, the source, destination, and database row MUST
remain unchanged and the conflict MUST be reported.

**Verify:** Migrate a normal source, a pre-copied identical destination, and a
same-path sentinel containing different bytes; confirm copy/reuse behavior,
byte-for-byte verification, no overwrite of the sentinel, and no row update for
the conflict.

#### FR-3.5: Update Only After Verified Copies Exist

The migration MUST update an eligible row to its canonical forward-slash path
only after the required destination has passed FR-3.4. Each update MUST confirm
that the row still contains the planned legacy value so concurrent or unexpected
changes cannot be silently overwritten. Source files MUST remain in place after
the database update. A successful run MUST finish with every eligible row using
a canonical path that resolves to the verified copied file.

**Verify:** Interrupt execution before copy, after copy but before row update,
and after row update; at every point confirm each database path resolves to an
existing file, source files remain, stale-row changes are rejected, and a later
rerun completes all eligible rows safely.

#### FR-3.6: Make Repeated And Partial Runs Idempotent

Re-running the migration after success MUST create no additional files and make
no database changes. Re-running after a partial failure MUST skip already
canonical rows, reuse only verified deterministic copies, and continue eligible
remaining work without generating alternate destinations. The command MUST
return a nonzero status and an explicit summary when any row is unresolved or
conflicting; it MUST never report full completion for a partial migration.

**Verify:** Run the migration three times after success and compare file lists,
hashes, row values, and counts; separately fail midway and rerun, confirming the
final state matches a clean one-pass migration with no duplicate destinations.

#### FR-3.7: Require A Quiescent Live Migration And Preserve Backups

Documentation MUST require stopping application writes and creating or
confirming recoverable database and upload backups before applying the command
to live state. The migration command MUST refuse or fail safely when it cannot
obtain the database write access needed for the planned compare-and-update
operations. This specification and its automated verification MUST NOT apply the
migration to live `boozerun.db` or real `static/uploads/`; live execution remains
a separate explicit operator action.

**Verify:** Hold a conflicting database writer during an isolated migration and
confirm safe refusal/failure with no incorrect row updates, then inspect the
documented live procedure for stop, backup, preflight, apply, verify, and restart
steps.

### Architectural Requirements

#### AR-3.1: Separate File/Data Migration From Schema Migration

The upload migration belongs in a focused script under `scripts/`, not in the
database-only `migrations/runner.py` transaction or application startup. It may
reuse small path-normalization and verification helpers, but MUST remain direct
and repository-local without adding a general migration framework.

#### AR-3.2: Use Deterministic UUID Identity For Legacy Copies

Legacy destinations MUST use a documented deterministic UUID algorithm over a
stable application namespace plus the numeric run ID and normalized source path.
New interactive uploads continue using independently generated UUIDs. Both
sources produce the same canonical path shape while only the migration requires
repeatable identity.

#### AR-3.3: Preserve A Safe Operation Order

For each migration unit, the required order is: validate and confine the source,
derive the stable destination, create or verify the non-overwritten copy, verify
content equality, compare the current database value with the planned legacy
value, update the row, and confirm the canonical path resolves. No step may
delete or modify the legacy source.

### Feature Validation

Migration tests must use a tiny temporary SQLite database and upload root and
cover preflight, all eligibility categories, shared references, two runs,
deterministic mapping, byte-identical reuse, conflicting destinations, failures
at every operation boundary, stale rows, database locking, partial progress,
three successful reruns, exact summaries/statuses, and final path-to-file
integrity. Tests must also prove that neither the live database nor repository
upload root is opened or changed.

## Data Requirements

- `Entry.image_path` remains a nullable string; no table, column, constraint,
  index, relationship, or schema-migration changes.
- Every newly stored or successfully migrated non-null value has the canonical
  relative form
  `static/uploads/beer_runs/{beer_run_id}/{uuid}.jpg`.
- Before migration, legacy strings remain readable and are normalized only in
  API output. During migration, each eligible string is replaced only after its
  canonical copy is verified and its current value still matches the plan.
- The `Entry.beer_run_id` written by the scoped create route remains the same
  authorized ID used in the image folder; migration uses each existing row's
  valid run assignment as its folder authority.
- Original legacy files remain byte-for-byte unchanged after migration as
  rollback copies and to preserve previously shared flat `/static` URLs.
- Runtime files under `static/uploads/` remain protected user data and excluded
  from commits.

## Integration Points

- `main.py`: `save_optimized_image`, `write_upload_image`,
  `create_scoped_entry`, scoped entry serialization, upload-root creation, and
  the existing `/static` mount.
- `permissions.py`: authoritative member access and run identity before upload
  processing.
- `models.py` and `schemas.py`: unchanged persisted nullable path and unchanged
  twelve-field entry response.
- `tests/test_scoped_routes.py` and `tests/conftest.py`: isolated database,
  multi-run identities, upload writer seam, response-shape, authorization, and
  failure tests.
- `static/js/modules/map.js`: existing popup and detail image consumers; nested
  paths require no new UI contract.
- `scripts/build_wrapped_data.py` and `tests/test_wrapped.py`: existing path
  normalization and disposable flat/nested image-tree verification.
- A focused upload-migration script under `scripts/`: explicit preflight/apply,
  source confinement, deterministic destinations, copy verification,
  compare-and-update behavior, progress summaries, and exit status.
- Focused upload-migration tests: temporary database/root, partial failure,
  rerun, conflict, and final integrity coverage without live runtime access.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 009: Scope Entries And Leaderboard API | **Extends** - completes the deferred collision-safe naming, run-folder, exclusive ownership, cleanup, and test-seam work while preserving scoped create/read contracts | FR-1.1 through FR-1.5, FR-2.2 through FR-2.4, AR-1.1, AR-1.3, AR-2.2 |
| Spec 003: Backfill Existing Trip | **Modifies** - explicitly permits historical image references to change only through this verified file/data migration while preserving the original files and all visible behavior | FR-2.1, FR-3.2 through FR-3.7, AR-3.3 |
| Spec 011: Add Beer-Run Selector UI | **References** - uses the selected run already carried by the scoped entry-create URL and preserves popup/detail behavior | FR-1.1, FR-2.1, AR-1.3 |
| Spec 001: Add Database Migrations | **References** - follows its explicit-operation, visible-failure, isolated-test, and runtime-data protections while keeping filesystem work outside the schema runner | FR-3.1, FR-3.6, FR-3.7, AR-3.1 |

## Constraints

- Keep FastAPI, SQLAlchemy, SQLite, Pillow, vanilla JavaScript, static HTML/CSS,
  and the no-build deployment model.
- Add no package, storage service, framework, queue, background worker, schema
  change, or broad media abstraction.
- Preserve member-only authenticated writes, authorization-before-upload
  ordering, existing multipart fields, Pillow normalization, the exact create
  response, and the exact entry-list field set.
- Never mutate live `boozerun.db`, uploads, `users.json`, or caches during
  implementation or verification without explicit authorization. Tests and
  browser checks must use isolated database and upload roots.
- Keep `static/uploads/` excluded from commits; only source, tests, and this
  durable specification may change.
- Implement and test the migration only against disposable database and upload
  roots. Do not run it against live state as part of implementation verification.
- Run focused upload/scoped-route/upload-migration/Wrapped tests and the complete
  `uv --cache-dir .uv-cache run pytest` suite during implementation.
- Inspect a disposable running app in the Codex in-app browser on desktop and a
  mobile-sized viewport. Confirm a new upload and a legacy upload render in both
  the popup thumbnail and detail sheet with no console or network errors.

## Failure Modes

- **Generated destination already exists:** preserve it and retry with a new
  UUID within a bounded limit; sanitized failure after exhaustion.
- **Run directory cannot be created:** create no entry and return the sanitized
  create error without exposing a filesystem path.
- **Image decoding or normalization fails:** remove only any exclusively created
  request file, roll back, and return the sanitized create error.
- **Database work fails before commit:** roll back, remove only the request-owned
  new file, and retain all legacy/concurrent media.
- **Targeted cleanup fails:** preserve the original sanitized response and do
  not broaden cleanup to a directory or another candidate; verification must
  demonstrate the failure does not leak internals.
- **Commit succeeds:** return the normal success and retain the file; no later
  cleanup path may treat it as an orphan.
- **Legacy path contains backslashes:** leave its database value and file
  unchanged until migration, return a forward-slash value from the entry API,
  and normalize it for confined source lookup and canonical migration output.
- **Legacy source is missing, empty, outside the upload root, or invalid:** do
  not copy or rewrite it; report it as unresolved and exit nonzero.
- **Deterministic migration destination already contains identical bytes:**
  verify and reuse it before the guarded database update.
- **Deterministic migration destination contains different bytes:** preserve
  both files and the legacy row, report a conflict, and exit nonzero.
- **Migration stops after copy but before row update:** the legacy row still
  resolves to its retained source; rerun verifies and reuses the same copy.
- **Migration stops after row update:** the canonical row resolves to the
  verified destination and the legacy source remains; rerun skips the completed
  row without creating another file.
- **Row changes after planning:** the guarded update fails for that row rather
  than overwriting the new value; report partial completion explicitly.

## Security And Privacy Boundaries

- The authorized path run, never caller-controlled filename or multipart
  metadata, determines storage scope.
- UUID names reduce guessability but are not an access-control mechanism.
  Everything beneath `/static` remains publicly retrievable when its URL is
  known, including media belonging to private runs.
- No response may expose local absolute paths or raw filesystem/image/database
  failures.
- Migration diagnostics may identify entry IDs and normalized app-relative
  paths needed for operator repair but MUST NOT print credentials, tokens, raw
  database contents, or paths outside the configured roots.
- This feature neither validates users by original filename nor trusts file
  extensions for stored path selection; the server continues normalizing bytes
  to JPEG.
- Run-directory separation must not be described as tenant isolation or private
  media delivery.

## Performance Impact

- Each new upload adds constant-time UUID allocation, one run-directory
  existence/creation operation, and the existing image normalization/write.
- No database query, table scan, upload-tree scan, public-run enumeration, or
  startup creation per run is added to normal request handling.
- Collision retries are bounded so a faulty UUID source or hostile filesystem
  state cannot create an unbounded request loop.
- Nested directories limit the number of files in one flat folder while keeping
  current Raspberry Pi-class deployment and static serving behavior.
- The one-time migration performs bounded database enumeration plus one
  byte-for-byte copy and verification per distinct run/source pair. Retaining
  flat rollback copies temporarily increases media storage by up to roughly the
  size of the eligible legacy image set.

## Rollout And Rollback

1. Add focused request and migration tests against isolated database and upload
   roots before changing production path generation.
2. Deploy the collision-safe writer, compatibility reads, migration command,
   tests, and operator documentation together. No schema or frontend asset
   migration is required.
3. Stop live application writes and confirm recoverable database and upload
   backups without overwriting protected backup state.
4. Run the migration's read-only preflight with explicit live paths. Resolve all
   missing, invalid, or conflicting cases before apply.
5. Run the explicit apply command. Require a zero exit status and a final audit
   showing every non-null entry image path is canonical and resolves to a
   byte-verified nested file; retained flat sources must still exist.
6. Start the app and verify focused behavior, the full pytest gate, protected
   runtime state, and disposable plus live smoke checks appropriate to the
   operator-approved deployment.
7. A code rollback does not require file deletion: nested active paths and flat
   rollback copies remain statically servable by the older app. The older writer
   may resume creating flat files, but rollback must never delete either set.

## Out Of Scope

- Automatically applying the upload migration at application startup, schema
  migration time, or during normal requests.
- Deleting retained flat legacy source copies after active database references
  become canonical; any later cleanup requires a separately reviewed retention
  and rollback decision.
- Authenticated/private media delivery, signed URLs, media encryption, or a new
  static-file authorization route.
- Deleting upload files or recursively deleting run directories when an entry,
  user, or beer-run is deleted.
- General orphan discovery, historical orphan cleanup, media deduplication,
  quotas, retention policies, cloud/object storage, or CDN changes.
- New image formats, quality/dimension policy changes, content moderation,
  antivirus scanning, upload-size policy, or changes to the file input UI.
- Scoping or otherwise changing Wrapped content beyond verifying that its
  existing path handling accepts nested files.

## Assumptions And Risks

- **Assumption:** The scoped entry route and `MemberAccess` contract from Spec
  009 remain the only entry-upload write path.
- **Assumption:** Numeric beer-run IDs are immutable and safe as stable directory
  names; run names may change.
- **Assumption:** Starlette's existing `/static` mount and the browser's current
  relative URL construction accept nested paths without a frontend change.
- **Assumption:** Existing legacy image rows have valid `beer_run_id` values
  after the Release 1 backfill; exceptions are unresolved rather than guessed.
- **Risk:** Public static serving means private-run photos remain accessible to
  anyone who learns the URL. UUIDs reduce accidental discovery but do not solve
  that existing privacy limitation.
- **Risk:** Filesystem and SQLite commits are not one atomic transaction. Unique
  request ownership and copy-before-rewrite ordering keep every active path
  resolvable, but a failed migration can leave a verified unreferenced copy that
  a rerun must reuse rather than duplicate.
- **Risk:** An implementation that merely generates a UUID and then opens the
  destination in overwrite mode would not satisfy FR-1.3; collision tests must
  force candidate reuse and inspect sentinel bytes.
- **Risk:** Retaining originals protects rollback and hard-coded legacy static
  references but temporarily duplicates media storage. This is an intentional
  safety tradeoff; destructive cleanup is outside this feature.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Goals, Specification Decisions, Features
  1-3, Constraints, Failure Modes, and Out Of Scope define new-upload behavior,
  compatibility, mandatory legacy migration, and testable boundaries.
- [x] **Testing strategy** - Feature Validation sections, Constraints, and
  Rollout And Rollback require isolated real-writer and migration tests,
  collision/interruption/rerun coverage, full pytest, and disposable
  desktop/mobile browser inspection.
- [x] **Existing patterns** - AR-1.1, AR-1.3, AR-2.1, AR-3.1, Integration Points,
  and Related Specs reference the current `main.py` writer, shared permissions,
  database-only schema runner, scoped tests, map consumers, and Wrapped
  normalizer.
- [x] **Dependencies** - Specification Decisions and Constraints confirm Python
  UUID/hash/copy/filesystem support and existing Pillow behavior are sufficient;
  no new package or service is introduced.
- [x] **Architecture & interfaces** - FR-1.1 through FR-1.5, FR-2.2, FR-3.1
  through FR-3.7, all ARs, Data Requirements, and Integration Points define the
  writer, migration command, path contract, API boundaries, and unchanged
  schema.
- [x] **Error handling & failure modes** - FR-1.3, FR-2.3, FR-2.4, FR-3.2
  through FR-3.7, AR-2.2, AR-3.3, and Failure Modes cover request collisions,
  directory/image/database failures, migration conflicts, interruptions,
  guarded updates, cleanup, and post-commit behavior.
- [x] **Security review** - FR-1.1, FR-1.2, FR-2.3, FR-3.2, FR-3.7, AR-1.2,
  AR-3.3, and Security And Privacy Boundaries assess untrusted filenames,
  filesystem confinement, diagnostics, authorization ordering, and unchanged
  public-media exposure.
- [x] **Performance impact** - FR-1.3, FR-1.4, FR-3.3, FR-3.6, and Performance
  Impact define bounded retries, lazy directories, normal-request isolation,
  deterministic reuse, migration copying, and temporary storage growth.
- [x] **Rollout & migration** - FR-2.1, FR-3.1 through FR-3.7, AR-2.3, all AR-3
  requirements, Data Requirements, and Rollout And Rollback define mandatory
  copy-first migration, preflight, live-write quiescence, verification,
  idempotent reruns, retained sources, and data-safe code rollback.
- [x] **Assumptions & risks** - Specification Decisions and Assumptions And Risks
  record selected-run authority, immutable IDs, filesystem/database atomicity,
  deterministic legacy identity, retained-copy storage cost, collision
  semantics, and the static-media privacy limitation.
