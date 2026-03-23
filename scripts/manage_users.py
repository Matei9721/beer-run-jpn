import os
import sys
import argparse
from typing import Callable

# Add the project root to sys.path so we can import local modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, engine
import models
from auth import get_password_hash

def _normalize_username(username: str) -> str:
    normalized = (username or "").strip()
    if not normalized:
        raise ValueError("Username cannot be empty.")
    return normalized


def _validate_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty.")
    return password


def _find_user(db: Session, username: str):
    normalized = _normalize_username(username)
    return db.query(models.User).filter(func.lower(models.User.username) == normalized.lower()).first()


def _ensure_tables_exist():
    models.Base.metadata.create_all(bind=engine)


def add_user(username: str, password: str, session_factory: Callable[[], Session] = SessionLocal) -> int:
    db = session_factory()
    try:
        normalized_username = _normalize_username(username)
        validated_password = _validate_password(password)
        user = _find_user(db, normalized_username)
        if user:
            print(f"User '{user.username}' already exists.", file=sys.stderr)
            return 1
        hashed_pw = get_password_hash(validated_password)
        user = models.User(username=normalized_username, hashed_password=hashed_pw)
        db.add(user)
        db.commit()
        print(f"User '{normalized_username}' added successfully.")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        db.rollback()
        return 1
    except Exception as e:
        print(f"Error adding user: {e}", file=sys.stderr)
        db.rollback()
        return 1
    finally:
        db.close()


def delete_user(
    username: str,
    delete_entries: bool = False,
    session_factory: Callable[[], Session] = SessionLocal,
) -> int:
    db = session_factory()
    try:
        normalized_username = _normalize_username(username)
        user = _find_user(db, normalized_username)
        if not user:
            print(f"User '{normalized_username}' not found.", file=sys.stderr)
            return 1

        entry_count = db.query(models.Entry).filter(models.Entry.user_id == user.id).count()
        if entry_count and not delete_entries:
            print(
                f"Refusing to delete user '{user.username}' because they still own {entry_count} entr{'y' if entry_count == 1 else 'ies'}. "
                "Re-run with --delete-entries to remove the dependent entries in the same transaction.",
                file=sys.stderr,
            )
            return 1

        if entry_count:
            db.query(models.Entry).filter(models.Entry.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
        if entry_count:
            print(f"User '{user.username}' and {entry_count} dependent entr{'y' if entry_count == 1 else 'ies'} deleted successfully.")
        else:
            print(f"User '{user.username}' deleted successfully.")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        db.rollback()
        return 1
    except Exception as e:
        print(f"Error deleting user: {e}", file=sys.stderr)
        db.rollback()
        return 1
    finally:
        db.close()


def rename_user(
    old_username: str,
    new_username: str,
    session_factory: Callable[[], Session] = SessionLocal,
) -> int:
    db = session_factory()
    try:
        normalized_old_username = _normalize_username(old_username)
        normalized_new_username = _normalize_username(new_username)
        user = _find_user(db, normalized_old_username)
        if not user:
            print(f"User '{normalized_old_username}' not found.", file=sys.stderr)
            return 1
        if user.username.lower() == normalized_new_username.lower():
            print("New username must be different from the current username.", file=sys.stderr)
            return 1

        existing_user = _find_user(db, normalized_new_username)
        if existing_user:
            print(f"User '{existing_user.username}' already exists. Choose a different new username.", file=sys.stderr)
            return 1

        previous_username = user.username
        user.username = normalized_new_username
        db.commit()
        print(f"Username changed from '{previous_username}' to '{normalized_new_username}' successfully.")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        db.rollback()
        return 1
    except Exception as e:
        print(f"Error renaming user: {e}", file=sys.stderr)
        db.rollback()
        return 1
    finally:
        db.close()


def main(argv=None, session_factory: Callable[[], Session] = SessionLocal) -> int:
    parser = argparse.ArgumentParser(description="Manage users in the database.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Add a new user.")
    add_parser.add_argument("username", type=str, help="Username to add.")
    add_parser.add_argument("password", type=str, help="Password for the user.")

    del_parser = subparsers.add_parser("delete", help="Delete a user.")
    del_parser.add_argument("username", type=str, help="Username to delete.")
    del_parser.add_argument(
        "--delete-entries",
        action="store_true",
        help="Delete the user's dependent entries in the same transaction.",
    )

    rename_parser = subparsers.add_parser("rename", help="Rename a user.")
    rename_parser.add_argument("old_username", type=str, help="Current username.")
    rename_parser.add_argument("new_username", type=str, help="New username.")

    args = parser.parse_args(argv)
    _ensure_tables_exist()

    if args.command == "add":
        return add_user(args.username, args.password, session_factory=session_factory)
    if args.command == "delete":
        return delete_user(args.username, delete_entries=args.delete_entries, session_factory=session_factory)
    if args.command == "rename":
        return rename_user(args.old_username, args.new_username, session_factory=session_factory)

    return 1

if __name__ == "__main__":
    raise SystemExit(main())
