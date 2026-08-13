# BoozeRunJpn 🍺🇯🇵

A lightweight, high-performance web application designed to track drink consumption during a trip to Japan. Optimized for Raspberry Pi 3.

## Features
- **Cyber-Tokyo Aesthetic**: Modern glassmorphism UI with neon accents.
- **Global Leaderboard**: Real-time ranking by liters and alcohol volume.
- **Interactive Map**: Visualize drink locations with clustering and detail views.
- **Slick Mobile UX**: Custom bottom detail sheets and user-gesture triggered GPS.
- **Image Optimization**: Automatic server-side resizing and compression for fast roaming.
- **Auto-Sync**: Background polling and manual refresh to keep data in sync.

## Tech Stack
- **Backend**: FastAPI (Python 3.13)
- **Database**: SQLite + SQLAlchemy
- **Frontend**: Vanilla HTML5/CSS3/JS + Leaflet
- **Deployment**: Uvicorn + Caddy (for HTTPS)

## Running the Application

### 1. Install Dependencies
Ensure you have `uv` installed, then run:
```powershell
uv sync
```

### 2. Configure private authentication values

Generate a cryptographically random secret with this cross-platform Python command:

```powershell
uv --cache-dir .uv-cache run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy `.env.example` to a private repository-root `.env` file. Replace both
placeholders: use the generated value for `SECRET_KEY` and choose a private
signup code to share only with invited users.

```dotenv
SECRET_KEY=paste-the-generated-value-here
SIGNUP_CODE=replace-with-private-signup-code
```

The application refuses to start when `SECRET_KEY` is missing, blank, padded
with whitespace, too short, or still set to an example value. A `SECRET_KEY`
already defined in the process environment takes precedence over `.env`. Keep
the value private and stable: changing it invalidates every issued login token
and requires users to log in again.

The application also refuses to start when `SIGNUP_CODE` is missing, blank,
padded with whitespace, or still set to the tracked example placeholder. A
`SIGNUP_CODE` already defined in the process environment takes precedence over
`.env`. Keep the real code private and out of source control. Participants send
it only in the JSON body of `POST /api/signup`; successful signup creates an
account but does not add it to BeerRunJPN or any other beer run.

### 3. Apply Database Migrations
Before starting the app, bring the local database to the expected schema:
```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py
```

For an existing database with the current `users` and `entries` tables, this records the baseline migration without recreating those tables. To check readiness without applying changes:
```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py --check
```

### Migrate legacy upload paths

The upload-path migration is a separate operator action; schema migration and
application startup never run it automatically. It copies legacy images into
run-specific UUID paths, verifies the copies, updates matching entry rows, and
retains every original flat file for rollback and old-URL compatibility.

Before applying it to live data:

1. Stop the application and any other process that can write entries.
2. Create or confirm recoverable, separately named backups of both the SQLite
   database and the complete `static/uploads` tree. Do not overwrite an
   existing backup while doing this.
3. Run the read-only preflight with both live paths stated explicitly:

```powershell
uv --cache-dir .uv-cache run python scripts/migrate_upload_paths.py --database .\boozerun.db --upload-root .\static\uploads --preflight
```

Resolve every reported missing, invalid, or conflicting entry before apply.
Preflight returns a nonzero status while any unresolved row remains.

4. With application writes still stopped, apply the migration explicitly:

```powershell
uv --cache-dir .uv-cache run python scripts/migrate_upload_paths.py --database .\boozerun.db --upload-root .\static\uploads --apply
```

5. Require a zero exit status, rerun preflight, and confirm its summary reports
   no planned, missing, invalid, or conflicting rows. Confirm the retained flat
   sources and their new nested copies are both present before restarting the
   application.

The command is resumable: after a partial failure, leave both source and nested
files in place, correct the reported problem, and rerun the same apply command.
It verifies and reuses an identical deterministic destination rather than
creating another copy. Never delete retained legacy sources as part of this
procedure.

### 4. Start the Backend
Run the FastAPI server on all interfaces:
```powershell
uv --cache-dir .uv-cache run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. Expose with HTTPS (Caddy)
To use Geolocation on mobile phones outside your local network, you **must** use HTTPS. Install [Caddy](https://caddyserver.com/) and run:

```powershell
.\caddy_windows_amd64.exe run
```
*Replace `your-domain.com` with your actual domain or a dynamic DNS address.*

## Testing
To verify API and database integrity:
```powershell
uv --cache-dir .uv-cache run pytest
```
