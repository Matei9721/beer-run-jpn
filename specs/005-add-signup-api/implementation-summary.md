# Implementation Summary: 005-add-signup-api

**Status:** Completed
**Date:** 2026-07-19
**Branch:** `005-add-signup-api`
**Worktree:** N/A - branch workflow used

## Overview

Implemented the signup-code-gated `POST /api/signup` flow, including fail-fast private configuration, strict request typing, safe username/password validation, Argon2 hashing, version-2 ID-based access tokens, rollback-safe error handling, and signup-specific validation-error sanitization. Added an ordered SQLite migration and matching SQLAlchemy metadata so ASCII case variants share one username identity namespace under concurrent requests. Signup creates no beer-run membership and leaves BeerRunJPN data unchanged. Auth-facing HTTP handlers now live in a focused `auth_routes.py` router so `main.py` remains the lightweight application composition and trip-route module.

## Team Execution

| Teammate | Role | Tasks Completed |
|----------|------|-----------------|
| `impl_signup_config_map` | Feature 1 explorer | Mapped configuration, docs, startup, and auth-test integration points. |
| `impl_signup_identity_map` | Feature 2 explorer | Mapped migration/model requirements, collision handling, and file-conflict boundaries. |
| `impl_signup_token_map` | Feature 3 explorer | Mapped route transaction ordering, token reuse, rollback paths, and API tests. |
| `implement_signup_migration` | Migration/model implementer | Added migration 004, ORM index metadata, migration registration, and focused migration tests. |
| `implement_signup_api` | Config/API implementer | Added signup configuration, schema, route, safe errors, docs, and focused auth tests; fixed audit findings. |
| `audit_signup_spec` | Independent compliance auditor | Audited every FR/AR, identified two security/error-classification blockers, and confirmed their fixes. |

**Parallel phases:** The migration/model stream and config/API stream ran concurrently with strict, non-overlapping file ownership. Read-only feature exploration and final compliance auditing were also delegated.

**Sequential phases:** Integrated review, audit-finding fixes, focused/full tests, real HTTP smoke validation, requirement audit, and this summary were completed sequentially.

## Files Created

- `migrations/versions/004_case_insensitive_usernames.py` - Refuses legacy ASCII-case collisions and creates the unique `NOCASE` username index.
- `auth_routes.py` - Owns login, signup, current-user routes, and signup-specific request error handling.
- `specs/005-add-signup-api/ADR.md` - Records the user-requested route-module extraction from the spec's original `main.py` placement.
- `specs/005-add-signup-api/implementation-summary.md` - Records execution, validation, and requirement adherence.

## Files Modified

- `.env.example` - Adds only the rejected `SIGNUP_CODE` placeholder.
- `README.md` - Documents private signup-code configuration, precedence, startup refusal, and zero-membership signup behavior.
- `auth.py` - Adds signup configuration validation and constant-time exact code comparison.
- `main.py` - Adds startup readiness and registers the focused auth router and signup validation-error handler.
- `schemas.py` - Adds strict-string `SignupRequest`.
- `models.py` - Declares matching binary and unique `NOCASE` username indexes.
- `migrations/runner.py` - Registers migration 004 after the BeerRunJPN backfill.
- `tests/conftest.py` - Provides deterministic test signup configuration before app import.
- `tests/test_auth.py` - Covers configuration, startup, validation privacy, hashing, tokens, duplicate/race handling, rollback, and membership preservation.
- `tests/test_migrations.py` - Covers index semantics, collision refusal, idempotency, upgrades, and protected-data preservation.
- `AGENTS.md` - Retains the Spec 005 durable-reference update and records the auth-route module boundary.
- `repository_rules.md` - Records the lightweight auth-route extraction as the authoritative backend boundary.

## Test Results

- Baseline before implementation: `uv --cache-dir .uv-cache run pytest` - **96 passed**, 1 existing Argon2 deprecation warning.
- Integrated auth/migration checkpoint: `uv --cache-dir .uv-cache run pytest tests/test_migrations.py tests/test_auth.py` - **121 passed**, 1 existing warning.
- Final full suite after audit fixes: `uv --cache-dir .uv-cache run pytest` - **149 passed**, 1 existing warning.
- Post-refactor focused auth suite: `uv --cache-dir .uv-cache run pytest tests/test_auth.py` - **104 passed**, 1 existing warning.
- Post-refactor full suite: `uv --cache-dir .uv-cache run pytest` - **149 passed**, 1 existing warning.
- Independent post-fix auth/migration audit run - **128 passed**, 1 existing warning.
- Real HTTP smoke test using Uvicorn and an explicitly named temporary SQLite database:
  - valid signup: `201 Created`
  - returned bearer token on `/api/me`: `200 OK`, stored username `SmokeUser1`
  - duplicate signup: `409 Conflict`
  - incorrect signup code: `403 Forbidden`
- `git diff --check` - passed.
- Temporary smoke database, WAL/SHM files, logs, and server process were removed after validation.
- `uv --cache-dir .uv-cache run python scripts/migrate_db.py --check` reported the real local database is missing `004_case_insensitive_usernames`; this was a read-only check and no live migration was applied.

## Spec Adherence

| Requirement | Status | Implementation | Test / verification |
|-------------|--------|----------------|---------------------|
| FR-1.1 | Done | `auth.py:validate_signup_configuration` | `.env` load and process-precedence tests. |
| FR-1.2 | Done | `auth.py:validate_signup_configuration`, `main.py` startup | Direct validation plus isolated missing/blank/padded/placeholder startup tests. |
| FR-1.3 | Done | `auth.py:signup_code_matches`, `auth_routes.py:signup` | Exact Unicode-safe comparison and code-before-query tests; HTTP smoke bad-code `403`. |
| FR-1.4 | Done | `.env.example`, `README.md` | Test requires both documents to contain only the rejected placeholder. |
| AR-1.1 | Done | `auth.py`, `auth_routes.py`, `main.py` | Startup/config tests; no new settings layer or dependency. |
| AR-1.2 | Done | `auth.py:signup_code_matches` | Exact comparison tests and hashing-without-signup-config subprocess test. |
| AR-1.3 | Done | `auth_routes.py:sanitize_signup_validation_error`, sanitized route failures | Nested credential and malformed-body no-echo tests across response/stdout/stderr. |
| FR-2.1 | Done | `schemas.py:SignupRequest`, signup-only 422 handler | Missing, non-string, and malformed JSON tests; no rows created. |
| FR-2.2 | Done | `auth_routes.py:SIGNUP_USERNAME_PATTERN`, `auth_routes.py:signup` | Boundary, allowed-character, trimming, and rejected-character tests. |
| FR-2.3 | Done | `auth_routes.py` password composition checks | Short/no-letter/no-digit/non-ASCII-only tests plus whitespace-preservation login test. |
| FR-2.4 | Done | migration 004, `models.py` indexes, signup duplicate lookup | Sequential case variants, mixed-case login, real index enforcement, and concurrent API test. |
| FR-2.5 | Done | `auth.get_password_hash` reuse in `auth_routes.py:signup` | Stored hash differs from plaintext and verifies; failure rollback/no-echo tests. |
| FR-2.6 | Done | Signup inserts only `models.User` | BeerRunJPN, memberships, entries, and existing-user before/after test plus HTTP smoke. |
| AR-2.1 | Done | migration 004, `migrations/runner.py`, `models.py` | Unique/`NOCASE` PRAGMA assertions and duplicate insert rejection. |
| AR-2.2 | Done | migration collision preflight | Collision fixture refuses unrecorded migration without revealing or rewriting rows. |
| AR-2.3 | Done | case-insensitive precheck, `auth_routes.py:_is_username_unique_violation`, rollback paths | Concurrent API test, realistic username-unique `409`, and unrelated-integrity sanitized `500`. |
| AR-2.4 | Done | Index-only migration with no row mutation | Unusual legacy-name and BeerRunJPN preservation tests. |
| FR-3.1 | Done | `auth_routes.py:signup` reuses `schemas.Token` and `auth.create_access_token` | Exact response/claim tests and HTTP smoke token type. |
| FR-3.2 | Done | Existing `/api/me` bearer dependency | Signup token immediately authenticates and mixed-case login resolves the same ID. |
| FR-3.3 | Done | Flush/token/commit ordering and rollback handlers | Hash, lookup, token, unique, unrelated-integrity, and concurrent failure tests return no partial token/account. |
| AR-3.1 | Done | Direct reuse of `auth_routes.py`, `schemas.py`, and `auth.py` primitives | Code review and full regression suite; one focused FastAPI router, no new auth service abstraction. |
| AR-3.2 | Done | `db.add` -> `db.flush` -> token preparation -> `db.commit` -> response | Rollback and no-partial-row tests for every injected failure stage. |

## Living Documentation

`specs/docs/` does not exist, so no living domain documents were available for incremental update. The durable spec reference remains in `AGENTS.md`.

## Deviations From Spec

- `ADR-001` records the user-requested placement-only refactor from `main.py` to `auth_routes.py`; no API or persistence behavior changed.
- The implementation remains on the user-selected `005-add-signup-api` branch rather than the skill's default `spec/005-add-signup-api` naming convention, by explicit user direction.

## Runtime Data Status

No migration was applied to `boozerun.db`, `boozerun_backup.db`, `test.db`, `users.json`, uploads, or any other protected runtime state. The local readiness check reports migration 004 is pending and must be applied separately by the operator after configuring a private `SIGNUP_CODE` and taking the normal runtime backup.
