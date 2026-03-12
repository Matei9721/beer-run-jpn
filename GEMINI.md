# Project Overview

**BoozeRunJpn** is a lightweight, mobile-first web application designed to track drink consumption during a trip to Japan. It features a modern Cyber-Tokyo aesthetic, a global leaderboard, and an interactive map with detail sheets.

# Features & UX

* **Modern Aesthetic**: Glassmorphism UI with neon accents, optimized for both mobile and desktop.
* **Hybrid Map UX**: Small map popups with drink thumbnails that transition into a full-screen Bottom Sheet for complete details.
* **Image Optimization**: Server-side resizing (max 1080px) and JPEG compression via Pillow for fast loading on roaming data.
* **Reliable Geolocation**: User-gesture triggered GPS capture to bypass mobile browser security restrictions.
* **Auto-Polling & Sync**: A persistent "Sync Bar" that polls the server every 30s and allows manual on-demand refreshes.
* **Persistence**: Remembers the latest username locally using `localStorage`.

# Tech Stack

* **Backend**: FastAPI (Python 3.13+)
* **Image Processing**: Pillow (Resizing & Compression)
* **Database**: SQLite + SQLAlchemy 2.0+
* **Frontend**: Vanilla JS + CSS Glassmorphism + Leaflet + Leaflet.markercluster
* **Package Management**: `uv`

# Project Structure

```text
/
├── .python-version      # UV-managed Python version (3.13)
├── pyproject.toml       # Dependencies (fastapi, pillow, sqlalchemy, etc.)
├── main.py              # Backend API & Image processing logic
├── models.py            # Database schemas
├── database.py          # SQLite engine & session setup
├── static/              
│   ├── css/style.css    # Cyber-Tokyo glassmorphism styles
│   ├── js/app.js        # Frontend logic & Map/Sheet orchestration
│   └── uploads/         # Optimized JPEG drink photos
├── templates/
│   └── index.html       # Main application entry point
└── test_main.py         # API verification tests
```

# Usage & Deployment

### Running Locally
```powershell
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Running with HTTPS (Required for Geolocation)
To access outside your network with secure GPS support, use Caddy:
```powershell
caddy reverse-proxy --from your-domain.com --to localhost:8000
```

### Testing
```powershell
uv run pytest test_main.py
```
