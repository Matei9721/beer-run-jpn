# Spec 008: Add Invite Code API

**Status:** Draft

## Overview

Beer-run owners need a safe way to let other existing accounts join a run without manually editing memberships. This feature adds persistent, reusable invite capabilities and three JSON endpoints for owner-only invite creation, public minimal preview, and authenticated idempotent acceptance.

The API builds on the current branch's shared beer-run authorization policies and membership uniqueness constraint. Each beer-run has at most one high-entropy bearer code, which its owner can retrieve whenever needed and which reveals no private run data beyond the minimum name and ID needed for an invite preview.

## Goals

- Let a beer-run owner create or retrieve the beer-run's single permanent shareable invite.
- Let anyone holding a valid invite code preview the target run's identity without authentication.
- Let an authenticated user accept an invite and become a normal member.
- Make repeated and concurrent acceptance idempotent without changing an existing role.
- Keep invite codes collision-resistant, URL-safe, case-sensitive, and treated as sensitive persisted data.
- Preserve the current lightweight router, authorization, migration, and isolated-test architecture.

## Specification Decisions

- **Invite lifetime:** A beer-run's invite does not expire, rotate, or change and remains valid until its beer-run is deleted. Expiration and revocation are deferred rather than optional requirements.
- **One invite per run:** Each beer-run has at most one invite code. The first successful create request establishes it; every later create request returns that same persisted code and link without mutation.
- **Invite reuse:** The permanent invite can be accepted by multiple distinct users and remains valid after every acceptance.
- **Bearer capability:** Possession of a valid code authorizes preview and, with an authenticated account, joining. Public run visibility and existing membership are not prerequisites.
- **Stored secret:** SQLite stores the raw code because owners must be able to retrieve the same permanent link later. The database and backups therefore contain usable invite credentials and must remain protected runtime data.
- **Frontend link contract:** `invite_url` is an origin-independent root-relative URL in the form `/?invite=<code>`. Task 13 will resolve it against the browser's current origin when displaying or copying an absolute link.
- **Preview disclosure:** Preview returns only `beer_run_id` and `beer_run_name`; it does not expose visibility, owner identity, member count, member list, entries, or other run data.
- **Acceptance result:** First and repeated acceptance return `200 OK` with the existing `BeerRunResponse` shape. The caller's actual role is preserved and reported.

---

## Feature 1: Persistent Secure Invite Capabilities

**Who & why:** Run owners need one stable code they can retrieve and share repeatedly without managing invite history or rotation. The persisted model must enforce that simple one-to-one lifecycle, support fast lookup, and avoid disturbing existing users, runs, memberships, or entries.

### Functional Requirements

#### FR-1.1: Represent An Invite For One Beer-Run

The system MUST represent each invite with a generated integer ID, one non-null unique target `beer_run_id`, one non-null globally unique raw code, and a non-null creation timestamp. A beer-run may have zero or one invite, and each invite belongs to exactly one existing beer-run. The model MUST expose a singular beer-run-to-invite relationship without adding a user or creator relationship that the API does not need.

**Verify:** Request an invite twice for one run and once for another run; confirm the first run still has exactly one unchanged invite row, the second has one different invite row, and no user, membership, or entry row changes.

#### FR-1.2: Generate High-Entropy URL-Safe Codes

When a beer-run has no invite, its initial creation attempt MUST generate a code containing at least 256 bits of cryptographically secure randomness and encoded as exactly 43 unpadded URL-safe characters from `[A-Za-z0-9_-]`. Later retrieval requests MUST reuse the stored code rather than invoke the generator. Codes are case-sensitive. The generator MUST use a cryptographically secure operating-system randomness source and MUST NOT derive codes from run IDs, names, timestamps, usernames, passwords, JWTs, or the global signup code.

**Verify:** Create a representative batch of invites and confirm every returned code has the required length/alphabet, no duplicate is observed, and changing letter case causes lookup to fail unless that exact changed code was independently issued.

#### FR-1.3: Persist The Permanent Code As Sensitive Data

The server MUST persist the exact raw code so the owner-only create endpoint can return the same permanent code and link on later requests. The code MUST NOT be returned in preview or acceptance response bodies, explicitly written by invite-handling code to application logs, or included in error details. The database, backups, browser history, and infrastructure access logs are secret-bearing surfaces addressed under Constraints and Assumptions And Risks.

**Verify:** Create an invite, request it again as the owner, and confirm both responses exactly match the one stored code while preview and acceptance bodies, application-authored logs, and errors do not echo it.

#### FR-1.4: Preserve Existing Data Through The Invite Migration

The next ordered migration MUST add the invite table, its beer-run foreign key, a unique beer-run index enforcing at most one invite per run, and a globally unique code index without rewriting or deleting existing users, runs, memberships, entries, credentials, timestamps, image paths, or migration history. Fresh and upgraded isolated databases MUST reach the same invite-capable schema.

**Verify:** Apply the migration to fresh and representative pre-invite databases and confirm the new constraints and indexes exist while every pre-existing row and field remains unchanged.

### Architectural Requirements

#### AR-1.1: Align Model And SQLite Invariants

Add `BeerRunInvite` in `models.py` and the corresponding singular relationship on `BeerRun`. Add `006_add_beer_run_invites` as the next migration after `005_beer_run_name_nocase` in `migrations/versions/` and register it in `migrations/runner.py`. ORM metadata and migrated SQLite schema MUST agree on non-null fields, the beer-run foreign key, one-invite-per-run uniqueness, global code uniqueness, and lookup indexes.

#### AR-1.2: Use Existing Capabilities Only

Use Python standard-library cryptographic randomness plus the project's existing FastAPI, SQLAlchemy, Pydantic, and SQLite capabilities. Do not add a token library, encryption layer, invitation service, queue, cache, email provider, or frontend build dependency.

#### AR-1.3: Make Create-Or-Retrieve Safe Under Concurrency

Database unique constraints on both `beer_run_id` and `code` are the final concurrency backstops. A code collision with another run MUST roll back and retry with a newly generated code for up to three total generation attempts. If two requests concurrently create the first invite for one run, the losing request MUST roll back, re-read the winner's invite, and return that same code as a normal idempotent success. Exhausted code collisions or unrelated persistence failures MUST return a sanitized `500` and leave no partial invite.

### Feature Validation

Apply the ordered migration only to isolated fresh and upgraded databases. Verify table shape, foreign keys, indexes, one-invite-per-run enforcement, globally unique codes, data preservation, migration ordering, readiness checks, and idempotent migration execution. At the API level, force a cross-run code collision and confirm a fresh code is returned after retry; issue overlapping first-create requests for one run and confirm both return the one winning invite; force three code collisions and an unrelated persistence error and confirm sanitized rollback.

---

## Feature 2: Owner Invite Creation And Public Preview

**Who & why:** An owner needs a single API call that yields a link they can share through any channel. A recipient needs to see which run the link targets before logging in or joining, including when that run is private.

### Functional Requirements

#### FR-2.1: Let Only The Run Owner Create Invites

`POST /api/beer-runs/{beer_run_id}/invites` MUST require valid bearer authentication and the `owner` role for the target run. It MUST use the current shared owner-access policy, preserving its exact error contract: missing or invalid authentication returns `401` with `Could not validate credentials` and `WWW-Authenticate: Bearer`; an authenticated normal member or non-member returns `403` with `Beer-run owner access required`; and an authenticated owner requesting a missing run receives `404` with `Beer-run not found`.

The endpoint accepts no request body. The first successful request MUST create exactly one invite and return `201 Created`. Every later successful request for the same run MUST return the existing invite unchanged with `200 OK`.

**Verify:** Exercise the endpoint as owner twice, normal member, non-member, logged-out caller, invalid-token caller, and owner against a missing run; confirm exact statuses/details/headers, `201` then `200` for the owner, and exactly one invite row.

#### FR-2.2: Return A Stable Shareable-Link Contract

The create response MUST contain exactly these fields:

- `code`: the run's permanent raw invite code, newly generated only on first creation.
- `invite_url`: `/?invite=<code>`, with the code URL-encoded as a query value.
- `beer_run_id`: the target run ID.
- `beer_run_name`: the target run's current name.
- `created_at`: the persisted invite creation timestamp.

The root-relative URL MUST NOT depend on the request `Host`, forwarded headers, a deployment hostname, or a new public-base-URL setting. It is presentation data only and MUST NOT become an authorization input.

**Verify:** Create an invite through both local HTTP and a request carrying alternate host/proxy headers; confirm the response remains the same root-relative `/?invite=` shape, and decoding its query value reproduces the returned code exactly.

#### FR-2.3: Return The Same Permanent Invite

After a run has an invite, every authorized call to `POST /api/beer-runs/{beer_run_id}/invites` MUST return the exact persisted `code`, `invite_url`, `beer_run_id`, and `created_at`. It MUST resolve `beer_run_name` from the run's current name, so a rename changes only that response field and never changes the code, link, invite ID, or creation timestamp. A valid invite remains usable by multiple distinct authenticated users and remains valid after any acceptance.

**Verify:** Request the invite before and after a run rename and after two different users accept it; confirm the stored invite count remains one, the code/link/ID/timestamp never change, the returned run name updates, and the same code still previews and accepts successfully.

#### FR-2.4: Preview A Valid Invite Without Authentication

`GET /api/invites/{code}` MUST be publicly accessible. An exact valid code MUST return `200 OK` with exactly `beer_run_id` and the run's current `beer_run_name`, even when the run is private and the caller is logged out or is not a member. The endpoint MUST resolve the current run name at request time so a rename is reflected without changing the invite.

**Verify:** Preview a private-run invite while logged out and confirm only the two allowed fields are returned; rename the run as owner and confirm the same code previews the new name.

#### FR-2.5: Conceal Invalid Invite Details

Any supplied path-segment code that is malformed, unknown, case-changed, or whose target run no longer exists MUST return `404 Not Found` with detail `Invite not found`. A malformed supplied code is any route value not exactly 43 characters from the required URL-safe alphabet. A request that omits the `{code}` path segment is outside this endpoint and may receive FastAPI's standard route-level `404`. Invite responses MUST NOT reveal whether an invite row, deleted run, or similarly prefixed code ever existed.

**Verify:** Request representative too-short, too-long, invalid-character, case-changed, random, and deleted-run codes; confirm the same status and detail with no run metadata or raw database diagnostics.

### Architectural Requirements

#### AR-2.1: Keep Invite HTTP Flows In A Focused Router

Place invite creation, preview, acceptance, and their direct response-building helpers in a focused `invite_routes.py` `APIRouter`, following the existing `auth_routes.py` and `beer_run_routes.py` boundary. Register it in `main.py`. Keep shared beer-run authorization in `permissions.py`, JWT identity in `auth.py`, persistent entities in `models.py`, and public data shapes in `schemas.py`.

#### AR-2.2: Reuse The Current Owner Dependency

Invite creation MUST consume `permissions.OwnerAccess` from `permissions.authorize_owner_access` and use its already-loaded `BeerRun` and membership. It MUST NOT reimplement role checks, trust caller-provided ownership, compare run names, or weaken ownership for public runs.

#### AR-2.3: Define Dedicated Invite Schemas

Define explicit Pydantic response models in `schemas.py` for invite creation and preview. Do not reuse `BeerRunResponse` for public preview because that would disclose fields outside the minimal invite capability contract.

### Feature Validation

Using the current isolated owner/member/non-member fixture, verify the exact creation authorization matrix, first-create `201`, later `200`, stable response fields, and concurrent create-or-retrieve behavior. Preview private and public runs without authentication, confirm minimal disclosure and uniform invalid-code errors, and confirm the permanent invite follows run renames and supports multiple recipients.

---

## Feature 3: Authenticated Idempotent Invite Acceptance

**Who & why:** A recipient who already has an account needs one authenticated action to join the run. Network retries, double taps, resumed login flows, and concurrent requests must not create duplicate memberships or accidentally demote an existing owner.

### Functional Requirements

#### FR-3.1: Require Authentication Before Resolving An Invite

`POST /api/invites/{code}/accept` MUST require a valid bearer-authenticated user before revealing whether the code is valid. Missing or invalid authentication MUST return the shared `401` response with detail `Could not validate credentials` and `WWW-Authenticate: Bearer`, for both valid and invalid codes. The endpoint accepts no request body.

**Verify:** Submit valid and invalid codes without a token and with an invalid token; confirm all requests return the exact shared `401` response and perform no invite or membership query-visible mutation.

#### FR-3.2: Add A Non-Member With The Member Role

For a valid invite and an authenticated user with no membership in the target run, acceptance MUST insert exactly one `BeerRunMember` row with `role = "member"`. The invite and every existing run, user, entry, and unrelated membership MUST remain unchanged.

**Verify:** Accept a private-run invite as a non-member and confirm one new membership with the correct run, user, role, and timestamp while the invite remains valid and unrelated data is unchanged.

#### FR-3.3: Make Acceptance Idempotent And Preserve Roles

If the caller already has a membership in the run, acceptance MUST succeed without inserting or modifying a membership. An existing `member` remains `member`; an existing `owner` remains `owner`. Sequential retries and concurrent acceptance requests for the same user and invite MUST leave exactly one membership and return the same successful response semantics.

**Verify:** Accept twice as a newly joined member, accept as an existing normal member, accept as the run owner, and issue overlapping accepts for one non-member; confirm one membership per user/run and no role changes.

#### FR-3.4: Return The Joined Run In The Existing Shape

Successful first or repeated acceptance MUST return `200 OK` with the existing `BeerRunResponse` fields: `id`, `name`, `is_public`, `created_at`, `member_count`, and `current_user_role`. The response MUST reflect committed current data: `member_count` includes the newly added membership when applicable, and `current_user_role` is the caller's preserved actual role.

**Verify:** Accept as a new member, repeat as that member, and accept as the owner; confirm `200` each time, stable run identity, accurate committed member counts, and roles of `member`, `member`, and `owner` respectively.

#### FR-3.5: Return A Uniform Error For Invalid Invites

After authentication succeeds, any supplied malformed, unknown, case-changed, or deleted-run invite code MUST return `404 Not Found` with detail `Invite not found`. A request omitting the `{code}` path segment is outside this endpoint and may receive FastAPI's standard route-level `404`. Invalid acceptance MUST create no membership and MUST not disclose internal invite, table, SQL, or target-run details.

**Verify:** Authenticate and accept representative invalid-code categories; confirm the uniform `404`, zero new memberships, and sanitized output.

### Architectural Requirements

#### AR-3.1: Resolve Identity Without Requiring Prior Membership

Acceptance MUST use the existing `auth.get_current_user` boundary and shared unauthorized error, then resolve the invite and run directly. It MUST NOT use `authorize_member_access` or `authorize_public_read`, because the caller intentionally may not yet be a member and invite possession is the capability for private-run discovery.

#### AR-3.2: Use Membership Uniqueness As The Concurrency Backstop

The endpoint MUST pre-check for an existing membership for readable idempotent behavior, while treating `uq_beer_run_members_run_user` as the authoritative concurrent-duplicate guard. If an insert loses a duplicate-membership race, it MUST roll back, re-read the committed membership, preserve that role, and return normal `200` success. Unrelated integrity or persistence errors MUST roll back and return a sanitized `500` with detail `Unable to accept invite`.

#### AR-3.3: Return Fresh Committed Membership Metadata

The acceptance response MUST be built from database state after the successful commit or post-race re-read. It MUST NOT rely on a stale pre-insert relationship collection when calculating `member_count` or `current_user_role`.

### Feature Validation

Exercise first acceptance, sequential retry, concurrent retry, existing member, existing owner, two distinct recipients, public and private target runs, invalid authentication, invalid codes, and forced persistence failure. Inspect the isolated database after every case and run the complete test suite after focused invite tests pass.

## Data Requirements

- `beer_run_invites.id`: generated integer primary key.
- `beer_run_invites.beer_run_id`: non-null foreign key to `beer_runs.id` with a unique index enforcing at most one invite per run.
- `beer_run_invites.code`: non-null, globally unique, indexed 43-character case-sensitive URL-safe raw invite code.
- `beer_run_invites.created_at`: non-null UTC creation timestamp following existing model timestamp conventions.
- A run can have zero or one invite; an invite belongs to one run.
- Invites have no creator, recipient, expiration, revoked, accepted, use-count, or maximum-use field in this release.
- Accepting an invite changes only `beer_run_members` when the caller is not already a member.
- Existing `(beer_run_id, user_id)` membership uniqueness and `owner|member` role constraints remain authoritative.

## Integration Points

- `models.py`: `BeerRunInvite`, its constraints, and the `BeerRun.invites` relationship.
- `schemas.py`: dedicated invite create/preview responses; existing `BeerRunResponse` for acceptance.
- `invite_routes.py`: create, preview, and accept HTTP flows plus invite response construction.
- `permissions.py`: existing owner access and shared authentication/error contracts; no policy semantics change.
- `auth.py`: existing version-2 user-ID bearer identity; invite codes remain separate from JWTs and `SIGNUP_CODE`.
- `beer_run_routes.py`: run deletion must remove that run's invites within the existing delete transaction before deleting the run.
- `main.py`: register the invite router while retaining startup migration readiness checks.
- `migrations/versions/` and `migrations/runner.py`: add and require the next ordered invite migration.
- `tests/conftest.py`: current isolated database and owner/member/non-member setup.
- `tests/test_invites.py`: focused endpoint, security, idempotency, concurrency, and rollback coverage.
- `tests/test_beer_run_schema.py`: invite relationship, foreign-key, and uniqueness coverage.
- `tests/test_migrations.py`: ordered version, fresh/upgrade/idempotency, schema/index/FK, and data-preservation coverage.
- Release 1 Task 13 frontend: consume `invite_url`, public preview, authenticated accept, and returned `BeerRunResponse`.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|--------------|-----------------------|
| Spec 007: Centralize Beer-Run Authorization | **Depends on** - invite creation consumes its shared typed owner policy and exact 401/403/404 contract | FR-2.1, AR-2.2, AR-3.1 |
| Spec 006: Add Beer-Run CRUD API | **Extends** - adds an invite router and makes run deletion remove associated invites while reusing the existing beer-run response and transaction patterns | FR-2.2, FR-3.4, AR-2.1, AR-3.3 |
| Spec 005: Add Signup API | **Extends** - supplies the later membership-creation path intentionally excluded from signup while keeping invite codes separate from the global signup code | FR-3.1 through FR-3.5, AR-3.1 |
| Spec 002: Add Beer-Run Schema | **Extends** - adds invite persistence and uses its membership uniqueness and owner/member role invariants | FR-1.1, FR-1.4, FR-3.2, FR-3.3, AR-3.2 |
| Spec 001: Add Database Migrations | **Extends** - adds the next readiness-enforced ordered migration through the established isolated upgrade path | FR-1.4, AR-1.1 |

## Constraints

- Keep the compact FastAPI, direct SQLAlchemy session, SQLite, and static frontend architecture; add no service layer or build step.
- Preserve all current JWT, signup, beer-run CRUD, public/private visibility, owner/member authorization, entry, leaderboard, upload, and Wrapped behavior.
- Do not apply the invite migration to, reset, overwrite, or otherwise mutate live `boozerun.db` or any protected runtime database while implementing or testing. Use isolated databases and the existing test override.
- Treat invite codes as secrets: raw codes are necessarily persisted for owner retrieval, but invite-handling code must not explicitly log them, include them in error details, or return them in response bodies outside the owner-only create-or-retrieve response. Operators must protect the database, backups, browser history, and URL-bearing access logs.
- Keep preview disclosure minimal and make all invalid-code states indistinguishable.
- Use `uv --cache-dir .uv-cache run pytest` for full verification after focused schema, migration, authorization, and endpoint tests.
- This API-only feature changes no browser assets, so no cache-busting or browser layout inspection is required.

## Failure Modes And Recovery

- **Missing or invalid authentication on create/accept:** return the shared bearer `401`; do not create or reveal anything.
- **Authenticated non-owner creates invite:** return the shared owner `403`; do not create an invite.
- **Missing run during owner creation:** return `404 Beer-run not found` through the owner policy.
- **Malformed, unknown, case-changed, or orphaned code:** return `404 Invite not found` with no distinguishing detail.
- **Cross-run code collision:** roll back and generate a fresh code, for no more than three total attempts.
- **Concurrent first creation for one run:** the database permits one invite; the losing request rolls back, re-reads the winner, and returns the same permanent invite with `200`.
- **Concurrent membership acceptance:** the database permits one membership; a losing duplicate insert is converted to the same idempotent `200` response after rollback and re-read.
- **Unexpected invite creation failure:** roll back and return sanitized `500 Unable to create invite`; no raw code or partial row remains.
- **Unexpected invite acceptance failure:** roll back and return sanitized `500 Unable to accept invite`; the existing membership state remains valid.
- **Run deletion:** remove the target run's invites, entries, and memberships in the same transaction before the run; unrelated invites and data remain unchanged. Deleted invite codes subsequently return the common `404`.
- **Rollback:** application rollback removes the router/model usage only after a reviewed database rollback handles the invite table; existing runs, memberships, entries, accounts, and credentials require no data rewrite.

## Rollout And Migration

1. Add the invite model, schemas, router, router registration, run-delete integration, ordered migration, and focused tests as one deployment unit.
2. Validate the migration against isolated fresh and representative upgraded copies, including foreign keys, unique run/code indexes, existing-row preservation, and idempotency.
3. Run `uv --cache-dir .uv-cache run python scripts/migrate_db.py --check` against an intended runtime database only as a read-only readiness check unless the user separately authorizes applying migrations.
4. Back up runtime data through the operator's normal process before any separately authorized production migration.
5. Apply the migration through `scripts/migrate_db.py`, then deploy the application; startup must continue refusing traffic when the required migration is missing.
6. Verify owner creation, public private-run preview, first/repeated acceptance, owner-role preservation, invalid-code concealment, and run deletion.
7. Rollback must preserve existing data. Dropping the invite table discards only invite capabilities, after which all previously shared links stop working; memberships already created by accepted invites remain memberships unless a separate, explicitly authorized membership change removes them.

## Out of Scope

- Invite expiration, expiration cleanup, revocation, rotation, replacement, separate listing endpoints, labels, audit history, one-time use, maximum uses, or usage counters.
- Per-recipient, username-targeted, or email-targeted invitations; email, SMS, QR-code, or messaging delivery.
- Creating accounts during invite acceptance or bypassing the existing `SIGNUP_CODE`; logged-out login/signup-and-resume behavior belongs to Task 13.
- Invite UI, copy buttons, client routing/query handling, automatic run selection, or cache-busting; Task 13 owns the browser flow.
- Promoting invited users to owner, changing an existing role, removing members, leaving a run, or transferring ownership.
- Rate limiting, CAPTCHA, IP blocking, or a general abuse-prevention framework.
- A configured canonical public origin or absolute invite URL returned by the backend.
- Changing run visibility, listing semantics, entry/leaderboard scoping, JWT format, password hashing, or the global signup-code configuration.

## Validation Strategy

1. Verify the new migration on fresh and upgraded isolated databases, including migration history, schema columns, foreign key, one-invite-per-run uniqueness, global code uniqueness, preservation, and idempotency.
2. Verify model relationships and constraints with SQLite foreign keys enabled.
3. Test invite creation with real owner, member, non-member, missing-auth, invalid-auth, and missing-run cases, asserting exact existing authorization contracts.
4. Test code alphabet, length, entropy source by inspection, permanent raw-code storage, repeated and concurrent create-or-retrieve behavior, cross-run collision retry/exhaustion, root-relative URL shape, and secret-free application logs/errors.
5. Test public minimal preview for private and public runs, current-name behavior after rename, and uniform invalid-code responses.
6. Test authenticated first acceptance, sequential and concurrent retries, existing member, existing owner, two different recipients, accurate returned member counts/roles, and persistent invite reuse.
7. Test run deletion removes only its invites and makes those codes invalid while preserving unrelated invites and memberships already created through acceptance.
8. Force unrelated creation and acceptance persistence failures and confirm rollback plus sanitized `500` responses.
9. Run focused invite, schema, migration, permission, and CRUD tests, then run `uv --cache-dir .uv-cache run pytest` against isolated data.
10. Run `git diff --check` and verify protected runtime files remain untouched.

## Assumptions And Risks

- **Confirmed decision:** Each beer-run has one permanent reusable invite. The owner-only create endpoint doubles as retrieval after first creation, so owners and the later frontend never need separate create, list, or recovery flows.
- **Confirmed decision:** The permanent code must be stored in recoverable raw form so the same link can be returned forever. Anyone who can read the database or its backups can therefore use active invites; repository runtime-data protections and operational access controls are the mitigation.
- **Assumption:** Non-expiring invites are acceptable for this small Release 1 trip workflow because the code intentionally remains permanent and no revoke lifecycle is requested. The security tradeoff is that a leaked link remains usable until run deletion.
- **Mitigation:** Codes retain 256 bits of cryptographic randomness, making guessing infeasible, but anyone who obtains the code from a link, database, backup, history, or access log can preview and join with an authenticated account.
- **Risk:** Public preview intentionally reveals a private run's ID and current name to a code holder. The response excludes visibility, ownership, membership, entries, and other private data.
- **Risk:** A root-relative link is not directly shareable outside a browser until the frontend resolves it against the current origin. This avoids incorrect or attacker-controlled origins in the API and gives Task 13 a deployment-neutral contract.
- **Risk:** The task-prescribed preview and acceptance routes include the raw code in the URL, so browser history, reverse-proxy logs, and Uvicorn access logs may record it. Deployment access logs must be access-controlled and retained as sensitive operational data; eliminating URL exposure would require a different API contract outside this task.
- **Risk:** Without rate limiting, an attacker can submit guesses, but 256 bits of randomness makes successful enumeration infeasible. A broader abuse-control layer remains out of scope.
- **Risk:** Permanent codes cannot be invalidated without deleting the run under this release contract. Rotation or revocation would require a future lifecycle change and an explicit compatibility decision for already shared links.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Features 1-3, Specification Decisions, Constraints, and Out of Scope define creation, preview, acceptance, and lifecycle boundaries; every FR has a `Verify` condition.
- [x] **Testing strategy** - Feature Validation sections and Validation Strategy cover isolated migration, model, endpoint, concurrency, security, rollback, deletion, and full-suite checks.
- [x] **Existing patterns** - AR-1.1, AR-2.1, AR-2.2, AR-3.1, and Integration Points reference the current migration runner, router modules, shared permissions, auth boundary, direct sessions, and test fixtures.
- [x] **Dependencies** - AR-1.2 and Constraints confirm existing dependencies and Python standard-library primitives are sufficient; no new package is introduced.
- [x] **Architecture & interfaces** - All ARs plus Data Requirements and Integration Points define module ownership, models, indexes, foreign keys, response shapes, and transaction boundaries.
- [x] **Error handling & failure modes** - FR-1.4, FR-2.1, FR-2.5, FR-3.1, FR-3.5, AR-1.3, AR-3.2, and Failure Modes define authentication, authorization, invalid-code, collision, concurrency, deletion, rollback, and sanitized server errors.
- [x] **Security review** - FR-1.2, FR-1.3, FR-2.4, FR-2.5, FR-3.1, Constraints, and Assumptions And Risks cover entropy, recoverable secret storage, operational protection, minimal disclosure, enumeration resistance, bearer capability, and deferred abuse controls.
- [x] **Performance impact** - Digest and membership indexes bound lookups to direct indexed queries; creation and first acceptance add one row each, previews are read-only, and no background work, polling, or unbounded scan is introduced.
- [x] **Rollout & migration** - FR-1.4, Rollout And Migration, Constraints, and run-deletion requirements define isolated verification, readiness, protected runtime state, deployment ordering, data preservation, and rollback consequences.
- [x] **Assumptions & risks** - Specification Decisions and Assumptions And Risks explicitly record one permanent invite per run, recoverable raw-code storage, minimal private preview, root-relative links, and deferred lifecycle/abuse work.
