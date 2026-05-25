# Tasks: Add Database Migrations

**Input**: Design documents from `/specs/001-add-database-migrations/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/migration-runner.md, quickstart.md

**Tests**: Required because this feature changes database schema handling, scripts, app startup behavior, and test database setup.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the local migration package and command entry points without changing runtime behavior yet.

- [x] T001 Create the migration package directories and marker files in `migrations/__init__.py`, `migrations/versions/__init__.py`
- [x] T002 Create an empty migration runner module scaffold in `migrations/runner.py`
- [x] T003 Create an empty initial migration module scaffold in `migrations/versions/001_initial_schema.py`
- [x] T004 Create the migration command scaffold with argument parsing for `--database` and `--check` in `scripts/migrate_db.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared migration primitives that every user story depends on.

**Critical**: No user story work can begin until this phase is complete.

- [x] T005 Define migration identifiers, ordered migration registry, and migration result types in `migrations/runner.py`
- [x] T006 Implement SQLite connection/path helpers for explicit database paths in `migrations/runner.py`
- [x] T007 Implement `schema_migrations` table creation and applied-version lookup in `migrations/runner.py`
- [x] T008 Implement migration recording that writes a version only after successful apply or baseline adoption in `migrations/runner.py`
- [x] T009 Add migration-specific exception classes and user-facing error messages in `migrations/runner.py`
- [x] T010 [P] Add shared SQLite inspection test helpers in `tests/test_migrations.py`

**Checkpoint**: Foundation ready. User story implementation can begin.

---

## Phase 3: User Story 1 - Safely Prepare Existing Data For Release 1 (Priority: P1) MVP

**Goal**: Apply the migration path to a copy of the current database, accept the existing current schema as the starting baseline, and preserve users and entries.

**Independent Test**: Apply migrations to a test database that already contains current `users` and `entries` tables but no migration history, then verify the baseline is recorded and rows are preserved.

### Tests for User Story 1

- [x] T011 [P] [US1] Add a baseline-adoption test for an existing current-schema database in `tests/test_migrations.py`
- [x] T012 [P] [US1] Add an idempotency test that re-runs migrations without duplicating schema changes or altering rows in `tests/test_migrations.py`
- [x] T013 [P] [US1] Add a failed-migration safety test that verifies failed migrations are not recorded in `tests/test_migrations.py`

### Implementation for User Story 1

- [x] T014 [US1] Implement baseline table/column detection for current `users` and `entries` structures in `migrations/versions/001_initial_schema.py`
- [x] T015 [US1] Implement baseline adoption that records `001_initial_schema` without recreating current tables in `migrations/runner.py`
- [x] T016 [US1] Implement ordered migration application and idempotent no-op behavior for applied migrations in `migrations/runner.py`
- [x] T017 [US1] Wire apply mode in `scripts/migrate_db.py` to run migrations and return non-zero on visible failure

**Checkpoint**: User Story 1 is independently functional and protects existing data copies.

---

## Phase 4: User Story 2 - Create A Fresh Release 1 Database (Priority: P2)

**Goal**: Create a fresh database from migrations and make tests initialize schema from the same migration source.

**Independent Test**: Start from an empty database path, run migrations, verify baseline schema and migration history exist, and confirm app tests use migrated schema.

### Tests for User Story 2

- [x] T018 [P] [US2] Add a fresh-database migration test that verifies `users`, `entries`, and `schema_migrations` are created in `tests/test_migrations.py`
- [x] T019 [P] [US2] Add or update an app startup/test-client fixture test that proves the test database is initialized through migrations in `tests/conftest.py` and `tests/test_main.py`

### Implementation for User Story 2

- [x] T020 [US2] Implement fresh baseline schema creation for `users`, `entries`, indexes, and relationships in `migrations/versions/001_initial_schema.py`
- [x] T021 [US2] Update `tests/conftest.py` to initialize the test database through `migrations.runner` instead of `Base.metadata.create_all`
- [x] T022 [US2] Update `scripts/setup_db.py` so schema preparation runs through the migration runner before syncing `users.json`
- [x] T023 [US2] Update `scripts/manage_users.py` so user management requires or verifies migrated schema instead of implicitly calling `models.Base.metadata.create_all`

**Checkpoint**: User Stories 1 and 2 both work independently: existing database copies are preserved, and fresh/test databases are created from migrations.

---

## Phase 5: User Story 3 - Detect Missing Schema Updates During Startup (Priority: P3)

**Goal**: Block app startup with a clear migration-required error when a database is genuinely behind the required migration state.

**Independent Test**: Start readiness validation against an intentionally outdated database and verify startup/check mode fails clearly before normal app use.

### Tests for User Story 3

- [x] T024 [P] [US3] Add check-mode contract tests for migrated and outdated databases in `tests/test_migrations.py`
- [x] T025 [P] [US3] Add an app startup readiness test for missing required migration history in `tests/test_main.py`

### Implementation for User Story 3

- [x] T026 [US3] Implement read-only migration readiness validation and check-mode exit behavior in `migrations/runner.py`
- [x] T027 [US3] Wire `scripts/migrate_db.py --check` to validation-only mode with clear migration-required output
- [x] T028 [US3] Replace import-time `models.Base.metadata.create_all(bind=engine)` in `main.py` with migration readiness validation that blocks startup on missing required migrations
- [x] T029 [US3] Ensure startup readiness validation does not apply pending migrations or mutate protected runtime data in `main.py`

**Checkpoint**: All user stories are independently functional and app startup no longer silently hides missing migrations.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quickstart validation, and final safety checks.

- [x] T030 [P] Update database setup and migration usage documentation in `README.md`
- [x] T031 [P] Update repository migration guidance in `repository_rules.md`
- [x] T032 Run quickstart fresh database validation command from `specs/001-add-database-migrations/quickstart.md`
- [x] T033 Run quickstart existing-data validation against a copy of `boozerun.db` from `specs/001-add-database-migrations/quickstart.md`
- [x] T034 Run the full verification command `uv --cache-dir .uv-cache run pytest`
- [x] T035 Verify `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and local caches were not deleted, reset, overwritten, or staged without explicit instruction

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies, can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can be implemented after or alongside US1 once shared runner primitives exist.
- **User Story 3 (Phase 5)**: Depends on Foundational completion; startup integration is safest after US1 and US2 migration behavior is stable.
- **Polish (Phase 6)**: Depends on desired user stories being complete.

### User Story Dependencies

- **US1 Safely Prepare Existing Data**: MVP and highest priority. Establishes baseline adoption and idempotency.
- **US2 Create Fresh Database**: Uses the same runner and initial migration to create empty databases and align tests.
- **US3 Detect Missing Schema Updates**: Uses runner readiness checks and integrates them into app startup.

### Within Each User Story

- Write the listed tests first and confirm they fail for the missing behavior.
- Implement migration/version behavior before wiring scripts or startup.
- Validate each story at its checkpoint before moving to the next priority.

### Parallel Opportunities

- T010 can run in parallel with foundational runner primitives after test file creation decisions are clear.
- T011, T012, and T013 can be drafted in parallel because they target separate migration behaviors in the same test module but should be merged carefully.
- T018 and T019 can be drafted in parallel because they cover migration creation and app test setup.
- T024 and T025 can be drafted in parallel because they cover CLI/check behavior and startup behavior.
- T030 and T031 can be completed in parallel during polish.

---

## Parallel Example: User Story 1

```text
Task: "T011 [US1] Add a baseline-adoption test for an existing current-schema database in tests/test_migrations.py"
Task: "T012 [US1] Add an idempotency test that re-runs migrations without duplicating schema changes or altering rows in tests/test_migrations.py"
Task: "T013 [US1] Add a failed-migration safety test that verifies failed migrations are not recorded in tests/test_migrations.py"
```

---

## Parallel Example: User Story 2

```text
Task: "T018 [US2] Add a fresh-database migration test that verifies users, entries, and schema_migrations are created in tests/test_migrations.py"
Task: "T019 [US2] Add or update an app startup/test-client fixture test that proves the test database is initialized through migrations in tests/conftest.py and tests/test_main.py"
```

---

## Parallel Example: User Story 3

```text
Task: "T024 [US3] Add check-mode contract tests for migrated and outdated databases in tests/test_migrations.py"
Task: "T025 [US3] Add an app startup readiness test for missing required migration history in tests/test_main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational migration primitives.
3. Complete Phase 3 for US1.
4. Stop and validate US1 against an isolated database that mimics the current `boozerun.db` schema.

### Incremental Delivery

1. Add US1 so existing database copies can be baselined safely.
2. Add US2 so fresh/test databases come from migrations.
3. Add US3 so startup blocks genuinely outdated databases.
4. Complete polish documentation and quickstart validation.

### Safety Notes

- Do not run destructive operations against `boozerun.db`.
- Use temporary databases or copies for migration validation.
- Do not add Alembic or a new migration framework for Release 1.
- No browser inspection is required unless later tasks introduce frontend changes.
