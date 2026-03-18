import os
import json
import sqlite3
from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from auth import get_password_hash

DB_FILE = "boozerun.db"
CONFIG_FILE = "users.json"

def migrate():
    """Adds missing columns to the database."""
    if not os.path.exists(DB_FILE):
        print(f"Database {DB_FILE} not found. Skipping manual migration (tables will be created by app).")
        return

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "hashed_password" not in columns:
            print("Adding 'hashed_password' column to 'users' table...")
            cursor.execute("ALTER TABLE users ADD COLUMN hashed_password TEXT")
            conn.commit()
            print("Migration successful.")
        else:
            print("'hashed_password' column already exists.")
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
