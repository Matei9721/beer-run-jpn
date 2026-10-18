from __future__ import annotations

import sqlite3


ID = "009_add_beer_run_wrapped_flag"
DESCRIPTION = "Add per-run Wrapped availability"

_TABLE = "beer_runs"
_COLUMN = "has_wrapped"
_CHECK = "ck_beer_runs_has_wrapped_boolean"
_CANONICAL_RUN_NAME = "BeerRunJPN"


class BeerRunWrappedSchemaConflict(RuntimeError):
    """Raised when an existing Wrapped flag is not safe to baseline."""


def _column(conn: sqlite3.Connection) -> tuple | None:
    return next(
        (row for row in conn.execute(f'PRAGMA table_info("{_TABLE}")') if row[1] == _COLUMN),
        None,
    )


def _has_boolean_check(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_TABLE,),
    ).fetchone()
    if row is None or row[0] is None:
        return False
    normalized = "".join(row[0].lower().split())
    return (
        f"constraint{_CHECK}" in normalized
        and "check(has_wrappedin(0,1))" in normalized
    )


def _canonical_run_is_enabled(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT has_wrapped FROM beer_runs WHERE name = ? COLLATE NOCASE",
        (_CANONICAL_RUN_NAME,),
    ).fetchone()
    return row is None or row[0] == 1


def baseline_matches(conn: sqlite3.Connection) -> bool:
    column = _column(conn)
    if column is None:
        return False
    return (
        column[2].upper() == "BOOLEAN"
        and column[3] == 1
        and str(column[4]).strip("'\"") == "0"
        and _has_boolean_check(conn)
        and _canonical_run_is_enabled(conn)
    )


def apply(conn: sqlite3.Connection) -> None:
    if _column(conn) is not None:
        if baseline_matches(conn):
            return
        raise BeerRunWrappedSchemaConflict(
            "Cannot apply the Wrapped-availability migration because an incompatible "
            "beer_runs.has_wrapped column already exists. Repair the partial schema "
            "deliberately, then retry."
        )

    conn.execute(
        f"ALTER TABLE {_TABLE} ADD COLUMN {_COLUMN} BOOLEAN NOT NULL DEFAULT 0 "
        f"CONSTRAINT {_CHECK} CHECK ({_COLUMN} IN (0, 1))"
    )
    conn.execute(
        "UPDATE beer_runs SET has_wrapped = 1 WHERE name = ? COLLATE NOCASE",
        (_CANONICAL_RUN_NAME,),
    )
