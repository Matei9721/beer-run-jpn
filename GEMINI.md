# Project Overview

**BoozeRunJpn** is a lightweight, mobile-first web application designed to track drink consumption during a trip to Japan. It features a modern Cyber-Tokyo aesthetic, a global leaderboard, and an interactive map with detail sheets.

# Features & UX

* **Modern Aesthetic**: Glassmorphism UI with neon accents, optimized for both mobile and desktop.
* **Hybrid Map UX**: Small map popups with drink thumbnails that transition into a full-screen Bottom Sheet for complete details.
* **Image Optimization**: Server-side resizing (max 1080px) and JPEG compression via Pillow for fast loading on roaming data.
* **Reliable Geolocation**: User-gesture triggered GPS capture to bypass mobile browser security restrictions.
* **Auto-Polling & Sync**: A persistent "Sync Bar" that polls the server every 30s and allows manual on-demand refreshes.
* **Persistence**: Remembers the latest username locally using `localStorage`.
* **Authentication**: Lightweight JWT-based login system. Unauthenticated users can view data; only logged-in users can add drinks.

# Tech Stack

* **Backend**: FastAPI (Python 3.13+)
* **Auth**: JWT (python-jose) + Argon2 (argon2-cffi)
* **Image Processing**: Pillow (Resizing & Compression)
* **Database**: SQLite + SQLAlchemy 2.0+
* **Frontend**: Vanilla JS + CSS Glassmorphism + Leaflet + Leaflet.markercluster
* **Package Management**: `uv`

# Project Structure

```text
/
├── scripts/
│   └── setup_db.py      # Database migration & user sync script
├── tests/
│   ├── test_main.py     # General API tests
│   └── test_auth.py     # Authentication & access control tests
├── static/              
│   ├── css/style.css    # Cyber-Tokyo glassmorphism styles
│   ├── css/auth.css     # Auth modal & button styles
│   ├── js/app.js        # Frontend logic & Map/Sheet orchestration
│   └── uploads/         # Optimized JPEG drink photos
├── templates/
│   └── index.html       # Main application entry point
├── main.py              # Backend API & Route orchestration
├── auth.py              # Auth logic & JWT handling
├── models.py            # Database schemas
├── schemas.py           # Pydantic models
├── database.py          # SQLite engine & session setup
├── utils.py             # Image processing & helper functions
└── users.json           # User configuration (Git-ignored)
```

# Usage & Deployment

### 1. Setup Users & Database
Create a `users.json` file in the root:
```json
[
    {"username": "matei", "password": "securepassword"},
    {"username": "friend", "password": "anotherpassword"}
]
```
Then run the setup script (handles migrations and user sync):
```powershell
uv run python scripts/setup_db.py
```

### 2. Running Locally
```powershell
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. Running with HTTPS (Required for Geolocation)
To access outside your network with secure GPS support, use Caddy:
```powershell
caddy reverse-proxy --from your-domain.com --to localhost:8000
```

### 4. Testing
```powershell
uv run pytest
```
