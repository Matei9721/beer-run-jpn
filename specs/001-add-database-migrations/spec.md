# Feature Specification: Add Database Migrations

**Feature Branch**: `001-add-database-migrations`

**Created**: 2026-05-25

**Status**: Draft

**Input**: User description: "Create the first Release 1 specification from release1_tasks/01_add_database_migrations.md. The feature introduces a real migration path so Release 1 schema changes can be applied safely to the existing local database, with fresh database creation, preservation of existing users and entries, applied-migration tracking, test setup alignment, and app startup behavior that no longer silently hides missing migrations."

## Clarifications

### Session 2026-05-25

- Q: How should the migration path handle an existing database that already has the current users and entries tables but no migration history? -> A: Treat it as the starting baseline automatically and preserve existing data.
- Q: What should app startup do when required migrations are missing? -> A: Block startup with a clear migration-required error.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Safely Prepare Existing Data For Release 1 (Priority: P1)

As the app owner, I want an existing trip database to be brought up to the Release 1 schema without losing users or entries, so I can deploy schema changes with confidence.

**Why this priority**: Protecting existing trip data is the highest-value outcome and the main risk this feature is meant to remove.

**Independent Test**: Can be fully tested by applying the migration path to a copy of the existing database and verifying that all users and entries remain present afterward.

**Acceptance Scenarios**:

1. **Given** a copy of the current database with users and entries but no migration history, **When** the migration path is applied, **Then** the database is accepted as the starting baseline, marked as migrated, and all original users and entries remain available.
2. **Given** a database that has already been migrated, **When** the migration path is applied again, **Then** no duplicate schema changes occur and existing user data remains unchanged.
3. **Given** a database that cannot be migrated cleanly, **When** the app owner attempts migration, **Then** the failure is visible and no silent partial success is reported.

---

### User Story 2 - Create A Fresh Release 1 Database (Priority: P2)

As a developer or deployer, I want a fresh environment to be initialized from the same migration source, so new installations and tests start with the intended Release 1 schema.

**Why this priority**: Fresh setup must match upgraded setup, otherwise test and deployment environments can drift.

**Independent Test**: Can be fully tested by starting from an empty database location, applying the migration path, and verifying the expected baseline schema and migration history are present.

**Acceptance Scenarios**:

1. **Given** no existing database at the target location, **When** the migration path is applied, **Then** a usable database is created with the required user, entry, and migration-history structures.
2. **Given** a newly created database, **When** the app starts against it, **Then** startup succeeds because the database is at the expected migration state.

---

### User Story 3 - Detect Missing Schema Updates During Startup (Priority: P3)

As the app owner, I want startup to reveal when required migrations have not been applied, so the app does not appear healthy while using an outdated schema.

**Why this priority**: Clear startup feedback reduces deployment risk once the safe migration path exists.

**Independent Test**: Can be fully tested by starting the app against an intentionally outdated database and confirming that the startup result clearly indicates the missing migration state.

**Acceptance Scenarios**:

1. **Given** a database missing required migration history, **When** the app starts, **Then** startup is blocked and clearly reports that migration work is required.
2. **Given** a database at the current migration state, **When** the app starts, **Then** startup proceeds normally without modifying protected runtime data unexpectedly.

### Edge Cases

- The migration path is run more than once against the same database.
- The target database is empty or does not exist yet.
- The target database contains current users and entries but no recorded migration history; it should be accepted as the starting baseline when the current baseline schema matches.
- A migration fails partway through and must leave users and entries protected from accidental deletion or overwrite.
- Tests run in isolation and must not read from or write to the live trip database.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a repeatable migration path that can be invoked by developers and deployers before running Release 1 code.
- **FR-002**: The system MUST be able to create a fresh database from the migration path without requiring a separate schema creation mechanism.
- **FR-003**: The system MUST preserve existing users and entries when applying the migration path to a copy of the current database.
- **FR-004**: The system MUST record which migrations have been successfully applied so repeated runs can identify completed work.
- **FR-005**: The system MUST avoid applying the same migration more than once to the same database.
- **FR-006**: The system MUST make migration failures visible to the person running the app or migration path.
- **FR-007**: The app MUST block startup with a clear migration-required error when a database is missing required migrations.
- **FR-008**: Automated tests MUST initialize their database state from the same migration source used for fresh setup and upgrades.
- **FR-009**: Existing tests MUST continue to pass after the migration path is introduced.
- **FR-010**: The migration approach MUST remain small and local to this repository for Release 1.
- **FR-011**: The system MUST treat an existing database with the current baseline user and entry structures, but no migration history, as the starting baseline and record the baseline migration without recreating or overwriting existing data.

### Key Entities *(include if feature involves data)*

- **Migration**: A named, ordered schema change that can be applied to bring a database toward the Release 1 schema.
- **Applied Migration Record**: A durable record that a migration has completed successfully for a specific database.
- **User**: Existing account data that must remain available after migration.
- **Entry**: Existing trip or drink log data that must remain available after migration.

## Constitution & Operational Impact *(mandatory)*

- **Touched state**: Source files, test setup, migration files, and database schema state. Runtime databases are read or migrated only through an explicit migration action.
- **Runtime data protection**: `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and local caches must not be deleted, reset, overwritten, or committed. Migration validation must use copies or isolated test databases unless the user directly instructs otherwise.
- **Auth/API impact**: No intended change to authentication behavior, password handling, bearer-token requirements, or public response shapes. Existing users must remain able to authenticate after migration.
- **Mobile/performance impact**: No intended change to mobile UI, geolocation, uploads, image behavior, cache-busting, or HTTPS requirements.
- **Verification required**: Focused migration tests plus the full project test command, `uv --cache-dir .uv-cache run pytest`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of users and entries in a representative copy of the current database remain present after migration.
- **SC-002**: A fresh database can be initialized and accepted by app startup in one documented migration run.
- **SC-003**: Re-running the migration path on an already migrated database completes without duplicating schema changes or altering existing users and entries.
- **SC-004**: An outdated database state prevents normal app startup and reports that migration is required before app use proceeds.
- **SC-005**: The complete automated test suite passes after the migration path is introduced.

## Assumptions

- Release 1 starts from the current user and entry data model as the initial baseline.
- The live trip database is protected runtime data; validation should use a copy unless the user explicitly approves direct migration.
- The migration path is intended for this repository and Release 1 scope, not as a general-purpose migration platform.
- No user-facing UI changes are required for this feature.
