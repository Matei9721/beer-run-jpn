from __future__ import annotations

import sqlite3

ID = "004_case_insensitive_usernames"
DESCRIPTION = "Enforce case-insensitive username uniqueness"

USERNAME_INDEX = "uq_users_username_nocase"


class CaseInsensitiveUsernameCollision(RuntimeError):
    """Raised when existing users cannot safely receive the NOCASE index."""


def _has_case_insensitive_collision(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM users
        WHERE username IS NOT NULL
        GROUP BY username COLLATE NOCASE
        HAVING COUNT(*) > 1
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def apply(conn: sqlite3.Connection) -> None:
    if _has_case_insensitive_collision(conn):
        raise CaseInsensitiveUsernameCollision(
            "Cannot apply case-insensitive username uniqueness because existing "
            "accounts collide when ASCII letter case is ignored. Resolve the "
            "duplicate account identities deliberately, then retry the migration."
        )

    conn.execute(
        f"""
        CREATE UNIQUE INDEX {USERNAME_INDEX}
        ON users (username COLLATE NOCASE)
        """
    )
