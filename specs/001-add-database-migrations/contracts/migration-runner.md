# Contract: Migration Runner

## Command

```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py [--database PATH] [--check]
```

## Arguments

- `--database PATH`: Optional SQLite database path. Defaults to the app database path used by `database.py`.
- `--check`: Validate whether all required migrations are applied without applying changes.

## Expected Behavior

### Apply mode

- Creates the target database when it does not exist.
- Ensures migration history tracking exists.
- Applies pending migrations in order.
- If the target database has the current baseline `users` and `entries` structures but no migration history, records the initial migration as applied without recreating or overwriting those tables.
- Exits successfully when the database is at the current migration state.
- Exits successfully without duplicate work when run again on an already migrated database.

### Check mode

- Does not modify the database.
- Exits successfully when the database is at the current migration state.
- Exits with a non-zero status and a clear migration-required message when required migrations are missing.

## App Startup Contract

- Startup performs readiness validation only.
- Startup does not apply pending migrations.
- Startup blocks with a clear migration-required error when the database is genuinely behind the required migration state.
- Startup accepts an existing current-schema database only after the baseline migration has been recorded by the explicit migration command.

## Failure Contract

- Migration failures are visible in command output.
- Failed migrations are not recorded as applied.
- Existing users and entries are not intentionally deleted, overwritten, or recreated.
- Tests and validation must use temporary databases or copies, not the live `boozerun.db`, unless the user explicitly instructs otherwise.
