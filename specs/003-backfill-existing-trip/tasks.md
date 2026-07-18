# Tasks: Backfill Existing Trip

**Input**: Design documents from `/specs/003-backfill-existing-trip/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/backfill-and-ui-compatibility.md, quickstart.md

**Tests**: Required for this feature because it changes database migration behavior, backend route behavior, and existing app data flow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **BoozeRunJpn app**: root Python modules (`main.py`, `auth.py`, `database.py`, `models.py`, `schemas.py`), `scripts/`, `templates/`, `static/`, `data/`, and `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working context and prepare shared test helpers without changing runtime data.

- [X] T001 Inspect current git status and confirm runtime files (`boozerun.db`, `test.db`, `users.json`, `static/uploads/`) are not staged for changes
- [X] T002 [P] Review existing migration registration and version naming in `migrations/runner.py` and `migrations/versions/002_add_beer_run_schema.py`
- [X] T003 [P] Review current default-trip route behavior in `main.py` for `/api/entries`, `/api/leaderboard`, `/token`, and `/api/me`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add reusable test fixtures and helpers needed by all user stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add helper functions for representative pre-backfill databases with users `Tamei` and `user` plus historical entries in `tests/test_migrations.py`
- [X] T005 Add helper assertions for BeerRunJPN rows, memberships, public-run counts, and entry assignments in `tests/test_migrations.py`
- [X] T006 Add a direct default-run lookup helper or query pattern for route code in `main.py`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Preserve Existing Trip Data In BeerRunJPN (Priority: P1) MVP

**Goal**: Existing users and historical entries are migrated into exactly one public default run named BeerRunJPN, with Tamei as owner when present.

**Independent Test**: Apply migrations to a representative pre-backfill database and confirm BeerRunJPN exists, every existing user is a member, every existing historical entry belongs to BeerRunJPN, Tamei is owner, and BeerRunJPN is the only public run created by this backfill.

### Tests for User Story 1 (REQUIRED)

- [X] T007 [P] [US1] Add migration test for creating public BeerRunJPN from representative existing data in `tests/test_migrations.py`
- [X] T008 [P] [US1] Add migration test that every existing user receives exactly one BeerRunJPN membership in `tests/test_migrations.py`
- [X] T009 [P] [US1] Add migration test that every existing unassigned historical entry receives BeerRunJPN `beer_run_id` in `tests/test_migrations.py`
- [X] T010 [P] [US1] Add migration test that existing Tamei is owner and BeerRunJPN is the only public run after backfill in `tests/test_migrations.py`
- [X] T011 [P] [US1] Add migration test that user credentials and entry fields are preserved during backfill in `tests/test_migrations.py`

### Implementation for User Story 1

- [X] T012 [US1] Create `migrations/versions/003_backfill_existing_trip.py` with migration metadata, BeerRunJPN creation/reuse, public visibility, membership insertion, Tamei owner assignment, and entry assignment
- [X] T013 [US1] Register `003_backfill_existing_trip` after `002_add_beer_run_schema` in `migrations/runner.py`
- [X] T014 [US1] Ensure `migrations/versions/003_backfill_existing_trip.py` records migration success only after all backfill operations complete
- [X] T015 [US1] Run `uv --cache-dir .uv-cache run pytest tests/test_migrations.py` and confirm US1 migration tests pass

**Checkpoint**: User Story 1 is independently functional and testable.

---

## Phase 4: User Story 2 - Keep Existing App Behavior Working (Priority: P2)

**Goal**: Current login, entry creation, entry listing, public trip data, and leaderboard behavior continue to work with BeerRunJPN as the implicit default run.

**Independent Test**: Use the existing TestClient flows after migrations and confirm response shapes remain compatible while entries and leaderboard totals are scoped to BeerRunJPN.

### Tests for User Story 2 (REQUIRED)

- [X] T016 [P] [US2] Update TestClient setup to create a migrated BeerRunJPN default run and membership data in `tests/conftest.py`
- [X] T017 [P] [US2] Add route test that existing login and `/api/me` behavior remain unchanged in `tests/test_main.py`
- [X] T018 [P] [US2] Add route test that `POST /api/entries` assigns the new entry to BeerRunJPN without requiring a run field in `tests/test_main.py`
- [X] T019 [P] [US2] Add route test that `GET /api/entries` returns the existing payload shape and only BeerRunJPN default-trip entries in `tests/test_main.py`
- [X] T020 [P] [US2] Add route test that `/api/leaderboard` totals match BeerRunJPN entries and preserve the existing response shape in `tests/test_main.py`

### Implementation for User Story 2

- [X] T021 [US2] Update `main.py` entry creation to assign BeerRunJPN to new entries created through the existing UI
- [X] T022 [US2] Update `main.py` entry listing to read BeerRunJPN entries by default while preserving the optional username filter and response fields
- [X] T023 [US2] Update `main.py` leaderboard aggregation to compute totals from BeerRunJPN entries while preserving sorting and response fields
- [X] T024 [US2] Update `tests/conftest.py` fixtures so existing route tests run against the fully migrated default-run state
- [X] T025 [US2] Run `uv --cache-dir .uv-cache run pytest tests/test_main.py` and confirm UI compatibility route tests pass

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Support Safe Local Retry (Priority: P3)

**Goal**: Re-running the migration locally does not duplicate BeerRunJPN, duplicate memberships, change valid entry assignments, or alter totals.

**Independent Test**: Apply the backfill repeatedly to the same migrated database, including partial-backfill states, and confirm counts, roles, assignments, and totals stay stable.

### Tests for User Story 3 (REQUIRED)

- [X] T026 [P] [US3] Add migration test that applying migrations three times leaves exactly one BeerRunJPN row in `tests/test_migrations.py`
- [X] T027 [P] [US3] Add migration test that reruns leave exactly one BeerRunJPN membership per existing user in `tests/test_migrations.py`
- [X] T028 [P] [US3] Add migration test that reruns preserve BeerRunJPN entry assignments and leaderboard source totals in `tests/test_migrations.py`
- [X] T029 [P] [US3] Add migration test that existing entries assigned to another run are not moved to BeerRunJPN in `tests/test_migrations.py`
- [X] T030 [P] [US3] Add migration test for missing Tamei operator feedback without creating a Tamei user in `tests/test_migrations.py`

### Implementation for User Story 3

- [X] T031 [US3] Harden `migrations/versions/003_backfill_existing_trip.py` for rerun-safe BeerRunJPN reuse and public visibility correction
- [X] T032 [US3] Harden `migrations/versions/003_backfill_existing_trip.py` for rerun-safe membership creation and Tamei owner correction
- [X] T033 [US3] Harden `migrations/versions/003_backfill_existing_trip.py` to update only unassigned historical entries and preserve entries already assigned to other runs
- [X] T034 [US3] Ensure missing Tamei behavior in `migrations/versions/003_backfill_existing_trip.py` produces clear operator feedback without inventing user data
- [X] T035 [US3] Run `uv --cache-dir .uv-cache run pytest tests/test_migrations.py` and confirm retry/idempotency tests pass

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify the full feature, documentation, and runtime-data safety.

- [X] T036 [P] Update `specs/003-backfill-existing-trip/quickstart.md` if implementation details or verification commands changed
- [X] T037 [P] Inspect `templates/index.html`, `static/js/app.js`, and related static files to confirm no run-selection UI or cache-busting changes are required
- [X] T038 Run `uv --cache-dir .uv-cache run pytest tests/test_migrations.py tests/test_main.py`
- [X] T039 Run `uv --cache-dir .uv-cache run pytest`
- [X] T040 Verify `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and local caches were not deleted, reset, or staged without instruction
- [X] T041 If any templates or static frontend files changed, start the local app and inspect the affected entry and leaderboard flows in the Codex in-app browser, including a mobile-sized viewport

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - blocks all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP
- **User Story 2 (Phase 4)**: Depends on Foundational completion; route tests may use US1 migration behavior for realistic setup
- **User Story 3 (Phase 5)**: Depends on Foundational completion; hardening is easiest after US1 backfill exists
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - no dependency on US2 or US3
- **User Story 2 (P2)**: Can start after Foundational, but final route fixture setup expects the default run created by US1
- **User Story 3 (P3)**: Can start after US1 implementation exists because it hardens the same migration behavior

### Parallel Opportunities

- T002 and T003 can run in parallel during setup
- T004 and T005 are both in `tests/test_migrations.py`, so coordinate if parallelizing; T006 can run independently in `main.py`
- US1 test tasks T007-T011 target the same file and should be coordinated, but they can be conceptually drafted in parallel
- US2 test tasks T017-T020 target `tests/test_main.py`; T016 targets `tests/conftest.py` and can proceed separately
- US3 test tasks T026-T030 target the same file and should be coordinated, while implementation hardening stays in one migration file
- T036 and T037 can run in parallel during polish

---

## Parallel Example: User Story 2

```text
Task: "Update TestClient setup to create a migrated BeerRunJPN default run and membership data in tests/conftest.py"
Task: "Add route test that existing login and /api/me behavior remain unchanged in tests/test_main.py"
Task: "Add route test that POST /api/entries assigns the new entry to BeerRunJPN without requiring a run field in tests/test_main.py"
Task: "Add route test that GET /api/entries returns the existing payload shape and only BeerRunJPN default-trip entries in tests/test_main.py"
Task: "Add route test that /api/leaderboard totals match BeerRunJPN entries and preserve the existing response shape in tests/test_main.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. Validate with `uv --cache-dir .uv-cache run pytest tests/test_migrations.py`
5. Stop and confirm existing users/entries are correctly backfilled into BeerRunJPN

### Incremental Delivery

1. Complete Setup + Foundational
2. Add User Story 1 to migrate historical data into BeerRunJPN
3. Add User Story 2 to preserve current route/UI behavior against the default run
4. Add User Story 3 to harden local retry and partial-state behavior
5. Run focused tests, then the full suite

### Notes

- Write required tests before implementation and confirm they fail for the missing behavior.
- Avoid changing templates or static assets unless route compatibility proves it necessary.
- Do not run migration commands against `boozerun.db` or `test.db` unless the user explicitly asks.
- Keep response shapes compatible for current frontend consumers.
