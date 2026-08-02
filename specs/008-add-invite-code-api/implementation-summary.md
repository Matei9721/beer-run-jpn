# Implementation Summary: 008-add-invite-code-api

**Status:** Completed
**Date:** 2026-08-02
**Branch:** `spec/008-add-invite-code-api` (based on `codex/007-membership-authorization-helpers`)
**Worktree:** N/A — implemented directly on the branch, `--worktree` was not used

## Overview

Added one permanent, reusable invite per beer-run plus three JSON endpoints: owner-only
create-or-retrieve, public minimal preview, and authenticated idempotent acceptance. The
feature builds on the shared `permissions` owner policy (Spec 007), the existing
`BeerRunResponse` shape, the ordered migration runner, and the isolated test fixture.
Each beer-run's invite carries a 256-bit (43-character URL-safe) bearer code persisted in
recoverable raw form so the owner's create endpoint doubles as retrieval forever.

## Team Execution

Implemented solo. This is a medium-sized, tightly coupled spec — the router, schemas,
model, and migration all interlock, so sequential implementation with no subagents was
the right call.

**Parallel phases:** schema/migration tests and endpoint tests were written against
already-complete code (additive, non-conflicting).
**Sequential phases:** model → migration → schemas → router → registration → tests.

## Files Created

- `invite_routes.py` — invite create/preview/accept router, code generator, and
  response builders.
- `migrations/versions/006_add_beer_run_invites.py` — invite table, foreign key, unique
  beer-run and code indexes, code-format check, and strict full-schema baseline
  validation that refuses incomplete pre-existing invite tables.
- `tests/test_invites.py` — 44 focused endpoint/security/idempotency/concurrency tests.
- `specs/008-add-invite-code-api/implementation-summary.md` — this file.

## Files Modified

- `models.py` — added `BeerRunInvite` and the singular `BeerRun.invites` relationship.
- `schemas.py` — added `InviteCreateResponse` and `InvitePreviewResponse`.
- `migrations/runner.py` — registered migration `006_add_beer_run_invites`.
- `main.py` — registered the invite router.
- `beer_run_routes.py` — run deletion now removes the run's invites in the same
  transaction before the run.
- `tests/test_beer_run_schema.py` — invite relationship/FK/uniqueness coverage.
- `tests/test_migrations.py` — ordered, fresh/upgrade/idempotent, schema/index/FK,
  complete-baseline, partial-schema refusal, and data-preservation coverage plus
  updated `MIGRATION_VERSIONS`.

## Test Results

- `uv --cache-dir .uv-cache run pytest` → **275 passed** (216 pre-existing + 59 new),
  1 pre-existing passlib deprecation warning.
- `git diff --check` → clean; protected runtime files (`boozerun.db`, `boozerun_backup.db`,
  `test.db`, `users.json`, `static/uploads/`) untouched.

## Spec Adherence

| Requirement | Status | Implementation | Test |
|-------------|--------|---------------|------|
| FR-1.1 Invite model + singular relationship | Done | `models.py:BeerRunInvite`, `BeerRun.invites` | `test_beer_run_schema.py::test_beer_run_exposes_singular_invite_relationship` |
| FR-1.2 256-bit URL-safe codes | Done | `invite_routes.py::_generate_code` (`secrets.token_urlsafe(32)`) | `test_invites.py::test_code_is_43_url_safe_characters` |
| FR-1.3 Sensitive raw-code storage | Done | `beer_run_invites.code`; no logging/errors echo code | preview/accept bodies assert no code |
| FR-1.4 Preservation migration | Done | `migrations/versions/006_*.py` | `test_migrations.py::test_invite_migration_applies_to_pre_invite_database_and_preserves_rows` |
| AR-1.1 Model/SQLite invariant agreement | Done | model + migration share FK, unique indexes, and check; baseline validates every invariant and rejects partial tables | schema + migration tests, including complete baseline and partial-schema refusal |
| AR-1.2 Std-lib only | Done | `secrets`, `re`, `urllib.parse` | — |
| AR-1.3 Create-or-retrieve concurrency | Done | unique backstops, retry ≤3, loser re-reads winner | `test_invites.py::TestConcurrentCreation` |
| FR-2.1 Owner-only create (401/403/404) | Done | `Depends(permissions.authorize_owner_access)` | `test_invites.py::TestCreateAuthorization` |
| FR-2.2 Stable link contract | Done | `_invite_create_response` root-relative `/?invite=` | `TestCreateResponseContract` |
| FR-2.3 Same permanent invite after rename | Done | name resolved at response build | `test_permanent_invite_follows_rename_without_changing_code` |
| FR-2.4 Public minimal preview | Done | `GET /api/invites/{code}` | `test_invites.py::TestPreview` |
| FR-2.5 Uniform invalid-code 404 | Done | `_invite_not_found()` | `test_preview_malformed_codes_return_404` |
| AR-2.1 Focused router registered | Done | `invite_routes.py` in `main.py` | — |
| AR-2.2 Reuse shared owner policy | Done | `authorize_owner_access` | `TestCreateAuthorization` |
| AR-2.3 Dedicated schemas | Done | `InviteCreateResponse`, `InvitePreviewResponse` | response-shape assertions |
| FR-3.1 Auth precedes code validity | Done | `auth.get_current_user` + 401 first | `test_invites.py::TestAcceptAuthorization` |
| FR-3.2 Non-member becomes member | Done | insert `BeerRunMember(role="member")` | `test_non_member_accepts_private_run_invite` |
| FR-3.3 Idempotent + role preserving | Done | pre-check + unique backstop | `TestAcceptBehavior` |
| FR-3.4 Existing BeerRunResponse | Done | `_beer_run_response` from fresh COUNT | `test_owner_accept_preserves_owner_role` |
| FR-3.5 Uniform invalid accept 404 | Done | `_invite_not_found()` after auth | `test_invalid_codes_create_no_membership` |
| AR-3.1 Identity without membership | Done | `auth.get_current_user` (not member/public policy) | `TestAcceptAuthorization` |
| AR-3.2 Membership uniqueness backstop | Done | rollback + re-read on duplicate race | `test_lost_duplicate_membership_race_preserves_committed_role` |
| AR-3.3 Fresh committed metadata | Done | member_count counted from DB post-commit | accept response assertions |
| Run-delete removes invites | Done | `beer_run_routes.py:delete_beer_run` | `test_delete_run_removes_invites_and_memberships` |

## Deviations from Spec

None. Implementation decisions (explicit `CREATE UNIQUE INDEX` in migration 006 rather
than inline `UNIQUE` constraints; negated-class `GLOB` check for the code alphabet) match
the spec's "unique index" wording and the Data Requirements — no ADR required.

## Notes

- The app now refuses to start against a runtime `boozerun.db` that lacks migration 006,
  as required by the Rollout section. Apply via `scripts/migrate_db.py` when deploying.
- `specs/docs/` does not exist, so the living-docs update step was skipped (docs have not
  been bootstrapped in this repo).
- This API-only feature changes no browser assets, so no cache-busting or browser layout
  inspection was required.
