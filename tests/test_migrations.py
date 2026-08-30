import importlib
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from migrations import runner
from migrations.runner import Migration, MigrationRequired, apply_migrations, validate_database_ready
from scripts.migrate_db import main as migrate_main


MIGRATION_VERSIONS = [
    "001_initial_schema",
    "002_add_beer_run_schema",
    "003_backfill_existing_trip",
    "004_case_insensitive_usernames",
    "005_beer_run_name_nocase",
    "006_add_beer_run_invites",
    "007_add_user_auth_subject",
]


def table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def column_names(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def index_names(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        return {row[1] for row in conn.execute(f"PRAGMA index_list({table})")}


def foreign_key_targets(db_path: Path, table: str) -> set[tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
        return {(row[3], row[2]) for row in conn.execute(f"PRAGMA foreign_key_list({table})")}


def migration_versions(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]


def username_index_details(
    db_path: Path, index_name: str
) -> tuple[bool, list[str]] | None:
    with sqlite3.connect(db_path) as conn:
        index_row = next(
            (
                row
                for row in conn.execute("PRAGMA index_list(users)")
                if row[1] == index_name
            ),
            None,
        )
        if index_row is None:
            return None
        collations = [
            row[4]
            for row in conn.execute(f"PRAGMA index_xinfo({index_name})")
            if row[5] == 1
        ]
    return bool(index_row[2]), collations


def assert_username_indexes(db_path: Path) -> None:
    assert username_index_details(db_path, "ix_users_username") == (
        True,
        ["BINARY"],
    )
    assert username_index_details(db_path, "uq_users_username_nocase") == (
        True,
        ["NOCASE"],
    )


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


def create_pre_backfill_schema_with_history(db_path: Path, include_tamei: bool = True) -> None:
    create_current_schema_without_history(db_path)
    with sqlite3.connect(db_path) as conn:
        if include_tamei:
            conn.execute(
                "INSERT INTO users (id, username, hashed_password) VALUES (2, 'Tamei', 'tamei-hash')"
            )
            conn.execute(
                """
                INSERT INTO entries
                    (id, drink_type, abv, quantity, brand, latitude, longitude, image_path, timestamp, timezone, timezone_code, user_id)
                VALUES
                    (2, 'Sake', 15.0, 0.2, 'Owner Drink', 3.0, 4.0, 'static/uploads/tamei.jpg', '2026-05-25 13:00:00', 'Europe/Amsterdam', 'CEST', 2)
                """
            )


def create_schema_with_partial_backfill_state(db_path: Path) -> None:
    create_pre_backfill_schema_with_history(db_path)
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE version = '003_backfill_existing_trip'")


def restore_pre_case_insensitive_username_schema(db_path: Path) -> None:
    """Return a fully migrated database to the pre-004 (username) state.

    Also removes the downstream 006 invite migration so re-applying reaches a
    genuinely ordered 004 -> 005 -> 006 chain.
    """
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '004_case_insensitive_usernames'"
        )
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '005_beer_run_name_nocase'"
        )
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '006_add_beer_run_invites'"
        )
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '007_add_user_auth_subject'"
        )
        conn.execute("DROP INDEX IF EXISTS uq_users_username_nocase")
        conn.execute("DROP INDEX IF EXISTS uq_beer_runs_name_nocase")
        conn.execute("DROP TABLE IF EXISTS beer_run_invites")


def table_rows(db_path: Path, table: str) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()


def row_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def scalar(db_path: Path, sql: str, params: tuple = ()):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def beer_run_jpn_id(db_path: Path) -> int:
    return scalar(db_path, "SELECT id FROM beer_runs WHERE name = 'BeerRunJPN'")


def membership_roles(db_path: Path) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        return {
            row[0]: row[1]
            for row in conn.execute(
                """
                SELECT users.username, beer_run_members.role
                FROM beer_run_members
                JOIN users ON users.id = beer_run_members.user_id
                JOIN beer_runs ON beer_runs.id = beer_run_members.beer_run_id
                WHERE beer_runs.name = 'BeerRunJPN'
                ORDER BY users.username
                """
            )
        }


def entry_beer_run_ids(db_path: Path) -> set[int | None]:
    with sqlite3.connect(db_path) as conn:
        return {row[0] for row in conn.execute("SELECT beer_run_id FROM entries ORDER BY id")}


def global_total_alcohol(db_path: Path) -> float:
    return scalar(db_path, "SELECT SUM(quantity * (abv / 100.0)) FROM entries")


def beer_run_jpn_total_alcohol(db_path: Path) -> float:
    return scalar(
        db_path,
        """
        SELECT SUM(entries.quantity * (entries.abv / 100.0))
        FROM entries
        JOIN beer_runs ON beer_runs.id = entries.beer_run_id
        WHERE beer_runs.name = 'BeerRunJPN'
        """,
    )


def test_existing_current_schema_is_baselined_without_losing_rows(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)

    result = apply_migrations(db_path)

    assert result.baselined == ("001_initial_schema",)
    assert result.applied == (
        "002_add_beer_run_schema",
        "003_backfill_existing_trip",
        "004_case_insensitive_usernames",
        "005_beer_run_name_nocase",
        "006_add_beer_run_invites",
        "007_add_user_auth_subject",
    )
    assert migration_versions(db_path) == MIGRATION_VERSIONS
    assert row_count(db_path, "users") == 1
    assert row_count(db_path, "entries") == 1
    assert_username_indexes(db_path)


def test_migrations_are_idempotent_for_migrated_database(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)

    apply_migrations(db_path)
    result = apply_migrations(db_path)

    assert result.skipped == tuple(MIGRATION_VERSIONS)
    assert migration_versions(db_path) == MIGRATION_VERSIONS
    assert row_count(db_path, "users") == 1
    assert row_count(db_path, "entries") == 1
    assert_username_indexes(db_path)


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

    assert result.applied == tuple(MIGRATION_VERSIONS)
    assert {"users", "entries", "schema_migrations", "beer_runs", "beer_run_members"}.issubset(table_names(db_path))
    assert {"id", "username", "hashed_password", "auth_subject"}.issubset(
        column_names(db_path, "users")
    )
    assert {"timezone", "timezone_code", "user_id", "beer_run_id"}.issubset(column_names(db_path, "entries"))
    assert {"id", "name", "is_public", "created_at"}.issubset(column_names(db_path, "beer_runs"))
    assert {"id", "beer_run_id", "user_id", "role", "created_at"}.issubset(column_names(db_path, "beer_run_members"))
    assert migration_versions(db_path) == MIGRATION_VERSIONS


def test_beer_run_schema_migration_adds_lookup_indexes_and_foreign_keys(tmp_path):
    db_path = tmp_path / "fresh.db"

    apply_migrations(db_path)

    assert "ix_entries_beer_run_id" in index_names(db_path, "entries")
    assert "ix_beer_runs_is_public" in index_names(db_path, "beer_runs")
    assert "ix_beer_run_members_user_id" in index_names(db_path, "beer_run_members")
    assert "ix_beer_run_members_beer_run_id" in index_names(db_path, "beer_run_members")
    assert ("beer_run_id", "beer_runs") in foreign_key_targets(db_path, "entries")
    assert ("beer_run_id", "beer_runs") in foreign_key_targets(db_path, "beer_run_members")
    assert ("user_id", "users") in foreign_key_targets(db_path, "beer_run_members")


def test_beer_run_schema_migration_preserves_existing_rows(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)

    apply_migrations(db_path)

    assert row_count(db_path, "users") == 1
    assert row_count(db_path, "entries") == 1
    assert row_count(db_path, "beer_runs") == 1
    assert row_count(db_path, "beer_run_members") == 1


def test_beer_run_schema_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "fresh.db"

    apply_migrations(db_path)
    result = apply_migrations(db_path)

    assert result.skipped == tuple(MIGRATION_VERSIONS)
    assert migration_versions(db_path) == MIGRATION_VERSIONS


def test_case_insensitive_username_index_is_unique_and_uses_nocase(tmp_path):
    db_path = tmp_path / "fresh.db"
    apply_migrations(db_path)

    assert_username_indexes(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, hashed_password, auth_subject) VALUES ('Alice', 'first-hash', ?)",
            ("A" * 43,),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO users (username, hashed_password, auth_subject) VALUES ('alice', 'second-hash', ?)",
                ("B" * 43,),
            )

    assert scalar(
        db_path,
        "SELECT COUNT(*) FROM users WHERE username = 'Alice' COLLATE NOCASE",
    ) == 1


def test_case_insensitive_username_migration_refuses_legacy_collisions(tmp_path):
    db_path = tmp_path / "collision.db"
    apply_migrations(db_path)
    restore_pre_case_insensitive_username_schema(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, hashed_password, auth_subject) VALUES (10, 'Alice', 'first-hash', ?)",
            ("C" * 43,),
        )
        conn.execute(
            "INSERT INTO users (id, username, hashed_password, auth_subject) VALUES (11, 'alice', 'second-hash', ?)",
            ("D" * 43,),
        )

    before = {
        table: table_rows(db_path, table)
        for table in ("users", "entries", "beer_runs", "beer_run_members")
    }

    with pytest.raises(RuntimeError) as exc_info:
        apply_migrations(db_path)

    message = str(exc_info.value)
    assert "case-insensitive username uniqueness" in message
    assert "Resolve the duplicate account identities" in message
    for private_value in ("Alice", "alice", "first-hash", "second-hash"):
        assert private_value not in message
    # Only migrations before 004 (the one that should fail) are recorded.
    assert migration_versions(db_path) == MIGRATION_VERSIONS[:3]
    assert username_index_details(db_path, "ix_users_username") == (
        True,
        ["BINARY"],
    )
    assert username_index_details(db_path, "uq_users_username_nocase") is None
    assert {
        table: table_rows(db_path, table)
        for table in ("users", "entries", "beer_runs", "beer_run_members")
    } == before


def test_case_insensitive_username_migration_preserves_beer_run_jpn_data(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)
    apply_migrations(db_path)
    restore_pre_case_insensitive_username_schema(db_path)
    before = {
        table: table_rows(db_path, table)
        for table in ("users", "entries", "beer_runs", "beer_run_members")
    }

    result = apply_migrations(db_path)

    assert result.applied == (
        "004_case_insensitive_usernames",
        "005_beer_run_name_nocase",
        "006_add_beer_run_invites",
    )
    assert {
        table: table_rows(db_path, table)
        for table in ("users", "entries", "beer_runs", "beer_run_members")
    } == before
    assert membership_roles(db_path) == {"Tamei": "owner", "user": "member"}
    assert_username_indexes(db_path)


def test_case_insensitive_username_migration_preserves_unusual_legacy_names(tmp_path):
    db_path = tmp_path / "legacy.db"
    apply_migrations(db_path)
    restore_pre_case_insensitive_username_schema(db_path)
    legacy_users = [
        (10, " Legacy User! ", "space-hash"),
        (11, "Ålice", "upper-hash"),
        (12, "åLICE", "lower-hash"),
    ]
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO users (id, username, hashed_password, auth_subject) VALUES (?, ?, ?, ?)",
            [(*user, chr(69 + offset) * 43) for offset, user in enumerate(legacy_users)],
        )

    result = apply_migrations(db_path)

    assert result.applied == (
        "004_case_insensitive_usernames",
        "005_beer_run_name_nocase",
        "006_add_beer_run_invites",
    )
    with sqlite3.connect(db_path) as conn:
        preserved = conn.execute(
            "SELECT id, username, hashed_password FROM users ORDER BY id"
        ).fetchall()
    assert preserved == legacy_users
    assert_username_indexes(db_path)


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


def test_backfill_creates_public_beer_run_jpn_from_existing_data(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)

    apply_migrations(db_path)

    assert row_count(db_path, "beer_runs") == 1
    assert scalar(db_path, "SELECT is_public FROM beer_runs WHERE name = 'BeerRunJPN'") == 1


def test_backfill_adds_every_existing_user_as_member(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)

    apply_migrations(db_path)

    assert membership_roles(db_path) == {"Tamei": "owner", "user": "member"}
    assert row_count(db_path, "beer_run_members") == 2


def test_backfill_assigns_existing_unassigned_entries_to_beer_run_jpn(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)

    apply_migrations(db_path)

    assert entry_beer_run_ids(db_path) == {beer_run_jpn_id(db_path)}


def test_backfill_sets_tamei_owner_and_only_public_run(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)

    apply_migrations(db_path)

    assert membership_roles(db_path)["Tamei"] == "owner"
    assert scalar(db_path, "SELECT COUNT(*) FROM beer_runs WHERE is_public = 1") == 1


def test_backfill_preserves_credentials_and_entry_fields(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)
    before_total = global_total_alcohol(db_path)

    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT hashed_password FROM users WHERE username = 'Tamei'").fetchone()[0] == "tamei-hash"
        row = conn.execute(
            """
            SELECT drink_type, abv, quantity, brand, latitude, longitude, image_path, timestamp, timezone, timezone_code
            FROM entries WHERE id = 2
            """
        ).fetchone()
    assert row == ("Sake", 15.0, 0.2, "Owner Drink", 3.0, 4.0, "static/uploads/tamei.jpg", "2026-05-25 13:00:00", "Europe/Amsterdam", "CEST")
    assert beer_run_jpn_total_alcohol(db_path) == before_total


def test_backfill_three_runs_leave_one_beer_run_jpn(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)

    apply_migrations(db_path)
    apply_migrations(db_path)
    apply_migrations(db_path)

    assert scalar(db_path, "SELECT COUNT(*) FROM beer_runs WHERE name = 'BeerRunJPN'") == 1


def test_backfill_rerun_leaves_one_membership_per_user(tmp_path):
    db_path = tmp_path / "existing.db"
    create_schema_with_partial_backfill_state(db_path)

    apply_migrations(db_path)

    assert scalar(
        db_path,
        """
        SELECT COUNT(*)
        FROM (
            SELECT user_id, COUNT(*) AS memberships
            FROM beer_run_members
            JOIN beer_runs ON beer_runs.id = beer_run_members.beer_run_id
            WHERE beer_runs.name = 'BeerRunJPN'
            GROUP BY user_id
            HAVING memberships != 1
        )
        """,
    ) == 0


def test_backfill_rerun_preserves_assignments_and_totals(tmp_path):
    db_path = tmp_path / "existing.db"
    create_schema_with_partial_backfill_state(db_path)
    before_assignments = entry_beer_run_ids(db_path)
    before_total = beer_run_jpn_total_alcohol(db_path)

    apply_migrations(db_path)

    assert entry_beer_run_ids(db_path) == before_assignments
    assert beer_run_jpn_total_alcohol(db_path) == before_total


def test_backfill_preserves_entries_assigned_to_other_runs(tmp_path, monkeypatch):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)
    beer_run_schema_module = importlib.import_module("migrations.versions.002_add_beer_run_schema")
    monkeypatch.setattr(
        runner,
        "MIGRATIONS",
        (
            Migration(runner.initial_schema.ID, runner.initial_schema.DESCRIPTION, runner.initial_schema),
            Migration(beer_run_schema_module.ID, beer_run_schema_module.DESCRIPTION, beer_run_schema_module),
        ),
    )
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO beer_runs (name, is_public) VALUES ('Other Run', 0)")
        other_run_id = conn.execute("SELECT id FROM beer_runs WHERE name = 'Other Run'").fetchone()[0]
        conn.execute("UPDATE entries SET beer_run_id = ? WHERE id = 1", (other_run_id,))

    monkeypatch.setattr(runner, "MIGRATIONS", runner.MIGRATIONS + (Migration("003_backfill_existing_trip", "Backfill existing trip into BeerRunJPN", importlib.import_module("migrations.versions.003_backfill_existing_trip")),))
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT beer_run_id FROM entries WHERE id = 1").fetchone()[0] == other_run_id


def test_backfill_missing_tamei_warns_without_creating_user(tmp_path, capsys):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path, include_tamei=False)

    apply_migrations(db_path)

    assert "Tamei user not found" in capsys.readouterr().out
    assert scalar(db_path, "SELECT COUNT(*) FROM users WHERE username = 'Tamei'") == 0


# ── Invite migration (006) ──────────────────────────────────────────


def restore_pre_invite_schema(db_path: Path) -> None:
    """Return a fully migrated database to the pre-invite (005) state."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '006_add_beer_run_invites'"
        )
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '007_add_user_auth_subject'"
        )
        conn.execute("DROP TABLE IF EXISTS beer_run_invites")


def add_invite(db_path: Path, beer_run_id: int, code: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO beer_run_invites (beer_run_id, code) VALUES (?, ?)",
            (beer_run_id, code),
        )


def test_invite_migration_creates_table_columns_fk_and_indexes(tmp_path):
    db_path = tmp_path / "fresh.db"
    apply_migrations(db_path)

    assert "beer_run_invites" in table_names(db_path)
    assert {"id", "beer_run_id", "code", "created_at"}.issubset(
        column_names(db_path, "beer_run_invites")
    )
    assert ("beer_run_id", "beer_runs") in foreign_key_targets(db_path, "beer_run_invites")
    indexes = index_names(db_path, "beer_run_invites")
    assert "uq_beer_run_invites_beer_run_id" in indexes
    assert "uq_beer_run_invites_code" in indexes
    assert "ix_beer_run_invites_id" in indexes


def test_invite_migration_applies_to_pre_invite_database_and_preserves_rows(tmp_path):
    db_path = tmp_path / "existing.db"
    create_current_schema_without_history(db_path)
    apply_migrations(db_path)
    restore_pre_invite_schema(db_path)

    before = {
        table: table_rows(db_path, table)
        for table in ("users", "entries", "beer_runs", "beer_run_members")
    }

    result = apply_migrations(db_path)

    assert result.applied == ("006_add_beer_run_invites",)
    assert "beer_run_invites" in table_names(db_path)
    assert {
        table: table_rows(db_path, table)
        for table in ("users", "entries", "beer_runs", "beer_run_members")
    } == before
    assert migration_versions(db_path) == MIGRATION_VERSIONS


def test_invite_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "fresh.db"
    apply_migrations(db_path)

    result = apply_migrations(db_path)

    assert result.skipped == tuple(MIGRATION_VERSIONS)
    assert row_count(db_path, "beer_run_invites") == 0


def test_invite_migration_baselines_complete_existing_table(tmp_path):
    db_path = tmp_path / "complete.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '006_add_beer_run_invites'"
        )

    result = apply_migrations(db_path)

    assert result.baselined == ("006_add_beer_run_invites",)
    assert migration_versions(db_path) == MIGRATION_VERSIONS


def test_invite_migration_refuses_partial_existing_table(tmp_path):
    db_path = tmp_path / "partial.db"
    apply_migrations(db_path)
    restore_pre_invite_schema(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE beer_run_invites (
                id INTEGER PRIMARY KEY,
                beer_run_id INTEGER NOT NULL,
                code VARCHAR NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    with pytest.raises(RuntimeError) as exc_info:
        apply_migrations(db_path)

    message = str(exc_info.value)
    assert "beer_run_invites already exists" in message
    assert "Repair or remove the partial table deliberately" in message
    assert migration_versions(db_path) == MIGRATION_VERSIONS[:5]
    assert index_names(db_path, "beer_run_invites") == set()
    assert foreign_key_targets(db_path, "beer_run_invites") == set()
    assert row_count(db_path, "beer_run_invites") == 0


def test_invite_migration_enforces_one_invite_per_run(tmp_path):
    db_path = tmp_path / "enforce.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run A')")
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run B')")
        run_a = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run A'").fetchone()[0]
        run_b = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run B'").fetchone()[0]

    add_invite(db_path, run_a, "A" * 43)

    with pytest.raises(sqlite3.IntegrityError):
        add_invite(db_path, run_a, "B" * 43)

    # The failed insert left the original invite untouched.
    assert row_count(db_path, "beer_run_invites") == 1
    assert scalar(db_path, "SELECT code FROM beer_run_invites") == "A" * 43


def test_invite_migration_enforces_globally_unique_code(tmp_path):
    db_path = tmp_path / "unique.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run A')")
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run B')")
        run_a = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run A'").fetchone()[0]
        run_b = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run B'").fetchone()[0]

    add_invite(db_path, run_a, "A" * 43)

    # Same code on another run must be rejected.
    with pytest.raises(sqlite3.IntegrityError):
        add_invite(db_path, run_b, "A" * 43)

    assert row_count(db_path, "beer_run_invites") == 1


def test_invite_migration_rejects_malformed_codes(tmp_path):
    db_path = tmp_path / "format.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run A')")
        run_a = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run A'").fetchone()[0]

    for bad_code in ("short", "A" * 44, "!" * 43, "A" * 42 + "!"):
        with pytest.raises(sqlite3.IntegrityError):
            add_invite(db_path, run_a, bad_code)

    assert row_count(db_path, "beer_run_invites") == 0


def test_invite_migration_codes_are_case_sensitive(tmp_path):
    db_path = tmp_path / "case.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run A')")
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Run B')")
        run_a = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run A'").fetchone()[0]
        run_b = conn.execute("SELECT id FROM beer_runs WHERE name = 'Run B'").fetchone()[0]

    add_invite(db_path, run_a, "A" * 43)

    # A case-changed variant is a different code and must be accepted on the
    # other run without colliding with the original.
    add_invite(db_path, run_b, "a" * 43)

    # Lookup is case-sensitive: the original code resolves only to run_a.
    with sqlite3.connect(db_path) as conn:
        run_id = conn.execute(
            "SELECT beer_run_id FROM beer_run_invites WHERE code = ?",
            ("A" * 43,),
        ).fetchone()[0]
        assert run_id == run_a
        assert conn.execute(
            "SELECT beer_run_id FROM beer_run_invites WHERE code = ?",
            ("a" * 43,),
        ).fetchone()[0] == run_b


# ── Authentication-subject migration (007) ─────────────────────────


def test_auth_subject_migration_backfills_unique_non_null_random_subjects(tmp_path):
    db_path = tmp_path / "existing.db"
    create_pre_backfill_schema_with_history(db_path)

    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, username, hashed_password, auth_subject FROM users ORDER BY id"
        ).fetchall()
        columns = {row[1]: row for row in conn.execute("PRAGMA table_info(users)")}
    assert [(row[0], row[1], row[2]) for row in rows] == [
        (1, "user", "hash"),
        (2, "Tamei", "tamei-hash"),
    ]
    subjects = [row[3] for row in rows]
    assert len(subjects) == len(set(subjects))
    assert all(
        len(subject) == 43
        and set(subject) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
        for subject in subjects
    )
    assert columns["auth_subject"][3] == 1
    assert "uq_users_auth_subject" in index_names(db_path, "users")


def test_auth_subject_migration_enforces_format_uniqueness_and_non_null(tmp_path):
    db_path = tmp_path / "enforce.db"
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO users (username, hashed_password, auth_subject) VALUES (?, ?, ?)",
            ("Alice", "hash", "A" * 43),
        )
        for username, subject in (
            ("Bob", None),
            ("Carol", "short"),
            ("Dave", "!" * 43),
            ("Eve", "A" * 43),
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO users (username, hashed_password, auth_subject) VALUES (?, ?, ?)",
                    (username, "hash", subject),
                )


def test_auth_subject_migration_baselines_complete_existing_schema(tmp_path):
    db_path = tmp_path / "complete.db"
    apply_migrations(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "DELETE FROM schema_migrations WHERE version = '007_add_user_auth_subject'"
        )

    result = apply_migrations(db_path)

    assert result.baselined == ("007_add_user_auth_subject",)
    assert migration_versions(db_path) == MIGRATION_VERSIONS
