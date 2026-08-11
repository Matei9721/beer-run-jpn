# BoozeRunJpn Repository Rules

This document consolidates the project's former constitution and repository
rules. It is the authoritative durable guidance for work in this repository.

## Core Principles

### I. Lightweight Direct Architecture

BoozeRunJpn must remain a compact FastAPI, SQLite, and static-assets application.
Backend behavior belongs in the existing direct modules unless demonstrated
complexity justifies extraction. Frontend work must use the existing vanilla
JavaScript module boundaries. Do not add a build system, SPA framework, or broad
abstraction layer unless the user explicitly requests it and the tradeoff is
documented.

The app is optimized for a small trip-tracking workflow and Raspberry Pi-class
deployment; unnecessary structure makes maintenance and deployment harder.

### II. Runtime Data Is Protected

Local runtime state is user data, not disposable workspace noise. Never delete,
reset, commit, overwrite, or destructively migrate `boozerun.db`,
`boozerun_backup.db`, `test.db`, `users.json`, `static/uploads/`, or local caches
without direct user instruction.

Schema and persisted-data changes must account for `models.py`, API
serialization in `main.py`, and the migration path in `migrations/` plus
`scripts/migrate_db.py`. Account for `scripts/setup_db.py` when user setup is
affected.

### III. Verification Is Required For Changed Behavior

Changes to backend routes, auth, database models, migrations, scripts, data
generation, or Wrapped behavior must be verified with:

```powershell
uv --cache-dir .uv-cache run pytest
```

Changes to auth, entry creation, leaderboards, schemas, migrations, or Wrapped
generation must add or update focused tests. Frontend layout or interaction
changes must also be inspected in the running local app with the Codex in-app
browser, including mobile-sized views when layout changes.

### IV. Mobile Trip UX And Performance

Preserve mobile-first use during travel. Geolocation must remain
user-triggerable, map and detail interactions must stay touch-friendly,
leaderboard cards must continue to open user history, and uploads must remain
size-conscious through server-side image normalization.

Static asset changes that affect deployed browser behavior must update relevant
cache-busting query strings. Features that depend on phone geolocation must
document the HTTPS or localhost requirement.

### V. Auth, Privacy, And API Boundaries

Authenticated writes must continue to require bearer-token access. Password
handling must use the existing hashed-password path or a reviewed replacement
with equivalent security. Public API response shapes must stay stable unless
frontend consumers and tests are updated in the same change. Sensitive local
files and uploaded user media must remain out of commits unless the user
explicitly requests otherwise.

## Stack And Architecture

- Python 3.13+, FastAPI, SQLAlchemy 2.x, SQLite, Pydantic, Pillow, pytest, and `uv`
- Vanilla HTML/CSS/ES modules with Leaflet CDN assets
- Uvicorn for local serving and Caddy for local HTTPS
- `main.py`: application startup, public/trip routes, default BeerRunJPN behavior, and image handling
- `auth_routes.py`: login, signup, current-user routes, and signup request error handling
- `auth.py`: JWT creation/validation and password hashing
- `database.py`: SQLite engine/session setup
- `models.py`: SQLAlchemy models for users, entries, beer-runs, and memberships
- `schemas.py`: API request and response models
- `migrations/`: ordered SQLite migrations; use `scripts/migrate_db.py`
- `scripts/`: migration, user-management, setup, and generated-data utilities
- `templates/` and `static/`: browser-facing UI; no bundler
- `tests/`: pytest coverage using an isolated database
- `specs/`: durable feature specifications and design history; keep these even
  when the workflow or tool that produced them is retired

Use `uv --cache-dir .uv-cache run ...` for repeatable local dependency behavior.

## Repository Workflow

- Start by checking `git status --short`; valuable local runtime state and
  untracked trip artifacts are common in this repository.
- Keep edits scoped. Small direct changes are usually preferable to new
  abstraction layers in this compact app.
- Code comments and test docstrings must not cite specification identifiers or
  task numbers (for example `FR-1.5`, `AR-2.5`, `Spec 009`, or `Task 15`).
  Comments describe the code's intent and behavior in the code's own terms;
  requirement IDs belong in `specs/` documents and implementation summaries,
  not in source.
- Distinguish source files, generated data, specifications, and runtime state
  when planning a change. State explicitly when a task crosses those boundaries.
- Treat existing `specs/` documents as durable project knowledge. Do not delete
  them merely because their original authoring tool is no longer used.
- Do not assume older README commands or test counts are current. Use the
  commands in this document and inspect the present result.
- The `.gitignore` may contain an older corrupted-looking `users.json` line with
  embedded NUL characters. If editing it, preserve intended ignores and verify
  `git status --short` afterward.

## Files And Runtime State

- Treat `main.py`, `auth_routes.py`, `auth.py`, `database.py`, `models.py`, `schemas.py`,
  `migrations/`, `scripts/`, `templates/`, `static/css`, `static/js`, tests,
  specifications, and project metadata as source or durable project material.
- Treat `boozerun.db`, `boozerun_backup.db`, `test.db`, `users.json`,
  `static/uploads/`, `.venv/`, `.uv-cache/`, `.pytest_cache/`,
  `.playwright-cli/`, `.idea/`, and `__pycache__/` as runtime or local state.
- Do not apply a migration to `boozerun.db` unless the user explicitly
  authorizes it. Use `scripts/migrate_db.py --check` for a read-only readiness
  check.
- Tests must use the isolated test database override and must never point at
  `boozerun.db`.
- Preserve existing uploaded-image paths unless a dedicated, tested file
  migration says otherwise.
- `data/wrapped.json` is generated by `scripts/build_wrapped_data.py` but is
  currently tracked. Regenerate it when changed Wrapped logic affects the
  requested output.

## Backend Rules

- `BeerRunJPN` is the public fallback run for an unsigned visitor and for a
  signed-in user without a valid remembered selection. Ranking, map, filters,
  and entry creation are scoped to the run selected in the shared picker.
- Persist a signed-in user's selected run by immutable ID, validate it on each
  identity transition, and clear scoped browser state before displaying a
  different run. Anonymous selections are session-only. A public run grants
  read access only; writing still requires that user's current membership.
- Keep public API response shapes stable unless frontend consumers and tests are
  updated in the same change.
- Keep JWT/password/configuration primitives in `auth.py` and auth-facing HTTP
  flows in `auth_routes.py`; the frontend stores the access token in
  `localStorage` under `access_token`.
- Uploaded images are normalized and stored under `static/uploads/`. Keep image
  handling in `main.py` unless it grows enough to justify extraction.

## Frontend Rules

Retain these browser module responsibilities:

- `static/js/modules/api.js`: network calls
- `static/js/modules/auth.js`: token and auth UI state
- `static/js/modules/map.js`: Leaflet and marker behavior
- `static/js/modules/ui.js`: rendering and UI helpers
- `static/js/modules/beer-runs.js`: run-picker UI and selected-run storage key
- `static/js/app.js`: application orchestration
- `static/js/wrapped.js`: Wrapped reel behavior

When changing deployed static JavaScript or CSS, update relevant cache-busting
query strings in `templates/index.html`, `templates/wrapped.html`, and module
imports in `static/js/app.js` as applicable.

CDN-backed dependencies can make browser behavior network-dependent; pytest does
not validate CDN loading. Inspect frontend changes in the running local app with
the Codex in-app browser. Check desktop and mobile-sized viewports when layout
changes. Use Playwright CLI only when the user specifically requests it or the
in-app browser cannot perform the needed check.

After changing Wrapped templates, CSS, JavaScript, or generated data, inspect
`/wrapped` on desktop and mobile-sized viewports.

## Verification And Completion

- Run the full pytest suite after backend, migration, auth, script,
  data-generation, or Wrapped behavior changes.
- Add or update focused tests for auth behavior, entry creation or serialization,
  leaderboard calculations, database schemas, migrations, and Wrapped
  generation.
- Pair pytest with browser inspection for frontend and Wrapped changes.
- A change is complete only when relevant tests and browser checks pass,
  generated data is refreshed when required, and runtime state remains
  preserved.
- If a required check cannot run, report what was not verified and why.

## Operational Commands

```powershell
# Install dependencies
uv sync

# Run locally
uv --cache-dir .uv-cache run uvicorn main:app --host 127.0.0.1 --port 8000

# Run for LAN/mobile access
uv --cache-dir .uv-cache run uvicorn main:app --host 0.0.0.0 --port 8000

# Run tests
uv --cache-dir .uv-cache run pytest

# Apply or check database migrations
uv --cache-dir .uv-cache run python scripts/migrate_db.py
uv --cache-dir .uv-cache run python scripts/migrate_db.py --check

# Sync users after migrations
uv --cache-dir .uv-cache run python scripts/setup_db.py

# Generate Wrapped data
uv --cache-dir .uv-cache run python scripts/build_wrapped_data.py

# Run the local HTTPS proxy
.\caddy_windows_amd64.exe run
```

For mobile GPS, use HTTPS or localhost. Plain HTTP on another device will
usually block geolocation.

Use `scripts/manage_users.py` to manage users without editing `users.json`.
Deleting a user with entries requires `--delete-entries`; the script
intentionally refuses otherwise.

## Governance

Update this document when architecture, operational safety, or quality gates
materially change. Amendments should explain why the rule changed and update
dependent agent guidance in the same change.

Any intentional exception to a required rule must be called out with its
rationale and the simpler or safer alternative considered. User instructions
take precedence when they explicitly authorize an exception.
