import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from migrations import runner
from migrations.runner import Migration, MigrationRequired, apply_migrations, validate_database_ready
from scripts.migrate_db import main as migrate_main


def table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def column_names(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def migration_versions(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]


def create_current_schema_without_history(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER NOT NULL,
                username VARCHAR,
                hashed_password VARCHAR,
                PRIMARY KEY (id)
            );
            CREATE UNIQUE INDEX ix_users_username ON users (username);
            CREATE INDEX ix_users_id ON users (id);

            CREATE TABLE entries (
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
            CREATE INDEX ix_entries_id ON entries (id);
            """
        )
        conn.execute(
            "INSERT INTO users (id, username, hashed_password) VALUES (1, 'user', 'hash')"
        )
        conn.execute(
            """
            INSERT INTO entries
                (id, drink_type, abv, quantity, brand, latitude, longitude, image_path, timestamp, timezone, timezone_code, user_id)
            VALUES
                (1, 'Beer', 5.0, 0.5, 'Test', 1.0, 2.0, 'static/uploads/test.jpg', '2026-05-25 12:00:00', 'Europe/Amsterdam', 'CEST', 1)
            """
        )


def row_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_existing_current_schema_is_baselined_without_losing_rows(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)

    result = apply_migrations(db_path)

    assert result.baselined == ("001_initial_schema",)
    assert result.applied == ()
    assert migration_versions(db_path) == ["001_initial_schema"]
    assert row_count(db_path, "users") == 1
    assert row_count(db_path, "entries") == 1


def test_migrations_are_idempotent_for_migrated_database(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)

    apply_migrations(db_path)
    result = apply_migrations(db_path)

    assert result.skipped == ("001_initial_schema",)
    assert migration_versions(db_path) == ["001_initial_schema"]
    assert row_count(db_path, "users") == 1
    assert row_count(db_path, "entries") == 1


def test_failed_migration_is_not_recorded(tmp_path, monkeypatch):
    db_path = tmp_path / "broken.db"

    def fail(_conn):
        raise RuntimeError("boom")

    bad_module = SimpleNamespace(ID="999_bad", DESCRIPTION="bad", apply=fail)
    monkeypatch.setattr(runner, "MIGRATIONS", (Migration("999_bad", "bad", bad_module),))

    with pytest.raises(RuntimeError):
        apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0


def test_fresh_database_is_created_from_migrations(tmp_path):
    db_path = tmp_path / "fresh.db"

    result = apply_migrations(db_path)

    assert result.applied == ("001_initial_schema",)
    assert {"users", "entries", "schema_migrations"}.issubset(table_names(db_path))
    assert {"id", "username", "hashed_password"}.issubset(column_names(db_path, "users"))
    assert {"timezone", "timezone_code", "user_id"}.issubset(column_names(db_path, "entries"))
    assert migration_versions(db_path) == ["001_initial_schema"]


def test_check_mode_accepts_migrated_database(tmp_path):
    db_path = tmp_path / "fresh.db"
    apply_migrations(db_path)

    validate_database_ready(db_path)


def test_check_mode_rejects_database_without_migration_history(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)

    with pytest.raises(MigrationRequired):
        validate_database_ready(db_path)


def test_migrate_command_check_mode_returns_expected_status(tmp_path, capsys):
    db_path = tmp_path / "fresh.db"
    apply_migrations(db_path)

    assert migrate_main(["--database", str(db_path), "--check"]) == 0
    assert "up to date" in capsys.readouterr().out

    outdated_path = tmp_path / "outdated.db"
    create_current_schema_without_history(outdated_path)

    assert migrate_main(["--database", str(outdated_path), "--check"]) == 1
    assert "Migration required" in capsys.readouterr().err
