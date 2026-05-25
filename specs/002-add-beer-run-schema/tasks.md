# Tasks: Add Beer-Run Schema

**Input**: Design documents from `/specs/002-add-beer-run-schema/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required because this feature changes database models and migrations.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing migration foundation and add the new migration shell.

- [X] T001 Review current migration runner ordering and baseline behavior in migrations/runner.py and migrations/versions/001_initial_schema.py
- [X] T002 Create migration module skeleton with ID, DESCRIPTION, baseline detection placeholder, and apply entry point in migrations/versions/002_add_beer_run_schema.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared entities and migration registration that every user story depends on.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 Register 002_add_beer_run_schema after 001_initial_schema in migrations/runner.py
- [X] T004 Add BeerRun and BeerRunMember imports, constraints, indexes, and relationships scaffold in models.py
- [X] T005 Add User.memberships and Entry.beer_run relationship scaffolds in models.py
- [X] T006 [P] Add migration helper assertions for beer_runs, beer_run_members, indexes, and entries.beer_run_id to tests/test_migrations.py
- [X] T007 [P] Add shared BeerRun/BeerRunMember fixture helpers for valid owner-backed runs in tests/test_beer_run_schema.py

**Checkpoint**: Foundation ready - schema entities are registered and story-specific tests can be added.

---

## Phase 3: User Story 1 - Organize Entries Into Beer-Runs (Priority: P1) MVP

**Goal**: Entries can be associated with a valid beer-run and discovered from either side of the relationship.

**Independent Test**: Create a beer-run, create entries for that run, and confirm each entry has exactly one valid beer-run relationship.

### Tests for User Story 1

- [X] T008 [P] [US1] Add migration test that fresh databases contain entries.beer_run_id with a foreign-key path to beer_runs in tests/test_migrations.py
- [X] T009 [P] [US1] Add model test for creating a beer-run with two entries and reading entries through the beer-run relationship in tests/test_beer_run_schema.py
- [X] T010 [P] [US1] Add model test for reading an entry's beer-run relationship and rejecting an invalid beer_run_id when foreign keys are enabled in tests/test_beer_run_schema.py

### Implementation for User Story 1

- [X] T011 [US1] Implement beer_runs table creation and entries.beer_run_id addition in migrations/versions/002_add_beer_run_schema.py
- [X] T012 [US1] Implement Entry.beer_run_id column and Entry.beer_run relationship in models.py
- [X] T013 [US1] Implement BeerRun.entries relationship in models.py
- [X] T014 [US1] Ensure tests create entries with valid beer_run_id where required in tests/conftest.py and tests/test_beer_run_schema.py

**Checkpoint**: User Story 1 is independently testable with model and migration tests.

---

## Phase 4: User Story 2 - Manage Beer-Run Memberships (Priority: P2)

**Goal**: Users can belong to multiple beer-runs, beer-runs can contain multiple users, memberships have owner/member roles, duplicate memberships are rejected, and valid runs have at least one owner.

**Independent Test**: Assign one user to two beer-runs, assign two users to one beer-run, verify roles, verify duplicate rejection, and verify valid fixtures include an owner.

### Tests for User Story 2

- [X] T015 [P] [US2] Add model test for one user belonging to two beer-runs in tests/test_beer_run_schema.py
- [X] T016 [P] [US2] Add model test for two users belonging to one beer-run with owner/member roles in tests/test_beer_run_schema.py
- [X] T017 [P] [US2] Add duplicate membership rejection test for the same user and beer-run in tests/test_beer_run_schema.py
- [X] T018 [P] [US2] Add invalid membership role rejection test in tests/test_beer_run_schema.py
- [X] T019 [P] [US2] Add owner-presence validation test for valid beer-run fixtures in tests/test_beer_run_schema.py

### Implementation for User Story 2

- [X] T020 [US2] Implement beer_run_members table with user_id, beer_run_id, role, uniqueness, role constraint, and lookup indexes in migrations/versions/002_add_beer_run_schema.py
- [X] T021 [US2] Implement BeerRunMember model with role constraint, user relationship, and beer_run relationship in models.py
- [X] T022 [US2] Implement BeerRun.memberships relationship in models.py
- [X] T023 [US2] Implement User.memberships relationship in models.py
- [X] T024 [US2] Add helper or model-level validation used by tests to assert each persisted beer-run has at least one owner in tests/test_beer_run_schema.py

**Checkpoint**: User Stories 1 and 2 are independently testable with model and migration tests.

---

## Phase 5: User Story 3 - Support Public And Private Runs (Priority: P3)

**Goal**: New beer-runs are private by default, beer-run names are unique, and the schema can represent BeerRunJPN as the only public run immediately after the Task 03 backfill while still allowing future explicitly public runs.

**Independent Test**: Create a new beer-run without visibility and confirm it is private, reject duplicate names, and create/query public BeerRunJPN plus another explicit public run as representable data.

### Tests for User Story 3

- [X] T025 [P] [US3] Add model test that a new BeerRun defaults to private in tests/test_beer_run_schema.py
- [X] T026 [P] [US3] Add unique beer-run name rejection test in tests/test_beer_run_schema.py
- [X] T027 [P] [US3] Add model test proving BeerRunJPN can be the only public run in an immediate post-backfill fixture in tests/test_beer_run_schema.py
- [X] T028 [P] [US3] Add model test proving additional explicitly public beer-runs remain representable future data in tests/test_beer_run_schema.py

### Implementation for User Story 3

- [X] T029 [US3] Implement BeerRun name uniqueness, is_public default false, created_at, and public lookup index in migrations/versions/002_add_beer_run_schema.py
- [X] T030 [US3] Implement BeerRun.name, BeerRun.is_public default, BeerRun.created_at, and related indexes/constraints in models.py
- [X] T031 [US3] Add minimal BeerRun schemas only if needed by tests or existing serialization paths in schemas.py

**Checkpoint**: All user stories are independently functional and testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify migration contract, documentation, and runtime data protection.

- [X] T032 [P] Add fresh database contract assertions for 001_initial_schema and 002_add_beer_run_schema ordering in tests/test_migrations.py
- [X] T033 [P] Add upgraded baseline database contract assertions preserving existing users and entries in tests/test_migrations.py
- [X] T034 [P] Add idempotent re-run assertions for 002_add_beer_run_schema in tests/test_migrations.py
- [X] T035 Update specs/002-add-beer-run-schema/quickstart.md if implementation discovers any changed verification or Task 03 handoff detail
- [X] T036 Run `uv --cache-dir .uv-cache run pytest` from C:\Documents\GitHub\beer-run-jpn
- [X] T037 Verify git status in C:\Documents\GitHub\beer-run-jpn does not include runtime data changes to boozerun.db, test.db, users.json, static/uploads/, uploaded files, or local caches

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion
- **User Story 2 (Phase 4)**: Depends on Foundational completion; can be implemented after or alongside US1 if model file edits are coordinated
- **User Story 3 (Phase 5)**: Depends on Foundational completion; can be implemented after or alongside US1/US2 if model and migration edits are coordinated
- **Polish (Phase 6)**: Depends on desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: MVP, no dependency on US2 or US3 after foundation
- **US2 (P2)**: Uses BeerRun from foundation and can be tested independently with membership fixtures
- **US3 (P3)**: Uses BeerRun from foundation and can be tested independently with visibility/name fixtures

### Parallel Opportunities

- T006 and T007 can run in parallel after T002.
- US1 test tasks T008-T010 can run in parallel.
- US2 test tasks T015-T019 can run in parallel.
- US3 test tasks T025-T028 can run in parallel.
- Polish migration contract tests T032-T034 can run in parallel.

---

## Parallel Example: User Story 1

```text
Task: "T008 [P] [US1] Add migration test that fresh databases contain entries.beer_run_id with a foreign-key path to beer_runs in tests/test_migrations.py"
Task: "T009 [P] [US1] Add model test for creating a beer-run with two entries and reading entries through the beer-run relationship in tests/test_beer_run_schema.py"
Task: "T010 [P] [US1] Add model test for reading an entry's beer-run relationship and rejecting an invalid beer_run_id when foreign keys are enabled in tests/test_beer_run_schema.py"
```

## Parallel Example: User Story 2

```text
Task: "T015 [P] [US2] Add model test for one user belonging to two beer-runs in tests/test_beer_run_schema.py"
Task: "T016 [P] [US2] Add model test for two users belonging to one beer-run with owner/member roles in tests/test_beer_run_schema.py"
Task: "T017 [P] [US2] Add duplicate membership rejection test for the same user and beer-run in tests/test_beer_run_schema.py"
```

## Parallel Example: User Story 3

```text
Task: "T025 [P] [US3] Add model test that a new BeerRun defaults to private in tests/test_beer_run_schema.py"
Task: "T026 [P] [US3] Add unique beer-run name rejection test in tests/test_beer_run_schema.py"
Task: "T027 [P] [US3] Add model test proving BeerRunJPN can be the only public run in an immediate post-backfill fixture in tests/test_beer_run_schema.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Run focused US1 tests from tests/test_beer_run_schema.py and tests/test_migrations.py
5. Stop and validate before layering memberships and visibility behavior

### Incremental Delivery

1. Setup + Foundational: migration registered and base entities scaffolded
2. US1: entry-to-run grouping works
3. US2: memberships, roles, uniqueness, and owner invariant work
4. US3: private default, unique names, and public-run representation work
5. Polish: migration contract, idempotency, full pytest, and runtime data safety check

### Notes

- Tests should be written before implementation and should fail for the missing behavior.
- Task 02 does not create or backfill BeerRunJPN; Task 03 owns that data migration.
- Use isolated test databases only; do not directly mutate boozerun.db.
- Use `uv --cache-dir .uv-cache run pytest` as the standard verification command.
