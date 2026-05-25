# Implementation Plan: Add Database Migrations

**Branch**: `001-add-database-migrations` | **Date**: 2026-05-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-add-database-migrations/spec.md`

## Summary

Introduce a small in-repo SQLite migration path for Release 1 so fresh databases, tests, and existing `boozerun.db` copies all reach the same schema through one source of truth. The implementation will add migration tracking, a baseline migration for the current `users` and `entries` structures, an explicit migration command, startup validation that blocks genuinely outdated databases, and test setup that initializes schema through migrations instead of direct metadata creation.

## Technical Context

**Language/Version**: Python 3.13+

**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, SQLite standard library access, pytest, Uvicorn

**Storage**: SQLite database files in the repository root for local runtime (`boozerun.db`) and isolated test databases

**Testing**: pytest with `uv --cache-dir .uv-cache run pytest`; focused tests for migration runner, startup validation, fresh database creation, idempotent re-runs, and baseline adoption of an existing database copy

**Target Platform**: Local Windows development and lightweight Linux/Raspberry Pi-style deployment using the existing Python app

**Project Type**: Compact FastAPI web app plus local scripts

**Performance Goals**: Migration status checks complete during app startup without noticeable delay for the small local trip database; full migration run should complete in seconds for current project-scale data

**Constraints**: Do not add Alembic or a new framework for Release 1; do not delete, overwrite, or directly migrate live runtime data during tests; app startup must block when required migrations are missing; existing public API and auth behavior remain unchanged

**Scale/Scope**: Current single SQLite database with `users` and `entries` tables, plus ordered Release 1 migrations tracked in a local `schema_migrations` table

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Lightweight Direct Architecture**: PASS. The plan keeps migration behavior in a small repo-local module/script and uses existing FastAPI, SQLAlchemy, SQLite, and pytest dependencies. No Alembic, build system, service, or broad abstraction is introduced.
- **Runtime Data Protection**: PASS. The feature touches source files, test setup, migration files, and database schema state. Tests and validation use temporary databases or copies; `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, and caches are not deleted, overwritten, committed, or directly migrated without explicit user instruction.
- **Verification**: PASS. Add focused migration tests and run `uv --cache-dir .uv-cache run pytest`. No frontend or Wrapped UI inspection is required because no UI, static asset, or generated Wrapped behavior changes.
- **Mobile Trip UX And Performance**: PASS. No mobile UI, geolocation, upload, image optimization, cache-busting, or HTTPS behavior changes are planned.
- **Auth, Privacy, And API Boundaries**: PASS. Authenticated writes, password hashing, public response shapes, uploaded media, and sensitive local files remain unchanged. Existing users must still authenticate after migration.

## Project Structure

### Documentation (this feature)

```text
specs/001-add-database-migrations/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- migration-runner.md
|-- checklists/
|   `-- requirements.md
`-- spec.md
```

### Source Code (repository root)

```text
database.py                  # Existing engine/session setup; may expose database URL/path helpers
main.py                      # Replace import-time create_all with migration readiness validation
models.py                    # Current baseline user/entry model definitions remain the schema reference
pyproject.toml               # Optional script entry if needed for the migration command
scripts/
|-- setup_db.py              # Keep user sync flow, route schema work through migrations
|-- manage_users.py          # Stop implicit table creation or require migrated schema first
`-- migrate_db.py            # New explicit migration command entry point
migrations/
|-- __init__.py
|-- runner.py                # Small local migration runner and readiness checks
`-- versions/
    |-- __init__.py
    `-- 001_initial_schema.py
tests/
|-- conftest.py              # Initialize test schema through migrations
|-- test_migrations.py       # Fresh DB, baseline adoption, idempotency, failure/readiness tests
|-- test_main.py
`-- test_auth.py
```

**Structure Decision**: Use the existing single-project layout. Add one `migrations/` package for migration logic and migration files, plus one script command under `scripts/`. This keeps schema evolution local and reviewable while avoiding a general migration framework for Release 1.

## Phase 0: Research

Completed in [research.md](research.md). Decisions:

- Use a small in-repo migration runner instead of Alembic.
- Store applied migration identifiers in `schema_migrations`.
- Treat existing databases matching the current `users` and `entries` baseline as already at the initial migration.
- Block app startup when required migrations are missing instead of applying migrations automatically.
- Use migrations for test schema setup so test and deployment schema paths match.

## Phase 1: Design And Contracts

Completed artifacts:

- [data-model.md](data-model.md)
- [contracts/migration-runner.md](contracts/migration-runner.md)
- [quickstart.md](quickstart.md)

Design summary:

- `migrations.runner` owns migration ordering, applied-history checks, baseline detection, applying pending migrations, and readiness validation.
- `scripts/migrate_db.py` provides the explicit human/deployment command.
- `main.py` performs readiness validation at startup and fails clearly when migrations are missing.
- Tests create isolated database files and apply migrations before exercising the app.
- `scripts/setup_db.py` continues to sync users from `users.json` after schema readiness, rather than creating schema directly.

## Post-Design Constitution Check

- **Lightweight Direct Architecture**: PASS. The design adds only a small local package and script; no external framework or service.
- **Runtime Data Protection**: PASS. The quickstart requires copy-based validation for `boozerun.db`, and tests use isolated databases.
- **Verification**: PASS. Focused migration tests and full pytest command are documented.
- **Mobile Trip UX And Performance**: PASS. No affected mobile/browser surfaces.
- **Auth, Privacy, And API Boundaries**: PASS. Auth data is preserved; no API response changes.

## Complexity Tracking

No constitution violations.
