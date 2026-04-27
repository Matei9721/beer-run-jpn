# BoozeRunJpn Project Guide

## What This Project Is

BoozeRunJpn / BeerRunJPN is a small FastAPI web app for logging drinks from a Japan trip. It has:

- A public leaderboard and drink map.
- JWT login for users who can add drink entries.
- Photo uploads that are normalized, resized, and saved as JPEGs.
- A static vanilla-JS frontend with Leaflet maps.
- A `/wrapped` recap reel powered by generated JSON in `data/wrapped.json`.

The app is intentionally lightweight: Python backend, SQLite database, static templates/assets, no frontend build step.

## Tech Stack

- Python 3.13+
- FastAPI + Uvicorn
- SQLAlchemy 2.x + SQLite
- Pydantic
- JWT auth via `python-jose`
- Argon2 password hashing via `passlib` / `argon2-cffi`
- Pillow for upload image optimization
- Vanilla HTML/CSS/ES modules
- Leaflet + Leaflet.markercluster from CDN
- `uv` for dependency and command execution
- Pytest for tests

## Main Commands

Install dependencies:

```powershell
uv sync
```

Run the app locally:

```powershell
uv --cache-dir .uv-cache run uvicorn main:app --host 127.0.0.1 --port 8000
```

Run on the local network:

```powershell
uv --cache-dir .uv-cache run uvicorn main:app --host 0.0.0.0 --port 8000
```

Run tests:

```powershell
uv --cache-dir .uv-cache run pytest
```

Current verification status: `uv --cache-dir .uv-cache run pytest` passes with 10 tests and 1 Argon2 deprecation warning.

Browser-test the running app with the Browser Use plugin (`@browser-use`) in the Codex in-app browser. Prefer it over Playwright CLI for local app inspection, screenshots, and interaction checks.

Initialize or migrate the app database and sync users from `users.json`:

```powershell
uv --cache-dir .uv-cache run python scripts/setup_db.py
```

Generate Wrapped data from the current SQLite database:

```powershell
uv --cache-dir .uv-cache run python scripts/build_wrapped_data.py
```

Manage users directly in the database:

```powershell
uv --cache-dir .uv-cache run python scripts/manage_users.py add <username> <password>
uv --cache-dir .uv-cache run python scripts/manage_users.py rename <old_username> <new_username>
uv --cache-dir .uv-cache run python scripts/manage_users.py delete <username>
uv --cache-dir .uv-cache run python scripts/manage_users.py delete <username> --delete-entries
```

Run Caddy for HTTPS/mobile geolocation deployment using the local `Caddyfile`:

```powershell
.\caddy_windows_amd64.exe run
```

## Repository Structure

```text
.
|-- main.py                     # FastAPI app, API routes, image upload processing
|-- auth.py                     # JWT creation/validation and password hashing
|-- database.py                 # SQLite engine/session setup, points at boozerun.db
|-- models.py                   # SQLAlchemy User and Entry tables
|-- schemas.py                  # Pydantic response models
|-- pyproject.toml              # Python metadata, dependencies, pytest config
|-- uv.lock                     # Locked Python dependency graph
|-- users.json                  # Local user/password seed file, untracked runtime config
|-- boozerun.db                 # Local app database, untracked runtime state
|-- test.db                     # Test database created by pytest, untracked runtime state
|-- data/
|   |-- drinks.json             # Drink type and quantity options served by /api/config
|   `-- wrapped.json            # Generated Wrapped reel payload served by /api/wrapped
|-- scripts/
|   |-- setup_db.py             # Simple migration plus users.json sync
|   |-- manage_users.py         # Add, rename, and delete DB users
|   `-- build_wrapped_data.py   # Builds data/wrapped.json from boozerun.db
|-- templates/
|   |-- index.html              # Main app shell
|   `-- wrapped.html            # Wrapped reel shell
|-- static/
|   |-- css/                    # App, auth, and Wrapped styles
|   |-- js/
|   |   |-- app.js              # Main app orchestration
|   |   |-- wrapped.js          # Wrapped reel renderer/player
|   |   `-- modules/            # api/auth/map/ui frontend modules
|   |-- img/logo.png
|   |-- audio/wrapped.mp3
|   `-- uploads/                # Uploaded drink images, local runtime state
`-- tests/
    |-- conftest.py             # TestClient and SQLite test DB override
    |-- test_auth.py
    |-- test_main.py
    `-- test_wrapped.py
```

## Runtime Behavior

- `main.py` calls `models.Base.metadata.create_all(bind=engine)` on import/startup, so missing SQLite tables are created automatically.
- `database.py` hardcodes the app database to `boozerun.db` in the repository root.
- Tests override `get_db` with `sqlite:///./test.db` in `tests/conftest.py`.
- `users.json` is optional. `scripts/setup_db.py` uses it to create or update users with hashed passwords.
- Login is case-insensitive, but `auth.get_current_user` later looks up the username from the JWT exactly as stored in the token.
- Posting `/api/entries` requires a bearer token. Viewing entries, leaderboard, config, and Wrapped is public.
- Uploaded images are stored under `static/uploads` as optimized JPEGs using timestamp filenames.
- The frontend polls leaderboard and entries every 30 seconds and also supports manual refresh through the sync bar.

## API Surface

- `GET /` returns `templates/index.html`.
- `GET /wrapped` returns `templates/wrapped.html`.
- `GET /api/config` returns `data/drinks.json`.
- `GET /api/wrapped` returns `data/wrapped.json`.
- `POST /token` accepts OAuth2 form fields and returns a bearer token.
- `GET /api/me` returns the authenticated user.
- `GET /api/leaderboard` returns users sorted by total pure alcohol.
- `GET /api/entries` returns entries, optionally filtered by `?username=`.
- `POST /api/entries` creates an authenticated drink entry from multipart form data.

## Frontend Notes

- There is no bundler. JavaScript is loaded as browser ES modules.
- `static/js/app.js` imports modules with query-string cache busters.
- `templates/index.html` and `templates/wrapped.html` also use query-string cache busters for JS/CSS.
- When changing static JS or CSS that has been deployed or tested in a browser, bump the relevant `?v=` values so stale browser caches do not hide the change.
- Leaflet, marker clustering, fonts, and marker icons are loaded from public CDNs.
- Mobile geolocation requires HTTPS except on localhost. Use Caddy or another HTTPS reverse proxy for phones.
- For manual or visual frontend verification, use `@browser-use` against `http://127.0.0.1:8000/` or `http://127.0.0.1:8000/wrapped`. Reload the tab after static asset changes before checking screenshots or DOM state.

## Wrapped Notes

- `data/wrapped.json` is generated, but currently tracked.
- `scripts/build_wrapped_data.py` reads `boozerun.db`, validates image paths under the project root, skips empty/missing images, and writes the full slide payload.
- Wrapped uses `static/audio/wrapped.mp3` if present.
- The Wrapped tests exercise both `/wrapped` and `build_wrapped_data`.
- Wrapped is layout-heavy; after changing `templates/wrapped.html`, `static/css/wrapped.css`, `static/js/wrapped.js`, or `data/wrapped.json`, start the server and inspect `/wrapped` with `@browser-use` on desktop and mobile-sized viewports when possible.

## Local State To Treat Carefully

The current working tree has many local/untracked runtime artifacts, including IDE settings, Playwright logs, databases, caches, user config, and uploaded photos. Do not delete, reset, or commit them unless explicitly asked.

Important local artifacts:

- `boozerun.db`
- `test.db`
- `users.json`
- `static/uploads/`
- `.venv/`
- `.uv-cache/`
- `.pytest_cache/`
- `.playwright-cli/`
- `.idea/`
- `Caddyfile`
- `caddy_windows_amd64.exe`

Also note: `.gitignore` currently appears to contain mojibake / NUL-byte corruption near the `users.json` entry, and `users.json` still appears as untracked in `git status`.
