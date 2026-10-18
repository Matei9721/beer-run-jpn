import os
import json
from pathlib import Path
import sys

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from beer_run import models
from beer_run.auth import get_password_hash
from beer_run.database import SessionLocal
from beer_run.migrations.runner import apply_migrations
from beer_run.paths import DEFAULT_DATABASE_PATH, REPOSITORY_ROOT

DB_FILE = str(DEFAULT_DATABASE_PATH)
CONFIG_FILE = str(REPOSITORY_ROOT / "users.json")

def migrate():
    """Apply repository database migrations."""
    result = apply_migrations(DB_FILE)
    if result.applied:
        print(f"Applied migrations: {', '.join(result.applied)}")
    if result.baselined:
        print(f"Baselined migrations: {', '.join(result.baselined)}")
    if result.skipped and not result.applied and not result.baselined:
        print("Database migrations are already up to date.")

def sync_users():
    """Syncs users from users.json to the database."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file {CONFIG_FILE} not found. Skipping user sync.")
        return

    try:
        with open(CONFIG_FILE, "r") as f:
            users_config = json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding {CONFIG_FILE}. Check format.")
        return

    db = SessionLocal()
    try:
        print(f"Syncing {len(users_config)} users from config...")
        for user_data in users_config:
            username = user_data.get("username")
            password = user_data.get("password")
            
            if not username or not password:
                continue

            user = db.query(models.User).filter(models.User.username == username).first()
            hashed_pw = get_password_hash(password)

            if user:
                user.hashed_password = hashed_pw
                print(f"Updated user: {username}")
            else:
                user = models.User(username=username, hashed_password=hashed_pw)
                db.add(user)
                print(f"Created user: {username}")
        
        db.commit()
        print("User sync complete.")
    except Exception as e:
        print(f"Error syncing users: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
    sync_users()
