from __future__ import annotations

import sqlite3

ID = "001_initial_schema"
DESCRIPTION = "Current users and entries baseline schema"

REQUIRED_COLUMNS = {
    "users": {"id", "username", "hashed_password"},
    "entries": {
        "id",
        "drink_type",
        "abv",
        "quantity",
        "brand",
        "latitude",
        "longitude",
        "image_path",
        "timestamp",
        "timezone",
        "timezone_code",
        "user_id",
    },
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def baseline_matches(conn: sqlite3.Connection) -> bool:
    return all(required.issubset(_columns(conn, table)) for table, required in REQUIRED_COLUMNS.items())


def apply(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER NOT NULL,
            username VARCHAR,
            hashed_password VARCHAR,
            PRIMARY KEY (id)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
        CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);

        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER NOT NULL,
            drink_type VARCHAR,
            abv FLOAT,
            quantity FLOAT,
            brand VARCHAR,
            latitude FLOAT,
            longitude FLOAT,
            image_path VARCHAR,
            timestamp DATETIME,
            timezone TEXT,
            timezone_code TEXT,
            user_id INTEGER,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        );

        CREATE INDEX IF NOT EXISTS ix_entries_id ON entries (id);
        """
    )
