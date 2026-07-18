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
uv --cache-dir .uv-cache run uvicorn main:app --host 127.0.0.1 --port 8000

# Run tests
uv --cache-dir .uv-cache run pytest

# Apply or check database migrations
uv --cache-dir .uv-cache run python scripts/migrate_db.py
uv --cache-dir .uv-cache run python scripts/migrate_db.py --check

# Generate Wrapped data
uv --cache-dir .uv-cache run python scripts/build_wrapped_data.py
```

## Architecture At A Glance

- `main.py`: FastAPI routes, default BeerRunJPN behavior, and image handling
- `auth.py`: JWT creation/validation and password hashing
- `database.py`: SQLite engine/session setup
- `models.py`: SQLAlchemy models for users, entries, beer-runs, and memberships
- `migrations/`: ordered SQLite migrations
- `templates/` and `static/`: browser-facing UI; no bundler
- `tests/`: pytest coverage using an isolated database
- `specs/`: durable feature specifications and design history
