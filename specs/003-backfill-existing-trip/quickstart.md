# Quickstart: Backfill Existing Trip

## Preconditions

- Work on branch `003-backfill-existing-trip`.
- Do not delete or overwrite `boozerun.db`, `test.db`, `users.json`, `static/uploads/`, or local caches.
- Use isolated temporary databases for tests and manual migration checks.

## Implementation Outline

1. Add migration version `003_backfill_existing_trip`.
2. Register it after `002_add_beer_run_schema` in `migrations/runner.py`.
3. Backfill or reuse `BeerRunJPN` as the public default run.
4. Add every existing user as a BeerRunJPN member.
5. Promote existing `Tamei` to owner when present and report clearly when absent.
6. Assign every unassigned historical entry to BeerRunJPN.
7. Update existing app routes so entry creation, entry listing, and leaderboard totals use BeerRunJPN implicitly.
8. Keep current UI response shapes and form behavior stable.

## Verification

Run focused tests while developing:

```powershell
uv --cache-dir .uv-cache run pytest tests/test_migrations.py tests/test_main.py
```

Run the full suite before considering the feature complete:

```powershell
uv --cache-dir .uv-cache run pytest
```

If any templates or static frontend files change, start the local app and inspect the affected flows in the Codex in-app browser, including a mobile-sized viewport.

## Expected Results

- Existing users can still log in.
- Historical entries appear in the same current trip experience.
- New entries created through the current UI belong to BeerRunJPN.
- BeerRunJPN leaderboard totals match previous global totals.
- Re-running migrations does not duplicate BeerRunJPN or memberships.
- The app starts only when all required migrations, including the backfill, are recorded.
