# Implementation Summary: 007-centralize-beer-run-authorization

**Status:** Completed
**Date:** 2026-08-02
**Branch:** `codex/007-membership-authorization-helpers` (implemented directly on the current branch per explicit user request — no new `spec/007-*` branch was created)
**Worktree:** N/A — implemented directly on the branch

## Overview

Centralized beer-run authorization into a new `permissions.py` module exposing
three shared FastAPI dependencies — public-read, member-only, and owner-only —
each returning a typed access result containing the already-authorized
`BeerRun` and (for member/owner policies) the caller's non-null membership.
The detail, update, and delete CRUD routes now consume these dependencies
instead of duplicating inline visibility, ownership, and required-auth checks.
All authorization decisions are based on the persisted `is_public` flag and
`BeerRunMember` rows; no decision reads the run name, and `BeerRunJPN` has no
name-based special status.

No schema, migration, or runtime-data change was required.

## Team Execution

Implemented solo — the work is one tightly coupled unit (routes consume the new
module's interface), so parallel writers would only conflict on the shared
policy API.

**Parallel phases:** research (spec + codebase exploration), test-writing for
independent assertion groups.
**Sequential phases:** module → route integration → fixtures → focused tests →
integration tests → full-suite verification.

## Files Created

- `permissions.py` — typed access results (`PublicReadAccess`,
  `MemberAccess`, `OwnerAccess`), shared `UNAUTHORIZED` / `FORBIDDEN` /
  `NOT_FOUND` errors, and `authorize_public_read`, `authorize_member_access`,
  `authorize_owner_access` dependencies composing `auth.get_current_user` +
  `database.get_db` and accepting `beer_run_id` from the path.
- `tests/test_permissions.py` — focused direct-call tests for all three
  policies (15 tests).
- `specs/007-centralize-beer-run-authorization/implementation-summary.md` —
  this file.

## Files Modified

- `beer_run_routes.py` — detail/update/delete now consume the shared
  dependencies; create reuses `permissions.UNAUTHORIZED`; `_beer_run_response`
  now derives the caller role from an optional membership instead of re-scanning
  the run's memberships; list keeps the set-based visibility query and passes
  each run's caller membership. Removed inline detail-visibility, owner-role,
  and required-auth logic and the module-local `_UNAUTHORIZED` constant.
- `tests/conftest.py` — added the `owner_member_nonmember_run` fixture creating
  a private and a public run with genuine owner, `role="member"`, and
  absent-membership identities plus bearer tokens and an open session.
- `tests/test_beer_run_crud.py` — added `TestSharedAuthorizationIntegration`
  (9 tests): genuine normal-member private-detail read, member/non-member owner
  rejection on update and delete, owner update+delete, and actual
  missing/invalid bearer-token composition for public/private reads and
  mutations.

## Test Results

```text
uv --cache-dir .uv-cache run pytest
213 passed, 1 warning (pre-existing argon2 deprecation warning)
```

Baseline before implementation: 189 passed. Net new tests: 24 (15 focused
permission tests + 9 integration tests).

## Spec Adherence

| Requirement | Status | Implementation | Test |
|-------------|--------|---------------|------|
| FR-1.1 public reads from `is_public` only | Done | `permissions.py:authorize_public_read` | `test_public_run_allows_everyone_with_truthful_membership`, `test_public_read_ignores_name_and_tracks_is_public` |
| FR-1.2 private reads require membership; 404 concealment | Done | `permissions.py:authorize_public_read` | `test_private_run_requires_membership`, `test_missing_run_404` |
| FR-1.3 member-only: 401 then 404, no `is_public` bypass | Done | `permissions.py:authorize_member_access` | `TestMemberPolicy` (incl. `test_401_takes_precedence_over_missing_run`, `test_is_public_does_not_bypass_membership`) |
| FR-1.4 owner-only: 401 / 403 / 404, no bypass | Done | `permissions.py:authorize_owner_access` | `TestOwnerPolicy` (incl. 403 for member & non-member, `test_public_visibility_does_not_weaken_ownership`) |
| FR-1.5 return run + (optional/non-null) membership | Done | typed result dataclasses | membership-null/role assertions across `TestPublicReadPolicy`/`TestMemberPolicy`/`TestOwnerPolicy` |
| AR-1.1 focused permissions module | Done | `permissions.py` | code inspection |
| AR-1.2 truthful typed results | Done | dataclasses with `\| None` on `PublicReadAccess` only | code inspection |
| AR-1.3 composes `get_current_user` + `get_db`, direct-callable | Done | dependency signatures | direct calls in `tests/test_permissions.py`; shared session via `Depends(get_db)` in routes |
| AR-1.4 direct SQLAlchemy reads; no frontend/caller state | Done | `db.get(...)` + membership query | code inspection |
| AR-1.5 centralized errors | Done | shared constants | status/detail/header assertions |
| AR-1.6 ≤ run + matching membership per check | Done | two queries per policy | code inspection |
| FR-2.1 detail uses public-read policy, same response | Done | `beer_run_routes.py:get_beer_run` | existing detail tests + `test_member_reads_private_detail` |
| FR-2.2 update uses owner policy, consumes authorized data | Done | `beer_run_routes.py:update_beer_run` | `test_owner_update_and_delete`, `test_member_cannot_update`, `test_non_member_owner_rejection` |
| FR-2.3 delete uses owner policy, preserves transaction | Done | `beer_run_routes.py:delete_beer_run` | `test_member_cannot_delete`, `test_owner_update_and_delete`, existing cascade tests |
| FR-2.4 list stays set-based, aligned with public-read rule | Done | `_visible_runs_query` unchanged | `TestListBeerRuns` |
| AR-2.1 no inline auth duplication in routes | Done | dependencies own auth | code inspection |
| AR-2.2 public API shapes unchanged | Done | `schemas.py` untouched | existing response-shape tests |
| AR-2.3 reusable for later scoped APIs | Done | public/member/owner deps standalone | code inspection |
| FR-3.1 distinct owner / member / non-member identities | Done | `owner_member_nonmember_run` fixture | fixture setup |
| FR-3.2 every policy tested directly + token composition | Done | `tests/test_permissions.py` + `TestSharedAuthorizationIntegration` | 15 + 9 tests |
| FR-3.3 non-`BeerRunJPN` public run; name vs `is_public` | Done | `test_public_read_ignores_name_and_tracks_is_public` | rename + toggle assertions |
| FR-3.4 integration regression incl. genuine member coverage | Done | `TestSharedAuthorizationIntegration` | member detail/update/delete + invalid-token cases |
| AR-3.1 isolated test data only | Done | uses conftest DB override | `git status` shows no runtime-state changes |
| AR-3.2 reusable setup in conftest, no prod test helpers | Done | `owner_member_nonmember_run` in `tests/conftest.py` | code inspection |

## Deviations from Spec

- **Branch:** The user explicitly requested implementing on the current branch
  (`codex/007-membership-authorization-helpers`) rather than creating
  `spec/007-centralize-beer-run-authorization`. No ADR recorded — this is a
  direct user instruction, not a design deviation.
- None otherwise. All FRs/ARs implemented as specified.

## Living Docs

`spec/docs/` does not exist in this repository (docs were never bootstrapped), so
the incremental living-docs update was skipped. Run `/spec-docs --full` if
generated docs are desired.
