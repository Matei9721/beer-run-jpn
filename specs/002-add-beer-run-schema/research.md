# Research: Add Beer-Run Schema

## Decision: Use the existing in-repo SQLite migration runner

**Rationale**: Task 01 introduced `migrations.runner`, `schema_migrations`, and explicit migration commands as the Release 1 schema path. Registering one ordered migration keeps fresh databases, test databases, and upgraded copies on the same source of truth.

**Alternatives considered**:

- Add Alembic: Rejected because the project constitution and prior plan intentionally keep Release 1 migrations local and small.
- Use `Base.metadata.create_all`: Rejected because it bypasses migration history and cannot safely express ordered schema evolution.

## Decision: Add direct BeerRun and BeerRunMember models

**Rationale**: The app currently keeps data modeling in `models.py` with direct SQLAlchemy relationships. Adding the two entities there matches the existing architecture and gives tests and later tasks a stable model surface.

**Alternatives considered**:

- Store beer-run membership as JSON or denormalized columns: Rejected because users can belong to multiple runs and runs can contain multiple users.
- Create a separate repository/service layer: Rejected because the feature does not need a broader abstraction.

## Decision: Constrain membership role values to owner and member

**Rationale**: The specification defines exactly two Release 1 roles. Constraining values in the data model and migration prevents ambiguous role strings and gives future authorization tasks reliable input.

**Alternatives considered**:

- Leave roles unconstrained free text: Rejected because typo variants would break authorization assumptions.
- Create a separate roles table: Rejected as unnecessary for two fixed Release 1 values.

## Decision: Make beer-run names unique

**Rationale**: The clarification session chose unique names. This keeps `BeerRunJPN` idempotent for Task 03 and prevents selectors or admin tools from showing indistinguishable runs.

**Alternatives considered**:

- Allow duplicate private names: Rejected because it creates ambiguity without clear user value.
- Restrict only public names: Rejected because duplicate private names would still complicate membership and entry grouping.

## Decision: Add entry-to-beer-run relationship in schema, defer historical assignment to Task 03

**Rationale**: This task must create the schema capability, but Task 03 explicitly owns creating `BeerRunJPN`, assigning all existing entries, adding all existing users as members, setting Tamei as owner, and proving idempotent backfill behavior. The schema migration should prepare the column and constraints in a way that the next data migration can complete the invariant for existing rows.

**Alternatives considered**:

- Backfill existing rows in this task: Rejected because Task 03 is scoped to the data migration behavior and acceptance criteria.
- Leave entries permanently optional: Rejected because the final Release 1 schema requires every entry to belong to one valid beer-run.

## Decision: Add lookup indexes for common run paths

**Rationale**: The spec calls out efficient lookup of a user's beer-runs, a beer-run's members, a beer-run's entries, and public beer-runs. SQLite indexes on membership user/run columns, entry run column, and the public flag support these paths without changing architecture.

**Alternatives considered**:

- Add indexes only after performance problems appear: Rejected because these are cheap, predictable relationship lookups and are part of the schema contract.
- Add broad composite indexes for every future query: Rejected because this feature should stay scoped to known Release 1 paths.
