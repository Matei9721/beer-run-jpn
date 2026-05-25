# Contract: Beer-Run Schema Migration

## Purpose

Define the expected behavior of the Release 1 schema migration that adds beer-run capability without performing the Task 03 historical backfill.

## Migration Identity

- New migration version: `002_add_beer_run_schema`
- Must run after: `001_initial_schema`
- Must be registered in the migration runner's ordered migration list.

## Fresh Database Contract

Given an empty database path, when migrations are applied:

- `schema_migrations` records both `001_initial_schema` and `002_add_beer_run_schema`.
- `users` and `entries` baseline structures exist.
- `beer_runs` exists.
- `beer_run_members` exists.
- `entries` includes the beer-run relationship field.
- New beer-run records default to private when visibility is omitted.
- Duplicate beer-run names are rejected.
- Duplicate memberships for the same user and beer-run are rejected.
- Membership role values outside `owner` and `member` are rejected.

## Existing Baseline Database Contract

Given a database already baselined at `001_initial_schema`, when the new migration is applied:

- Existing users are preserved.
- Existing entries are preserved.
- Beer-run tables and lookup indexes are added.
- The entry-to-beer-run field is added in preparation for Task 03 backfill.
- The migration records `002_add_beer_run_schema` exactly once.

## Idempotency Contract

Given a database that already has `002_add_beer_run_schema` recorded, when migrations are applied again:

- The migration is skipped.
- No duplicate tables, indexes, constraints, or membership records are created.
- Existing users and entries remain unchanged.

## Out Of Scope

- Creating `BeerRunJPN`.
- Assigning existing entries to `BeerRunJPN`.
- Adding every existing user as a BeerRunJPN member.
- Assigning Tamei as BeerRunJPN owner.
- Proving leaderboard totals under `BeerRunJPN`.

Those behaviors belong to Task 03 backfill.
