# Implementation summary

## Delivered

- Added normalized, bodyless invite API helpers for owner creation, anonymous preview, and authenticated acceptance.
- Added a distinct owner-only `Invite people` action in the existing beer-run picker, including permanent-link validation, read-only link display, clipboard fallback, and Web Share support.
- Added a focused invite-flow module for deep-link parsing, anonymous preview, login/signup continuation, acceptance validation, stale-session protection, URL scrubbing, focus management, and retry/error states.
- Suppresses the Join action when the confirmed account already owns or belongs to the previewed run, including repeated access to the same invite.
- Reused the existing app identity/context lifecycle for accepted runs: membership upsert, selected-run persistence, scoped refresh, and one My Runs reconciliation.
- Scrubbed invite parameters from ordinary share links and normalized accepted links to `?run=<id>` while preserving unrelated query parameters.
- Added responsive recipient and owner invite UI with cache-busted static assets.
- Matched invite actions to the existing cyan/pink dark-theme picker controls rather than the browser's default button styling.

## Boundary note

The picker remains responsible for the owner subview's DOM state and compact link actions because it already owns the run-picker sheet, focus trap, and owner-role rendering. `invites.js` owns the invite protocol, response validation, recipient flow, and URL/security rules; the picker delegates the server request to `app.js` and uses the shared validator. This preserves the existing component boundary without adding a second sheet implementation.

## Verification

- `node --check` passed for `app.js`, `api.js`, `beer-runs.js`, and `invites.js`.
- `git diff --check` passed.
- `uv --cache-dir .uv-cache run pytest tests/test_invites.py`: 44 passed.
- `uv --cache-dir .uv-cache run pytest`: 330 passed, 1 pre-existing Argon2/passlib deprecation warning.
- Codex in-app browser smoke check: invalid invite renders one focused dialog with no console errors; 390x844 has no horizontal overflow (`scrollWidth === innerWidth`).

No runtime database or uploaded media files were modified.
