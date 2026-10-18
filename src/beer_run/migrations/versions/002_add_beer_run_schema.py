from __future__ import annotations

import sqlite3

ID = "002_add_beer_run_schema"
DESCRIPTION = "Add beer-runs, memberships, and entry run association"

REQUIRED_COLUMNS = {
    "beer_runs": {"id", "name", "is_public", "created_at"},
    "beer_run_members": {"id", "beer_run_id", "user_id", "role", "created_at"},
    "entries": {"beer_run_id"},
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def baseline_matches(conn: sqlite3.Connection) -> bool:
    return all(
        _table_exists(conn, table) and required.issubset(_columns(conn, table))
        for table, required in REQUIRED_COLUMNS.items()
    )


def _add_entry_beer_run_id(conn: sqlite3.Connection) -> None:
    if "beer_run_id" in _columns(conn, "entries"):
        return

    conn.execute(
        """
        ALTER TABLE entries
        ADD COLUMN beer_run_id INTEGER REFERENCES beer_runs(id)
        """
    )


def apply(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS beer_runs (
            id INTEGER NOT NULL,
            name VARCHAR NOT NULL,
            is_public BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            CONSTRAINT uq_beer_runs_name UNIQUE (name)
        );

        CREATE INDEX IF NOT EXISTS ix_beer_runs_id ON beer_runs (id);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_beer_runs_name ON beer_runs (name);
        CREATE INDEX IF NOT EXISTS ix_beer_runs_is_public ON beer_runs (is_public);

        CREATE TABLE IF NOT EXISTS beer_run_members (
            id INTEGER NOT NULL,
            beer_run_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role VARCHAR NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            CONSTRAINT uq_beer_run_members_run_user UNIQUE (beer_run_id, user_id),
            CONSTRAINT ck_beer_run_members_role CHECK (role IN ('owner', 'member')),
            FOREIGN KEY(beer_run_id) REFERENCES beer_runs (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        );

        CREATE INDEX IF NOT EXISTS ix_beer_run_members_id ON beer_run_members (id);
        CREATE INDEX IF NOT EXISTS ix_beer_run_members_beer_run_id ON beer_run_members (beer_run_id);
        CREATE INDEX IF NOT EXISTS ix_beer_run_members_user_id ON beer_run_members (user_id);
        """
    )
    _add_entry_beer_run_id(conn)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_entries_beer_run_id ON entries (beer_run_id)")
