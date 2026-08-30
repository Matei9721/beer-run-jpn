# Spec 016: Delete Account And Personal Data

## Overview

BoozeRunJpn must let an authenticated participant permanently delete their own account without deleting runs or data that belong to other people. The feature adds an account-deletion preflight, password-and-phrase confirmation, ownership blockers, coordinated database and photo cleanup, a non-reusable authentication subject, and a dedicated responsive account settings flow.

## Goals

- Give users a clear summary and deliberate self-service account-deletion flow.
- Remove the deleting user's credentials, memberships, entries, and exclusively owned entry photos across all runs.
- Preserve runs, invites, shared photos, and every other user's data.
- Ensure an old bearer token can never authenticate a later account whose numeric database ID is reused.
- Make database and filesystem failure boundaries explicit, recoverable, and testable with disposable state.

---

## Feature 1: Durable Authentication Identity

**Who & why:** Participants need bearer tokens to remain bound to one account lifetime. Numeric SQLite row IDs may be reused after deletion, so authentication needs a non-reusable identity that is independent of the relational primary key.

### Functional Requirements

#### FR-1.1: Assign A Non-Reusable Authentication Subject

Every user MUST have a non-null, globally unique, opaque authentication subject generated from cryptographically secure randomness. Existing users MUST receive distinct subjects during migration, and signup MUST assign one before issuing a token.

**Verify:** Upgrade a populated disposable database and create new accounts, then confirm every user has a distinct non-empty subject that is not derived from the numeric user ID or username.

#### FR-1.2: Issue And Resolve New-Format Tokens By Authentication Subject

New access tokens MUST use the opaque authentication subject as `sub` and an incremented integer token version. Authentication MUST resolve a user only by exact subject match and MUST NOT fall back to numeric ID or username lookup.

**Verify:** Log in and confirm the token authenticates the matching subject, while tokens with numeric, username, missing, malformed, or nonexistent subjects receive the existing generic `401` response.

#### FR-1.3: Permanently Reject Earlier Token Versions

Deployment of this feature MUST reject every earlier token version, including otherwise valid version-2 numeric-ID tokens. Deleting an account and creating another account with the same username or reused numeric ID MUST never make the deleted account's token valid.

**Verify:** Capture an old token, delete its account, force or observe numeric-ID reuse, create a replacement account, and confirm only the replacement token authenticates.

### Architectural Requirements

#### AR-1.1: Preserve Domain IDs

Keep `users.id` and all existing numeric foreign keys as domain/database identifiers. Add the authentication subject to `models.User`, the ordered migration system in `migrations/versions/` and `migrations/runner.py`, signup, login, and `auth.py`; do not expose it in public API responses or logs.

#### AR-1.2: Preserve Lightweight JWT Boundaries

Continue using the existing HS256, configured secret, 30-day expiry, `OAuth2PasswordBearer`, and generic authentication failure contract from Spec 004. Do not add a session service or revocation table when a random per-account-lifetime subject meets the requirement directly.

---

## Feature 2: Deletion Preflight And Ownership Blockers

**Who & why:** A participant considering deletion needs to understand what will be removed and whether they still own runs. Owners must transfer ownership or deliberately delete a run instead of losing or silently destroying shared data.

### Functional Requirements

#### FR-2.1: Return An Authenticated Deletion Summary

`GET /api/me/deletion-summary` MUST require bearer authentication and return the caller's entry count across all runs, membership count, and owned runs as bounded objects containing only run ID and name. Counts and run details MUST be recomputed from the database and MUST NOT expose other users' entries, identities, membership details, invite codes, or image paths.

**Verify:** Request the summary for a user with entries and memberships in several runs and confirm the exact caller-scoped counts and owned-run list with no unrelated personal data.

#### FR-2.2: Block Every Current Run Owner

`DELETE /api/me` MUST re-query ownership inside the deletion operation. If the caller owns one or more runs, return `409 Conflict` with a stable structured detail containing code `owned_runs_block_deletion`, a corrective message, and each blocking run's ID and name; no rows or files may change.

**Verify:** Attempt deletion as an owner of public and private runs and confirm the complete blocker list and unchanged database/upload state.

#### FR-2.3: Guide Owners To Safe Resolution

The account UI MUST render each blocking run as an actionable item that takes the user to that run's management controls for ownership transfer or run deletion. It MUST NOT offer an account-deletion override, cascade-delete a run, delete an invite, or remove another member's data.

**Verify:** From the blocked dialog, activate each run action and confirm the matching run's management view opens with safe transfer/delete guidance and account deletion remains unavailable.

### Architectural Requirements

#### AR-2.1: Use Stable Structured Errors

Use the existing FastAPI `detail` envelope but provide a documented object for ownership conflicts so the vanilla frontend can act on run IDs without parsing prose. Authentication, validation, and unexpected failures retain sanitized stable status categories.

---

## Feature 3: Confirmed Coordinated Deletion

**Who & why:** A participant who has resolved ownership needs one deliberate operation that proves current control of the account and removes personal data without leaving a partially deleted usable identity.

### Functional Requirements

#### FR-3.1: Require Current Password And Exact Confirmation

`DELETE /api/me` MUST accept a JSON body containing the current password and the exact case-sensitive phrase `DELETE MY ACCOUNT`. Missing or incorrect confirmation MUST return a validation failure; a wrong password MUST return a generic credential failure. Neither failure may mutate database rows or files, invalidate the session, or reveal stored credential state.

**Verify:** Exercise missing, mistyped, wrong-case, wrong-password, and malformed requests and confirm sanitized failures with the account, token, entries, memberships, and photos intact.

#### FR-3.2: Delete Only The Caller's Rows

After rechecking ownership and confirmation, the operation MUST delete the caller's entries across every run, all caller memberships, the password credential, authentication subject, and user row in one database transaction. Runs, invites, other memberships, and all other users and entries MUST remain unchanged.

**Verify:** Delete a non-owner who participates in multiple shared runs and confirm caller rows are absent while all cross-user and run-owned rows are byte-for-byte equivalent in relevant fields.

#### FR-3.3: Remove Only Exclusively Owned Canonical Photos

The operation MUST consider photos referenced by the caller's entries across all runs. It may remove a physical file only when the path is a validated canonical run-scoped upload beneath the configured root and no surviving entry references the normalized path. Missing, legacy, malformed, wrong-run, symlinked, hard-linked, outside-root, shared, and unrelated files MUST be retained safely.

**Verify:** Use a disposable upload tree containing every listed path category across several runs and confirm only provably exclusive canonical caller photos are removed.

#### FR-3.4: Coordinate Files And Database Through Quarantine

Before database mutation, validated exclusive files MUST be moved by same-filesystem rename into a private operation-specific quarantine beneath the configured upload root. Any collection or move failure MUST restore already moved files, leave the database untouched, and return a sanitized non-success response. A database failure MUST roll back all rows and restore quarantined files before returning non-success. After a successful commit the account deletion is authoritative; quarantined files MUST be purged best-effort, and purge failure MUST leave inaccessible orphaned quarantine data rather than restore public files or report that the account still exists.

**Verify:** Inject collection, first/later move, commit, restore, and post-commit purge failures and confirm each response matches the authoritative database state, no live row points at a missing photo, and no other user's file moves.

#### FR-3.5: Return A Stable Success Contract

Successful deletion MUST return a stable response that confirms deletion without echoing username, password, subject, image paths, invite codes, or other personal data. Repeating the request with the deleted token MUST receive the normal generic `401` response.

**Verify:** Delete an account, inspect the response for only the documented confirmation fields, then retry with the same token and confirm `401`.

### Architectural Requirements

#### AR-3.1: Keep Cleanup Direct And Reusable

Extend `upload_cleanup.py` or add one focused sibling module using its existing canonical-path validation and containment rules. Keep the HTTP flow in `auth_routes.py`; do not place filesystem orchestration in schemas, models, or frontend code.

#### AR-3.2: Serialize The Destructive Decision

The ownership check, candidate collection, and explicit row deletions MUST occur under one coordinated SQLite write operation appropriate to this compact single-database app. The implementation MUST document and test the point at which the database becomes authoritative and avoid a race that can create a surviving reference to quarantined media.

#### AR-3.3: Sanitize Secret-Bearing Validation

Extend request-validation sanitization to the account deletion path so FastAPI never echoes submitted password or confirmation values. Application logs and errors MUST omit passwords, confirmation text, auth subjects, invite codes, image contents, and unnecessary personal/path data.

---

## Feature 4: Account Settings Experience And Success Cleanup

**Who & why:** Signed-in users need a discoverable but clearly separated account area where destructive identity deletion cannot be confused with routine logout or run administration.

### Functional Requirements

#### FR-4.1: Provide A Dedicated Account Settings View

Add an authenticated account/settings control and a focused responsive settings module. The view MUST separate `Delete account` from Logout and run management, load the deletion summary on demand, and show entries, memberships, and owned runs before exposing final confirmation.

**Verify:** Open settings on desktop and at 390x844 and confirm the summary, separation, readable hierarchy, touch targets, scrolling, and absence of horizontal overflow.

#### FR-4.2: Provide An Accessible Two-Factor Confirmation Interaction

The final form MUST include a current-password field and an exact typed-confirmation field, keep the destructive submit disabled until the phrase matches, support cancel, Escape, backdrop behavior, status/error announcements, focus containment/restoration, and a non-ambiguous pending state. It MUST never persist either field.

**Verify:** Exercise keyboard and touch open, cancel, wrong phrase, submission, failure, and focus restoration flows on desktop and mobile.

#### FR-4.3: Preserve Session And Private UI On Failure

For validation, wrong-password, ownership, network, or server failure, the browser MUST treat the request as non-success: retain the access token, remembered run selection, current identity and rendered private state, explain the corrective action, and permit a safe retry or cancel.

**Verify:** Inject each failure category and confirm no local or rendered state is cleared and the user remains authenticated.

#### FR-4.4: Clear All Identity-Scoped State On Success

Only after confirmed API success, the browser MUST remove `access_token`, remove the deleted user's remembered-run key, abort in-flight identity/run/entry work, clear pending invite state and invite/run URL parameters, clear cached identity/run/leaderboard/entries and private dialogs/content, and render the logged-out public BeerRunJPN fallback. Ordinary non-private UI preferences MUST remain.

**Verify:** Seed every relevant local, URL, in-memory, and rendered state category, complete deletion, and confirm none remains usable before the public fallback is shown.

### Architectural Requirements

#### AR-4.1: Preserve Frontend Module Boundaries

Keep HTTP calls in `static/js/modules/api.js`, token/auth visibility in `auth.js`, account dialog state in a focused `account-settings.js`, invite reset behavior in `invites.js`, and identity orchestration in `app.js`. Reuse existing picker and accessible dialog patterns without turning the application into a SPA or adding a build step.

#### AR-4.2: Update Static Cache Versions And Inspect Rendered UI

Update all relevant query-string cache versions in `templates/index.html` and module imports. Inspect successful, blocked, cancel, and failure flows in the running app on desktop and a 390x844 mobile viewport using only a disposable database and upload root.

---

## Data Requirements

- Add a unique, indexed, non-null opaque authentication subject to `users` and backfill existing rows through ordered migration 007.
- Preserve numeric primary and foreign keys and all existing run, invite, entry, and membership schemas otherwise.
- Migration must support fresh and populated disposable databases, fail safely, preserve indexes/relationships, and be reported missing by migration readiness checks.
- Account deletion must not modify tracked Wrapped data or any live `boozerun.db`, uploads, `users.json`, or caches during verification.

## Integration Points

- `auth.py`, `auth_routes.py`, `models.py`, and `schemas.py` for token identity and API contracts.
- `migrations/versions/`, `migrations/runner.py`, and migration tests for subject rollout.
- `upload_cleanup.py` for user-scoped candidate validation and quarantine operations.
- `static/js/modules/api.js`, `auth.js`, `invites.js`, a new `account-settings.js`, and `static/js/app.js` for UI orchestration and cleanup.
- `templates/index.html` and `static/css/style.css` for the settings control and responsive accessible dialog.

## Related Specs

| Spec | Relationship | Affected Requirements |
|------|-------------|-----------------------|
| Spec 004: Harden Auth Tokens | **Modifies** - replaces numeric token subjects with per-account subjects and increments the token version | FR-1.1-FR-1.3, AR-1.1-AR-1.2 |
| Spec 005: Add Signup API | **Modifies** - signup must assign an auth subject before issuing a token | FR-1.1-FR-1.2 |
| Spec 010: Update Frontend Auth And Signup | **Extends** - adds account settings and success-only identity cleanup | FR-4.1-FR-4.4 |
| Spec 013: Add Invite UI And Accept Flow | **Modifies** - deletion success must clear pending invite state safely | FR-4.4, AR-4.1 |
| Spec 014: Organize Upload Paths By Beer Run | **References** - reuses canonical run-scoped path safety boundaries | FR-3.3-FR-3.4 |
| Spec 015: Edit And Delete Own Entries | **References** - composes caller-owned entry authorization and cleanup behavior | FR-3.2-FR-3.3 |
| Release 2 Task 03: Transfer Beer-Run Ownership | **Depends on** - owners need a non-destructive resolution before deleting their account | FR-2.3 |
| Release 2 Task 05: Delete A Beer-Run | **References** - reuses run management and destructive confirmation patterns | FR-2.3, FR-4.2 |

## Constraints

- Keep the FastAPI, SQLAlchemy, SQLite, vanilla JavaScript, and static-template architecture with no frontend build step or new framework.
- Preserve public API shapes outside the new endpoints and token-format migration.
- Treat account deletion as permanent; no soft-delete or undo UI is included.
- Verification uses only isolated databases and disposable upload roots.
- Full pytest, focused API/migration/upload tests, JavaScript syntax checks, `git diff --check`, and rendered desktop/mobile verification are required.

## Out Of Scope

- Operator/admin deletion of another user's account.
- Cascading deletion of owned runs or an override around ownership blockers.
- Password reset, username change, session enumeration, or per-device logout.
- Export/download of personal data before deletion.
- Recovery of a deleted account or restoration after the database commit succeeds.
- Removing retained unsafe legacy/malformed/orphan files that cannot be proven exclusive.

## Assumptions And Risks

- Ownership transfer is expected from Release 2 Task 03; if unavailable in the current checkout, blocker guidance may still open run management and offer the implemented delete-run path without weakening the blocker.
- Migrating to the new token version intentionally signs all existing browser sessions out once. The existing rejected-session UX handles reauthentication.
- Cross-resource atomicity is approximated with same-filesystem quarantine plus an explicit database-authoritative commit point; crashes and restore failures require conservative retention and testable recovery behavior.
- SQLite write serialization is sufficient for the app's compact deployment model, but the implementation must not imply distributed transaction guarantees.

## Spec Completeness Checklist

- [x] **Scope & acceptance criteria** - Goals, four feature sections, Constraints, and Out Of Scope define the complete end-to-end boundary.
- [x] **Testing strategy** - Every FR includes a Verify line and Constraints require focused, full-suite, syntax, diff, and browser checks.
- [x] **Existing patterns** - AR-1.2, AR-3.1, AR-4.1, Integration Points, and Related Specs identify current auth, cleanup, picker, and dialog patterns.
- [x] **Dependencies** - No new library is required; Related Specs records ownership-transfer ordering and reusable foundations.
- [x] **Architecture & interfaces** - Endpoint shapes, migration impact, token semantics, module boundaries, and authoritative commit point are specified.
- [x] **Error handling & failure modes** - FR-2.2, FR-3.1, FR-3.4, FR-4.3, and Assumptions And Risks cover conflicts, secrets, rollback, restore, purge, network, and UI failure.
- [x] **Security review** - FR-1.2-FR-1.3, FR-3.1-FR-3.3, AR-3.3, and Constraints cover identity binding, authorization, validation, disclosure, and path isolation.
- [x] **Performance impact** - Caller-scoped indexed queries, bounded metadata, and compact SQLite serialization are explicit; deletion is an infrequent destructive operation.
- [x] **Rollout & migration** - Data Requirements and FR-1.1-FR-1.3 define migration 007, backfill, readiness, and intentional one-time session invalidation.
- [x] **Assumptions & risks** - The dedicated section covers task ordering, session invalidation, cross-resource atomicity, crash recovery, and SQLite limits.
