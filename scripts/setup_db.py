import os
import json
import sys

# Add the project root to sys.path so we can import local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from database import SessionLocal
import models
from auth import get_password_hash
from migrations.runner import apply_migrations

DB_FILE = os.path.join(BASE_DIR, "boozerun.db")
CONFIG_FILE = os.path.join(BASE_DIR, "users.json")

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
