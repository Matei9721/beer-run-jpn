# Feature Specification: Add Beer-Run Schema

**Feature Branch**: `002-add-beer-run-schema`

**Created**: 2026-05-25

**Status**: Draft

**Input**: User description: "Create the second Release 1 specification from release1_tasks/02_add_beer_run_schema.md. The feature adds beer-run data structures for runs, memberships with owner and member roles, private-by-default visibility with BeerRunJPN as the only public run, entry-to-run association, duplicate membership protection, common lookup support, and a schema migration."

## Clarifications

### Session 2026-05-25

- Q: How should BeerRunJPN memberships be created for existing migrated data? -> A: Task 03 backfill will add every existing user as a BeerRunJPN member and set Tamei as owner.
- Q: Should Release 1 forbid public beer-runs other than BeerRunJPN? -> A: Multiple public beer-runs are allowed, but BeerRunJPN is the only public run created by migration.
- Q: Should beer-run names be unique? -> A: Beer-run names must be unique.
- Q: Must every beer-run have an owner? -> A: Every beer-run must have at least one owner membership.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Organize Entries Into Beer-Runs (Priority: P1)

As a trip participant, I want each drink entry to belong to a specific beer-run, so entries can be grouped by the shared run they were created for.

**Why this priority**: Entry grouping is the core capability this schema enables and must exist before memberships or visibility rules can be useful.

**Independent Test**: Can be fully tested by creating a beer-run, creating entries for that run, and confirming each entry is associated with exactly one valid run.

**Acceptance Scenarios**:

1. **Given** a beer-run exists, **When** a participant creates an entry for that run, **Then** the entry is associated with that beer-run.
2. **Given** an entry exists, **When** its details are inspected, **Then** the associated beer-run can be identified.
3. **Given** no valid beer-run is available for a new entry after beer-run assignment is active, **When** the entry is created, **Then** the entry is rejected rather than becoming ungrouped.

---

### User Story 2 - Manage Beer-Run Memberships (Priority: P2)

As a beer-run owner, I want users to be members of one or more beer-runs with a clear role in each run, so the app can represent shared runs without duplicating user accounts.

**Why this priority**: Memberships define who belongs to each run and support future authorization and collaboration behavior.

**Independent Test**: Can be fully tested by assigning one user to multiple beer-runs, assigning multiple users to one beer-run, and confirming each membership carries one allowed role.

**Acceptance Scenarios**:

1. **Given** one user and two beer-runs, **When** the user is added to both beer-runs, **Then** the user belongs to both runs.
2. **Given** two users and one beer-run, **When** both users are added to that beer-run, **Then** the beer-run contains both users.
3. **Given** a user is added to a beer-run, **When** the membership is recorded, **Then** the membership role is either owner or member.
4. **Given** a user already belongs to a beer-run, **When** the same user is added to that same run again, **Then** the duplicate membership is rejected.
5. **Given** a beer-run exists, **When** its memberships are inspected, **Then** at least one membership has the owner role.

---

### User Story 3 - Support Public And Private Runs (Priority: P3)

As the app owner, I want new beer-runs to be private by default while preserving BeerRunJPN as the only public run created by migration, so Release 1 can introduce multi-run structure without exposing new runs unexpectedly.

**Why this priority**: Privacy defaults protect future runs and preserve the current public trip behavior as a deliberate exception.

**Independent Test**: Can be fully tested by creating a new beer-run and confirming it is private unless explicitly marked public, then confirming the migrated state creates BeerRunJPN as the only public run.

**Acceptance Scenarios**:

1. **Given** a new beer-run is created without a visibility choice, **When** it is saved, **Then** it is private by default.
2. **Given** the Release 1 seed or migration state includes BeerRunJPN, **When** public beer-runs are listed or counted immediately after migration, **Then** BeerRunJPN is the only public run.
3. **Given** another beer-run exists, **When** its visibility is not explicitly changed to public, **Then** it remains private.
4. **Given** existing entries are migrated into BeerRunJPN by the backfill task, **When** BeerRunJPN memberships are inspected, **Then** every existing user is a member and Tamei has the owner role.

### Edge Cases

- A user belongs to several beer-runs and must remain a distinct member in each one.
- Several users belong to the same beer-run and must each have exactly one membership for that run.
- A duplicate membership is attempted through any supported data path.
- A beer-run would be left without any owner membership.
- A beer-run is created or renamed to a name already used by another beer-run.
- An entry references a beer-run that does not exist.
- A new beer-run is created without an explicit visibility value.
- Existing entries from before beer-runs are introduced must have a valid beer-run assignment after the Task 03 backfill.
- Existing users must become BeerRunJPN members during the backfill task, with Tamei assigned as owner.
- Only one public run, BeerRunJPN, is expected immediately after Release 1 migration, while later explicitly public runs remain representable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST represent beer-runs as durable groupings for entries and members.
- **FR-002**: The system MUST represent a membership between a user and a beer-run.
- **FR-003**: A user MUST be able to belong to multiple beer-runs.
- **FR-004**: A beer-run MUST be able to contain multiple users.
- **FR-005**: Each membership MUST have exactly one role from the allowed Release 1 roles: owner or member.
- **FR-006**: The system MUST reject duplicate memberships for the same user in the same beer-run.
- **FR-007**: Each entry MUST belong to exactly one valid beer-run once the schema and Task 03 backfill sequence is complete.
- **FR-008**: The system MUST make the beer-run for an entry discoverable from the entry.
- **FR-009**: The system MUST make the entries for a beer-run discoverable from the beer-run.
- **FR-010**: New beer-runs MUST be private by default unless explicitly made public.
- **FR-011**: The migrated Release 1 state MUST create BeerRunJPN as the only public beer-run, while allowing other beer-runs to be explicitly marked public later.
- **FR-012**: The schema change MUST be delivered through the existing migration path so fresh databases and upgraded databases reach the same beer-run-capable state.
- **FR-013**: Existing users and entries MUST be preserved when the beer-run schema is applied to an existing database through the approved migration path.
- **FR-014**: The system MUST support efficient lookup of a user's beer-runs, a beer-run's members, a beer-run's entries, and public beer-runs.
- **FR-015**: The schema MUST support the follow-on backfill task adding every existing user as a BeerRunJPN member and assigning Tamei as BeerRunJPN owner.
- **FR-016**: Beer-run names MUST be unique so the same name cannot identify more than one beer-run.
- **FR-017**: Every beer-run MUST have at least one owner membership.

### Key Entities *(include if feature involves data)*

- **Beer-Run**: A uniquely named run that groups entries and memberships. It has a visibility state indicating whether it is public or private.
- **Beer-Run Membership**: A relationship between one user and one beer-run, with a role of owner or member. A user can have at most one membership per beer-run.
- **User**: An existing account that can belong to zero or more beer-runs through memberships.
- **Entry**: An existing drink or trip log item that belongs to exactly one beer-run after this schema and the Task 03 backfill sequence are complete.

## Constitution & Operational Impact *(mandatory)*

- **Touched state**: Source files, migration files, tests, and database schema state.
- **Runtime data protection**: `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and local caches must not be deleted, reset, overwritten, or committed. Existing runtime data must be migrated only through the explicit migration path or isolated test copies.
- **Auth/API impact**: No intended change to password handling, token behavior, or existing authentication requirements. This feature prepares beer-run ownership and membership data for later authorization work but does not grant new unauthenticated write access.
- **Mobile/performance impact**: No intended change to mobile UI, geolocation, uploads, image behavior, cache-busting, or HTTPS requirements. Lookup support should keep common trip views responsive for the current local trip scale.
- **Verification required**: Focused schema and migration tests for memberships, roles, default privacy, entry-to-run assignment, duplicate rejection, and BeerRunJPN public visibility, plus the full project test command, `uv --cache-dir .uv-cache run pytest`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of entries in a representative database have exactly one valid beer-run assignment after this schema and the Task 03 backfill sequence are complete.
- **SC-002**: A test user can belong to at least two beer-runs without duplicating the user account.
- **SC-003**: A test beer-run can contain at least two distinct users with valid owner or member roles.
- **SC-004**: 100% of duplicate membership attempts for the same user and beer-run are rejected before duplicate data is stored.
- **SC-005**: 100% of newly created beer-runs without an explicit visibility choice are private.
- **SC-006**: Immediately after Release 1 migration, the state identifies exactly one public beer-run, BeerRunJPN, while the schema can still represent additional explicitly public beer-runs later.
- **SC-007**: The schema can represent every existing user as a BeerRunJPN member and Tamei as BeerRunJPN owner during the follow-on backfill.
- **SC-008**: 100% of attempts to create or rename a beer-run to an already-used name are rejected before duplicate run names are stored.
- **SC-009**: 100% of beer-runs in schema and migration tests have at least one owner membership.
- **SC-010**: The complete automated test suite passes after the beer-run schema is introduced.

## Assumptions

- The database migration feature from the previous Release 1 task is available and is the approved path for schema changes.
- Existing entries should be assigned to BeerRunJPN during migration so historical trip data remains grouped and usable.
- Task 03 owns the data backfill details: every existing user becomes a BeerRunJPN member, every existing entry is assigned to BeerRunJPN, and Tamei is the BeerRunJPN owner.
- BeerRunJPN is the initial public run for Release 1; additional public runs are not created by this task's migration but remain valid future data.
- This feature introduces data representation only; user-facing beer-run management screens and full membership authorization behavior are separate future work.
