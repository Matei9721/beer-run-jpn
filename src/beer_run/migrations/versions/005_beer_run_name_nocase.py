from __future__ import annotations

import sqlite3

ID = "005_beer_run_name_nocase"
DESCRIPTION = "Enforce case-insensitive uniqueness on beer-run names"

_NAME_INDEX = "uq_beer_runs_name_nocase"


class CaseInsensitiveBeerRunCollision(RuntimeError):
    """Raised when existing beer-runs cannot safely receive the NOCASE index."""


def _has_case_insensitive_collision(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM beer_runs
        WHERE name IS NOT NULL
        GROUP BY name COLLATE NOCASE
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def apply(conn: sqlite3.Connection) -> None:
    # Guard: refuse if any existing names collide case-insensitively.
    if _has_case_insensitive_collision(conn):
        raise CaseInsensitiveBeerRunCollision(
            "Cannot apply case-insensitive name uniqueness on beer_runs because "
            "existing names collide when ASCII letter case is ignored. Resolve the "
            "duplicate run names deliberately, then retry the migration."
        )

    # Add a NOCASE unique index on name.  The existing case-sensitive
    # UNIQUE constraint from migration 002 remains in place; this index is
    # the stricter one — it rejects case variants that the old constraint
    # would allow, but does not conflict with it.  This is the same pattern
    # used for usernames in migration 004.
    conn.execute(
        f"""
        CREATE UNIQUE INDEX "{_NAME_INDEX}"
        ON beer_runs (name COLLATE NOCASE)
        """
    )
