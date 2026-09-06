from __future__ import annotations

import sqlite3


ID = "008_add_terms_acceptances"
DESCRIPTION = "Add append-only Terms acceptance history"

_TABLE = "terms_acceptances"
_USER_INDEX = "ix_terms_acceptances_user_id"
_VERSION_CHECK = "ck_terms_acceptances_version_nonblank"


class TermsAcceptanceSchemaConflict(RuntimeError):
    """Raised when an existing acceptance table is not safe to baseline."""


def _table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_TABLE,),
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection) -> dict[str, tuple]:
    return {row[1]: row for row in conn.execute(f'PRAGMA table_info("{_TABLE}")')}


def _has_unique_user_version(conn: sqlite3.Connection) -> bool:
    for index in conn.execute(f'PRAGMA index_list("{_TABLE}")'):
        if not index[2]:
            continue
        columns = [
            row[2]
            for row in conn.execute(f'PRAGMA index_info("{index[1]}")')
        ]
        if columns == ["user_id", "terms_version"]:
            return True
    return False


def _has_user_index(conn: sqlite3.Connection) -> bool:
    row = next(
        (
            row
            for row in conn.execute(f'PRAGMA index_list("{_TABLE}")')
            if row[1] == _USER_INDEX
        ),
        None,
    )
    if row is None or row[2]:
        return False
    columns = [row[2] for row in conn.execute(f'PRAGMA index_info("{_USER_INDEX}")')]
    return columns == ["user_id"]


def _has_cascade_user_foreign_key(conn: sqlite3.Connection) -> bool:
    rows = list(conn.execute(f'PRAGMA foreign_key_list("{_TABLE}")'))
    return any(
        row[2] == "users"
        and row[3] == "user_id"
        and row[4] == "id"
        and row[6].upper() == "CASCADE"
        for row in rows
    )


def _has_nonblank_check(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (_TABLE,),
    ).fetchone()
    if row is None or row[0] is None:
        return False
    normalized = "".join(row[0].lower().split())
    return (
        f"constraint{_VERSION_CHECK}" in normalized
        and "check(length(trim(terms_version))>0)" in normalized
    )


def baseline_matches(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn):
        return False
    columns = _columns(conn)
    if set(columns) != {"id", "user_id", "terms_version", "accepted_at"}:
        return False
    if columns["id"][2].upper() != "INTEGER" or columns["id"][5] != 1:
        return False
    for name in ("user_id", "terms_version", "accepted_at"):
        if columns[name][3] != 1:
            return False
    return (
        _has_unique_user_version(conn)
        and _has_user_index(conn)
        and _has_cascade_user_foreign_key(conn)
        and _has_nonblank_check(conn)
    )


def apply(conn: sqlite3.Connection) -> None:
    if _table_exists(conn):
        if baseline_matches(conn):
            return
        raise TermsAcceptanceSchemaConflict(
            "Cannot apply Terms-acceptance migration because an incompatible "
            "terms_acceptances table already exists. Repair the partial schema "
            "deliberately, then retry."
        )

    conn.execute(
        f"""
        CREATE TABLE {_TABLE} (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            terms_version VARCHAR NOT NULL,
            accepted_at DATETIME NOT NULL,
            CONSTRAINT uq_terms_acceptances_user_version
                UNIQUE (user_id, terms_version),
            CONSTRAINT {_VERSION_CHECK}
                CHECK (length(trim(terms_version)) > 0),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        f"CREATE INDEX {_USER_INDEX} ON {_TABLE} (user_id)"
    )
