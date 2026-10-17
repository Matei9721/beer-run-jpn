# BoozeRunJpn Agent Guide

## Required Repository Instructions

Before planning, editing, or running mutating commands, read and follow
[`repository_rules.md`](repository_rules.md). It is the authoritative source for
this repository's architecture principles, runtime-data protections, workflow,
verification gates, frontend constraints, and operational commands.

If guidance in another project document conflicts with `repository_rules.md`,
follow `repository_rules.md` unless the user explicitly directs otherwise.

## Project Overview

BoozeRunJpn is a compact FastAPI app for logging drinks during a trip. It has a
public BeerRunJPN trip view, authenticated drink-entry creation, optimized
photo uploads, a vanilla JavaScript and Leaflet frontend, and a generated
`/wrapped` recap.

Keep the application lightweight: Python, SQLite, static templates/assets, and
no frontend build step.

## Primary Commands

```powershell
# Install dependencies
uv sync

# Run locally
uv --cache-dir .uv-cache run uvicorn beer_run.main:app --app-dir src --host 127.0.0.1 --port 8000

# Run tests
uv --cache-dir .uv-cache run pytest

# Apply or check database migrations
uv --cache-dir .uv-cache run python scripts/migrate_db.py
uv --cache-dir .uv-cache run python scripts/migrate_db.py --check

# Generate Wrapped data
uv --cache-dir .uv-cache run python scripts/build_wrapped_data.py --run-id <id>
```

## Architecture At A Glance

- `src/beer_run/main.py`: application startup, public/trip routes, legacy trip APIs, and image handling
- `src/beer_run/auth_routes.py`: login, signup, current-user routes, and signup request error handling
- `src/beer_run/auth.py`: JWT creation/validation and password hashing
- `src/beer_run/database.py`: SQLite engine/session setup
- `src/beer_run/models.py`: SQLAlchemy models for users, entries, beer-runs, and memberships
- `src/beer_run/migrations/`: ordered SQLite migrations
- `src/frontend/app/`: production browser UI and assets; no bundler
- `src/frontend/pages/` and `src/frontend/static/`: direct legal and Wrapped surfaces
- `static/uploads/`: protected runtime uploads
- `tests/`: pytest coverage using an isolated database
- `specs/`: durable feature specifications and design history
- `specs/004-harden-auth-tokens/spec.md`: Release 1 auth-hardening contract for private JWT configuration, stable ID-based tokens, and forced legacy-session login
- `specs/005-add-signup-api/spec.md`: Release 1 signup API contract for private signup-code configuration, validated account creation, case-insensitive username identity, and immediate bearer tokens
