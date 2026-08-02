# Spec 007: Centralize Beer-Run Authorization

**Status**: Draft

## Overview

Beer-run authorization is currently implemented directly inside individual CRUD routes. The existing behavior is correct for public and private reads, but repeated membership and owner checks make future run-scoped APIs vulnerable to inconsistent access decisions or accidental data exposure.

This feature introduces shared, typed authorization dependencies for public-read, member-only, and owner-only access. A run's `is_public` value is the only public-read signal: `BeerRunJPN` is the currently seeded public run, but it has no special authorization status and future public runs must be equally readable without authentication.

## Goals

- Give run-scoped endpoints one shared dependency for public-read access, one for membership, and one for ownership.
- Preserve the public/private behavior and HTTP status contracts established by Spec 006.
- Return typed access results containing the already-authorized beer-run and, when applicable, the caller's membership.
- Prevent authorization from depending on frontend state, caller-supplied roles, or the name `BeerRunJPN`.
- Provide reusable authorization boundaries for the invite and scoped-entry features that follow this task.

## Specification Decisions

- **Public-read rule**: Every `BeerRun` with `is_public = true` is readable without authentication. `BeerRunJPN` is not a name-based exception and must not be the only possible public run.
- **Private-read rule**: A private run is readable only by an authenticated member of that run.
- **Write rule**: Public visibility grants read access only. Member-only and owner-only writes still require the corresponding membership role.
- **Owner denial compatibility**: Preserve Spec 006 behavior: an authenticated caller who is not an owner receives `403 Forbidden`, whether the caller is a normal member or a non-member. A missing run remains `404`.
- **Private-read concealment**: Missing runs and private runs inaccessible to the caller both return the same `404` response.
- **Member-only concealment**: An authenticated non-member receives the same `404` as a missing run from member-only policies so future scoped data endpoints do not reveal private run existence.
- **Authentication precedence**: Member-only and owner-only policies resolve required authentication before target-run existence, so missing or invalid credentials return `401` even when the requested run is missing. Public-read policies retain optional authentication and evaluate an invalid token as a logged-out caller.
- **Module boundary**: JWT decoding and user identity remain in `auth.py`; beer-run access policy belongs in a small dedicated permissions module rather than a service layer.
- **Data impact**: The existing `BeerRun` and `BeerRunMember` models contain all required authorization data. No schema migration, backfill, or runtime-data change is required.

---

## Feature 1: Shared Beer-Run Access Policies

**Who & why:** Backend developers adding run-scoped entries, leaderboards, invitations, or management endpoints need a single trustworthy way to authorize a caller. Without shared policies, each endpoint can interpret public visibility, membership, roles, and missing-run errors differently.

### Functional Requirements

#### FR-1.1: Authorize Reads From The Run Visibility Flag

The public-read policy MUST allow any caller, including a logged-out caller, an invalid-token caller resolved as logged out, or an authenticated non-member, to read a beer-run when `BeerRun.is_public` is `true`. The decision MUST be based on the persisted `is_public` value and MUST NOT compare the run's name with `BeerRunJPN` or any other literal name.

**Verify:** Create a public run with a name other than `BeerRunJPN` and confirm logged-out, invalid-token, and authenticated non-member callers are authorized to read it with no fabricated membership.

#### FR-1.2: Require Membership For Private Reads

The public-read policy MUST authorize a private run only when the current authenticated user has a `BeerRunMember` row for that run. Both `owner` and `member` roles qualify for private-read access. A logged-out, invalid-token, or authenticated non-member caller requesting a private run MUST receive `404 Not Found` with detail `Beer-run not found`, identical to the response for a missing run.

**Verify:** For one private run, confirm its owner and a normal member are authorized, while logged-out, invalid-token, non-member, and missing-run requests receive the same `404` status and detail.

#### FR-1.3: Require Authentication And Membership For Member Access

The member-only policy MUST first require a valid authenticated user and then require a `BeerRunMember` row for the target run. Either `owner` or `member` role satisfies this policy; `is_public = true` MUST NOT bypass membership for member-only operations. Missing or invalid authentication MUST return `401 Unauthorized` with detail `Could not validate credentials` and a `WWW-Authenticate: Bearer` header without revealing whether the run exists. After authentication succeeds, a missing run or a run for which the caller is not a member MUST return `404 Not Found` with detail `Beer-run not found`.

**Verify:** Confirm an owner and normal member pass member access on both public and private runs, while logged-out and invalid-token callers receive `401` and authenticated non-members or missing-run callers receive the common `404` response.

#### FR-1.4: Require The Owner Role For Owner Access

The owner-only policy MUST first require a valid authenticated user and then require that user's membership for the target run to have `role = "owner"`. A normal member or authenticated non-member MUST receive `403 Forbidden` with the shared detail `Beer-run owner access required`; public visibility MUST NOT weaken this requirement. Missing or invalid authentication MUST use the standard `401` response without revealing whether the run exists. After authentication succeeds, a missing run MUST return `404 Not Found` with detail `Beer-run not found`.

**Verify:** Confirm an owner succeeds, a real normal member and authenticated non-member both receive the same `403`, a logged-out caller receives `401`, and a missing run receives `404`.

#### FR-1.5: Return The Authorized Run And Membership

Every access policy MUST return the loaded target run so the consuming endpoint does not repeat the run lookup. Member-only and owner-only access MUST also return a non-null membership. Public-read access MUST return the caller's membership when one exists and `null` when a logged-out caller or authenticated non-member reads a public run.

**Verify:** Inspect each successful access result and confirm it contains the target `BeerRun`, plus a non-null `BeerRunMember` for member/owner access and the correct optional membership for public reads.

### Architectural Requirements

#### AR-1.1: Keep Authorization In A Focused Permissions Module

Add a lightweight `permissions.py` module that owns beer-run access result types, shared authorization errors, and FastAPI-compatible dependencies. Keep JWT validation, bearer-token parsing, and current-user lookup in `auth.py`; do not introduce a repository, service layer, policy framework, or third-party authorization library.

#### AR-1.2: Use Truthful Typed Access Results

Define internal Python access result types rather than public Pydantic response schemas. Public-read results MUST type the membership as optional, while member and owner results MUST make the membership non-optional so endpoint implementations can use the authorized role without defensive null checks.

#### AR-1.3: Compose Existing FastAPI Dependencies

The shared policies MUST compose `auth.get_current_user` and `database.get_db`, and MUST accept `beer_run_id` from the endpoint path. They must remain usable through FastAPI `Depends` and directly callable with already-resolved users and sessions in focused tests. A route and its authorization dependency MUST obtain the same request-scoped session through `Depends(get_db)` and MUST NOT instantiate a separate session.

#### AR-1.4: Query Authorization Data Directly

Load the target `BeerRun` and the current user's matching `BeerRunMember` through direct SQLAlchemy session operations consistent with `beer_run_routes.py` and `database.py`. Authorization MUST NOT scan or trust frontend-provided member lists, `current_user_role` response fields, browser state, request-body roles, or other caller-controlled data.

#### AR-1.5: Centralize Error Construction

The permissions module MUST construct the shared `401`, `403`, and `404` errors so consuming routes do not reproduce status codes, details, or authentication headers. The same policy failure MUST produce the same response regardless of which endpoint consumes the dependency.

#### AR-1.6: Preserve Lightweight Query Behavior

The authorization portion of each single-run check MUST query no more than the target run and the caller's matching membership. Later response construction may load the target run's membership collection when needed for `member_count`, but authorization MUST NOT load memberships for unrelated runs or introduce an application-wide permission cache whose state could become stale.

---

## Feature 2: Integrate Shared Policies With Beer-Run Routes

**Who & why:** API callers already rely on the beer-run CRUD endpoints and their visibility behavior. The internal refactor must remove duplicated checks without changing which runs callers can see, who can mutate them, or the successful response shapes.

### Functional Requirements

#### FR-2.1: Use Public-Read Authorization For Run Detail

`GET /api/beer-runs/{beer_run_id}` MUST use the shared public-read policy. It MUST continue to return `BeerRunResponse` with the same fields and values, including `current_user_role = null` for a logged-out or authenticated non-member caller reading a public run and the actual role for a member.

**Verify:** Repeat the existing public, private-member, private-non-member, logged-out, and missing-run detail scenarios and confirm status codes and successful response bodies remain compatible.

#### FR-2.2: Use Owner Authorization For Run Update

`PATCH /api/beer-runs/{beer_run_id}` MUST use the shared owner policy before applying name or visibility changes. The route MUST consume the authorized run and membership returned by the policy rather than loading the run or recalculating ownership itself. Existing validation, duplicate-name handling, transaction behavior, and successful `BeerRunResponse` output remain unchanged.

**Verify:** Confirm owner updates still succeed, genuine normal members and non-members receive the shared `403`, unauthenticated callers receive `401`, and denied requests do not change the run.

#### FR-2.3: Use Owner Authorization For Run Deletion

`DELETE /api/beer-runs/{beer_run_id}` MUST use the shared owner policy before deleting entries, memberships, or the run. The route MUST consume the authorized run returned by the policy, while preserving the existing transaction, cascade order, confirmation response, and rollback behavior.

**Verify:** Confirm an owner can delete a run with its related rows, while genuine normal members, non-members, logged-out callers, and missing-run callers receive the specified authorization responses with no data removed.

#### FR-2.4: Keep List Visibility Aligned With Public-Read Policy

`GET /api/beer-runs` MUST retain an efficient set-based visibility query whose results match the shared public-read rule: every public run is visible to every caller, and private runs are visible only to their members. List visibility MUST NOT special-case `BeerRunJPN` by name; it does not need to invoke a single-run dependency once per result.

**Verify:** With two public runs and private runs belonging to different users, confirm logged-out callers see both public runs, while authenticated callers additionally see only their own private memberships.

### Architectural Requirements

#### AR-2.1: Remove Route-Level Authorization Duplication

After integration, `beer_run_routes.py` MUST NOT contain separate implementations of detail visibility, owner-role lookup, or required-authentication handling for the detail, update, and delete endpoints. Route functions remain responsible for request validation, persistence, response construction, and operation-specific error handling unrelated to authorization.

#### AR-2.2: Preserve Public API Shapes

Do not add fields to or remove fields from `BeerRunResponse`, create/update requests, or successful delete responses. This feature may standardize authorization error detail as specified in Feature 1, but it must not otherwise change the CRUD API contract established by Spec 006.

#### AR-2.3: Provide Stable Dependencies For Later Scoped APIs

The member and public-read dependencies MUST be reusable by later `/api/beer-runs/{beer_run_id}/...` endpoints without coupling them to CRUD-specific request or response types. Task 08 invite creation can consume owner access; Task 09 scoped reads can consume public-read access; and Task 09 scoped writes can consume member access.

---

## Feature 3: Authorization Contract Test Coverage

**Who & why:** Maintainers need tests that fail when a future endpoint weakens public/private separation, mistakes a non-member for a member, trusts a caller-provided role, or reintroduces a special case for `BeerRunJPN`.

### Functional Requirements

#### FR-3.1: Test Real Owner, Member, And Non-Member Identities

Focused authorization tests MUST create three distinct authenticated users: an owner, a genuine `role = "member"` participant in the same run, and a user with no membership. Test names and fixture names MUST reflect the persisted membership state rather than merely naming a non-member user "Member".

**Verify:** Inspect the isolated test database and confirm the three test callers have owner, member, and absent membership states before authorization assertions run.

#### FR-3.2: Test Every Shared Policy Directly

Focused tests MUST exercise the public-read, member-only, and owner-only policy logic directly with already-resolved owner, member, non-member, and `None` user values, including successful typed return values and all specified authorization failures. Endpoint/dependency-composition tests MUST separately cover actual missing and invalid bearer tokens because token decoding belongs to `auth.get_current_user`, not the permission policy itself.

**Verify:** Run the focused authorization and endpoint integration tests and confirm every policy branch has assertions for status, detail, authentication header when applicable, returned access data, and actual missing/invalid-token composition.

#### FR-3.3: Test General Public-Run Semantics

Tests MUST use at least one public run whose name is not `BeerRunJPN`. They MUST prove that both logged-out callers and authenticated non-members can read it, and that changing a run's name does not affect its public-read authorization while changing `is_public` does.

**Verify:** Rename an authorized public test run and confirm access remains; toggle the same run private and confirm anonymous/non-member access is denied.

#### FR-3.4: Test Route Integration Without Weakening Existing Behavior

Endpoint regression tests MUST preserve the observable detail, update, and delete behavior after dependency integration. At minimum, add genuine normal-member coverage for private detail, owner rejection on update, and owner rejection on delete, while retaining arbitrary-public-run anonymous-read coverage. Code inspection MUST separately confirm that the routes are wired to the shared dependencies and no equivalent inline authorization remains.

**Verify:** Run the beer-run CRUD and focused permissions tests and confirm the real normal member reads private detail successfully but cannot update or delete the run.

### Architectural Requirements

#### AR-3.1: Use Only Isolated Test Data

Authorization tests MUST use the existing isolated database override in `tests/conftest.py` or an equivalent per-test isolated SQLAlchemy session. They MUST NOT read from, migrate, or modify live `boozerun.db`, uploads, `users.json`, or other protected runtime state.

#### AR-3.2: Add Reusable Membership Test Setup

Provide narrowly scoped test setup for creating a run with owner, normal member, and non-member identities. Shared setup may live in `tests/conftest.py` when reused across modules, but production models MUST NOT gain test-only helpers.

---

## Data Requirements

- `BeerRun.is_public` remains the sole persisted public-read flag.
- `BeerRunMember.beer_run_id`, `user_id`, and `role` remain the sole persisted membership and ownership inputs.
- Existing roles remain `owner` and `member`; no additional role or permission table is introduced.
- No columns, indexes, migrations, backfills, or runtime-data transformations are required.
- No authorization decision may be based on the mutable beer-run name.

## Integration Points

- `permissions.py`: new internal typed access results, shared errors, and FastAPI dependencies.
- `auth.py`: existing optional current-user resolution is consumed but its JWT behavior remains unchanged.
- `database.py`: existing request-scoped SQLAlchemy session dependency is reused.
- `models.py`: existing `BeerRun` and `BeerRunMember` fields provide authorization state; no model change is expected.
- `beer_run_routes.py`: detail, update, and delete routes consume shared policies; list semantics remain aligned.
- `schemas.py`: existing public API schemas remain unchanged.
- `tests/conftest.py`: isolated database and reusable membership setup.
- `tests/test_permissions.py`: focused policy and typed-result coverage.
- `tests/test_beer_run_crud.py`: integration and regression coverage for the refactored routes.
- Future Task 08 and Task 09 routes: consumers of owner, member, and public-read dependencies.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 006: Add Beer-Run CRUD API | **Modifies** — centralizes its authorization behavior, preserves FR-3.1/FR-3.2 general public-run visibility and owner mutation status codes, and supersedes FR-3.4's name-specific implication that `BeerRunJPN` must remain permanently visible regardless of its persisted flag | FR-1.1 through FR-1.4, FR-2.1 through FR-2.4, AR-2.2 |
| Spec 004: Harden Auth Tokens | **Depends on** — uses its ID-based bearer-token user resolution as the trusted caller identity | FR-1.3, FR-1.4, AR-1.3 |
| Spec 002: Add Beer-Run Schema | **Depends on** — uses its visibility flag, membership uniqueness, indexed lookups, and owner/member roles; preserves support for multiple public runs | FR-1.1 through FR-1.5, AR-1.4 |
| Spec 003: Backfill Existing Trip | **References** — recognizes `BeerRunJPN` as the initially seeded public run without giving its name special authorization meaning | FR-1.1, FR-2.4, FR-3.3 |

This spec supersedes the `BeerRunJPN`-only shorthand in `release1_tasks/07_add_membership_authorization_helpers.md` and `release1_tasks/09_scope_entries_and_leaderboard_api.md`. For authorization, their references to public `BeerRunJPN` mean any run with `is_public = true`.

## Constraints

- Keep the app's direct FastAPI, SQLAlchemy, and SQLite architecture; do not add a permission framework or new dependency.
- Preserve `auth.get_current_user` behavior: missing, invalid, expired, wrong-version, and deleted-user tokens resolve to no authenticated user.
- Preserve bearer-token requirements for authenticated writes.
- Preserve existing successful CRUD response shapes and database transactions.
- Keep list/detail visibility based on `is_public OR caller membership`.
- Treat all public runs equally regardless of name, creator, age, entry count, or membership count; this authorization rule does not change the separate owner invariant for valid runs.
- Use `uv --cache-dir .uv-cache run pytest` for full verification after implementation.

## Out of Scope

- Creating invite codes or accepting invitations; Task 08 owns those endpoints and data.
- Adding beer-run-scoped entry and leaderboard routes; Task 09 owns those endpoints.
- Changing the frontend run selector, entry calls, or auth UI.
- Changing how JWTs are created, validated, stored, or expired.
- Adding, renaming, or removing membership roles.
- Changing beer-run creation, naming, visibility updates, or deletion semantics beyond consuming shared authorization.
- Making `BeerRunJPN` immutable, permanently public, or otherwise privileged by name.
- Applying migrations or modifying live runtime data.

## Failure Modes And Recovery

- **Missing or invalid authentication on protected access**: return the shared `401` response with `WWW-Authenticate: Bearer`; perform no mutation.
- **Missing beer-run**: return the shared `404 Beer-run not found` response.
- **Private read by logged-out caller or non-member**: return the same `404` as a missing run so private existence is not disclosed through read endpoints.
- **Member-only access by authenticated non-member**: return the same `404` as a missing run and do not disclose scoped data.
- **Owner-only access by normal member or authenticated non-member**: preserve the shared `403 Beer-run owner access required` response from the clarified Spec 006 contract; perform no mutation.
- **Public read by non-member**: succeed with an optional membership value of `null`; do not manufacture a membership or role.
- **Visibility changes during later requests**: evaluate persisted authorization state on every request; do not rely on cached frontend state or long-lived application permission caches.
- **Unexpected database failure during authorization lookup**: allow the application's standard server-error handling to return a sanitized failure; never convert database failures into authorization success.
- **Refactor regression**: revert route dependency integration and the new permissions module together; no data rollback is needed because this feature changes no schema or persisted rows.

## Validation Strategy

1. Add focused tests for the typed results and direct public-read, member, and owner policies using owner, true member, and non-member identities.
2. Cover logged-out, invalid-token, authenticated-member, authenticated-non-member, and missing-run cases with exact status, detail, authentication precedence, and authentication-header assertions; explicitly verify invalid-token public read succeeds and invalid-token private read returns the common `404`.
3. Prove arbitrary `is_public = true` runs are anonymously readable and that no name-based `BeerRunJPN` authorization check exists.
4. Refactor detail, update, and delete routes, then run the focused permissions and beer-run CRUD test modules.
5. Run `uv --cache-dir .uv-cache run pytest` and confirm all existing behavior remains green using isolated test data.
6. Run `git diff --check` and confirm the worktree contains only the intended source, test, and living-document changes.

## Rollout And Rollback

1. Deploy the new permissions module, route integration, and focused tests together.
2. No database migration or configuration change is required before deployment.
3. Existing tokens, memberships, public flags, API request shapes, and successful response bodies remain valid.
4. After deployment, verify one arbitrary public run anonymously, one private run as member/non-member, and one owner-only mutation as owner/member/non-member.
5. Rollback removes the permissions module and restores the previous inline route checks. No persisted-data rollback or file migration is necessary.

## Assumptions And Risks

- **Inherited contract**: Spec 006's `403` response for every authenticated non-owner remains the compatibility contract for owner-only operations. This differs intentionally from private-read and member-only concealment, which use `404`.
- **Specification choice**: Owner-only routes standardize their former operation-specific `403` details to `Beer-run owner access required`; this is the sole intentional authorization-error text change and is required so every consumer of the owner policy returns the same response.
- **Assumption**: `is_public` is an intentional authorization input and may be enabled for future runs; `BeerRunJPN` is only the currently seeded example.
- **Risk**: A future endpoint may bypass the dependencies and implement a custom check. AR-2.3 and the focused test pattern mitigate this by making the shared policies directly reusable.
- **Risk**: Optional authentication treats an invalid token like a logged-out caller on public reads. This is existing `auth.get_current_user` behavior and is preserved; protected member/owner access still returns `401`.
- **Risk**: Standardizing owner error detail changes the text of existing PATCH/DELETE `403` responses, although their status and authorization meaning remain unchanged. Route and frontend consumers must not branch on the former operation-specific text.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — Features 1-3 define the shared policies, route integration, tests, and explicit non-goals; every FR has a concrete verification condition.
- [x] **Testing strategy** — Feature 3 and Validation Strategy cover direct policy tests, endpoint regression tests, identity roles, exact errors, and the full isolated pytest suite.
- [x] **Existing patterns** — AR-1.1 through AR-1.5 and Integration Points reference current `auth.py`, `database.py`, `models.py`, and `beer_run_routes.py` boundaries.
- [x] **Dependencies** — Constraints explicitly require existing FastAPI and SQLAlchemy capabilities and prohibit a new external authorization library or policy framework.
- [x] **Architecture & interfaces** — Features 1-2 define typed internal results, dependency composition, route consumers, module ownership, and unchanged public schemas.
- [x] **Error handling & failure modes** — FR-1.2 through FR-1.4 and Failure Modes And Recovery define exact `401`, `403`, and `404` behavior and distinguish read concealment from owner denial.
- [x] **Security review** — FR-1.1 through FR-1.4 and AR-1.4 define trusted inputs, public/private boundaries, required membership, required ownership, and prohibition of frontend or name-based authorization.
- [x] **Performance impact** — AR-1.6 limits each check to the target run and matching membership and prohibits unrelated scans or stale global caches.
- [x] **Rollout & migration** — Data Requirements and Rollout And Rollback confirm no schema/runtime migration and define deploy, verify, and code-only rollback steps.
- [x] **Assumptions & risks** — Assumptions And Risks records the owner-error compatibility choice, optional-auth behavior, public-flag semantics, bypass risk, and standardized error-text impact.
