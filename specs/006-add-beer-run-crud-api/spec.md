# Spec 006: Add Beer-Run CRUD API

**Feature Branch**: `006-add-beer-run-crud-api`

**Created**: 2026-07-26

**Status**: Draft

## Overview

BoozeRunJpn currently operates on a single hard-coded default beer-run (`BeerRunJPN`) with no API for users to create, list, inspect, update, or delete their own runs. This feature adds a full JSON CRUD API over beer-runs: authenticated users can create private runs with themselves as owner, list runs they belong to alongside public runs anyone can discover, view run details with membership metadata, and owners can rename, change visibility, or delete their runs.

The feature applies case-insensitive name uniqueness so that `Tokyo Run` and `tokyo run` cannot become separate runs, and enforces a consistent name policy. A logged-out visitor can browse public runs — including the existing `BeerRunJPN` — but cannot create, update, or delete any run.

## Goals

- Let authenticated users create a beer-run with themselves as the initial owner member.
- Return every run visible to the caller: private runs the caller is a member of, plus all public runs regardless of membership.
- Include `member_count` and `current_user_role` in list and detail responses so the frontend can render permissions without extra requests.
- Let the owner update a run's name and public/private flag, and delete the run entirely (cascading to memberships and entries).
- Enforce 3–64 character ASCII name validation with case-insensitive uniqueness at the database level.
- Keep new runs private by default and preserve the existing `BeerRunJPN` as a public run visible to everyone.
- Reject unauthenticated write access and non-owner mutations with clear HTTP status codes.

## Confirmed Decisions

- **Visibility model**: Public runs are visible to all callers (authenticated or not). Private runs are visible only to members. The list endpoint returns every visible run; the detail endpoint returns 404 for a private run the caller is not a member of.
- **Name rules**: A beer-run name is trimmed, must be 3–64 characters, and may contain only ASCII letters, ASCII digits, spaces, `_`, and `-`. Uniqueness is case-insensitive and enforced by a SQLite `NOCASE` unique index.
- **Create**: `POST /api/beer-runs` accepts `name` (and optional `is_public`, default `false`). The creator is automatically added as an `owner` member. Returns `201 Created` with the full run shape.
- **Update**: `PATCH /api/beer-runs/{beer_run_id}` allows the owner to change `name` and/or `is_public`. Name changes are validated identically to creation. Returns the updated run.
- **Delete**: `DELETE /api/beer-runs/{beer_run_id}` is owner-only. It cascades: all memberships for the run and all entries assigned to the run are deleted.
- **Response shape**: `id`, `name`, `is_public`, `created_at`, `member_count`, `current_user_role` (the caller's role string, or `null` for a logged-out caller viewing a public run).
- **Case-insensitive uniqueness**: A new ordered SQLite migration adds a `COLLATE NOCASE` unique index on `beer_runs.name`, matching the username pattern from Spec 005.
- The default trip `BeerRunJPN` remains public, visible to everyone, and unchanged by this feature beyond the migration that adds the NOCASE index.

---

## Feature 1: Beer-Run Name Validation And Case-Insensitive Uniqueness

**Who & why:** Any participant creating or renaming a beer-run needs predictable, readable name rules. Existing members need confidence that a differently-cased spelling cannot create a confusingly similar run. Operators need the database to enforce this invariant during concurrent requests.

### Functional Requirements

#### FR-1.1: Validate Name Format On Create And Update

The server MUST trim leading and trailing whitespace from the submitted name, then require a length of 3 through 64 characters inclusive and a complete match for `[A-Za-z0-9 _-]+`. Empty-after-trim, too-short, too-long, and disallowed-character values MUST be rejected with `422 Unprocessable Entity` and MUST create or change no database row.

**Verify:** Submit names at the 3- and 64-character boundaries (both succeed), a 2-character name (fails 422), a 65-character name (fails 422), names containing `!`, `@`, `#`, non-ASCII characters (each fails 422), and `"  Tokyo Run  "` (stored and returned as `"Tokyo Run"`).

#### FR-1.2: Reject Duplicate Names Case-Insensitively

Name lookup and persistence MUST be case-insensitive for the allowed ASCII name alphabet. Once `Tokyo Run` exists, attempts to create or rename another run to `Tokyo Run`, `tokyo run`, `TOKYO RUN`, or any other ASCII case variant MUST return `409 Conflict`. The server MUST perform a case-insensitive pre-check before insert/update and MUST also catch the database unique-constraint failure from a racing request, rolling back and returning the same `409`.

**Verify:** Create `Tokyo Run`, then attempt to create another run named `tokyo run` — confirm `409`. Rename an existing run to `tokyo run` — confirm `409`. Verify only one row exists for any case variant.

#### FR-1.3: Enforce Case-Insensitive Uniqueness In SQLite

Add the next ordered migration to enforce case-insensitive uniqueness on `beer_runs.name` via a `COLLATE NOCASE` unique index. Because SQLite cannot alter a column's uniqueness collation in-place, the migration MUST recreate the `beer_runs` table safely:

1. Check for case-insensitive duplicate names among existing rows. If any are found, fail with actionable guidance without recording the migration or changing data.
2. Create a new `beer_runs` table with the `NOCASE` unique index and the same column definitions.
3. Copy all existing rows from the old table to the new table, preserving every column value exactly.
4. Drop the old table and rename the new table.
5. Recreate any dependent indexes (the existing `ix_beer_runs_is_public` index on `is_public`).

The migration MUST complete atomically (all steps within one transaction) so a failure at any step leaves the database unchanged. Register it in `migrations/runner.py`.

**Verify:** Apply the migration to a fresh database and confirm the NOCASE unique index exists. Apply it to a database containing `BeerRunJPN` and confirm the row is preserved with identical `id`, `name`, `is_public`, and `created_at` values. Inject a second beer-run with a case-colliding name and confirm migration refuses without recording or changing data. Confirm the `ix_beer_runs_is_public` index is still present after migration.

#### FR-1.4: Update Model Metadata For Collation

Update `models.BeerRun.name` to declare `collation="NOCASE"` and remove the column-level `unique=True` in favor of a `__table_args__` unique index reflecting the migration's NOCASE collation, so ORM metadata and migrated databases describe the same invariant.

**Verify:** Inspect the model definition; confirm the column has `collation="NOCASE"` and the `__table_args__` includes a NOCASE unique index matching the migration.

### Architectural Requirements

#### AR-1.1: Follow The Existing Migration Pattern

Keep the migration in `migrations/versions/` as the next numbered file, register it in `migrations/runner.py`, and support `scripts/migrate_db.py --check`. Follow the pattern established by Spec 001 and extended by Spec 005 for the username NOCASE index.

#### AR-1.2: Match The Username Uniqueness Pattern

Use the same SQLite `COLLATE NOCASE` approach as the username case-insensitive index from Spec 005 (FR-2.1, AR-2.1). Collision detection must use the same read-only detection pattern: query for case-insensitive duplicates and fail before applying any schema change.

### Feature Validation

Apply the migration to an isolated fresh database and confirm the NOCASE unique index exists alongside the existing BeerRunJPN row. Apply it to a database containing `Tokyo Run` and `tokyo run` and confirm the migration refuses without recording. Apply it to the project's test database fixture and confirm `uv --cache-dir .uv-cache run pytest` passes all existing tests.

---

## Feature 2: Create Beer-Run

**Who & why:** A trip participant who wants to start their own run needs a simple JSON endpoint. Successfully creating a run must immediately make them the owner so they can manage the run without a separate join step.

### Functional Requirements

#### FR-2.1: Accept A JSON Create Request

`POST /api/beer-runs` MUST accept a JSON object with the required string field `name` and an optional boolean field `is_public` (default `false`). The request MUST include a valid `Authorization: Bearer <token>` header. Missing authentication MUST return `401 Unauthorized`. Missing `name` or a non-string `name` MUST return `422`.

**Verify:** Send requests without a token (401), without a name field (422), with a non-string name (422), and with `is_public` omitted (defaults to `false`).

#### FR-2.2: Create The Beer-Run And Owner Membership Atomically

After successful name validation, the server MUST insert a `beer_runs` row and a corresponding `beer_run_members` row with `role = 'owner'` for the authenticated user within one transaction. Both rows commit together or neither commits. The response MUST be `201 Created` with the full beer-run response shape: `id`, `name`, `is_public`, `created_at`, `member_count`, and `current_user_role`.

**Verify:** Create a run and inspect the database — confirm one `beer_runs` row and one `beer_run_members` row with `role = 'owner'` for the caller. Confirm `member_count` is `1` and `current_user_role` is `"owner"` in the response.

#### FR-2.3: Default New Runs To Private

When `is_public` is omitted or explicitly `false`, the created run MUST have `is_public = false`. When `is_public` is `true`, the run MUST be created as public and be visible to any caller (including logged-out visitors).

**Verify:** Create a run without `is_public` — confirm `is_public` is `false`. Create a run with `is_public: true` — confirm it appears in a logged-out list request.

#### FR-2.4: Return Standard Error Responses For Failures

Name validation failures MUST return `422`. Duplicate name (including case variants) MUST return `409`. Unexpected persistence failures MUST roll back the transaction and return `500` without exposing raw database errors, table names, or SQL.

**Verify:** Force a duplicate name, a too-short name, and a simulated persistence error — confirm 409, 422, and 500 respectively, with no raw SQL in any response body.

### Architectural Requirements

#### AR-2.1: Define Request And Response Schemas In `schemas.py`

Add `BeerRunCreateRequest` and `BeerRunResponse` Pydantic models to `schemas.py`. `BeerRunResponse` must include `id: int`, `name: str`, `is_public: bool`, `created_at: datetime`, `member_count: int`, and `current_user_role: Optional[str]` (the field name that communicates "no authenticated user" for logged-out public-run viewers). Use `model_config = ConfigDict(from_attributes=True)` following the existing `schemas.Entry` pattern.

#### AR-2.2: Add A Dedicated Beer-Run Router Module

Add a new `beer_run_routes.py` router module following the pattern established by `auth_routes.py` (FastAPI `APIRouter`, registered in `main.py` via `app.include_router`). The router owns all five beer-run CRUD endpoints, the optional-authentication dependency, and the name-validation helpers. Reuse the existing `get_db` and `auth.get_current_user` dependency patterns. Do not introduce a service layer or additional abstraction — the router is a direct-module grouping, not an architectural layer.

#### AR-2.3: Reuse The Transaction Pattern

Use the existing direct SQLAlchemy `Session` pattern: validate, insert beer-run, flush to obtain the ID, insert membership, commit, and return the response. Any exception after insert begins MUST roll back before returning an HTTP error.

### Feature Validation

With an authenticated test client, send `POST /api/beer-runs` with `{"name": "Tokyo Run"}`. Confirm `201`, `member_count: 1`, `current_user_role: "owner"`, `is_public: false`. Verify the database has one new `beer_runs` row and one new `beer_run_members` row for the caller with `role = 'owner'`. Repeat with `is_public: true` and confirm the run appears in a logged-out `GET /api/beer-runs` response.

---

## Feature 3: List And View Beer-Runs

**Who & why:** Participants need to discover runs they can join and see the runs they already belong to. Logged-out visitors browsing the app should still see public runs (including `BeerRunJPN`). The response must carry enough metadata — member count and the caller's role — so the frontend can show permissions without extra API calls.

### Functional Requirements

#### FR-3.1: List Visible Runs

`GET /api/beer-runs` MUST return every beer-run visible to the caller:
- **Authenticated callers**: all public runs PLUS all private runs where the caller has a membership.
- **Logged-out callers**: all public runs only.

The response MUST be a JSON array of beer-run objects, each containing `id`, `name`, `is_public`, `created_at`, `member_count`, and `current_user_role`. For logged-out callers, `current_user_role` MUST be `null` for every returned run. An empty list is valid when no runs are visible.

**Verify:** Create two private runs (as user A), one public run (as user A), and add user B as a member of one private run. As user B: list shows user B's one private run + the one public run = 2 runs. As logged-out: list shows only the one public run. As user A: list shows all 3 runs.

#### FR-3.2: Get Run Detail

`GET /api/beer-runs/{beer_run_id}` MUST return a single beer-run object if visible to the caller, using the same visibility rules as FR-3.1. A private run where the caller (or logged-out visitor) is not a member MUST return `404 Not Found`. A non-existent `beer_run_id` MUST also return `404` — the server MUST NOT distinguish between "does not exist" and "exists but you cannot see it."

**Verify:** Fetch a public run as a logged-out visitor (200 with `current_user_role: null`). Fetch a private run as a non-member (404). Fetch a private run as a member (200 with `current_user_role` set). Fetch run ID 99999 (404).

#### FR-3.3: Include Member Count And Caller Role

Every beer-run object in list and detail responses MUST include:
- `member_count`: the total number of memberships for that run.
- `current_user_role`: the authenticated caller's role for that run (`"owner"`, `"member"`, or `null` if not a member or not authenticated).

**Verify:** Create a run (owner: user A). Add user B as a member. Fetch as user A — `member_count: 2`, `current_user_role: "owner"`. Fetch as user B — `member_count: 2`, `current_user_role: "member"`. Fetch as logged-out — `member_count: 2`, `current_user_role: null`.

#### FR-3.4: BeerRunJPN Is Always Public And Visible

The existing `BeerRunJPN` run MUST appear in list and detail responses for all callers (authenticated or not) because it is public. Its `current_user_role` MUST be `null` for logged-out visitors and reflect the actual membership role (or `null`) for authenticated callers.

**Verify:** Fetch `GET /api/beer-runs` as a logged-out visitor — `BeerRunJPN` is present. Fetch its detail — 200. Confirm a user who is not a BeerRunJPN member still sees it in their list.

### Architectural Requirements

#### AR-3.1: Use A Single Visibility Query Pattern

Build list and detail queries from the same visibility logic: public runs always pass the filter; private runs require a membership row for the caller's user ID. Use SQLAlchemy joins or subqueries rather than in-memory filtering, keeping the pattern efficient for the local SQLite scale.

#### AR-3.2: Optional Authentication Dependency

`GET /api/beer-runs` and `GET /api/beer-runs/{beer_run_id}` MUST NOT require authentication. Use a dependency that resolves the current user when a valid token is present and returns `None` when no token or an invalid token is provided, without raising `401`. Follow the pattern: extract the token, attempt decode, return user or `None`.

**Verify:** Send requests with no header, with an expired token, and with a valid token — all return 200 for visible runs. The resolved user identity is `None` for the first two cases.

### Feature Validation

1. Seed the test database with `BeerRunJPN` (public, pre-existing from migration), create two private runs as user A, one public run as user A, and add user B as a member to one private run.
2. As user A: list returns 4 runs (2 private owned + 1 public owned + BeerRunJPN). Each run has correct `member_count` and `current_user_role`.
3. As user B: list returns 3 runs (1 private membership + 2 public runs). Confirm `member_count` and `current_user_role` are correct for each.
4. As logged-out: list returns only the 2 public runs. `current_user_role` is `null` for both.
5. Detail: non-member fetching user A's private run gets 404. Member gets 200 with correct metadata.
6. Confirm 404 for non-existent run ID.

---

## Feature 4: Update Beer-Run

**Who & why:** A run owner needs to rename their run or change its visibility after creation. Only the owner should be able to make these changes — a regular member must not be able to modify the run.

### Functional Requirements

#### FR-4.1: Accept A JSON Update Request

`PATCH /api/beer-runs/{beer_run_id}` MUST accept a JSON object with optional string field `name` and optional boolean field `is_public`. At least one field must be present; an empty JSON object MUST return `422`. Authentication is required; missing or invalid token MUST return `401`.

**Verify:** Send PATCH with `{"name": "New Name"}` (200), with `{"is_public": true}` (200), with `{}` (422), and without a token (401).

#### FR-4.2: Restrict Updates To The Owner

Only a caller whose membership has `role = 'owner'` for the target beer-run MAY update it. A non-member or a caller with `role = 'member'` MUST receive `403 Forbidden`. A non-existent `beer_run_id` MUST return `404`.

**Verify:** Owner updates name — 200. Member of the same run attempts update — 403. Non-member attempts update — 403. Logged-out visitor attempts update — 401.

#### FR-4.3: Validate Name Changes Identically To Creation

When `name` is provided, it MUST be validated using the same rules as FR-1.1 (trim, 3–64 chars, allowed-character pattern) and FR-1.2 (case-insensitive uniqueness). Changing the name to its current value (same case or different case) MUST succeed without error. Changing it to a name used by a *different* run (including case variants) MUST return `409 Conflict`.

**Verify:** Rename to the same name with different case — 200, name unchanged (preserves original casing). Rename to a name used by another run — 409. Rename to an empty-after-trim name — 422.

#### FR-4.4: Return The Updated Run

A successful update MUST return `200 OK` with the full `BeerRunResponse` shape reflecting the changes. Member count and caller role MUST be accurate for the updated state.

**Verify:** Update `is_public` to `true` and confirm the response has `is_public: true`. Update `name` and confirm the response has the new trimmed name.

### Architectural Requirements

#### AR-4.1: Reuse The Same Validation And Response Patterns

Reuse the name validation logic from Feature 1 and the response building from Feature 2/3. Do not duplicate validation code. The same Pydantic response schema (`BeerRunResponse`) applies to create, list, detail, and update responses.

### Feature Validation

As the owner, rename a run and confirm 200 with the new name in the response and database. As the owner, change `is_public` to `true` and confirm the run now appears in a logged-out list. As a member (non-owner), attempt to rename — confirm 403 and no database change. Attempt to rename to an existing run's name — confirm 409.

---

## Feature 5: Delete Beer-Run

**Who & why:** A run owner needs to be able to remove a run that is no longer needed. Deletion must clean up all associated data so there are no orphaned memberships or entries.

### Functional Requirements

#### FR-5.1: Accept A Delete Request

`DELETE /api/beer-runs/{beer_run_id}` MUST require authentication. Missing or invalid token MUST return `401`. A non-existent `beer_run_id` MUST return `404`.

**Verify:** Send DELETE without a token (401). Send DELETE for a non-existent run ID (404).

#### FR-5.2: Restrict Deletion To The Owner

Only a caller whose membership has `role = 'owner'` for the target beer-run MAY delete it. A non-member or a caller with `role = 'member'` MUST receive `403 Forbidden`.

**Verify:** Owner deletes run — 200 or 204. Member of same run attempts delete — 403.

#### FR-5.3: Cascade Delete Memberships And Entries

A successful deletion MUST remove the beer-run row, ALL `beer_run_members` rows for that run, and ALL `entries` rows assigned to that run (`beer_run_id` matches) within a single transaction. The response MUST be `200 OK` with a confirmation body (`{"status": "deleted", "beer_run_id": <id>}`), following the existing response pattern at `main.py:222`. No orphaned memberships or entries may remain.

**Verify:** Create a run with 2 members and 3 entries. Delete as owner. Confirm the beer-run, both memberships, and all 3 entries are gone from the database. Confirm `BeerRunJPN` and its entries/memberships are untouched.

#### FR-5.4: Preserve Unrelated Data

Deletion MUST NOT affect users, other beer-runs, other memberships, other entries, or any other database row. The default `BeerRunJPN` run, its memberships, and its entries MUST be entirely unaffected by the deletion of another run.

**Verify:** Record counts of all tables before deletion. Delete a run. Confirm only the target run, its memberships, and its entries changed. All other counts are identical.

### Architectural Requirements

#### AR-5.1: Delete Within A Transaction

Perform the cascade delete within a single database transaction: delete entries, delete memberships, delete the beer-run, commit. Any failure MUST roll back the entire operation.

#### AR-5.2: Use The Existing Session Pattern

Reuse the existing `get_db` dependency and direct `Session` pattern. Do not configure SQLAlchemy cascade relationships on the ORM model — delete explicitly in the route to keep behavior visible and auditable.

### Feature Validation

As the owner, create a run, add entries, then delete it. Confirm 200 and verify all related rows are removed. As a member who is not the owner, attempt to delete — confirm 403 and all rows intact. Delete a run with no entries — confirm clean removal. Delete a run with entries — confirm entries are also removed.

---

## Data Requirements

- **Request: Create** — JSON with required `name: str` and optional `is_public: bool` (default `false`).
- **Request: Update** — JSON with optional `name: str` and optional `is_public: bool`; at least one must be present.
- **Response: BeerRun** — JSON with `id: int`, `name: str`, `is_public: bool`, `created_at: datetime`, `member_count: int`, `current_user_role: str | null`.
- A successful create adds one `beer_runs` row and one `beer_run_members` row with `role = 'owner'` for the caller.
- A successful update modifies the target `beer_runs` row only (name and/or is_public).
- A successful delete removes one `beer_runs` row, all associated `beer_run_members` rows, and all associated `entries` rows.
- The migration adds a `COLLATE NOCASE` unique index on `beer_runs.name` and removes the column-level case-sensitive `UNIQUE` constraint.
- Existing `BeerRunJPN` data, memberships, and entries are preserved by the migration and all CRUD operations.

## Integration Points

- `models.py`: update `BeerRun.name` column to `collation="NOCASE"` and add `__table_args__` with NOCASE unique index; `BeerRunMember` and `Entry` models are read/created/deleted by CRUD routes.
- `schemas.py`: add `BeerRunCreateRequest`, `BeerRunUpdateRequest`, and `BeerRunResponse` Pydantic models.
- `beer_run_routes.py`: new APIRouter module containing all five beer-run CRUD endpoints, the optional-authentication dependency, name-validation helpers, and the IntegrityError-detection helper for duplicate names (following the `auth_routes.py` pattern at `auth_routes.py:56-65`). Registered in `main.py` via `app.include_router`.
- `main.py`: register the beer-run router via `app.include_router(beer_run_routes.router)` alongside the existing `app.include_router(auth_routes.router)` at `main.py:36`.
- `auth.py`: add an `Optional[User]` dependency for routes that support both authenticated and logged-out access without raising 401.
- `migrations/versions/`: next ordered migration adding the NOCASE unique index on `beer_runs.name`.
- `migrations/runner.py`: register the new migration.
- `tests/conftest.py`: ensure the test database fixture has `BeerRunJPN` (already present from migration) and add helpers for creating test runs with memberships.
- `tests/test_beer_run_crud.py`: new test module covering create, list, detail, update, delete, visibility, authorization, validation, and cascade behavior.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 002: Add Beer-Run Schema | **Extends** — adds CRUD API over the beer-run data structures it defined; respects the private-by-default, unique-name, and owner-membership invariants it established | FR-2.2, FR-2.3, FR-5.3, AR-2.1 |
| Spec 005: Add Signup API | **References** — reuses the case-insensitive NOCASE migration pattern for name uniqueness; follows the same auth dependency and error-handling patterns | FR-1.3, AR-1.2, AR-2.2 |
| Spec 004: Harden Auth Tokens | **Depends on** — requires the version-2 ID-based JWT to resolve authenticated user identity for ownership checks and membership queries | FR-2.1, FR-3.3, FR-4.2, FR-5.2 |
| Spec 003: Backfill Existing Trip | **References** — preserves BeerRunJPN as the default public run with its existing memberships and entries untouched by CRUD operations | FR-3.4, FR-5.4 |
| Spec 001: Add Database Migrations | **Extends** — adds the next ordered, readiness-enforced schema migration using the established runner | FR-1.3, AR-1.1 |

## Constraints

- Keep the existing FastAPI, SQLAlchemy, SQLite, Pydantic, and direct-module architecture with no frontend build step or new application framework.
- Do not add a dependency; all required capabilities already exist in the stack.
- Never apply the migration to, delete, reset, overwrite, or commit `boozerun.db`, `boozerun_backup.db`, `test.db`, `users.json`, `static/uploads/`, or other protected runtime state.
- Keep `/token`, `/api/signup`, `/api/me`, `/api/entries`, `/api/leaderboard`, and all existing public API response shapes unchanged.
- Keep the `access_token` localStorage key, version-2 JWT identity semantics, token expiry, and bearer transport unchanged.
- Auth, schema, data, and migration changes require focused tests plus `uv --cache-dir .uv-cache run pytest`.
- This API-only feature requires no browser asset, cache-busting, layout, geolocation, upload, or Wrapped change.

## Out Of Scope

- Frontend UI for creating, listing, viewing, updating, or deleting beer-runs.
- Inviting users to a beer-run, accepting invitations, or leaving a beer-run.
- Changing member roles (promoting a member to owner, demoting an owner).
- Selecting a beer-run for entry creation — entries continue to use the default `BeerRunJPN` run via the existing entry-creation route.
- Pagination, search, or sorting for the list endpoint.
- Rate limiting on create/update/delete operations.
- Deleting or renaming the `BeerRunJPN` default run — no special protection is added; it is treated like any other public run.
- A dedicated service layer — the router module stays at the same architectural level as `auth_routes.py` with no additional abstraction.

## Failure Modes And Recovery

- **Duplicate name (same case or case variant)**: API returns `409 Conflict` after pre-check or database constraint catch; no row created or modified.
- **Invalid name format**: API returns `422` with field-level detail; no persistence begins.
- **Unauthenticated write**: API returns `401` before any query or mutation.
- **Non-owner update/delete**: API returns `403` after identifying the caller is not the owner.
- **Private run access by non-member**: API returns `404` (indistinguishable from non-existent run).
- **Concurrent duplicate name creation**: the NOCASE unique index permits at most one commit; the losing transaction rolls back and returns `409`.
- **Unexpected persistence failure**: transaction rolls back; API returns `500` without raw SQL, table names, or internal diagnostics.
- **Migration with existing case-colliding beer-run names**: migration aborts without recording or rewriting; the operator resolves the collision manually before retrying.
- **Delete with existing entries**: entries are deleted as part of the cascade; the operation succeeds.

## Feature Validation Strategy

1. **Migration**: Apply the new migration to a fresh database and to the project's test database fixture. Confirm the NOCASE unique index exists. Apply to a database with case-colliding beer-run names and confirm refusal without data change. Run `uv --cache-dir .uv-cache run pytest` to confirm all existing tests pass.

2. **Create flow**: Using an isolated test client, authenticate as a test user and send `POST /api/beer-runs` with valid and invalid names. Confirm `201` with correct response shape, auto-created owner membership, and private default. Confirm `422` for bad names, `409` for duplicates, `401` for missing auth.

3. **List/Detail visibility**: Seed the database with a mix of public and private runs across two users. Exercise the list and detail endpoints as user A (owner of some, member of others), user B (member only), and logged-out. Confirm each caller sees exactly the expected runs. Confirm `member_count` and `current_user_role` are correct in every response. Confirm `BeerRunJPN` is always visible.

4. **Update flow**: As owner, rename a run and toggle visibility. Confirm `200` and updated response. As a member (non-owner), attempt update — confirm `403`. As logged-out, confirm `401`. Attempt rename to duplicate — confirm `409`.

5. **Delete flow**: As owner, delete a run with members and entries. Confirm all related rows are removed. As non-owner, confirm `403`. Confirm unrelated data (other runs, users, `BeerRunJPN`) is untouched.

6. **Full test suite**: Run `uv --cache-dir .uv-cache run pytest` and confirm all new and existing tests pass.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Five features define the complete CRUD boundary, public/private visibility model, name validation, migration, response shapes, and error contracts. Out of Scope lists explicit non-goals. Acceptance criteria from the task are covered by FRs and Feature Validation sections.
- [x] **Feature validation strategy** — Each feature has per-feature validation exercises. The top-level Feature Validation Strategy consolidates the migration, create, list/detail, update, delete, and regression-testing checks.
- [x] **Existing patterns** — AR-1.1, AR-1.2, AR-2.2, AR-2.3, and AR-5.2 reference existing migration, route, session, schema, auth-dependency, and error-handling patterns by file path and spec number.
- [x] **Dependencies** — No new dependencies. All required capabilities (FastAPI, SQLAlchemy, SQLite, Pydantic, Argon2, JWT, pytest) are already in the project. Constraints section confirms this.
- [x] **Architecture & interfaces** — All five routes, request/response schemas, database migration, model change, and auth dependency are defined. Integration Points lists every touched file with its role.
- [x] **Error handling & failure modes** — FR-1.1, FR-1.2, FR-1.3, FR-2.4, FR-4.2, FR-4.3, FR-5.2, and the Failure Modes And Recovery section cover validation, duplicate, visibility, authorization, concurrency, migration-collision, and persistence failures with specific HTTP status codes and rollback behavior.
- [x] **Security review** — Authenticated writes require bearer tokens (401 for missing auth). Non-owner mutations return 403. Private runs return 404 for non-members (no information leak). Name input is validated against an allowlist pattern. Raw database errors are never exposed (500 sanitized). Secrets are never logged or returned.
- [x] **Performance impact** — List queries use SQL-level filtering (public OR membership join) with no in-memory scan. Create performs one name check, two inserts, and one commit. Update performs one ownership check and one column update. Delete cascades in a single transaction. All operations are O(1) or O(visible-runs); the local SQLite scale is unchanged.
- [x] **Rollout & migration** — FR-1.3 defines the ordered migration with collision preflight. Rollout And Rollback section below defines the apply/validate/rollback sequence. Constraints protect runtime data.
- [x] **Confirmed decisions & risks** — The Confirmed Decisions section records every user choice (visibility model, name rules, response shape, case-insensitivity, cascade delete). Out of Scope captures deferred work. No unresolved assumptions remain.

## Rollout And Rollback

1. Run `uv --cache-dir .uv-cache run python scripts/migrate_db.py --check` against the intended database to confirm the new migration is required but not yet applied.
2. Back up runtime data through the operator's normal process. Implementation and automated tests MUST use isolated databases only.
3. Apply the ordered migration through `scripts/migrate_db.py`. If case-colliding beer-run names are reported, stop, resolve them deliberately, and retry.
4. Deploy the routes, schemas, model update, migration registration, and tests together.
5. Validate: create a run, list runs, view public BeerRunJPN as logged-out, update name/visibility as owner, delete a run, confirm cascade.
6. Rollback may remove the API routes and revert the model metadata. The NOCASE index may be dropped through a reviewed database rollback procedure. It MUST NOT rename, merge, or delete beer-runs or their associated data.
