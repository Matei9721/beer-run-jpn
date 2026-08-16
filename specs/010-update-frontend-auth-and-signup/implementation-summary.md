# Implementation Summary: 010-update-frontend-auth-and-signup

**Status:** Completed
**Date:** 2026-08-02
**Branch:** `spec/010-update-frontend-auth-and-signup` (based on `codex/009-scope-entries-and-leaderboard-api`)
**Worktree:** N/A — implemented directly on the branch, `--worktree` was not used

## Overview

Added account creation to the existing auth modal. A visitor can now switch
between Login and Sign Up modes, validate signup input locally before any
request, submit to `POST /api/signup`, and have a successful signup behave
exactly like a successful login (token stored, modal closed, authenticated
controls shown, BeerRunJPN data refreshed through the existing path).

Login, logout, stored-session validation, and rejected legacy-session behavior
are preserved unchanged.

## Team Execution

Implemented solo — the change is one cohesive, tightly coupled frontend
feature (six interconnected files: `app.js` imports every module and
`index.html` wires all IDs), so parallel writers would have conflicted.

## Files Created

- `static/js/modules/signup.js` - Pure client-side account-creation logic:
  field validation, error formatting, and secret-safe server-failure
  message mapping. No DOM access, no project imports.
- `specs/010-update-frontend-auth-and-signup/implementation-summary.md` - This
  document.

## Files Modified

- `static/js/modules/api.js` - Added `signup(username, password, signupCode)`
  JSON POST helper; bumped cache-busting version to `?v=12`.
- `static/js/modules/auth.js` - Added `setAuthMode`, `showSignupError`,
  `clearSignupError`, `resetSignupForm`; extended `openLoginModal` /
  `closeLoginModal` to reset both panels and default to Login mode; bumped to
  `?v=11`.
- `static/js/app.js` - Added `handleAuthenticated` (shared post-login/signup
  refresh path), the signup form submit handler, mode-switch wiring, and the
  `signup.js` import; bumped `api.js`/`auth.js` import versions and the
  `app.js` cache-busting version.
- `templates/index.html` - Added the mode switch and signup form to the auth
  modal with associated labels, `aria` attributes, and `role="alert"` error
  region; bumped `auth.css` to `?v=9` and `app.js` to `?v=14`.
- `static/css/auth.css` - Added mode-switch, panel-toggle, and signup-error
  styles with 44px touch targets.

## Test Results

- `uv --cache-dir .uv-cache run pytest`: **313 passed** (backend unchanged).
- JS modules syntax-checked as ES modules via `node --check`.
- Isolated browser verification against a throwaway database
  (`BOOZERUN_DATABASE_PATH` pointing at a temp SQLite file, test-only
  `SECRET_KEY` and `SIGNUP_CODE`), on port 8001, never touching
  `boozerun.db`, `users.json`, or uploads. Scenarios exercised:

| Scenario | Result |
|----------|--------|
| Mode switch Login/Sign Up, values not copied, errors cleared | Pass |
| Empty / short username / weak password / mismatched confirm / blank code blocked with readable field messages, zero network calls | Pass |
| Incorrect non-blank code -> 403 "Invalid signup code..." | Pass |
| Valid signup -> single `201`, `access_token` in `localStorage`, modal closed, Logout + LOG DRINK shown | Pass |
| Duplicate username -> "Username already exists." (409), no token change | Pass |
| Server stopped mid-flow -> "Connection error. Please check your connection and try again." (network failure), button re-enabled | Pass |
| Successful login, failed login ("Invalid credentials"), logout | Pass |
| Stored-session: valid token restored on reload; invalid token removed + login prompt; `/api/me` 500 mock retained token + retry prompt | Pass |
| Mobile 375x667: modal fits viewport, no horizontal overflow, 44px touch targets, one panel visible | Pass |
| Console checks: only browser-default status logs and a generic "Signup request failed"; no passwords, codes, tokens, or request bodies | Pass |

## Spec Adherence

| Requirement | Status | Implementation | Test |
|-------------|--------|---------------|------|
| FR-1.1 Login/Signup modes | Done | `templates/index.html` modal, `auth.setAuthMode` | Browser: mode switch, value isolation |
| FR-1.2 Validate before request | Done | `signup.validateSignupFields` | Browser: 5 invalid cases, no network |
| FR-1.3 Submit JSON signup request | Done | `api.signup` in `static/js/modules/api.js` | Browser: 201/403/409 responses prove well-formed body |
| FR-1.4 Render failures readably | Done | `signup.getSignupFailureMessage` | Browser: 409, 403, network |
| FR-1.5 Authenticate after signup | Done | `handleAuthenticated` in `static/js/app.js` | Browser: 201, token, controls, refresh |
| FR-2.1 Preserve login/logout | Done | `handleAuthenticated` reuses original sequence; login handler unchanged | Browser: login, failed login, logout |
| FR-2.2 Preserve session validation | Done | `validateStoredSession` unchanged | Browser: valid / 401 / non-401 mock |
| FR-2.3 Secret-safe errors | Done | generic-only logging, sanitized messages | Browser console inspection |
| AR-1.1 Module boundaries | Done | api.js / auth.js / app.js / index.html / auth.css | Code review |
| AR-1.2 Reuse one refresh path | Done | `handleAuthenticated` shared by login + signup | Browser |
| AR-1.3 Cache busting | Done | `?v=` bumps on changed assets | Grep + browser asset load |
| AR-1.4 Accessible + mobile controls | Done | labels, `aria-pressed`, `role="alert"`, 44px targets | Browser mobile metrics |

## Deviations from Spec

None functionally. The user asked for a new file when adding significant
functionality; per the Integration Points table the signup-mode DOM helpers
live in `auth.js` (as specified) while the substantive new logic (validation,
failure mapping) was extracted into the new `static/js/modules/signup.js`
module. This is consistent with the module boundaries in AR-1.1.

One defect found and fixed during browser verification: after a successful
signup the submit button stayed `disabled` across modal reopens (the in-flight
disable is not cleared by `form.reset()`). Fixed by re-enabling it in
`auth.resetSignupForm()`.
