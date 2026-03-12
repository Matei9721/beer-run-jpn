# Project Overview

**BoozeRunJpn** is a lightweight, mobile-first web application designed to track drink consumption during a trip to Japan. It features a global leaderboard, a map visualization of all logged drinks, and a simple entry system that captures the user's GPS location and allows for photo proof.

# Flow

* **Leaderboard**: Displays consumption statistics (total liters and total alcohol) for all users.
* **Map Visualization**: A Leaflet-powered map displaying all drink locations, with user filtering and "spiderfy" clustering to handle multiple drinks at the same location.
* **Log a Drink**: Users can submit a new entry with a user-gesture triggered location capture and photo proof.
* **Automatic Geolocation**: Reliable GPS capture triggered via button click for mobile browser compatibility.

# Tech Stack

The application is optimized for low-resource environments like a Raspberry Pi 3 and requires no external subscriptions.

* **Backend**: FastAPI (Python 3.13+)
* **Package Management**: `uv`
* **Database**: SQLite
* **ORM**: SQLAlchemy 2.0+
* **Frontend**: Vanilla HTML5/CSS3/JS + Leaflet.js + Leaflet.markercluster
* **Testing**: `pytest`

# Project Structure

```text
/
├── .python-version      # UV-managed Python version (3.13)
├── pyproject.toml       # Project dependencies
├── uv.lock              # Reproducible lockfile
├── main.py              # FastAPI app & API routes
├── models.py            # SQLAlchemy models
├── database.py          # Database setup
├── static/              # Static assets
│   ├── css/style.css    # Mobile-first neon styling
│   ├── js/app.js        # Frontend logic (Tabs, Map, Geolocation)
│   └── uploads/         # Uploaded drink photos
├── templates/
│   └── index.html       # Main HTML template
└── test_main.py         # Automated API tests
```

# Usage

### Development / Deployment

```powershell
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

*Note: Mobile geolocation strictly requires HTTPS unless accessed via localhost.*

### Running Tests

```powershell
uv run pytest test_main.py
```

## Key Files

*   **`README.md`**: Project intent.
*   **`LICENSE`**: MIT License.
*   **`.gitignore`**: Standard ignore patterns.
