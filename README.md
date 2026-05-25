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

### 2. Apply Database Migrations
Before starting the app, bring the local database to the expected schema:
```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py
```

For an existing database with the current `users` and `entries` tables, this records the baseline migration without recreating those tables. To check readiness without applying changes:
```powershell
uv --cache-dir .uv-cache run python scripts/migrate_db.py --check
```

### 3. Start the Backend
Run the FastAPI server on all interfaces:
```powershell
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Expose with HTTPS (Caddy)
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
