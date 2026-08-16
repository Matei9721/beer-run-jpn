# Research: Add Database Migrations

## Decision: Use a small in-repo migration runner

**Rationale**: The feature explicitly avoids Alembic for Release 1, and the app has a compact SQLite schema with only `users`, `entries`, and migration tracking in scope. A local runner keeps deployment simple, makes review easy, and matches the constitution's lightweight architecture principle.

**Alternatives considered**:

- Alembic: rejected for Release 1 because it is heavier than needed and explicitly out of scope.
- Continue `Base.metadata.create_all`: rejected because it hides missing migrations and cannot safely express ordered schema evolution.
- Keep ad hoc SQL in `scripts/setup_db.py`: rejected because tests, deployment, and startup readiness would still not share a single schema source.

## Decision: Track migrations in `schema_migrations`

**Rationale**: A small database table is enough to record ordered applied migrations, make re-runs idempotent, and let startup determine whether the database is ready.

**Alternatives considered**:

- File-based migration state: rejected because state must travel with each SQLite database.
- Inferring state only from table columns: rejected because future migrations need durable history, not repeated structural guessing.

## Decision: Baseline existing current-schema databases automatically

**Rationale**: The current live database predates migration history. If it already has the expected baseline `users` and `entries` structures, the safe behavior is to record the initial migration as applied without recreating or overwriting existing data.

**Alternatives considered**:

- Manual baseline marking: rejected because it adds deployment friction and increases the chance of operator error.
- Treat no migration history as outdated in all cases: rejected because it would incorrectly block the existing valid database.

## Decision: Block startup when required migrations are missing

**Rationale**: The app should not appear healthy against a genuinely outdated schema. Blocking startup with a clear migration-required error makes deployment issues visible before users hit runtime failures.

**Alternatives considered**:

- Warn only: rejected because stale schema could still cause later data or API failures.
- Auto-apply migrations at startup: rejected because schema changes should be an explicit operational action for protected runtime data.

## Decision: Initialize tests from migrations

**Rationale**: Tests should exercise the same schema path used by fresh setup and deployment. This prevents drift between `Base.metadata.create_all` and the real migration sequence.

**Alternatives considered**:

- Keep test setup on `Base.metadata.create_all`: rejected because tests could pass while migration setup is broken.
- Use the live `test.db` directly: rejected because tests must use isolated state and avoid runtime data surprises.
