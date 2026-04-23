import os
import json
import sqlite3
import sys

# Add the project root to sys.path so we can import local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from auth import get_password_hash

DB_FILE = os.path.join(BASE_DIR, "boozerun.db")
CONFIG_FILE = os.path.join(BASE_DIR, "users.json")

def migrate():
    """Adds missing columns to the database."""
    if not os.path.exists(DB_FILE):
        print(f"Database {DB_FILE} not found. Skipping manual migration (tables will be created by app).")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(users)")
        user_columns = [info[1] for info in cursor.fetchall()]
        
        if "hashed_password" not in user_columns:
            print("Adding 'hashed_password' column to 'users' table...")
            cursor.execute("ALTER TABLE users ADD COLUMN hashed_password TEXT")
        else:
            print("'hashed_password' column already exists.")

        cursor.execute("PRAGMA table_info(entries)")
        entry_columns = [info[1] for info in cursor.fetchall()]

        if "timezone" not in entry_columns:
            print("Adding 'timezone' column to 'entries' table...")
            cursor.execute("ALTER TABLE entries ADD COLUMN timezone TEXT")
        else:
            print("'timezone' column already exists.")

        if "timezone_code" not in entry_columns:
            print("Adding 'timezone_code' column to 'entries' table...")
            cursor.execute("ALTER TABLE entries ADD COLUMN timezone_code TEXT")
        else:
            print("'timezone_code' column already exists.")

        conn.commit()
        print("Migration successful.")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

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

    # Ensure tables exist
    models.Base.metadata.create_all(bind=engine)

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
