# Implementation Summary: Beer-Run Selector UI

## Outcome

Implemented a shared beer-run picker that supplies one selected run to Ranking,
Map, the user filter, and Log Drink. The app now supports a bounded server-side
selector API and clears browser state before a run, identity, or access change
can reveal stale data.

## Delivered Changes

- Added additive `GET /api/beer-runs` selector modes in `beer_run_routes.py`:
  membership-only `view=mine`, public exact-name lookup, and bounded literal
  public prefix search. The legacy queryless response remains unchanged.
- Added focused API coverage for privacy, ordering, search bounds, literal LIKE
  characters, validation failures, caller role metadata, and bounded query
  count in `tests/test_beer_run_crud.py`.
- Added `static/js/modules/beer-runs.js` for the accessible picker, picker-local
  cancellation, public search, and per-user selected-run keys.
- Reworked `static/js/app.js` to validate remembered selections, use immutable
  run/identity refresh generations, cancel superseded scoped reads, render
  leaderboard and map data atomically, and fall back once to public BeerRunJPN
  after access loss.
- Made Log Drink visibility depend on the selected run's membership role,
  cleared marker/detail/modal/filter state on context changes, and updated the
  run-selector UI and cache versions.
- Refined the selector into a compact desktop panel and mobile bottom sheet
  with clearer active-run context, visibility badges, and scannable run cards.
- Updated `repository_rules.md` to replace the obsolete implicit-single-run
  guidance.

## Verification

- `uv --cache-dir .uv-cache run pytest tests/test_beer_run_crud.py` — 64 passed.
- `uv --cache-dir .uv-cache run pytest` — 328 passed, with the existing
  Argon2 deprecation warning.
- `git diff --check` — passed.
- Parsed the changed JavaScript ES modules with Node's module parser.
- Started the app against `beer-run-selector-browser.db` in the Windows temp
  directory, not `boozerun.db`; `/` and the public BeerRunJPN exact lookup both
  returned HTTP 200.
- Validated the picker in the required in-app Browser at desktop and 390x844.
  Confirmed the anonymous public search, public view-only state, Escape close
  and focus return, and no browser console errors. The Browser check found and
  prompted a fix for a load-time backdrop caused by the picker class overriding
  its `hidden` attribute; the follow-up desktop and mobile checks passed.

## Documentation

No `specs/docs/` directory exists in this repository, so there was no living
documentation artifact to update.

## Team Execution

Four read-only research agents mapped the backend API/query plan, frontend
module boundaries, stale-state/race controls, and isolated Browser test plan.
The implementation was completed on the existing user-requested branch
`codex/011-add-beer-run-selector-ui`; this intentionally retains the branch
created during specification work rather than creating the skill's usual
`spec/` branch or a worktree.
