# Spec 014 Implementation Summary

**Status:** Completed

**Date:** 2026-08-13

**Branch:** `spec/014-organize-upload-paths-by-beer-run`

**Based on:** `spec/013-add-invite-ui-and-accept-flow` at `d39204b39565f79f0bf37e82746e65f924f119ce`

**Worktree:** Existing repository worktree

## Outcome

New uploads now use collision-safe, server-derived paths of the form
`static/uploads/beer_runs/{beer_run_id}/{uuid}.jpg`. Existing flat paths remain
readable while a dedicated, explicit migration command can copy verified legacy
images into the same canonical layout and update their database references.

The implementation does not run the data migration automatically and did not
read, write, or migrate the live `boozerun.db` or `static/uploads/` tree.

## Execution

Research and implementation were split by non-overlapping file ownership:

| Workstream | Scope | Files |
| --- | --- | --- |
| Upload runtime | Run-scoped writer, response compatibility, failed-write cleanup, Wrapped coverage | `main.py`, `tests/test_scoped_routes.py`, `tests/test_upload_paths.py`, `tests/test_wrapped.py` |
| Migration operations | Explicit migration CLI, safety tests, operator documentation | `scripts/migrate_upload_paths.py`, `tests/test_upload_path_migration.py`, `README.md`, `repository_rules.md` |
| Compatibility review | Read-only API, UI, Wrapped, and test-contract review | No file changes |

The two implementation workstreams ran in parallel, followed by integration
review, migration interruption hardening, combined tests, the full suite, and
desktop/mobile browser verification.

## Files Changed

- `main.py`: accepts authorized run context in the upload writer, exclusively
  reserves UUID destinations, stores canonical forward-slash paths, normalizes
  legacy response separators, and removes only request-owned files on pre-commit
  failure.
- `scripts/migrate_upload_paths.py`: adds explicit `--preflight` and `--apply`
  modes with deterministic UUID5 destinations, confined source validation,
  non-overwriting verified copies, guarded row updates, and resumable execution.
- `tests/test_upload_paths.py`: exercises the real upload writer against
  disposable roots, including collision, concurrency, conversion, orientation,
  and resizing behavior.
- `tests/test_upload_path_migration.py`: covers planning, eligibility,
  deterministic mapping, reuse/conflict handling, locking, interruption,
  resumability, and idempotence.
- `tests/test_scoped_routes.py`: extends scoped API coverage for path ownership,
  compatibility, exact errors/responses, and targeted cleanup.
- `tests/test_wrapped.py`: proves flat, nested, and backslash-stored paths remain
  compatible with Wrapped generation.
- `README.md` and `repository_rules.md`: document the required stop, backup,
  preflight, apply, audit, and restart procedure and prohibit live application
  during automated verification.

## Requirement Traceability

| Requirement | Implementation and evidence |
| --- | --- |
| FR-1.1 | `write_upload_image` receives `access.beer_run.id` and derives the numeric run folder; scoped tests cover two runs and rename stability. |
| FR-1.2 | The writer generates a canonical UUID and `.jpg` basename without using `UploadFile.filename`; hostile-filename tests verify the stored shape. |
| FR-1.3 | Destinations are opened with exclusive `xb` creation and bounded retries; tests preserve collision sentinels, exercise exhaustion, and prove same-second uploads stay distinct. |
| FR-1.4 | Run directories are created lazily with parent creation; direct concurrent-writer tests start from a missing tree and preserve both files. |
| FR-1.5 | Pillow still applies EXIF transpose, RGB conversion, 1080-pixel bounding, and optimized JPEG output; direct writer and multipart tests cover these paths plus no/empty images. |
| AR-1.1 | Image handling remains a compact `main.py` helper/route boundary with `UPLOAD_ROOT` monkeypatchable to `tmp_path`. |
| AR-1.2 | New physical components are limited to the authorized integer ID, canonical UUID, and `.jpg`; stored values are constructed with `PurePosixPath`. |
| AR-1.3 | `MemberAccess` remains a dependency of the scoped route and denied/invalid requests are tested to create no upload tree. |
| FR-2.1 | Migration copies and retains legacy sources; migration tests assert byte identity, while browser verification confirms flat and nested URLs in popups and detail sheets. |
| FR-2.2 | `normalize_image_path_for_response` normalizes only serialized output; tests assert unchanged stored legacy values, the exact twelve-field list contract, and unchanged create response. |
| FR-2.3 | Allocation, image, directory, and database failures all use the exact sanitized 500 response and leave no new row; focused route tests cover every category. |
| FR-2.4 | `_OwnedUpload` records exclusively created files and cleanup performs one targeted unlink before commit only; tests cover partial image output, database failure, cleanup failure, sentinels, and committed success. |
| FR-2.5 | Existing Wrapped normalization accepts flat and nested paths; the expanded Wrapped test verifies both public URLs without changing unrelated output. |
| AR-2.1 | New paths are canonical at storage time and legacy separators are normalized at serialization time; the frontend's defensive replacement remains unchanged. |
| AR-2.2 | Cleanup accepts only `_OwnedUpload`, removes one file, and preserves commit as the final fallible database boundary. |
| AR-2.3 | Static serving, scoped reads, map rendering, and Wrapped generation accept mixed flat/nested data throughout a partial migration. |
| FR-3.1 | `scripts/migrate_upload_paths.py` requires explicit database/upload-root arguments and exactly one mode; read-only preflight reports categories without file or row changes. |
| FR-3.2 | Planning rejects null, canonical, missing, empty, directory, malformed, outside-root, and invalid-run cases; representative fixtures verify only eligible rows migrate. |
| FR-3.3 | A documented fixed UUID5 namespace maps normalized `run ID + source path` identity deterministically; tests cover cross-root stability, within-run sharing, and cross-run separation. |
| FR-3.4 | Copies use a verified staging file and atomic non-overwriting publish, reuse only byte-identical destinations, and preserve conflicts; tests cover normal, reusable, conflicting, failed, and interrupted copies. |
| FR-3.5 | Row updates occur only after destination verification and use `WHERE id`, original `image_path`, and `beer_run_id` guards; tests cover stale rows and interruption before/after commit while retaining sources. |
| FR-3.6 | Canonical rows are skipped and deterministic verified copies are reusable; tests cover partial recovery and three no-op reruns with exact status/summary checks. |
| FR-3.7 | Apply obtains `BEGIN IMMEDIATE` before filesystem side effects, lock tests prove safe refusal, and the operator runbook requires quiescence plus recoverable database/upload backups. |
| AR-3.1 | File/data migration is isolated in one repository-local script and does not modify the schema migration runner or application startup. |
| AR-3.2 | Legacy copies use deterministic UUID5 identity while interactive uploads retain independent UUID4 allocation, with one canonical path shape. |
| AR-3.3 | The script validates/confines, derives, copies or verifies, content-checks, compare-updates, and confirms the final file without deleting or modifying the legacy source. |

## Verification

- Baseline before implementation: `330 passed`, with one existing Passlib
  Argon2 deprecation warning.
- Focused integration suite:
  `uv --cache-dir .uv-cache run pytest tests/test_upload_paths.py tests/test_scoped_routes.py tests/test_upload_path_migration.py tests/test_wrapped.py`
  — `70 passed`, with the same existing warning.
- Full suite: `uv --cache-dir .uv-cache run pytest` — `360 passed`, with the
  same existing warning.
- `git diff --check` passed.
- Browser verification used an isolated temporary database, static root, and
  upload tree. At the default desktop viewport and at `390x844`, both a retained
  flat URL and a canonical nested URL loaded successfully in the map popup and
  drink-detail sheet. The browser reported no warnings or errors. The local
  test server and temporary fixture were removed afterward.

## Deviations And Follow-Up

No specification deviations remain. Live migration is intentionally an
operator-controlled follow-up: stop application writes, create recoverable
database and upload backups, run preflight, resolve reported issues, apply, run
the final preflight/audit, and then restart as documented in `README.md`.

The optional `spec/docs/` living-documentation tree is not bootstrapped in this
repository, so no generated architecture or testing document was updated.
