import os
import sys
import argparse

# Add the project root to sys.path so we can import local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
from auth import get_password_hash

def add_user(username: str, password: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            print(f"User '{username}' already exists.")
            return
        hashed_pw = get_password_hash(password)
        user = models.User(username=username, hashed_password=hashed_pw)
        db.add(user)
        db.commit()
        print(f"User '{username}' added successfully.")
    except Exception as e:
        print(f"Error adding user: {e}")
        db.rollback()
    finally:
        db.close()

def delete_user(username: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            print(f"User '{username}' not found.")
            return
        db.delete(user)
        db.commit()
        print(f"User '{username}' deleted successfully.")
    except Exception as e:
        print(f"Error deleting user: {e}")
        db.rollback()
    finally:
        db.close()

def rename_user(old_username: str, new_username: str):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == old_username).first()
        if not user:
            print(f"User '{old_username}' not found.")
            return
        if db.query(models.User).filter(models.User.username == new_username).first():
            print(f"User '{new_username}' already exists. Choose a different new username.")
            return
        user.username = new_username
        db.commit()
        print(f"Username changed from '{old_username}' to '{new_username}' successfully.")
    except Exception as e:
        print(f"Error renaming user: {e}")
        db.rollback()
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Manage users in the database.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new user.")
    add_parser.add_argument("username", type=str, help="Username to add.")
    add_parser.add_argument("password", type=str, help="Password for the user.")

    del_parser = subparsers.add_parser("delete", help="Delete a user.")
    del_parser.add_argument("username", type=str, help="Username to delete.")

    rename_parser = subparsers.add_parser("rename", help="Rename a user.")
    rename_parser.add_argument("old_username", type=str, help="Current username.")
    rename_parser.add_argument("new_username", type=str, help="New username.")

    args = parser.parse_args()

    if args.command == "add":
        add_user(args.username, args.password)
    elif args.command == "delete":
        delete_user(args.username)
    elif args.command == "rename":
        rename_user(args.old_username, args.new_username)

if __name__ == "__main__":
    main()
