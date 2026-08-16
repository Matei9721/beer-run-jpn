# Quickstart: Add Database Migrations

## 1. Review Current State

```powershell
git status --short
```

Confirm runtime files such as `boozerun.db`, `test.db`, `users.json`, and `static/uploads/` are treated as protected local state.

## 2. Run The Test Suite

```powershell
uv --cache-dir .uv-cache run pytest
```

Use this as the baseline before implementation and the final verification after implementation.

## 3. Validate A Fresh Database

After implementation, create an isolated temporary database and apply migrations:

```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py --database C:\tmp\beer-run-fresh.db
```

Expected result: the database is created, contains baseline user/entry schema plus migration history, and a second run completes without duplicate work.

## 4. Validate Existing Data Safely

Do not test directly against the live `boozerun.db`. Copy it first:

```powershell
Copy-Item boozerun.db C:\tmp\boozerun-migration-check.db
uv --cache-dir .uv-cache run python scripts/migrate_db.py --database C:\tmp\boozerun-migration-check.db
```

Expected result: all existing users and entries remain present, and the baseline migration is recorded without recreating existing tables.

## 5. Validate Startup Readiness

Run check mode against a migrated database:

```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py --database C:\tmp\beer-run-fresh.db --check
```

Expected result: migrated databases pass readiness checks. Databases missing required migration history fail check mode and app startup with a clear migration-required error.

## 6. Verify App Behavior

```powershell
uv --cache-dir .uv-cache run pytest
```

No browser inspection is required for this feature because it does not change frontend layout, static assets, geolocation, upload UI, or Wrapped pages.
