from __future__ import annotations

import importlib
import sqlite3

import pytest

from migrations.runner import apply_migrations


migration = importlib.import_module("migrations.versions.009_add_beer_run_wrapped_flag")


def test_migration_enables_only_canonical_run_and_defaults_new_runs_off(tmp_path):
    db_path = tmp_path / "wrapped-availability.db"
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT has_wrapped FROM beer_runs WHERE name = 'BeerRunJPN' COLLATE NOCASE"
        ).fetchone() == (1,)
        conn.execute(
            "INSERT INTO beer_runs (name, is_public, created_at) VALUES ('Another Run', 1, CURRENT_TIMESTAMP)"
        )
        assert conn.execute(
            "SELECT has_wrapped FROM beer_runs WHERE name = 'Another Run'"
        ).fetchone() == (0,)
        assert migration.baseline_matches(conn) is True
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE beer_runs SET has_wrapped = 2 WHERE name = 'Another Run'")


def test_migration_backfills_existing_runs_without_enabling_others(tmp_path):
    db_path = tmp_path / "existing-runs.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO beer_runs (name, is_public, created_at) VALUES ('Existing Run', 1, CURRENT_TIMESTAMP)"
        )
        conn.execute("DELETE FROM schema_migrations WHERE version = ?", (migration.ID,))
        conn.execute("ALTER TABLE beer_runs DROP COLUMN has_wrapped")

    result = apply_migrations(db_path)

    assert result.applied == (migration.ID,)
    with sqlite3.connect(db_path) as conn:
        values = dict(conn.execute("SELECT name, has_wrapped FROM beer_runs"))
        assert values["BeerRunJPN"] == 1
        assert values["Existing Run"] == 0


def test_migration_baselines_matching_existing_column(tmp_path):
    db_path = tmp_path / "baseline.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version = ?", (migration.ID,))

    result = apply_migrations(db_path)

    assert result.baselined == (migration.ID,)


def test_migration_refuses_partial_existing_column(tmp_path):
    db_path = tmp_path / "partial.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version = ?", (migration.ID,))
        conn.execute("ALTER TABLE beer_runs DROP COLUMN has_wrapped")
        conn.execute("ALTER TABLE beer_runs ADD COLUMN has_wrapped BOOLEAN DEFAULT 0")

    with pytest.raises(migration.BeerRunWrappedSchemaConflict):
        apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = ?", (migration.ID,)
        ).fetchone()[0] == 0
