# Spec 004: Harden Auth Tokens

**Feature Branch**: `004-harden-auth-tokens`

**Created**: 2026-07-19

**Status**: Draft

## Overview

BoozeRunJpn currently signs 30-day JWT access tokens with a secret embedded in source code and identifies users by mutable usernames. This feature moves the signing secret into private environment configuration, issues explicitly versioned tokens whose JWT subject is the stable user ID, rejects all legacy username-based tokens, and returns affected browser sessions to a clear login state without changing the public token or current-user response shapes.

## Goals

- Prevent the application from starting with a missing, weak, example, or formerly hard-coded JWT signing secret.
- Make new access tokens resolve users by stable database ID while preserving case-insensitive login.
- Force every legacy username-based token to re-authenticate cleanly and promptly.
- Remove login diagnostics that expose usernames or credential failure details.
- Preserve all existing users, entries, memberships, uploads, and public API response shapes without a database migration.

## Confirmed Decisions

- The application must fail startup with an actionable explanation when `SECRET_KEY` is missing or invalid; it must never fall back to a built-in secret.
- Legacy username-based tokens must fail with `401 Unauthorized` and the browser must ask the user to log in again.
- Validation must exercise case-insensitive login, an authenticated request, restart continuity with the same secret, forced logout for a legacy token, and startup refusal without a valid secret.
- A private root `.env` file is the local configuration path. A tracked `.env.example` may document the variable but must not contain a usable secret.

---

## Feature 1: Secure JWT Secret Configuration

**Who & why:** The local operator needs a signing key that is unique to the deployment and survives normal restarts without being exposed in version control. A missing or unsafe key must stop the service before it can issue or accept tokens, with enough information to correct the configuration safely.

### Functional Requirements

#### FR-1.1: Load The Secret From Private Configuration

The application MUST load `SECRET_KEY` from the process environment or the repository-root `.env` file. An already defined process environment value MUST take precedence over `.env`, and the source code MUST contain no fallback signing value.

**Verify:** Start the app once with different valid values in the process environment and `.env`, then confirm a token is signed and accepted with the process value rather than the `.env` value.

#### FR-1.2: Reject Missing Or Invalid Secrets

App startup MUST fail before serving requests when `SECRET_KEY` is missing, blank, shorter than 32 UTF-8 bytes, equal to the former hard-coded value `hidden-secret-but-not-really`, or equal to the documented `.env.example` placeholder. The failure MUST name `SECRET_KEY`, explain that a strong value must be set through `.env` or the process environment, and MUST NOT print the configured value.

**Verify:** For each invalid category, start the app in an isolated process and confirm it exits nonzero with an actionable `SECRET_KEY` error that does not echo the candidate secret.

#### FR-1.3: Provide Safe Operator Setup Documentation

The repository MUST include a tracked `.env.example` containing a non-secret placeholder and README instructions for creating private `.env` configuration with a cryptographically random secret. The instructions MUST document a cross-platform Python generation command based on `secrets.token_urlsafe(32)`, environment precedence, the startup failure behavior, and the fact that changing the secret invalidates all issued tokens.

**Verify:** Follow the README from a checkout with no `.env`, generate and configure a secret, and confirm the normal documented start command launches the app without exposing or committing the generated value.

### Architectural Requirements

#### AR-1.1: Use The Existing Lightweight Configuration Style

Use `python-dotenv` as a direct project dependency and its verified `load_dotenv(..., override=False)` behavior to populate `os.environ` from the root `.env` file while preserving externally supplied values. Keep the configuration boundary direct and small; do not introduce a general settings framework for this single secret.

#### AR-1.2: Validate At The Application Boundary

Expose an explicit auth-configuration validation path and invoke it during the existing `main.py` startup/import readiness sequence before the application serves routes. JWT encode and decode paths MUST also refuse to operate without validated configuration, while password-hashing helpers used by `scripts/manage_users.py` and `scripts/setup_db.py` MUST remain usable without loading JWT configuration merely because `auth.py` is imported.

#### AR-1.3: Protect Local Secret Files

Preserve the existing `.gitignore` rules that ignore `.env` and `.env.*` while allowing `.env.example`. No real key, generated `.env`, secret-bearing log output, or test secret may be committed.

### Feature Validation

From a checkout with no `SECRET_KEY`, attempt the documented app start and observe a clear non-secret-bearing configuration failure. Generate a key with the README command, place it in the private root `.env`, start the app successfully, log in, restart with the same `.env`, and confirm the previously issued new-format token still authenticates. Then change the key and confirm the former token is rejected and the user is prompted to log in again. If startup does not behave as expected, inspect the effective process environment and `.env` location without printing the key.

---

## Feature 2: Stable, Versioned User-ID Tokens

**Who & why:** Authenticated participants need their access tokens to remain tied to the same account even if an operator later renames that account. The server needs an unambiguous token format so mutable usernames and legacy tokens cannot accidentally resolve to a different user.

### Functional Requirements

#### FR-2.1: Issue User ID As JWT Subject

After successful login, the JWT `sub` claim MUST be the authenticated user's database ID encoded as its canonical positive-decimal string. The token MUST also include an explicit integer `token_version` claim with value `2` so the server can distinguish it from every legacy username-based token, including a token for a numeric username.

**Verify:** Decode a newly issued test token and confirm `sub` equals the fixture user's ID string and `token_version` equals `2`, with no username claim used for identity resolution.

#### FR-2.2: Resolve Current Users Strictly By ID

`auth.get_current_user` MUST accept only a valid signature, a valid expiration, `token_version == 2`, and a `sub` that is a string in canonical positive-decimal form. It MUST parse that subject as a user ID and load `models.User` by `User.id`; it MUST NOT fall back to username lookup.

**Verify:** Authenticate `/api/me` with a valid version-2 ID token and confirm it returns the matching user, then rename the user without changing its ID and confirm the same token returns the new username.

#### FR-2.3: Preserve Case-Insensitive Login

`POST /token` MUST continue to locate usernames case-insensitively and verify the stored password hash before issuing the ID-based token. It MUST preserve the existing successful response shape: `access_token` plus `token_type: bearer`.

**Verify:** Log in using a casing different from the stored username and confirm the returned token authenticates `/api/me` as the correctly cased stored account.

#### FR-2.4: Fail Invalid Identity Claims Uniformly

Tokens with a missing or incorrect version, missing subject, non-string subject, username subject, zero or negative ID, leading sign, whitespace, decimal notation, leading-zero noncanonical ID, or nonexistent/deleted user ID MUST return the existing generic `401 Unauthorized` response with `WWW-Authenticate: Bearer`. The response MUST NOT disclose whether the signature, token format, or account lookup failed.

**Verify:** Exercise every invalid claim category against `/api/me` and confirm each receives the same generic `401` contract without an unhandled exception.

#### FR-2.5: Remove Credential-Revealing Login Diagnostics

The login path MUST NOT print or log attempted usernames, account existence, missing password hashes, password mismatches, token contents, or secret values. Password verification MUST be performed at most once for an existing user with a stored hash during a single login attempt.

**Verify:** Capture output for successful login, unknown-user login, missing-hash login, and wrong-password login and confirm no auth-specific diagnostic or credential detail is emitted.

### Architectural Requirements

#### AR-2.1: Preserve JWT And API Boundaries

Continue using the existing `python-jose` HS256 encode/decode path in `auth.py`, the existing 30-day expiration policy, `OAuth2PasswordBearer`, and the public `schemas.Token` response. Store the numeric ID as a string because JWT `sub` is defined as a string subject identifier; do not change `/api/me` response fields.

#### AR-2.2: Reuse The Existing Primary Key

Use the existing `models.User.id` primary key and existing `Entry.user_id` and `BeerRunMember.user_id` relationships. This feature MUST add no model, migration, backfill, database rebuild, or runtime-row rewrite.

### Feature Validation

With a valid configured secret and an existing user, log in using different username casing, call `/api/me`, and perform an authenticated entry submission. Decode the new token only in a controlled test environment to confirm its version and ID subject. Rename the test user while preserving its ID and confirm the same token still resolves the account and ownership correctly. Diagnostics should focus on token claim shape and the user row ID; they must never print the signing key.

---

## Feature 3: Graceful Forced Login For Legacy Sessions

**Who & why:** Returning browser users may still have a username-based token in `localStorage` after deployment. They need the app to recognize that obsolete session promptly, remove it, and explain that they must log in again rather than appearing authenticated until a protected write fails.

### Functional Requirements

#### FR-3.1: Reject Every Legacy Token

The API MUST reject tokens that lack `token_version == 2`, including correctly signed legacy tokens whose `sub` is a normal username or a numeric username. It MUST return the same generic `401` contract used for other invalid credentials and MUST NOT attempt a compatibility username lookup.

**Verify:** Submit correctly signed legacy tokens for both `sub: "user"` and a numeric username subject with no version marker and confirm `/api/me` returns the same generic `401` for both.

#### FR-3.2: Validate Stored Sessions On Page Initialization

When `localStorage.access_token` exists, the browser MUST call the existing protected `/api/me` endpoint during initial application setup before presenting the session as authenticated. A valid token MUST preserve the logged-in UI; the absence of a token MUST continue to show the normal unauthenticated UI without a warning.

**Verify:** Reload once with a valid version-2 token and once without a token, confirming the correct UI state in each case and no unnecessary login prompt when no session existed.

#### FR-3.3: Clear Rejected Sessions And Request Login

When initial session validation or any protected request returns `401`, the browser MUST remove `localStorage.access_token`, switch to the unauthenticated UI, and show a clear session-expired message asking the user to log in again. The behavior MUST cover legacy tokens, expired tokens, invalid signatures, deleted users, and tokens invalidated by secret rotation.

**Verify:** Load the app with a legacy token, observe it being removed without attempting an entry submission, and confirm the user sees the login UI plus a fresh-login explanation.

#### FR-3.4: Preserve Sessions During Non-Auth Failures

Network failures and non-`401` server errors during `/api/me` validation MUST NOT be presented as invalid credentials and MUST NOT silently delete the stored token. The UI MUST expose a connection failure through the existing lightweight error style so the user can retry after connectivity returns.

**Verify:** Simulate a network failure and a `500` response from `/api/me`, then confirm the stored token remains and the UI does not claim that the user's credentials expired.

### Architectural Requirements

#### AR-3.1: Follow Existing Frontend Module Boundaries

Keep network behavior in `static/js/modules/api.js`, local token and auth UI state in `static/js/modules/auth.js`, and startup orchestration in `static/js/app.js`. Reuse `/api/me` rather than adding a new token-validation endpoint.

#### AR-3.2: Update Static Cache Busting

Any changed deployed JavaScript module MUST receive the repository's corresponding query-string version update in `static/js/app.js` imports and `templates/index.html` so clients do not retain pre-hardening auth behavior.

### Feature Validation

In a real browser, seed `localStorage.access_token` with a correctly signed legacy username token and reload the page. Confirm the app removes the token, switches out of authenticated-only UI, and visibly asks for login before any drink submission is attempted. Repeat with a valid version-2 token to confirm the session stays active, then simulate offline or server-error conditions to confirm transient failures do not destroy the stored session. Inspect both desktop and mobile-sized layouts because the login state and modal are visible UI.

## Data Requirements

- The JWT `sub` claim is the canonical string form of the existing positive integer `User.id`.
- The JWT `token_version` claim is the integer `2` for all tokens issued by this feature.
- The JWT continues to contain `exp` under the existing 30-day expiration policy.
- No persisted database schema or row changes are required. Existing users, credentials, entries, memberships, beer-runs, uploads, and ownership foreign keys remain unchanged.
- The private `.env` contains the real `SECRET_KEY`; `.env.example` contains only a rejected placeholder.

## Integration Points

- `auth.py`: environment-backed signing configuration, token version/claim validation, ID-based user resolution, and generic auth failures.
- `main.py`: startup configuration validation, case-insensitive `/token` behavior, single password verification, ID token issuance, and removal of noisy login prints.
- `models.py`: existing stable `User.id` identity; no modification expected.
- `static/js/modules/api.js`, `static/js/modules/auth.js`, and `static/js/app.js`: `/api/me` validation, local token removal, user-facing relogin behavior, and startup orchestration.
- `templates/index.html`: cache-busting and any minimal session-expired presentation hook required by the existing UI.
- `tests/conftest.py`, `tests/test_auth.py`, and `tests/test_main.py`: deterministic test secret before imports, focused token/config cases, and login-to-`/api/me` integration.
- `pyproject.toml` and `uv.lock`: direct `python-dotenv` dependency and lock update.
- `.env.example`, `.gitignore`, and `README.md`: safe local configuration and operator guidance.
- `scripts/manage_users.py` and `scripts/setup_db.py`: password hashing must remain usable without coupling those helpers to app-startup JWT validation.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 003: Backfill Existing Trip | **Modifies** - changes the internal token identity contract that Spec 003 intentionally preserved while retaining its external `/token` and `/api/me` response shapes | FR-2.1 through FR-2.4, AR-2.1 |
| Spec 001: Add Database Migrations | **References** - follows its clear startup-readiness failure pattern while explicitly requiring no migration | FR-1.2, AR-1.2, AR-2.2 |

## Constraints

- Keep the application within the existing FastAPI, SQLite, vanilla JavaScript, and no-build-step architecture.
- Do not weaken bearer-token protection, password hashing, or generic authentication failure responses.
- Never delete, reset, overwrite, migrate, or otherwise mutate `boozerun.db`, `boozerun_backup.db`, `test.db`, `users.json`, `static/uploads/`, or other protected runtime state for this feature.
- Preserve the current `access_token` localStorage key, `/token` response shape, `/api/me` response shape, HS256 algorithm, and 30-day token expiry unless a later specification explicitly changes them.
- Use a 256-bit-or-greater randomly generated HS256 secret; a `secrets.token_urlsafe(32)` value satisfies the documented generation path.
- All auth/config behavior changes require focused tests and the full `uv --cache-dir .uv-cache run pytest` suite.
- Visible forced-login behavior requires browser inspection on desktop and a mobile-sized viewport.

## Failure Modes And Recovery

- Missing or invalid `SECRET_KEY`: startup stops with corrective guidance; the operator supplies a valid key and restarts.
- Secret rotation: all former tokens fail uniformly; browsers clear them on the next initial validation or protected `401` and request login.
- Malformed, legacy, expired, invalid-signature, or deleted-user token: API returns generic `401`; browser clears stored session and requests login.
- `.env` conflicts with a process environment value: the process environment wins, allowing deployment overrides without modifying local files.
- `/api/me` network or server failure: the browser retains the token and reports a connectivity problem rather than claiming credential expiry.

## Rollout And Rollback

1. Before deployment, create a private `.env` with a newly generated valid secret and verify it is ignored by Git.
2. Deploy the code, dependency lock update, `.env.example`, README instructions, tests, and cache-busted frontend assets together.
3. Expect all pre-feature tokens to require one fresh login because the former hard-coded secret is prohibited and the token format version changes.
4. Verify login, `/api/me`, entry creation, restart continuity, and browser forced logout before exposing the release.
5. Rollback may restore the previous code, but MUST NOT restore or document the compromised hard-coded secret. If rollback is necessary, keep using private environment configuration and expect another forced login when signing configuration changes.
6. No database backup, migration, restore, or rebuild is part of rollout or rollback because the feature changes no persisted schema or rows.

## Out of Scope

- Public signup, password reset, email verification, or account recovery.
- Refresh tokens, server-side sessions, revocation lists, per-user token invalidation, or logout APIs.
- Changing the HS256 algorithm, 30-day expiry duration, password hashing algorithm, or bearer-token transport.
- Adding issuer, audience, scope, role, beer-run membership, or authorization claims beyond `sub`, `exp`, and `token_version`.
- Database schema changes, data migrations, user backfills, database recreation, or username-normalization changes.
- A general application settings framework or secret-management service.

## Feature Validation Strategy

Validation combines focused automated coverage with a real browser and process-level exercise:

1. Start without `SECRET_KEY` and with each rejected value; observe nonzero startup, actionable safe output, and no served routes.
2. Configure a generated private key, start the app, log in using different username casing, call `/api/me`, and submit an entry.
3. Inspect the test token claims, rename the fixture user without changing its ID, and confirm the same version-2 token resolves the renamed account.
4. Restart with the same key and confirm the token remains valid; rotate the key and confirm it is rejected.
5. Seed the browser with normal and numeric-username legacy tokens; reload and confirm immediate token removal plus a visible login request.
6. Reload with a valid token, no token, a simulated network failure, and a simulated `500` to verify correct session preservation and UI states.
7. Inspect the login/session behavior on desktop and a mobile-sized viewport, then run `uv --cache-dir .uv-cache run pytest`.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Goals, Features 1-3, Constraints, Failure Modes, and Out of Scope define the complete release boundary.
- [x] **Feature validation strategy** - Every feature contains a user-confirmed process/API/browser exercise, summarized in the top-level Feature Validation Strategy.
- [x] **Existing patterns** - AR-1.2, AR-2.1, AR-3.1, and Integration Points reference the current startup, auth, API, and frontend module patterns.
- [x] **Dependencies** - AR-1.1 limits the new dependency to verified `python-dotenv` behavior and rejects a broader settings framework.
- [x] **Architecture & interfaces** - Architectural Requirements, Data Requirements, and Integration Points define configuration, claims, API compatibility, frontend boundaries, and the explicit no-database impact.
- [x] **Error handling & failure modes** - FR-1.2, FR-2.4, FR-3.3, FR-3.4, and Failure Modes And Recovery cover startup, token, account, and connectivity failures.
- [x] **Security review** - FR-1.1 through FR-1.3, FR-2.1 through FR-2.5, Constraints, and Rollout address secret exposure, token ambiguity, account enumeration, and rotation.
- [x] **Performance impact** - FR-3.2 adds one `/api/me` call only when a stored token exists; no polling, schema, or steady-state backend work is introduced.
- [x] **Rollout & migration** - Rollout And Rollback explicitly defines configuration ordering, expected forced login, safe rollback, and no migration/rebuild.
- [x] **Confirmed decisions & risks** - Confirmed Decisions records the user choices; codebase evidence resolves ID availability, frontend token behavior, import boundaries, numeric-username ambiguity, and dependency needs.
