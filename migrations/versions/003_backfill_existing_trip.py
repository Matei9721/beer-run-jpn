from __future__ import annotations

import sqlite3

ID = "003_backfill_existing_trip"
DESCRIPTION = "Backfill existing trip into BeerRunJPN"

DEFAULT_RUN_NAME = "BeerRunJPN"
OWNER_USERNAME = "Tamei"


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _beer_run_jpn_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM beer_runs WHERE name = ?", (DEFAULT_RUN_NAME,)).fetchone()
    return None if row is None else row[0]


def baseline_matches(conn: sqlite3.Connection) -> bool:
    if not all(_table_exists(conn, table) for table in ("users", "entries", "beer_runs", "beer_run_members")):
        return False

    beer_run_id = _beer_run_jpn_id(conn)
    if beer_run_id is None:
        return False

    unassigned_entries = conn.execute("SELECT COUNT(*) FROM entries WHERE beer_run_id IS NULL").fetchone()[0]
    missing_memberships = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE NOT EXISTS (
            SELECT 1
            FROM beer_run_members
            WHERE beer_run_members.user_id = users.id
              AND beer_run_members.beer_run_id = ?
        )
        """,
        (beer_run_id,),
    ).fetchone()[0]
    return unassigned_entries == 0 and missing_memberships == 0


def _ensure_beer_run_jpn(conn: sqlite3.Connection) -> int:
    beer_run_id = _beer_run_jpn_id(conn)
    if beer_run_id is None:
        conn.execute(
            "INSERT INTO beer_runs (name, is_public) VALUES (?, 1)",
            (DEFAULT_RUN_NAME,),
        )
        beer_run_id = _beer_run_jpn_id(conn)
    else:
        conn.execute("UPDATE beer_runs SET is_public = 1 WHERE id = ?", (beer_run_id,))

    if beer_run_id is None:
        raise RuntimeError(f"Failed to create or locate {DEFAULT_RUN_NAME}")
    return beer_run_id


def _ensure_memberships(conn: sqlite3.Connection, beer_run_id: int) -> None:
    users = conn.execute("SELECT id, username FROM users").fetchall()
    tamei_found = False

    for user_id, username in users:
        role = "owner" if username == OWNER_USERNAME else "member"
        if username == OWNER_USERNAME:
            tamei_found = True

        existing = conn.execute(
            """
            SELECT id, role
            FROM beer_run_members
            WHERE beer_run_id = ? AND user_id = ?
            """,
            (beer_run_id, user_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO beer_run_members (beer_run_id, user_id, role)
                VALUES (?, ?, ?)
                """,
                (beer_run_id, user_id, role),
            )
        elif username == OWNER_USERNAME and existing[1] != "owner":
            conn.execute("UPDATE beer_run_members SET role = 'owner' WHERE id = ?", (existing[0],))

    if not tamei_found:
        print(f"Warning: {OWNER_USERNAME} user not found; {DEFAULT_RUN_NAME} owner was not assigned.")


def _assign_unassigned_entries(conn: sqlite3.Connection, beer_run_id: int) -> None:
    conn.execute(
        "UPDATE entries SET beer_run_id = ? WHERE beer_run_id IS NULL",
        (beer_run_id,),
    )


def apply(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    beer_run_id = _ensure_beer_run_jpn(conn)
    _ensure_memberships(conn, beer_run_id)
    _assign_unassigned_entries(conn, beer_run_id)
