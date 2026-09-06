from __future__ import annotations

import secrets
import sqlite3


ID = "007_add_user_auth_subject"
DESCRIPTION = "Add non-reusable authentication subjects to users"

_INDEX = "uq_users_auth_subject"
_FORMAT_CHECK = "ck_users_auth_subject_format"


class AuthSubjectSchemaConflict(RuntimeError):
    """Raised when an existing auth-subject schema is unsafe to baseline."""


def _columns(conn: sqlite3.Connection) -> dict[str, tuple]:
    return {row[1]: row for row in conn.execute("PRAGMA table_info(users)")}


def _has_unique_index(conn: sqlite3.Connection) -> bool:
    row = next(
        (row for row in conn.execute("PRAGMA index_list(users)") if row[1] == _INDEX),
        None,
    )
    if row is None or not row[2]:
        return False
    columns = [row[2] for row in conn.execute(f'PRAGMA index_info("{_INDEX}")')]
    return columns == ["auth_subject"]


def _has_format_check(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'"
    ).fetchone()
    if row is None or row[0] is None:
        return False
    normalized = "".join(row[0].lower().split())
    return (
        f"constraint{_FORMAT_CHECK}" in normalized
        and "check(length(auth_subject)=43andauth_subjectnotglob'*[^a-za-z0-9_-]*')"
        in normalized
    )


def baseline_matches(conn: sqlite3.Connection) -> bool:
    subject = _columns(conn).get("auth_subject")
    if subject is None or subject[3] != 1:
        return False
    if not _has_unique_index(conn) or not _has_format_check(conn):
        return False
    return conn.execute(
        """
        SELECT 1 FROM users
        WHERE auth_subject IS NULL
           OR length(auth_subject) != 43
           OR auth_subject GLOB '*[^A-Za-z0-9_-]*'
        LIMIT 1
        """
    ).fetchone() is None


def apply(conn: sqlite3.Connection) -> None:
    if "auth_subject" in _columns(conn):
        if baseline_matches(conn):
            return
        raise AuthSubjectSchemaConflict(
            "Cannot apply auth-subject migration because users.auth_subject "
            "already exists without the required non-null, format, and unique "
            "constraints. Repair the partial schema deliberately, then retry."
        )

    foreign_keys_enabled = bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])
    # The runner may have an implicit transaction open after recording the
    # preceding migration. PRAGMA foreign_keys is a no-op inside a transaction,
    # so end that unit before disabling checks for the table rebuild.
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("BEGIN")
    try:
        conn.execute(
            """
            CREATE TABLE users_new (
                id INTEGER NOT NULL,
                username VARCHAR COLLATE NOCASE,
                hashed_password VARCHAR,
                auth_subject VARCHAR NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT ck_users_auth_subject_format
                    CHECK (
                        length(auth_subject) = 43
                        AND auth_subject NOT GLOB '*[^A-Za-z0-9_-]*'
                    )
            )
            """
        )
        users = conn.execute(
            "SELECT id, username, hashed_password FROM users ORDER BY id"
        ).fetchall()
        conn.executemany(
            """
            INSERT INTO users_new (id, username, hashed_password, auth_subject)
            VALUES (?, ?, ?, ?)
            """,
            [(*user, secrets.token_urlsafe(32)) for user in users],
        )
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
        conn.execute(
            "CREATE UNIQUE INDEX ix_users_username ON users (username COLLATE BINARY)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX uq_users_username_nocase ON users (username COLLATE NOCASE)"
        )
        conn.execute("CREATE INDEX ix_users_id ON users (id)")
        conn.execute(f"CREATE UNIQUE INDEX {_INDEX} ON users (auth_subject)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if foreign_keys_enabled:
            conn.execute("PRAGMA foreign_keys = ON")
