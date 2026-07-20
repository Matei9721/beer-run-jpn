# Spec 005: Add Signup API

**Feature Branch**: `005-add-signup-api`

**Created**: 2026-07-19

**Status**: Draft

## Overview

BoozeRunJpn currently requires an operator script to create an account. This feature adds a public, signup-code-gated JSON API that validates new credentials, creates one case-insensitive user identity with an Argon2 password hash, and returns the same version-2 bearer-token shape as login so the new account is immediately authenticated.

Signup creates only the account. It does not add the user to BeerRunJPN, change any existing membership, or introduce browser UI; later Release 1 tasks own beer-run creation, invite acceptance, and frontend signup.

## Goals

- Allow a caller with the configured signup code to create an account through `POST /api/signup`.
- Enforce conservative username and password rules with readable API failures.
- Guarantee that ASCII case variants such as `Alice` and `alice` cannot become different user IDs, including under concurrent requests.
- Store only the existing Argon2 password hash and return the existing version-2 access-token contract after a successful commit.
- Keep the signup code private and fail startup when the deployment has not configured it safely.
- Preserve BeerRunJPN, all existing memberships, and every existing runtime row.

## Confirmed Decisions

- A username is trimmed, must be 3-32 characters, and may contain only ASCII letters, ASCII digits, `_`, and `-`.
- The first registered username casing is preserved for display. All ASCII case variants identify that same account; another signup using a case variant is rejected rather than creating a second ID.
- A password must contain at least eight characters, at least one ASCII letter of either case, and at least one ASCII digit.
- `SIGNUP_CODE` is required from the process environment or private root `.env`; missing or unsafe configuration prevents startup.
- Successful signup returns `201 Created`; duplicates return `409 Conflict`; an incorrect submitted code returns `403 Forbidden`; missing or malformed request fields use FastAPI's `422 Unprocessable Entity` contract.
- Feature validation uses a real API flow: JSON signup, bearer-authenticated `/api/me`, and duplicate/bad-code attempts.
- Signup creates no `BeerRunMember` row and must not modify BeerRunJPN or any of its existing users or memberships.
- The case-insensitive identity guarantee is enforced by an ordered SQLite migration, not only by an application-level pre-check.

---

## Feature 1: Private Signup-Code Configuration

**Who & why:** The local operator needs a lightweight way to decide who may create an account without deploying public registration or manually running a user-management script. The shared code must remain outside source control, and an unconfigured deployment must not accidentally expose signup.

### Functional Requirements

#### FR-1.1: Load The Signup Code From Private Configuration

The application MUST load `SIGNUP_CODE` from the process environment or the repository-root `.env` file. An already defined process-environment value MUST take precedence over `.env`, following the existing `SECRET_KEY` configuration behavior.

**Verify:** Configure different non-placeholder values in the process environment and `.env`, start the app, and confirm only the process-environment value authorizes signup.

#### FR-1.2: Fail Startup For Unsafe Signup Configuration

Application startup MUST fail before serving routes when `SIGNUP_CODE` is missing, blank, has leading or trailing whitespace, or equals the documented `.env.example` placeholder. The failure MUST name `SIGNUP_CODE`, explain that it belongs in `.env` or the process environment, and MUST NOT echo the configured value.

**Verify:** Start isolated app processes with each rejected configuration and confirm every process exits nonzero with actionable output that contains no submitted or configured signup code.

#### FR-1.3: Compare The Submitted Code Safely

`POST /api/signup` MUST require `signup_code` in its JSON body and compare it exactly and case-sensitively with the configured value. A present but incorrect or blank code MUST return `403 Forbidden`; the server MUST perform this comparison before looking up the requested username so an unauthorized caller cannot use signup to enumerate existing accounts.

**Verify:** Submit correct, incorrect, differently-cased, and blank codes for both existing and unused usernames; only the exact code succeeds, and every incorrect-code case returns the same `403` category without revealing whether the username exists.

#### FR-1.4: Document Safe Operator Setup

The tracked `.env.example` and README MUST document `SIGNUP_CODE` with a rejected placeholder, process-environment precedence, startup refusal, and instructions to keep the real value private. Documentation MUST NOT contain a working signup code.

**Verify:** Follow the README from a checkout with no private `.env`, configure both required auth values, and confirm the app starts while `git status --short` does not expose the private file or values.

### Architectural Requirements

#### AR-1.1: Extend The Existing Configuration Boundary

Keep signup-code loading and validation beside `validate_auth_configuration()` in `auth.py`, and invoke the new explicit validation path from the existing startup-readiness sequence in `main.py`. Continue using `python-dotenv` with `override=False`; do not introduce a settings framework or new dependency.

#### AR-1.2: Use Constant-Time Equality

Use Python's standard-library `secrets.compare_digest()` for the exact signup-code comparison. Password-hashing helpers imported by `scripts/manage_users.py` and `scripts/setup_db.py` MUST remain usable without requiring signup or JWT configuration merely because `auth.py` was imported.

#### AR-1.3: Keep Secrets Out Of Outputs

The configured code, submitted code, password, password hash, and access token MUST NOT be printed, logged, included in validation details, or returned except that the access token is returned in the successful `schemas.Token` response.

### Feature Validation

Set valid `SECRET_KEY` and `SIGNUP_CODE` values in a private test environment, then start the app and exercise signup with the exact code. Restart once with `SIGNUP_CODE` missing and once with the tracked placeholder to confirm safe startup refusal, then start with a valid process-environment code that differs from `.env` and confirm precedence. Inspect output only for variable names and corrective guidance, never secret values.

---

## Feature 2: Validated Case-Insensitive Account Creation

**Who & why:** A new participant needs a predictable account name and password policy, while existing participants need confidence that a differently-cased spelling cannot impersonate or split their identity. Operators need the database itself to preserve that invariant during simultaneous requests.

### Functional Requirements

#### FR-2.1: Accept A JSON Signup Request

`POST /api/signup` MUST accept a JSON object with the required string fields `username`, `password`, and `signup_code`. Missing fields, non-string fields, or structurally malformed JSON MUST use FastAPI's normal `422 Unprocessable Entity` validation response and MUST create no user.

**Verify:** Omit each field in turn, submit non-string values, and submit malformed JSON; every request returns `422` and the users table remains unchanged.

#### FR-2.2: Normalize And Validate Usernames

The server MUST remove leading and trailing whitespace from `username`, then require a length of 3 through 32 characters inclusive and a complete match for `[A-Za-z0-9_-]+`. It MUST store the trimmed spelling with its submitted letter casing unchanged; internal whitespace, non-ASCII letters, punctuation other than `_` and `-`, control characters, and values outside the length bounds MUST be rejected with `422` and MUST create no user.

**Verify:** Confirm the 3- and 32-character boundaries succeed, values outside them fail, every allowed character class succeeds, representative disallowed characters fail, and `"  Alice_1  "` is stored and returned as `"Alice_1"`.

#### FR-2.3: Validate Password Composition Without Mutation

The server MUST require a password of at least eight characters containing at least one ASCII letter from `[A-Za-z]` and at least one ASCII digit from `[0-9]`. It MUST validate the password exactly as submitted and MUST NOT trim, normalize, case-fold, or otherwise mutate it.

**Verify:** Confirm an eight-character letter-and-digit password succeeds; shorter, letter-only, digit-only, and non-ASCII-letter-only values fail with `422`; and a valid password containing leading or trailing spaces authenticates only when those spaces are supplied again.

#### FR-2.4: Treat ASCII Case Variants As One Identity

Username lookup and persistence MUST be case-insensitive for the allowed ASCII username alphabet. Once `Alice` exists, signup attempts for `Alice`, `alice`, `ALICE`, or any other ASCII case variant MUST return `409 Conflict`, MUST NOT return the existing account or a token for it, and MUST NOT create another user ID. Existing case-insensitive `/token` login MUST continue resolving every case variant to the original stored account and ID.

**Verify:** Create `Alice`, attempt at least three case-variant signups and confirm each returns `409` with one total matching user row, then log in as `aLiCe` and confirm `/api/me` returns the original ID and stored spelling `Alice`.

#### FR-2.5: Preserve Password Confidentiality

Every account created by signup MUST store a non-null hash produced by the existing Argon2-backed `auth.get_password_hash()` helper. Plaintext passwords MUST never be persisted or emitted, and validation or persistence failure MUST leave no partial user row.

**Verify:** Inspect the isolated test database after successful signup, confirm the stored value differs from the submitted password and passes `auth.verify_password()`, then confirm failed signup paths add no row and emit no password or hash.

#### FR-2.6: Leave Beer-Run Memberships Untouched

Signup MUST create only the `User` row. It MUST NOT create a `BeerRunMember`, add the new user to BeerRunJPN, change any existing membership or role, create a beer-run, or alter any entry. The signed-up account therefore begins with zero beer-run memberships until a later create-run or invite-acceptance flow adds one.

**Verify:** Record BeerRunJPN, membership, and entry rows before signup; sign up a user; then confirm only one new user row exists, the new user has zero memberships, and every pre-existing row and count is unchanged.

### Architectural Requirements

#### AR-2.1: Enforce Case-Insensitive Uniqueness In SQLite

Add the next ordered migration to create a unique index on `users.username COLLATE NOCASE`, and register it in `migrations/runner.py`. SQLite's built-in `NOCASE` folds the 26 ASCII uppercase characters, which exactly matches this feature's ASCII-only username case semantics. Update `models.User` metadata to declare the same `NOCASE` collation and unique identity rule so ORM metadata and migrated databases describe the same invariant.

#### AR-2.2: Refuse Ambiguous Legacy Data Without Rewriting It

Before creating the case-insensitive unique index, the migration MUST detect existing non-null usernames that collide under ASCII case-insensitive comparison. If collisions exist, it MUST fail with actionable, non-credential-bearing guidance and MUST NOT create the index, record the migration, merge accounts, change IDs, rename users, rewrite entries, or change memberships. The operator must resolve each collision deliberately before retrying.

#### AR-2.3: Defend Both Normal And Concurrent Duplicate Paths

The route MUST perform a case-insensitive pre-insert lookup to provide a readable `409` during normal use. It MUST also catch the database uniqueness failure produced by a racing insert, roll back the session, and return the same `409` category. Unexpected persistence failures MUST be rolled back and returned as a generic server error without raw SQL, usernames, hashes, or database details.

#### AR-2.4: Preserve Legacy Accounts Outside The New Input Policy

The new length and character rules apply to accounts created through `/api/signup`; the migration MUST NOT rename, delete, or invalidate an existing username merely because that legacy value would not pass the new signup validator. Existing accounts must retain their IDs, stored spellings, hashes, entries, memberships, and case-insensitive login behavior.

### Feature Validation

Apply the migration to isolated fresh and representative upgraded databases. Confirm existing IDs and BeerRunJPN state remain unchanged, and separately confirm a database containing `Alice` and `alice` refuses migration without recording it. With a valid migrated test database, send sequential and deliberately overlapping case-variant signup requests and confirm one user ID at most is created. Exercise username/password boundary matrices and inspect the stored hash and membership counts.

---

## Feature 3: Immediate Authenticated Signup Response

**Who & why:** A participant who successfully creates an account should be able to continue directly into authenticated app behavior without separately entering the same credentials again. The response must stay aligned with login so the later frontend task can reuse existing token handling.

### Functional Requirements

#### FR-3.1: Return The Existing Token Contract

After the user row has been created successfully, `POST /api/signup` MUST return `201 Created` with exactly the `schemas.Token` response shape: `access_token` and `token_type: "bearer"`. The token MUST use the new user's canonical decimal ID string as `sub`, the existing integer `token_version: 2`, and the existing expiration policy; it MUST NOT carry the username, password, password hash, or signup code.

**Verify:** Decode a signup token in the controlled test environment and confirm its fields match a `/token` response and its subject is the committed user's ID, with none of the prohibited data present.

#### FR-3.2: Authenticate The New Account Through Existing Boundaries

The access token returned by signup MUST immediately authenticate the existing `GET /api/me` endpoint. `/api/me` MUST return the new user's ID and preserved stored username casing without any signup-specific compatibility path.

**Verify:** Send the returned token as `Authorization: Bearer <token>` to `/api/me` and confirm `200 OK` with the committed ID and trimmed, casing-preserved username.

#### FR-3.3: Return No Token For Failed Or Uncommitted Accounts

The API MUST NOT return an access token unless the user insert commits successfully. A duplicate, validation error, incorrect code, hashing error, uniqueness race, or persistence failure MUST return its defined error category with no token and no partially committed account.

**Verify:** Force each failure category, including a commit-time uniqueness conflict, and confirm the response has no `access_token`, the transaction is rolled back, and no failed account can authenticate.

### Architectural Requirements

#### AR-3.1: Reuse Existing Auth Primitives

Keep the route in `main.py`, define the JSON request in `schemas.py`, reuse `schemas.Token`, hash through `auth.get_password_hash()`, and issue the token through `auth.create_access_token({"sub": str(user.id)})`. Do not create a second token format, password hasher, user repository, service layer, or auth framework.

#### AR-3.2: Preserve The Transaction Boundary

Use the existing direct SQLAlchemy `Session` pattern: add the user, obtain its database ID within the transaction, prepare the existing token, commit successfully, and only then return the response. Every exception after the insert begins MUST roll back before an HTTP error is returned.

### Feature Validation

With a migrated isolated database and valid private configuration, call `POST /api/signup` with a trimmed valid username, valid password, and exact signup code. Confirm `201`, the exact login token shape, and successful `/api/me`; then log in through `/token` with different username casing and confirm it resolves the same ID. Repeat with duplicate, invalid-password, bad-code, and forced persistence failures and confirm no token or partial account is produced.

## Data Requirements

- Request JSON contains three required strings: `username`, `password`, and `signup_code`.
- A successful signup adds exactly one `users` row with a generated existing integer primary key, the trimmed casing-preserved username, and a non-null Argon2 password hash.
- ASCII case-equivalent usernames share one identity namespace enforced by the case-insensitive unique index; duplicate signup does not reuse or disclose the existing account.
- Existing user rows, IDs, password hashes, entries, BeerRunJPN data, and beer-run memberships remain byte-for-byte and relationship-for-relationship unchanged by the migration and signup of another account.
- A newly signed-up user has zero `beer_run_members` rows.
- The successful response contains `access_token` and `token_type`; no new response model is introduced.
- The private `.env` may contain the real `SIGNUP_CODE`; `.env.example` contains only a rejected placeholder.

## Integration Points

- `auth.py`: signup-code loading/validation, safe equality comparison boundary, existing Argon2 hashing, and version-2 ID token issuance.
- `main.py`: startup readiness and the new public `POST /api/signup` JSON route beside `/token` and `/api/me`.
- `schemas.py`: required `SignupRequest`; existing `Token` remains the response model.
- `models.py`: `User.username` model metadata aligned with SQLite `NOCASE` uniqueness.
- `migrations/versions/`: next ordered migration adding the case-insensitive unique index after collision preflight.
- `migrations/runner.py` and `scripts/migrate_db.py`: register, apply, check, and safely report the new required migration without touching runtime data unless explicitly invoked.
- `tests/conftest.py`: deterministic `SIGNUP_CODE` before importing `main`, isolated migrated database, and existing client fixture.
- `tests/test_auth.py`: signup request, token, configuration, hashing, error, and `/api/me` coverage.
- `tests/test_migrations.py`: fresh/upgraded migration, collision refusal, idempotency, and data-preservation coverage.
- `.env.example` and `README.md`: private signup-code setup and startup behavior.
- `scripts/manage_users.py` and `scripts/setup_db.py`: existing password hashing remains usable; their account-management behavior is not expanded by this feature.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 004: Harden Auth Tokens | **Depends on** - signup reuses its private `.env` boundary, stable user-ID subject, version-2 token, and unchanged `schemas.Token` contract | FR-1.1 through FR-1.4, FR-3.1 through FR-3.3, AR-1.1 through AR-1.3, AR-3.1 |
| Spec 001: Add Database Migrations | **Extends** - adds the next ordered, readiness-enforced schema migration using the established runner and isolated verification path | AR-2.1, AR-2.2, Integration Points, Rollout And Rollback |
| Spec 002: Add Beer-Run Schema | **References** - preserves the rule that a user may have zero memberships and leaves membership creation to later run/invite features | FR-2.6, Data Requirements |
| Spec 003: Backfill Existing Trip | **References** - preserves every backfilled BeerRunJPN user, role, membership, entry, and default-trip relationship | FR-2.6, AR-2.2, AR-2.4, Data Requirements |

## Constraints

- Keep the existing FastAPI, SQLAlchemy, SQLite, Pydantic, Argon2, JWT, and direct-module architecture with no frontend build step or new application framework.
- Do not add a dependency; the required configuration, hashing, constant-time comparison, ORM, and database capabilities already exist.
- Never apply the migration to, delete, reset, overwrite, or commit `boozerun.db`, `boozerun_backup.db`, `test.db`, `users.json`, `static/uploads/`, or other protected runtime state while implementing or validating this feature.
- Keep `/token`, `/api/me`, existing public APIs, the `access_token` localStorage key, version-2 JWT identity semantics, token expiry, and bearer transport unchanged.
- Keep the first stored username spelling for display while treating ASCII letter casing as irrelevant to account identity.
- Validate signup on isolated databases; use `scripts/migrate_db.py --check` for read-only readiness unless the user separately authorizes a runtime migration.
- Auth, schema, and migration changes require focused tests plus `uv --cache-dir .uv-cache run pytest`.
- This API-only feature requires no browser asset, cache-busting, layout, geolocation, upload, or Wrapped change.

## Failure Modes And Recovery

- Missing or unsafe `SIGNUP_CODE`: startup stops with safe corrective guidance; the operator configures a private valid value and restarts.
- Incorrect submitted code: API returns `403` before username lookup; no row, hash, or token is created.
- Malformed username or password: API returns `422`; no persistence begins.
- Existing case-equivalent username: the pre-check or database constraint returns `409`; the original account and ID remain unchanged and undisclosed.
- Concurrent case-variant signups: the case-insensitive unique index permits at most one commit; every losing transaction rolls back and returns `409` without a token.
- Legacy database already contains case-colliding usernames: migration aborts without recording or rewriting; the operator resolves identities deliberately, then retries the normal migration command.
- Unexpected hashing, token, or persistence error: the transaction rolls back and the API returns a generic server failure without raw database or credential details.

## Rollout And Rollback

1. Configure a private valid `SIGNUP_CODE` alongside the valid `SECRET_KEY`, confirm `.env` remains ignored, and keep the tracked placeholder unusable.
2. Run `uv --cache-dir .uv-cache run python scripts/migrate_db.py --check` against the intended database to identify the new required migration without changing it.
3. Back up runtime data through the operator's normal process before any separately authorized production migration; implementation and automated tests MUST use isolated databases only.
4. Apply the ordered migration through `scripts/migrate_db.py`. If case-colliding legacy accounts are reported, stop, resolve them deliberately without changing ownership relationships, and retry.
5. Deploy route, schema, auth configuration, model metadata, migration registration, docs, and tests together; startup refuses traffic until both required configuration and migration readiness checks pass.
6. Validate signup, `/api/me`, mixed-case login, duplicate rejection, incorrect-code rejection, zero membership creation, and unchanged BeerRunJPN counts.
7. Rollback may remove the API/config requirement and drop only the new case-insensitive index through a reviewed database rollback procedure. It MUST NOT merge, rename, delete, or recreate users or restore a public/hard-coded signup code.

## Out Of Scope

- Signup UI, confirm-password UI, client-side validation, or changes to login/logout presentation; Release 1 Task 10 owns frontend signup.
- Automatically joining BeerRunJPN or any other run, changing existing memberships, selecting a run, creating a run, invite creation, or invite acceptance.
- Email addresses, email verification, password reset, account recovery, profiles, roles, administrator approval, CAPTCHA, or identity-provider login.
- Returning an existing account or token when a duplicate username is submitted.
- Unicode usernames, Unicode case folding, spaces within usernames, or punctuation beyond `_` and `-`.
- Changing the password-hashing algorithm, JWT algorithm, token version, token lifetime, bearer transport, or existing login response.
- Rate limiting, signup-code rotation endpoints, multiple signup codes, per-invite account codes, or public signup without a shared code.
- Automatically rewriting or merging legacy case-colliding users during migration.

## Feature Validation Strategy

1. In an isolated environment, verify process-environment/`.env` precedence and safe startup refusal for missing, blank, padded, or placeholder `SIGNUP_CODE` values.
2. Apply the migration to fresh and upgraded database fixtures, assert the new `NOCASE` unique index and migration history, and confirm all existing IDs, hashes, BeerRunJPN rows, memberships, entries, and totals are unchanged.
3. Apply it to a fixture containing `Alice` and `alice`; confirm it refuses without recording the migration or changing either account.
4. Use `curl` to send valid JSON signup data and confirm `201`, exactly `access_token` plus `token_type: bearer`, valid version-2 ID claims, and authenticated `/api/me` output.
5. Log in through `/token` using a different case and confirm `/api/me` returns the same ID and original stored casing.
6. Retry exact-case, mixed-case, and overlapping concurrent signup requests; confirm one account at most and consistent `409` failures with no returned token.
7. Exercise username boundaries/characters, password composition, missing fields, incorrect code, and forced persistence failure; confirm defined statuses, rollback, and no credential/secret output.
8. Compare BeerRunJPN, membership, and entry state before and after signup and confirm it is identical while the new account has zero memberships.
9. Run `uv --cache-dir .uv-cache run pytest` after focused auth and migration coverage passes.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Goals, Features 1-3, Constraints, Failure Modes, and Out Of Scope define the complete API-only boundary and status contracts.
- [x] **Feature validation strategy** - Every feature contains a confirmed API/process/database exercise, consolidated in Feature Validation Strategy.
- [x] **Existing patterns** - AR-1.1, AR-3.1, and Integration Points reference current config, login, hashing, token, session, migration, and test patterns.
- [x] **Dependencies** - AR-1.2 and Constraints confirm standard-library and existing dependency capabilities are sufficient; no dependency is added.
- [x] **Architecture & interfaces** - FR-2.1, FR-3.1, all ARs, Data Requirements, and Integration Points define request, response, persistence, configuration, migration, and module boundaries.
- [x] **Error handling & failure modes** - FR-1.2, FR-1.3, FR-2.1 through FR-2.5, FR-3.3, AR-2.2, AR-2.3, and Failure Modes And Recovery cover startup, validation, duplicate, race, migration, hashing, and persistence failures.
- [x] **Security review** - The signup gate is private and constant-time; username enumeration happens only after successful code validation; passwords are Argon2-hashed; secrets and raw errors are excluded; brute-force/rate-limiting expansion is explicitly out of scope.
- [x] **Performance impact** - Signup performs one code comparison, one indexed case-insensitive lookup, one Argon2 hash, one insert, and one token issuance per successful request; no polling or steady-state read-path work is added, and the unique index supports duplicate checks.
- [x] **Rollout & migration** - AR-2.1, AR-2.2, Constraints, and Rollout And Rollback define readiness, collision refusal, protected-state handling, deployment ordering, and safe rollback boundaries.
- [x] **Confirmed decisions & risks** - Confirmed Decisions records every user choice; codebase evidence resolves token/config/session patterns, migration need, and zero-membership behavior; remaining expansion items are explicitly out of scope.
