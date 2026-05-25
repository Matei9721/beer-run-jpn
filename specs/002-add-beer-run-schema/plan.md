# Implementation Plan: Add Beer-Run Schema

**Branch**: `002-add-beer-run-schema` | **Date**: 2026-05-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-add-beer-run-schema/spec.md`

## Summary

Add the Release 1 schema foundation for multi-run trip data: beer-runs, beer-run memberships with owner/member roles, private-by-default visibility, unique run names, entry-to-run association, and lookup indexes. The implementation will extend the existing SQLAlchemy model definitions and Pydantic schemas where needed, add a second in-repo SQLite migration after `001_initial_schema`, update the migration runner's ordered migration list, and add focused tests that prove relationships, constraints, defaults, and migration behavior work for fresh and upgraded databases. Task 03 remains responsible for backfilling live historical data into `BeerRunJPN`.

## Technical Context

**Language/Version**: Python 3.13+

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, SQLite standard library access, Pydantic, pytest, Uvicorn

**Storage**: SQLite database files in the repository root for local runtime (`boozerun.db`) and isolated test databases

**Testing**: pytest with `uv --cache-dir .uv-cache run pytest`; focused model and migration tests for beer-run relationships, membership uniqueness, role validation, private defaults, entry foreign-key behavior, unique run names, owner presence in valid fixtures, and migration idempotency

**Target Platform**: Local Windows development and lightweight Linux/Raspberry Pi-style deployment using the existing Python app

**Project Type**: Compact FastAPI web app plus local scripts

**Performance Goals**: Common lookups for a user's beer-runs, a beer-run's members, a beer-run's entries, and public beer-runs remain fast for current project-scale local data; migration runs complete in seconds for current trip-sized databases

**Constraints**: Use the existing in-repo migration runner; do not add Alembic or a new framework for Release 1; do not delete, overwrite, or directly migrate live runtime data during tests; existing auth behavior and public API response shapes remain unchanged unless explicitly covered by this feature

**Scale/Scope**: Current single SQLite database with `users`, `entries`, and `schema_migrations`, extended with beer-run tables and an `entries` relationship column. This task creates schema capability only; Task 03 performs the historical `BeerRunJPN` data backfill.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Lightweight Direct Architecture**: PASS. The plan uses existing FastAPI, SQLAlchemy, SQLite, Pydantic, pytest, and the local migration runner. No new framework, service, build step, or broad abstraction is introduced.
- **Runtime Data Protection**: PASS. The feature touches source files, tests, migration files, and database schema state. Tests use isolated databases or copies; `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and caches are not deleted, reset, overwritten, committed, or directly migrated without explicit user instruction.
- **Verification**: PASS. Add focused schema and migration tests and run `uv --cache-dir .uv-cache run pytest`. No frontend or Wrapped UI inspection is required because no UI, static asset, generated data, or browser behavior changes are planned.
- **Mobile Trip UX And Performance**: PASS. No mobile UI, geolocation, upload, image optimization, cache-busting, HTTPS, or map/detail behavior changes are planned.
- **Auth, Privacy, And API Boundaries**: PASS. Existing authentication, password hashing, bearer-token requirements, and public response shapes remain unchanged. Owner/member data is introduced for later authorization work but does not grant new unauthenticated writes in this feature.

## Project Structure

### Documentation (this feature)

```text
specs/002-add-beer-run-schema/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- beer-run-schema-migration.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
models.py                         # Add BeerRun, BeerRunMember, Entry beer-run relationship
schemas.py                        # Add schema types only if needed by tests or existing serialization paths
migrations/
|-- runner.py                     # Register the ordered Release 1 schema migration
`-- versions/
    |-- 001_initial_schema.py
    `-- 002_add_beer_run_schema.py
tests/
|-- conftest.py                   # Test DB continues to initialize through migrations
|-- test_migrations.py            # Fresh/upgrade/idempotency coverage for the new migration
`-- test_beer_run_schema.py       # Model-level relationship, constraint, and default coverage
```

**Structure Decision**: Keep the existing single-project layout. Add one new migration version and focused tests; do not introduce a separate schema service or migration framework. Keep Task 03 backfill logic out of this task except for ensuring the schema can support it.

## Phase 0: Research

Completed in [research.md](research.md). Decisions:

- Continue using the in-repo SQLite migration runner introduced by Task 01.
- Add `beer_runs` and `beer_run_members` as direct SQLAlchemy models.
- Represent membership roles as constrained string values `owner` and `member`.
- Make beer-run names unique and new beer-runs private by default.
- Add `beer_run_id` to `entries` as a required relationship for the final schema, while sequencing existing-data assignment with Task 03 backfill.
- Add indexes for user-to-run, run-to-member, run-to-entry, and public-run lookup paths.

## Phase 1: Design And Contracts

Completed artifacts:

- [data-model.md](data-model.md)
- [contracts/beer-run-schema-migration.md](contracts/beer-run-schema-migration.md)
- [quickstart.md](quickstart.md)

Design summary:

- `BeerRun` represents uniquely named runs with a private-by-default public flag.
- `BeerRunMember` joins users to beer-runs with role values limited to owner/member and a uniqueness rule for one membership per user per run.
- `Entry` gains a beer-run relationship so every entry can belong to one valid beer-run after the schema and backfill sequence is complete.
- The migration creates the new tables, indexes, constraints, and entry relationship column without performing the Task 03 data backfill.
- Tests verify schema capability with isolated databases and fixture-created valid runs rather than touching live runtime data.

## Post-Design Constitution Check

- **Lightweight Direct Architecture**: PASS. The design adds only direct models, a migration version, and focused tests using existing project patterns.
- **Runtime Data Protection**: PASS. Runtime databases and uploaded/local files remain protected; tests use isolated databases and migration-created schema.
- **Verification**: PASS. Focused tests and the full pytest command are documented.
- **Mobile Trip UX And Performance**: PASS. No affected mobile/browser surfaces.
- **Auth, Privacy, And API Boundaries**: PASS. Auth behavior and existing public responses remain unchanged; membership roles are data-only preparation for later authorization tasks.

## Complexity Tracking

No constitution violations.
