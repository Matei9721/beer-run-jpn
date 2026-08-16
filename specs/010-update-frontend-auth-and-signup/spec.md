# Spec 010: Update Frontend Auth And Signup

**Feature Branch**: `010-update-frontend-auth-and-signup`

**Created**: 2026-08-02

**Status**: Draft

## Overview

BoozeRunJpn already has a browser login/logout flow and a signup API, but the
browser has no way to create an account and its authentication UI assumes only
the login response path. This feature adds signup to the existing login modal,
connects it to `POST /api/signup`, and keeps the current token, session
validation, logout, and authenticated trip refresh behavior intact.

The browser must validate fields that can be validated locally, display server
validation failures without exposing secrets, store the token returned by a
successful signup, and refresh the authenticated view as it does after login.

## Goals

- Let a visitor switch between login and signup in the existing auth UI.
- Validate signup input locally before making a request.
- Present readable duplicate-username, invalid-code, validation, and network
  errors.
- Treat successful signup as an authenticated login with the same UI refresh
  behavior as successful login.
- Preserve the existing login, logout, stored-session validation, and rejected
  legacy-session behavior.

## Confirmed Decisions

- Signup remains in or directly alongside the existing login modal; no new
  frontend framework, build step, or separate account-management page is added.
- The signup code is client-validated only for presence/non-blank input. Its
  correctness is verified only by the server; the browser must render the
  server's `403 Forbidden` message for an incorrect code.
- The client mirrors the API's username and password rules for early feedback:
  trimmed usernames of 3-32 ASCII letters/digits/underscores/hyphens, and
  passwords of at least 8 characters containing an ASCII letter and digit.
  The submitted password is not trimmed or otherwise changed.
- Confirm-password is a client-only field and is never sent to the API.
- Successful signup stores `access_token` through the existing auth module,
  closes/resets the modal, marks the UI authenticated, and refreshes the
  current BeerRunJPN data and role exactly as successful login does.
- The browser displays API `detail` text or sanitized validation messages but
  never displays or logs the password, signup code, token, or password hash.

---

## Feature 1: Signup Form In The Auth Modal

**Who & why:** A new trip participant needs to create an account without using
an operator script, while existing users need the familiar login modal to keep
working. Keeping both flows together makes authentication discoverable on a
phone and avoids a second navigation surface.

### Functional Requirements

#### FR-1.1: Offer Login And Signup Modes

The existing auth modal MUST provide an accessible way to switch between Login
and Signup modes. Login mode MUST retain the current username/password fields,
submit action, error area, close behavior, and visual meaning. Signup mode MUST
show username, password, confirm password, and signup code fields, a signup
submit action, and an error/status area associated with the signup form.

Switching modes MUST clear the previous mode's error message and MUST NOT copy
password or signup-code values between forms. Closing the modal MUST preserve
the existing close and startup-modal behavior.

**Verify:** Open the auth modal, switch modes repeatedly on desktop and a
mobile-sized viewport, and confirm each mode exposes only its own fields and
the existing login flow remains usable.

#### FR-1.2: Validate Signup Fields Before Request

Submitting signup MUST be blocked without a network request when the username
is blank after trimming, is shorter than 3 or longer than 32 characters, or
contains characters outside ASCII letters, ASCII digits, `_`, and `-`. It MUST
also be blocked when the password is shorter than 8 characters, lacks an ASCII
letter, or lacks an ASCII digit; when the confirmation does not exactly match
the password; or when the signup code is blank after trimming.

Validation messages MUST identify the affected field in plain language. The
password itself and signup code MUST NOT be included in an error message or
console output. A valid password and code MUST be submitted exactly as entered;
only the username may be trimmed to match the API's normalization rule.

**Verify:** Exercise each invalid condition and confirm no `POST /api/signup`
request is made, the relevant readable message appears, and the secret values
are absent from the rendered error and browser console.

#### FR-1.3: Submit The Signup API Request

The signup helper in `static/js/modules/api.js` MUST send a JSON `POST` request
to `/api/signup` with `Content-Type: application/json` and exactly the API
fields `username`, `password`, and `signup_code`. It MUST return the native
response or an equivalent response wrapper that preserves HTTP status and JSON
body access for the auth orchestrator. Confirm-password MUST NOT be sent.

The helper MUST use the existing direct-fetch module boundary and MUST NOT add a
new dependency or authentication transport.

**Verify:** Intercept a successful signup request and confirm its method, URL,
content type, field names, and absence of confirm-password and authorization
headers.

#### FR-1.4: Render Signup Failures Readably

For a `409 Conflict`, the UI MUST show a readable duplicate-username message
based on the API detail, such as “Username already exists.” For a `403
Forbidden`, it MUST show a readable invalid-signup-code message. For `422
Unprocessable Entity`, it MUST render the server's sanitized detail messages
or an equivalent field-specific fallback. For other unsuccessful responses and
network failures, it MUST show a non-secret generic account-creation or
connection error.

The form MUST remain available for correction after every failure, and a failed
signup MUST NOT store, replace, or remove the existing `access_token`.

**Verify:** Test duplicate username, incorrect code, invalid server validation,
server error, and offline/network failure; confirm each message is readable,
the form remains usable, and an existing token is unchanged.

#### FR-1.5: Authenticate After Successful Signup

When `POST /api/signup` returns a successful `201 Created` response containing
the existing token shape, the browser MUST store `access_token` using the
existing auth module and treat the user as authenticated. It MUST close and
reset the auth modal, update login/logout and auth-restricted controls, clear
stale BeerRunJPN identity/role state as needed, and trigger the same authenticated
data refresh path used after successful login.

The browser MUST NOT make a second login request after signup and MUST NOT
create or modify BeerRunJPN membership; signup API behavior remains the
responsibility of Spec 005.

**Verify:** Complete signup with a valid isolated account, confirm one signup
request returns `201`, the returned token is present under `localStorage`
`access_token`, authenticated controls appear, the modal closes, and refreshed
data requests use the authenticated session.

---

## Feature 2: Preserve Existing Authentication Behavior

**Who & why:** Current participants must not lose access or encounter a second,
inconsistent authentication implementation while signup is added. The browser
must continue treating the server's token and `/api/me` response as the source
of truth for session state.

### Functional Requirements

#### FR-2.1: Preserve Login And Logout

Existing login MUST continue sending the current form-encoded `/token` request,
storing its returned bearer token, closing the modal, showing authenticated
controls, and refreshing the current trip data. Existing logout MUST continue
removing `access_token`, hiding authenticated controls, returning from a
restricted tab when necessary, clearing cached identity/role state, and
refreshing public data.

**Verify:** Run successful and failed login, then logout, and confirm request
formats, token storage/removal, visible controls, and refreshed data match the
behavior before signup was added.

#### FR-2.2: Preserve Stored-Session Validation

On startup, the browser MUST continue validating a stored token through
`GET /api/me`. A `401` response MUST remove the rejected token and prompt for
login again. Non-auth transient failures MUST retain the stored token and show
the existing retry-oriented message. A valid token MUST restore authenticated
controls without requiring a new login.

**Verify:** Start with a valid token, an invalid/legacy token, and a simulated
non-401 failure; confirm the token and UI outcomes follow the existing session
validation rules.

#### FR-2.3: Keep Auth Errors Secret-Safe

The frontend MUST not log request bodies, passwords, signup codes, access tokens,
or server response bodies that may contain sensitive input. It MAY log a
generic failure category for developer diagnostics. Rendered messages MUST use
known API detail text only after excluding sensitive fields and MUST fall back
to generic text for unexpected response shapes.

**Verify:** Inspect browser console and rendered DOM during successful and
failed login/signup flows; confirm no password, signup code, token, or raw
request payload appears.

---

## Architectural Requirements

#### AR-1.1: Retain Existing Frontend Module Boundaries

Network calls MUST remain in `static/js/modules/api.js`, token storage and
auth-state/UI helpers MUST remain in `static/js/modules/auth.js`, and event
orchestration MUST remain in `static/js/app.js`. Markup belongs in
`templates/index.html`; auth-specific presentation belongs in
`static/css/auth.css`. Do not introduce a frontend build system or framework.

#### AR-1.2: Reuse One Authenticated-Refresh Path

Signup success MUST reuse the existing post-login identity reset and refresh
behavior rather than duplicating a second BeerRunJPN resolution algorithm.
The implementation MUST continue using `localStorage` key `access_token` and
the existing `AUTH_STATES` values.

#### AR-1.3: Maintain Static Asset Cache Busting

When deployed JavaScript or CSS changes, the implementation MUST update the
relevant cache-busting query strings in `templates/index.html` and the module
imports in `static/js/app.js` as required by the repository's frontend rules.

#### AR-1.4: Keep Controls Accessible And Mobile-Usable

Signup and mode-switch controls MUST have associated labels, keyboard-accessible
focus/activation behavior, and usable touch targets. Error text MUST be
associated with the relevant form or status region and remain readable within
the existing mobile modal layout without exposing secrets.

## Data And API Requirements

- Consume the Spec 005 `POST /api/signup` contract: JSON request fields
  `username`, `password`, and `signup_code`; successful `201 Created` response
  with `access_token` and `token_type: bearer`; `403` invalid code; `409`
  duplicate username; and sanitized `422` validation details.
- Do not add browser persistence for passwords, confirm-password, or signup
  codes. The only auth persistence added or changed is the existing token key.
- Do not add database, migration, membership, or backend route changes.

## Integration Points

| Area | Existing boundary | Required interaction |
|------|-------------------|----------------------|
| API client | `static/js/modules/api.js` | Add the JSON signup request helper and preserve the current login helper. |
| Auth state | `static/js/modules/auth.js` | Reuse token storage, auth states, modal/error helpers, and add only signup-mode helpers needed by the UI. |
| App orchestration | `static/js/app.js` | Wire signup events and reuse successful-login refresh/reset behavior. |
| Browser UI | `templates/index.html`, `static/css/auth.css` | Add labeled signup controls, mode switching, errors, and mobile-safe styling. |
| Backend contract | `auth_routes.py`, `schemas.py`, Spec 005 | Consume the existing API without changing its response or error contract. |

## Constraints

- Keep the application vanilla JavaScript with no bundler or new dependency.
- Preserve the public API and existing login/logout behavior.
- Never expose or persist signup secrets in source, logs, DOM diagnostics, or
  browser storage.
- Browser checks must use an isolated/test configuration and must not mutate
  `boozerun.db`, `users.json`, or uploaded runtime data.
- Manual browser verification is required for frontend auth changes; inspect
  desktop and mobile-sized views in the Codex in-app browser.

## Out Of Scope

- Changing signup API validation, signup-code configuration, token claims,
  password hashing, or database behavior.
- Password reset, email verification, profile editing, CAPTCHA, rate limiting,
  account deletion, or account recovery.
- Client-side verification of whether the signup code is correct; only the
  server can make that determination.
- Beer-run selection, run creation, invite UI, membership changes, or changes
  to Wrapped visibility.
- A Playwright smoke test unless browser automation is already part of the
  repository's active verification workflow.

## Verification Scenarios

1. In an isolated running app, create an account with valid username, password,
   confirmation, and signup code; confirm `201`, token storage, authenticated
   controls, modal closure, and refreshed UI.
2. Submit a duplicate username and confirm a readable conflict message with no
   token replacement.
3. Submit mismatched passwords and confirm the API is not called.
4. Submit a missing/blank signup code and confirm the API is not called.
5. Submit an incorrect non-blank signup code and confirm the server's `403`
   failure is readable.
6. Exercise invalid username/password values and confirm local validation blocks
   the request; exercise server `422` details and confirm they render safely.
7. Run successful login, failed login, logout, valid stored-session validation,
   rejected legacy-session validation, and transient validation failure.
8. Inspect the auth modal in desktop and mobile-sized views, including keyboard
   focus and error overflow.
9. Run `uv --cache-dir .uv-cache run pytest` for the full existing suite; add
   focused frontend/API-boundary coverage only if the repository has a suitable
   JavaScript/browser test harness, otherwise record the manual browser checks.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|---------------------|
| Spec 005: Add Signup API | **Depends on** — supplies the signup request, token response, statuses, and sanitized errors consumed here | FR-1.3, FR-1.4, FR-1.5, Data And API Requirements |
| Spec 004: Harden Auth Tokens | **References** — defines the ID-based token/session behavior the frontend must preserve | FR-1.5, FR-2.2, AR-1.2 |
| Spec 009: Scope Entries And Leaderboard API | **References** — current authenticated refresh and BeerRunJPN data boundaries | FR-1.5, FR-2.1, AR-1.2 |

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** — FR-1.1 through FR-1.5 and FR-2.1 through FR-2.3 define signup and preserved auth behavior; Out Of Scope records boundaries.
- [x] **Testing strategy** — Verification Scenarios define manual browser coverage, isolated data requirements, and the existing pytest gate.
- [x] **Existing patterns** — AR-1.1, AR-1.2, and Integration Points use the current API/auth/app module boundaries and refresh path.
- [x] **Dependencies** — Constraints and AR-1.1 require no new library or build system.
- [x] **Architecture & interfaces** — FR-1.3, Data And API Requirements, and Integration Points define the browser/API contract and affected files.
- [x] **Error handling & failure modes** — FR-1.4, FR-2.2, and FR-2.3 cover validation, duplicate, invalid-code, server, network, rejected-token, and secret-safe failures.
- [x] **Security review** — Confirmed Decisions, FR-2.3, Data And API Requirements, and Constraints cover token storage, secret handling, API boundaries, and no sensitive logging.
- [x] **Performance impact** — Signup adds one request only on explicit form submission; normal public refresh and stored-session validation remain unchanged.
- [x] **Rollout & migration** — No schema or runtime-data migration is required; deploy static assets with cache-busting updates and roll back by reverting frontend assets.
- [x] **Assumptions & risks** — Confirmed Decisions resolves the code-validation ambiguity; the API contract dependency and browser/CDN verification risk are explicit.
