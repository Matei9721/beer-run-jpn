# Quickstart: Add Beer-Run Schema

## Preconditions

- Task 01 migration runner is present.
- Work is on branch `002-add-beer-run-schema`.
- Do not run schema changes directly against `boozerun.db` unless explicitly instructed.

## Implementation Checks

1. Add the new schema migration under `migrations/versions/002_add_beer_run_schema.py`.
2. Register the migration in `migrations/runner.py` after `001_initial_schema`.
3. Update `models.py` with `BeerRun`, `BeerRunMember`, user membership relationship, beer-run entry relationship, and entry beer-run relationship.
4. Update `schemas.py` only where existing serialization or tests require schema types.
5. Add focused tests for:
   - one user in two beer-runs
   - two users in one beer-run
   - duplicate membership rejection
   - unique beer-run name rejection
   - private default for new beer-runs
   - owner membership present in valid beer-run fixtures
   - entry creation requiring a valid beer-run after beer-run assignment is active
   - migration fresh database, upgraded baseline database, and idempotent re-run behavior

## Verification

Run the full suite:

```powershell
uv --cache-dir .uv-cache run pytest
```

## Manual Safety Check

For any local runtime validation, copy `boozerun.db` to a temporary path first and run migration checks against the copy. Do not delete, overwrite, or commit `boozerun.db`, `test.db`, `users.json`, uploaded files, or local caches.

## Handoff To Task 03

After this schema task is complete, Task 03 should create/backfill `BeerRunJPN`, assign all existing entries to it, add every existing user as a member, set Tamei as owner, mark it public, and prove the operation is idempotent.
