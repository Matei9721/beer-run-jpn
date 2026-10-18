from __future__ import annotations

import sqlite3

ID = "006_add_beer_run_invites"
DESCRIPTION = "Add one permanent invite per beer-run"

REQUIRED_COLUMNS = {
    "beer_run_invites": {"id", "beer_run_id", "code", "created_at"},
}

_TABLE = "beer_run_invites"
_RUN_INDEX = "uq_beer_run_invites_beer_run_id"
_CODE_INDEX = "uq_beer_run_invites_code"


class InviteSchemaConflict(RuntimeError):
    """Raised when an existing invite table is not safe to baseline."""


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _column_details(conn: sqlite3.Connection, table: str) -> dict[str, tuple]:
    return {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}


def _index_signature(
    conn: sqlite3.Connection,
    table: str,
    index_name: str,
) -> tuple[bool, tuple[tuple[str, str], ...]] | None:
    index_row = next(
        (row for row in conn.execute(f"PRAGMA index_list({table})") if row[1] == index_name),
        None,
    )
    if index_row is None:
        return None
    columns = tuple(
        (row[2], row[4])
        for row in conn.execute(f'PRAGMA index_xinfo("{index_name}")')
        if row[5] == 1
    )
    return bool(index_row[2]), columns


def _has_run_foreign_key(conn: sqlite3.Connection) -> bool:
    return any(
        row[3] == "beer_run_id" and row[2] == "beer_runs" and row[4] == "id"
        for row in conn.execute(f"PRAGMA foreign_key_list({_TABLE})")
    )


def _has_code_format_check(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_TABLE,),
    ).fetchone()
    if row is None or row[0] is None:
        return False
    normalized_sql = "".join(row[0].lower().split())
    return (
        "constraintck_beer_run_invites_code_format" in normalized_sql
        and "check(length(code)=43andcodenotglob'*[^a-za-z0-9_-]*')"
        in normalized_sql
    )


def baseline_matches(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, _TABLE):
        return False

    columns = _column_details(conn, _TABLE)
    if not REQUIRED_COLUMNS[_TABLE].issubset(columns):
        return False
    if not (
        columns["id"][3] == 1
        and columns["id"][5] == 1
        and columns["beer_run_id"][3] == 1
        and columns["code"][3] == 1
        and columns["created_at"][3] == 1
        and str(columns["created_at"][4]).upper() == "CURRENT_TIMESTAMP"
    ):
        return False

    return (
        _index_signature(conn, _TABLE, _RUN_INDEX)
        == (True, (("beer_run_id", "BINARY"),))
        and _index_signature(conn, _TABLE, _CODE_INDEX)
        == (True, (("code", "BINARY"),))
        and _has_run_foreign_key(conn)
        and _has_code_format_check(conn)
    )


def apply(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, _TABLE):
        if baseline_matches(conn):
            return
        raise InviteSchemaConflict(
            "Cannot apply invite migration because beer_run_invites already exists "
            "but does not have the required columns, constraints, indexes, and "
            "foreign key. Repair or remove the partial table deliberately, then retry."
        )

    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        BEGIN;

        CREATE TABLE beer_run_invites (
            id INTEGER NOT NULL,
            beer_run_id INTEGER NOT NULL,
            code VARCHAR NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            CONSTRAINT ck_beer_run_invites_code_format
                CHECK (length(code) = 43 AND code NOT GLOB '*[^A-Za-z0-9_-]*'),
            FOREIGN KEY(beer_run_id) REFERENCES beer_runs (id)
        );

        -- Unique indexes: at most one invite per run and globally unique codes.
        -- These also serve as the lookup indexes for invite resolution.
        CREATE UNIQUE INDEX uq_beer_run_invites_beer_run_id
            ON beer_run_invites (beer_run_id);
        CREATE UNIQUE INDEX uq_beer_run_invites_code
            ON beer_run_invites (code);

        CREATE INDEX ix_beer_run_invites_id ON beer_run_invites (id);

        COMMIT;
        """
    )
