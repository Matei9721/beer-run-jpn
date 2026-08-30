"""Focused contract tests for migration 008's acceptance evidence."""

from __future__ import annotations

import importlib
import sqlite3

import pytest

from migrations.runner import apply_migrations


migration = importlib.import_module("migrations.versions.008_add_terms_acceptances")


def _columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(terms_acceptances)")}


def _simulate_user_table_rebuild(conn: sqlite3.Connection) -> None:
    """Model migration 007's ID-preserving users-table replacement."""

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(
        "CREATE TABLE users_rebuilt ("
        "id INTEGER NOT NULL PRIMARY KEY, "
        "username VARCHAR NOT NULL, "
        "hashed_password VARCHAR NOT NULL, "
        "auth_subject VARCHAR NOT NULL, "
        "CONSTRAINT ck_users_auth_subject_format "
        "CHECK (length(auth_subject) = 43 "
        "AND auth_subject NOT GLOB '*[^A-Za-z0-9_-]*')"
        ")"
    )
    conn.execute(
        "INSERT INTO users_rebuilt (id, username, hashed_password, auth_subject) "
        "SELECT id, username, hashed_password, auth_subject FROM users"
    )
    conn.execute("DROP TABLE users")
    conn.execute("ALTER TABLE users_rebuilt RENAME TO users")
    conn.execute("CREATE UNIQUE INDEX ix_users_username ON users (username)")
    conn.execute(
        "CREATE UNIQUE INDEX uq_users_username_nocase ON users (username COLLATE NOCASE)"
    )
    conn.execute("CREATE UNIQUE INDEX uq_users_auth_subject ON users (auth_subject)")


def test_migration_creates_versioned_acceptance_schema(tmp_path):
    db_path = tmp_path / "legal.db"
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert _columns(conn) == {"id", "user_id", "terms_version", "accepted_at"}
        indexes = {
            row[1]: bool(row[2])
            for row in conn.execute("PRAGMA index_list(terms_acceptances)")
        }
        assert indexes["ix_terms_acceptances_user_id"] is False
        assert any(indexes.values())
        foreign_keys = list(conn.execute("PRAGMA foreign_key_list(terms_acceptances)"))
        assert any(
            row[2] == "users"
            and row[3] == "user_id"
            and row[4] == "id"
            and row[6].upper() == "CASCADE"
            for row in foreign_keys
        )
        assert migration.baseline_matches(conn) is True


def test_migration_preserves_existing_users_without_inventing_acceptance(tmp_path):
    db_path = tmp_path / "existing-user.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, hashed_password, auth_subject) "
            "VALUES ('Existing', 'hash', ?)",
            ("E" * 43,),
        )
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '008_add_terms_acceptances'"
        )
        conn.execute("DROP TABLE terms_acceptances")

    result = apply_migrations(db_path)

    assert result.applied == ("008_add_terms_acceptances",)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT username FROM users").fetchone()[0] == "Existing"
        assert conn.execute("SELECT COUNT(*) FROM terms_acceptances").fetchone()[0] == 0


def test_migration_enforces_unique_nonblank_and_cascading_rows(tmp_path):
    db_path = tmp_path / "constraints.db"
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO users (username, hashed_password, auth_subject) "
            "VALUES ('Accepted', 'hash', ?)",
            ("A" * 43,),
        )
        user_id = conn.execute("SELECT id FROM users WHERE username = 'Accepted'").fetchone()[0]
        conn.execute(
            "INSERT INTO terms_acceptances (user_id, terms_version, accepted_at) "
            "VALUES (?, '2026-08-30', CURRENT_TIMESTAMP)",
            (user_id,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO terms_acceptances (user_id, terms_version, accepted_at) "
                "VALUES (?, '2026-08-30', CURRENT_TIMESTAMP)",
                (user_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO terms_acceptances (user_id, terms_version, accepted_at) "
                "VALUES (?, '   ', CURRENT_TIMESTAMP)",
                (user_id,),
            )
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        assert conn.execute("SELECT COUNT(*) FROM terms_acceptances").fetchone()[0] == 0


def test_migration_baselines_matching_existing_table(tmp_path):
    db_path = tmp_path / "baseline.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '008_add_terms_acceptances'"
        )

    result = apply_migrations(db_path)

    assert result.baselined == ("008_add_terms_acceptances",)


def test_migration_refuses_partial_existing_table(tmp_path):
    db_path = tmp_path / "partial.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '008_add_terms_acceptances'"
        )
        conn.execute("DROP TABLE terms_acceptances")
        conn.execute(
            "CREATE TABLE terms_acceptances ("
            "id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, terms_version VARCHAR NOT NULL"
            ")"
        )

    with pytest.raises(migration.TermsAcceptanceSchemaConflict):
        apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert _columns(conn) == {"id", "user_id", "terms_version"}
        assert conn.execute(
            "SELECT COUNT(*) FROM schema_migrations "
            "WHERE version = '008_add_terms_acceptances'"
        ).fetchone()[0] == 0


def test_acceptance_table_survives_id_preserving_user_rebuild_after_008(tmp_path):
    db_path = tmp_path / "008-then-007.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, hashed_password, auth_subject) "
            "VALUES (41, 'BeforeRebuild', 'hash', ?)",
            ("B" * 43,),
        )
        conn.execute(
            "INSERT INTO terms_acceptances (user_id, terms_version, accepted_at) "
            "VALUES (41, '2026-08-30', CURRENT_TIMESTAMP)"
        )
        _simulate_user_table_rebuild(conn)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert list(conn.execute("PRAGMA foreign_key_check")) == []
        assert conn.execute(
            "SELECT user_id, terms_version FROM terms_acceptances"
        ).fetchone() == (41, "2026-08-30")
        conn.execute("DELETE FROM users WHERE id = 41")
        assert conn.execute("SELECT COUNT(*) FROM terms_acceptances").fetchone()[0] == 0


def test_008_applies_after_id_preserving_user_rebuild(tmp_path):
    db_path = tmp_path / "007-then-008.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '008_add_terms_acceptances'"
        )
        conn.execute("DROP TABLE terms_acceptances")
        _simulate_user_table_rebuild(conn)

    result = apply_migrations(db_path)

    assert result.applied == ("008_add_terms_acceptances",)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert migration.baseline_matches(conn) is True
        assert list(conn.execute("PRAGMA foreign_key_check")) == []
