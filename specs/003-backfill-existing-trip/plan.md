# Implementation Plan: Backfill Existing Trip

**Branch**: `003-backfill-existing-trip` | **Date**: 2026-05-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-backfill-existing-trip/spec.md`

## Summary

Backfill the existing single-trip dataset into the Release 1 beer-run schema by creating or reusing the public `BeerRunJPN` run, assigning historical users and entries to it, and making `Tamei` the owner when present. The implementation will add a third in-repo SQLite migration/data migration after `002_add_beer_run_schema`, update the migration runner order, and update the existing app route logic so current UI flows keep behaving like the old global-trip app by implicitly reading from and writing to `BeerRunJPN`.

## Technical Context

**Language/Version**: Python 3.13+

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, SQLite standard library access, Pydantic, pytest, Uvicorn

**Storage**: SQLite database files in the repository root for local runtime (`boozerun.db`) and isolated test databases

**Testing**: pytest with `uv --cache-dir .uv-cache run pytest`; focused migration, data-continuity, route, leaderboard, and retry/idempotency tests

**Target Platform**: Local Windows development and lightweight Linux/Raspberry Pi-style deployment using the existing Python app

**Project Type**: Compact FastAPI web app plus local scripts and static UI

**Performance Goals**: Backfill completes in seconds for current trip-sized databases; entry list and leaderboard views remain responsive for current local trip scale after filtering through the default run

**Constraints**: Use the existing in-repo migration runner; do not add Alembic, a new service, a frontend framework, or explicit run-selection UI for this task; do not delete, overwrite, or directly mutate live runtime data during tests; preserve existing auth behavior and current public route response compatibility

**Scale/Scope**: Current single SQLite database with `users`, `entries`, `beer_runs`, `beer_run_members`, and `schema_migrations`. This task migrates historical data into `BeerRunJPN` and keeps existing app surfaces working against that default run only.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Lightweight Direct Architecture**: PASS. The plan uses the existing FastAPI route module, SQLAlchemy models, SQLite migration runner, scripts, templates/static consumers, and pytest. No new service, framework, build step, or broad abstraction is introduced.
- **Runtime Data Protection**: PASS. The feature touches source files, tests, migration files, and database data through a controlled migration path. Tests must use isolated databases or explicit copies; `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and caches are not deleted, reset, overwritten, or committed.
- **Verification**: PASS. Add focused migration/backfill tests, route compatibility tests for entry creation/listing/leaderboard behavior, and run `uv --cache-dir .uv-cache run pytest`. Browser inspection is required only if templates or static UI behavior changes; the expected implementation should not visually alter the UI.
- **Mobile Trip UX And Performance**: PASS. Existing mobile entry submission, geolocation fields, image upload behavior, and list/map/detail consumers should keep their current behavior. No static asset change is planned; if one becomes necessary, update cache-busting and inspect mobile-sized views.
- **Auth, Privacy, And API Boundaries**: PASS. Login, bearer-token requirements, password hashing, and existing public response shapes remain stable. New writes through current entry creation must assign `BeerRunJPN` implicitly without weakening authentication.

## Project Structure

### Documentation (this feature)

```text
specs/003-backfill-existing-trip/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- backfill-and-ui-compatibility.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
main.py                                # Keep current routes working against BeerRunJPN by default
migrations/
|-- runner.py                          # Register the ordered Task 03 backfill migration
`-- versions/
    |-- 001_initial_schema.py
    |-- 002_add_beer_run_schema.py
    `-- 003_backfill_existing_trip.py  # Create/reuse BeerRunJPN and assign users/entries
scripts/
`-- migrate_db.py                      # Existing migration command continues to apply/check all migrations
tests/
|-- conftest.py                        # Test DB setup should include the backfilled default run
|-- test_migrations.py                 # Backfill, retry, and migration-history coverage
`-- test_main.py                       # Existing UI/API flow compatibility through route tests
```

**Structure Decision**: Keep the existing single-project layout. Implement backfill as the next migration version and keep app compatibility in the direct route layer rather than adding a run service or user-facing run selector. This matches Release 1's default-run bridge from single-trip behavior to future multi-run behavior.

## Phase 0: Research

Completed in [research.md](research.md). Decisions:

- Implement Task 03 as `003_backfill_existing_trip` in the existing migration sequence so fresh and upgraded databases reach the same default-run state.
- Keep `BeerRunJPN` lookup centralized in the route/migration code through a small direct helper or query pattern, not a new service layer.
- Preserve current UI behavior by making existing global routes implicitly target `BeerRunJPN` until later tasks add explicit run selection.
- Keep response shapes stable for `/api/entries` and `/api/leaderboard`; do not require frontend consumers to pass or display a run field for this task.
- Treat missing `Tamei` as an operator-visible migration failure or warning according to the existing migration command surface, without inventing an account.

## Phase 1: Design And Contracts

Completed artifacts:

- [data-model.md](data-model.md)
- [contracts/backfill-and-ui-compatibility.md](contracts/backfill-and-ui-compatibility.md)
- [quickstart.md](quickstart.md)

Design summary:

- `BeerRunJPN` is the default public run for all historical single-trip data.
- Every existing user receives one membership in `BeerRunJPN`; `Tamei` receives owner role when present and other users receive member role unless an existing valid role should be preserved during retry.
- Every existing unassigned historical entry receives the `BeerRunJPN` association; already assigned entries for other runs are left alone in development databases.
- Existing routes continue to present the default trip without run selection: entry listing reads BeerRunJPN entries, leaderboard totals aggregate BeerRunJPN entries, and new entry creation assigns BeerRunJPN.
- Tests prove fresh migration, upgraded migration, rerun safety, login continuity, route compatibility, and leaderboard continuity without touching live runtime databases.

## Post-Design Constitution Check

- **Lightweight Direct Architecture**: PASS. Design stays within existing migrations, `main.py`, scripts, and tests.
- **Runtime Data Protection**: PASS. Runtime data is changed only through the explicit migration path; test data uses isolated SQLite files.
- **Verification**: PASS. Focused tests and the full pytest command are documented. Browser inspection is conditional on visible UI/static changes.
- **Mobile Trip UX And Performance**: PASS. No planned UI layout, geolocation, upload, or static asset behavior change.
- **Auth, Privacy, And API Boundaries**: PASS. Auth and public response compatibility remain part of the implementation contract.

## Complexity Tracking

No constitution violations.
