# Feature Specification: Backfill Existing Trip

**Feature Branch**: `003-backfill-existing-trip`

**Created**: 2026-05-25

**Status**: Draft

**Input**: User description: "Write the specification for release1_tasks/03_backfill_existing_trip.md. The feature backfills the current single global trip into the new beer-run backend and database schema. The app must still work the same from the user's point of view after the schema change, so the rest of the app should be updated wherever needed to keep the current UI behavior working."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Preserve Existing Trip Data In BeerRunJPN (Priority: P1)

As an existing Beer Run JPN user, I want all historical users and entries to remain available after the new beer-run data model is introduced, so the current trip history is not lost or split across unknown runs.

**Why this priority**: Data continuity is the main purpose of this task. If historical entries or users are not associated with the default run, the app cannot preserve the current trip experience.

**Independent Test**: Can be fully tested with a representative pre-backfill database containing multiple users and entries, then confirming one public run named BeerRunJPN contains all of them after backfill.

**Acceptance Scenarios**:

1. **Given** an existing database with users and entries but no populated default beer-run, **When** the backfill is applied, **Then** exactly one beer-run named BeerRunJPN exists for the historical trip.
2. **Given** existing entries before backfill, **When** the backfill completes, **Then** every existing entry belongs to BeerRunJPN.
3. **Given** existing users before backfill, **When** the backfill completes, **Then** every existing user is a member of BeerRunJPN.
4. **Given** an existing user named Tamei, **When** the backfill completes, **Then** Tamei is an owner of BeerRunJPN.
5. **Given** the migrated data is inspected, **When** public runs are listed, **Then** BeerRunJPN is the only public run created by this backfill.

---

### User Story 2 - Keep Existing App Behavior Working (Priority: P2)

As a returning user, I want login, entry creation, entry listing, leaderboard totals, and existing trip pages to work as they did before, so the backend schema change does not interrupt normal use of the app.

**Why this priority**: The user-facing application must remain stable while the backend moves from a single global dataset to run-scoped data.

**Independent Test**: Can be fully tested by completing the same primary app flows before and after migration and confirming the visible results match for the existing Beer Run JPN trip.

**Acceptance Scenarios**:

1. **Given** a user account that could log in before migration, **When** the user logs in after migration, **Then** login succeeds with the same credentials.
2. **Given** historical entries existed before migration, **When** a user views the existing entry list or trip views after migration, **Then** those entries are still visible in the same user-facing context.
3. **Given** leaderboard totals before migration, **When** the BeerRunJPN leaderboard is viewed after migration, **Then** the totals match the previous global totals.
4. **Given** a logged-in user creates a new entry using the existing UI after migration, **When** the entry is saved, **Then** it appears in the same visible trip experience and belongs to BeerRunJPN.
5. **Given** existing public read-only views are used after migration, **When** the views load, **Then** they show BeerRunJPN data without requiring users to choose a run first.

---

### User Story 3 - Support Safe Local Retry (Priority: P3)

As the app maintainer, I want the backfill to be safe to rerun locally, so interrupted or repeated setup attempts do not create duplicate runs, duplicate memberships, or changed totals.

**Why this priority**: Local deployments and small-device setup often involve manual retries. The backfill must protect existing data from duplication.

**Independent Test**: Can be fully tested by applying the backfill more than once to the same migrated database and confirming all counts, roles, visibility, and totals remain stable.

**Acceptance Scenarios**:

1. **Given** BeerRunJPN already exists, **When** the backfill is rerun, **Then** no duplicate BeerRunJPN run is created.
2. **Given** users are already members of BeerRunJPN, **When** the backfill is rerun, **Then** no duplicate memberships are created.
3. **Given** entries already belong to BeerRunJPN, **When** the backfill is rerun, **Then** their run assignment remains valid and totals do not change.
4. **Given** BeerRunJPN already has Tamei as owner, **When** the backfill is rerun, **Then** Tamei remains owner and other users are not incorrectly promoted.

### Edge Cases

- The existing database contains no entries; BeerRunJPN should still be created and existing users should still become members.
- The existing database contains no users; BeerRunJPN should still be created without inventing user accounts.
- The existing database does not contain a user named Tamei; historical data should still be assigned to BeerRunJPN and the missing owner condition should be reported clearly for operator action.
- BeerRunJPN already exists from a partial previous attempt; the backfill should reuse it instead of creating another run.
- Some entries already have a valid BeerRunJPN assignment from a partial previous attempt; the backfill should leave them valid and fill only missing historical assignments.
- A user already has a BeerRunJPN membership; the backfill should leave that membership unique and ensure the correct role for Tamei.
- Other beer-runs may exist in a development database; this backfill should not move their already assigned entries into BeerRunJPN.
- Existing upload files, timestamps, users, passwords, and entry details must not be changed as a side effect of assigning run context.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST create or identify one default beer-run named BeerRunJPN for the existing historical trip.
- **FR-002**: The BeerRunJPN run created or used by the backfill MUST be public/readable.
- **FR-003**: Immediately after backfill on the existing single-trip dataset, BeerRunJPN MUST be the only public beer-run created by the backfill.
- **FR-004**: The system MUST add every existing user as a member of BeerRunJPN.
- **FR-005**: The system MUST assign the existing Tamei user the owner role for BeerRunJPN when that user exists.
- **FR-006**: Existing non-owner users added by the backfill MUST have a member role unless they already have a valid BeerRunJPN role that should be preserved.
- **FR-007**: The system MUST assign every existing unassigned historical entry to BeerRunJPN.
- **FR-008**: The system MUST preserve all existing user credentials and authentication behavior.
- **FR-009**: The system MUST preserve all existing entry details, including owner/user association, drink data, location data, notes, timestamps, image references, and any other user-visible fields.
- **FR-010**: Existing entry lists, public trip views, authenticated entry creation, and leaderboard displays MUST continue to show the current Beer Run JPN trip without requiring users to manually select a run.
- **FR-011**: Leaderboard totals for BeerRunJPN after backfill MUST match the previous global leaderboard totals for the same source data.
- **FR-012**: New entries created through the existing UI after the backfill MUST be associated with BeerRunJPN unless a later feature explicitly introduces run selection.
- **FR-013**: The backfill MUST be safe to retry without creating duplicate BeerRunJPN runs.
- **FR-014**: The backfill MUST be safe to retry without creating duplicate BeerRunJPN memberships.
- **FR-015**: The backfill MUST be safe to retry without changing already valid BeerRunJPN entry assignments or altering leaderboard totals.
- **FR-016**: The system MUST provide clear failure or operator feedback when the backfill cannot satisfy required ownership because the Tamei user is missing.
- **FR-017**: The backfill MUST not delete, reset, or replace runtime data files as part of normal operation.
- **FR-018**: The feature MUST include verification using a representative pre-backfill database with existing users and entries.

### Key Entities *(include if feature involves data)*

- **BeerRunJPN**: The default public beer-run representing the existing historical Beer Run JPN trip.
- **User**: An existing account that must keep its login behavior and become a BeerRunJPN member during backfill.
- **Tamei User**: The existing user account that must be assigned the BeerRunJPN owner role when present.
- **Entry**: An existing drink or trip record that must keep its current details and gain a BeerRunJPN association.
- **Beer-Run Membership**: The relationship that records an existing user's participation in BeerRunJPN and their role.

## Constitution & Operational Impact *(mandatory)*

- **Touched state**: Source files, migration or data-migration files, tests, database schema/data state, and app flows that read or write entries.
- **Runtime data protection**: `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and local caches must not be deleted, reset, overwritten, or committed. Runtime data may only be changed through an explicit migration/backfill path or isolated test copies.
- **Auth/API impact**: Existing credentials, password hashing, token behavior, and login requirements must remain unchanged. Existing public and authenticated response shapes should remain compatible unless a run field is already expected by the new schema work.
- **Mobile/performance impact**: Existing mobile trip screens, entry submission, image display, and leaderboard views should look and behave the same. Current trip-scale views should remain responsive after adding the BeerRunJPN association.
- **Verification required**: Focused backfill tests using representative pre-backfill data, retry/idempotency tests, tests for login/data continuity where practical, leaderboard total checks, and the full project test command, `uv --cache-dir .uv-cache run pytest`. Browser inspection is required only if app route or template behavior changes affect visible UI.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of existing entries in representative pre-backfill test data belong to BeerRunJPN after backfill.
- **SC-002**: 100% of existing users in representative pre-backfill test data are BeerRunJPN members after backfill.
- **SC-003**: When a Tamei user exists, 100% of backfill runs assign Tamei as a BeerRunJPN owner.
- **SC-004**: Re-running the backfill three consecutive times leaves exactly one BeerRunJPN run and one BeerRunJPN membership per existing user.
- **SC-005**: BeerRunJPN leaderboard totals after backfill match the pre-backfill global totals for the same representative data.
- **SC-006**: 100% of existing login test accounts that worked before backfill still authenticate after backfill.
- **SC-007**: A new entry created through the existing app flow after backfill appears in BeerRunJPN and is included in BeerRunJPN totals.
- **SC-008**: Immediately after backfill of the single-trip dataset, exactly one public beer-run exists: BeerRunJPN.
- **SC-009**: The complete automated test suite passes after the backfill and app compatibility updates are introduced.

## Assumptions

- The beer-run schema from the previous task exists before this backfill is applied.
- The current production-like dataset represents one historical trip, and that trip should become BeerRunJPN.
- Existing users are intended to see the same default trip experience after migration, with BeerRunJPN selected implicitly until a later feature introduces explicit run selection.
- Tamei is expected to exist in the real dataset and should be the BeerRunJPN owner.
- If Tamei is absent in a non-production or partial database, the backfill should not invent that account.
- This task updates app behavior only as needed to preserve the current UI and flows; broader multi-run selection, private-run authorization, and run-management screens are future work.
