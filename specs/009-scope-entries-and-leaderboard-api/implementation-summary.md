# Implementation Summary: 009-scope-entries-and-leaderboard-api

**Status:** Completed
**Date:** 2026-08-02
**Branch:** `codex/009-scope-entries-and-leaderboard-api` (worked in place — the
current checkout was already the dedicated spec branch carrying Specs 005-008)
**Worktree:** N/A — implemented directly on the branch, `--worktree` was not used

## Overview

Replaced the three global-looking entry/leaderboard routes with beer-run-ID-scoped
APIs, applied the shared Spec 007 visibility and membership policies, and updated
the browser to resolve the visible `BeerRunJPN` row through `GET /api/beer-runs`
and send that ID with every leaderboard, entry-list, and entry-create request.
The old `GET /api/leaderboard`, `GET /api/entries`, and `POST /api/entries`
routes were removed in the same change, and the repository frontend and tests now
use only the scoped contract.

## Team Execution

Implemented solo. The spec's three features are coupled by shared response
contracts and an atomic backend/frontend rollout requirement, so file-conflict
analysis favored sequential execution over subagent parallelism.

**Parallel phases:** none (sequential implementation for correctness).
**Sequential phases:** backend scoped routes → frontend scoped callers →
test migration + new focused tests → full pytest → Playwright browser validation.

## Files Created

- `tests/test_scoped_routes.py` — focused coverage for Features 1 & 2 and old-route
  removal (38 tests: isolation, entrant semantics, ranking, shape, visibility
  matrix, concealed 404s, bounded query count, index plan, member-only creation,
  upload seam, sanitized failures, commit finality, spoofed fields, old-route 404).
- `specs/009-scope-entries-and-leaderboard-api/implementation-summary.md` — this file.

## Files Modified

- `main.py` — added the `write_upload_image` image-writer seam (the narrow hook
  focused tests mock/redirect to an isolated directory), scoped
  `GET /api/beer-runs/{id}/leaderboard`, `GET /api/beer-runs/{id}/entries`, and
  `POST /api/beer-runs/{id}/entries`; removed the three old routes and the
  `get_default_beer_run`/`DEFAULT_BEER_RUN_NAME` helpers.
- `static/js/modules/api.js` — `fetchBeerRuns`, scoped `fetchLeaderboard`/`fetchEntries`
  (with optional bearer headers and normalized `{ok, data}` results), scoped
  `submitEntry`; removed unscoped URL construction.
- `static/js/app.js` — in-memory default-run resolution (`resolveDefaultBeerRun`),
  scoped `loadTripData` with 404-re-resolve-once and transient-retain behavior,
  availability messages, member-gated submission, role refresh on login/logout,
  and create-404 re-resolution; bumped `api.js` import cache version.
- `templates/index.html` — bumped `app.js` cache-busting query string to `v=13`.
- `tests/test_auth.py` — migrated three protected-route tests to the scoped POST.
- `tests/test_main.py` — migrated entry/leaderboard tests to the scoped routes.

## Test Results

- `uv --cache-dir .uv-cache run pytest` — **313 passed, 1 pre-existing warning**
  (baseline was 275 passed; +38 new scoped-route tests).
- `git diff --check` — clean.
- Playwright browser validation (disposable DB + isolated server on port 8123):
  leaderboard/map render, scoped network URLs confirmed, login + role refresh,
  username filter, manual refresh, entry submission → `200` + post-submit refresh,
  user-history modal, mobile 390px viewport, and zero console errors/warnings.

## Spec Adherence

| Requirement | Status | Implementation | Test |
|-------------|--------|---------------|------|
| FR-1.1 Scoped leaderboard route | Done | `main.py:get_scoped_leaderboard` | `TestScopedLeaderboard::test_leaderboard_totals_are_isolated_per_run` |
| FR-1.2 Entrants only | Done | SQL join of membership + entries | `test_leaderboard_includes_entrants_only`, `test_new_run_with_only_owner_returns_empty_array` |
| FR-1.3 Alcohol ranking | Done | `order_by(sum(alcohol).desc())` | `test_leaderboard_ranking_by_alcohol_within_run` |
| FR-1.4 Scoped entry list + 12 fields | Done | `main.py:get_scoped_entries` | `test_entries_isolated_shape_and_ordering` |
| FR-1.5 Case-insensitive username filter | Done | `func.lower(...) == func.lower(...)` (matches auth login) | `test_username_filter_is_case_insensitive_and_run_scoped` |
| FR-1.6 Read visibility policy | Done | `Depends(permissions.authorize_public_read)` | `test_visibility_matrix` |
| FR-1.7 Concealed private 404 | Done | shared `not_found_error` | `test_missing_run_and_inaccessible_private_are_identical`, `test_negative_and_non_integer_ids` |
| AR-1.1 Consume shared read result | Done | typed `PublicReadAccess` dependency | visibility matrix |
| AR-1.2 Scoped SQL + bounded queries | Done | one aggregate query; index exists | `test_leaderboard_query_count_does_not_grow_with_entrants`, `test_entries_use_run_scope_index` |
| AR-1.3 Reuse response contracts | Done | `response_model=list[schemas.LeaderboardUser]` / `list[schemas.Entry]` | shape assertions |
| FR-2.1 Scoped create route | Done | `main.py:create_scoped_entry` | `test_owner_and_member_succeed_in_public_and_private`, `test_multipart_validation_retains_422` |
| FR-2.2 Member-only writes | Done | `Depends(permissions.authorize_member_access)` | `test_non_member_denied_even_when_public`, `test_missing_auth_returns_401_with_bearer_challenge`, `test_missing_run_concealed_after_auth` |
| FR-2.3 Bind to auth + path run | Done | `user_id`/`beer_run_id` from server only | `test_spoofed_identity_fields_are_ignored` |
| FR-2.4 Preserve success response | Done | `{"status": "success", "entry_id": int}` | success-shape assertions |
| FR-2.5 Auth before upload write | Done | dependency gates route body | `test_denied_create_writes_no_entry_and_no_upload` |
| FR-2.6 Sanitized failures | Done | exact `500 {"detail": "Unable to create entry"}`, rollback, no delete | `test_image_failure_is_sanitized_and_rolls_back`, `test_pre_commit_database_failure_rolls_back` |
| AR-2.1 Consume shared member access | Done | typed `MemberAccess` dependency | member tests |
| AR-2.2 Direct entry/image architecture | Done | kept in `main.py`, reuses `save_optimized_image` | — |
| AR-2.3 No upload migration scope | Done | path format `static/uploads/<ts>.jpg` preserved | upload seam test |
| AR-2.4 Commit final boundary | Done | `flush` → capture id → `commit` | `test_commit_is_final_without_post_commit_refresh` |
| AR-2.5 Isolated upload seam | Done | `write_upload_image` mock/redirect seam | `test_create_entry_with_image_uses_isolated_writer_seam` |
| FR-3.1 Resolve default run via API | Done | `app.js:resolveDefaultBeerRun` | Playwright network log (`/api/beer-runs` → `/api/beer-runs/1/...`) |
| FR-3.2 Send default ID with calls | Done | `api.js` scoped helpers | Playwright network log |
| FR-3.3 Preserve visible behavior | Done | unchanged rendering + member gate | Playwright (login, filter, submit, user modal, mobile) |
| FR-3.4 Unavailable default handling | Done | `network`/`missing` reason → exact messages, block submit, retry | code path + Playwright |
| FR-3.5 Failure recovery, no corruption | Done | `loadTripData` 404-resolve-once / transient-retain; helpers return `{ok, data}` | unit tests + code path |
| FR-3.6 Old routes removed | Done | routes deleted from `main.py` | `TestOldRouteRemoval::test_old_routes_return_404` |
| AR-3.1 Module boundaries | Done | api.js network, app.js orchestration | — |
| AR-3.2 Selector as state substitution | Done | helpers require a run ID | code structure |
| AR-3.3 Cache busting | Done | `api.js?v=11`, `app.js?v=13` | Playwright asset load |

## Deviations from Spec

None. The scoped create route drops the legacy debug `print` statements from the
old handler; this does not affect any client-visible behavior or response shape.

## Notes

- `spec/docs/` does not exist, so the incremental living-docs step was skipped
  (docs have not been bootstrapped in this repository). Run
  `/spec-docs --full` if you want them generated.
- Browser validation ran against a disposable database and isolated upload root
  (temp dir); the protected `boozerun.db`, uploads, and other runtime state were
  not modified.
