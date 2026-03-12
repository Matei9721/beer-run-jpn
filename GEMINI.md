# Project Overview

**BoozeRunJpn** is a lightweight, mobile-first web application designed to track drink consumption during a trip to Japan. It features a global leaderboard and a simple entry system that automatically captures the user's GPS location and allows for photo proof of each drink.

# Flow

* **Leaderboard**: Displays consumption statistics (total liters and total alcohol) for all users on the main page.
* **Log a Drink**: Users can submit a new entry specifying the drink type, ABV%, quantity, and brand. 
* **Automatic Geolocation**: The app automatically retrieves the user's GPS coordinates (latitude/longitude) via the browser's Geolocation API.
* **Photo Proof**: Users can upload a picture of their drink, which is saved locally and linked to the entry.

# Tech Stack

The application is optimized for low-resource environments like a Raspberry Pi 3 and requires no external subscriptions.

* **Backend**: FastAPI (Python 3.13+)
* **Package Management**: `uv` (Fast, reliable dependency and Python version control)
* **Database**: SQLite (Zero-config, single-file storage)
* **ORM**: SQLAlchemy 2.0+ (Modern, asynchronous-ready database interaction)
* **Frontend**: Vanilla HTML5, CSS3, and JavaScript (No heavy frameworks or build steps)
* **Testing**: `pytest` with `httpx` for API verification

# Project Structure

```text
/
├── .python-version      # UV-managed Python version (3.13)
├── pyproject.toml       # Project dependencies and configuration
├── uv.lock              # Reproducible lockfile
├── main.py              # FastAPI application, routes, and static file serving
├── models.py            # SQLAlchemy database models (User, Entry)
├── database.py          # Database connection and session management
├── static/              # Static assets
│   ├── css/style.css    # Mobile-first neon/vibe styling
│   ├── js/app.js        # Frontend logic (leaderboard, geolocation, form submission)
│   └── uploads/         # Directory for uploaded drink proof photos
├── templates/
│   └── index.html       # Main application entry point
└── test_main.py         # Automated API and integration tests
```

# Usage

### Development / Deployment

To run the application locally or on a Raspberry Pi, ensure `uv` is installed, then execute:

```powershell
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

The application will be accessible at `http://<ip-address>:8000`.

### Running Tests

To verify the API and database logic:

```powershell
uv run pytest test_main.py
```

## Key Files

*   **`README.md`**: Brief project intent.
*   **`LICENSE`**: MIT License information.
*   **`.gitignore`**: Standard Python and SQLite ignore patterns.
