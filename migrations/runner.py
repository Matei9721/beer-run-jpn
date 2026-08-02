from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC
import importlib
from pathlib import Path
import sqlite3
from types import ModuleType
from typing import Iterable

from database import DATABASE_PATH

initial_schema = importlib.import_module("migrations.versions.001_initial_schema")
beer_run_schema = importlib.import_module("migrations.versions.002_add_beer_run_schema")
backfill_existing_trip = importlib.import_module("migrations.versions.003_backfill_existing_trip")
case_insensitive_usernames = importlib.import_module(
    "migrations.versions.004_case_insensitive_usernames"
)
beer_run_name_nocase = importlib.import_module(
    "migrations.versions.005_beer_run_name_nocase"
)


class MigrationError(Exception):
    """Base class for migration failures."""


class MigrationRequired(MigrationError):
    """Raised when the database is not at the required migration state."""


@dataclass(frozen=True)
class Migration:
    version: str
    description: str
    module: ModuleType


@dataclass(frozen=True)
class MigrationResult:
    applied: tuple[str, ...]
    baselined: tuple[str, ...]
    skipped: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(initial_schema.ID, initial_schema.DESCRIPTION, initial_schema),
    Migration(beer_run_schema.ID, beer_run_schema.DESCRIPTION, beer_run_schema),
    Migration(backfill_existing_trip.ID, backfill_existing_trip.DESCRIPTION, backfill_existing_trip),
    Migration(
        case_insensitive_usernames.ID,
        case_insensitive_usernames.DESCRIPTION,
        case_insensitive_usernames,
    ),
    Migration(
        beer_run_name_nocase.ID,
        beer_run_name_nocase.DESCRIPTION,
        beer_run_name_nocase,
    ),
)


def resolve_database_path(database_path: str | Path | None = None) -> Path:
    return Path(database_path or DATABASE_PATH)


def connect(database_path: str | Path | None = None) -> sqlite3.Connection:
    path = resolve_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def schema_migrations_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
    ).fetchone()
    return row is not None


def get_applied_versions(conn: sqlite3.Connection) -> set[str]:
    if not schema_migrations_exists(conn):
        return set()
    return {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}


def record_migration(conn: sqlite3.Connection, version: str) -> None:
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (version, datetime.now(UTC).isoformat()),
    )


def required_versions(migrations: Iterable[Migration] = MIGRATIONS) -> tuple[str, ...]:
    return tuple(migration.version for migration in migrations)


def apply_migrations(database_path: str | Path | None = None) -> MigrationResult:
    applied: list[str] = []
    baselined: list[str] = []
    skipped: list[str] = []

    with connect(database_path) as conn:
        ensure_schema_migrations(conn)
        applied_versions = get_applied_versions(conn)

        for migration in MIGRATIONS:
            if migration.version in applied_versions:
                skipped.append(migration.version)
                continue

            baseline_matches = getattr(migration.module, "baseline_matches", None)
            if baseline_matches and baseline_matches(conn):
                record_migration(conn, migration.version)
                applied_versions.add(migration.version)
                baselined.append(migration.version)
                continue

            migration.module.apply(conn)
            record_migration(conn, migration.version)
            applied_versions.add(migration.version)
            applied.append(migration.version)

    return MigrationResult(tuple(applied), tuple(baselined), tuple(skipped))


def validate_database_ready(database_path: str | Path | None = None) -> None:
    path = resolve_database_path(database_path)
    if not path.exists():
        raise MigrationRequired(f"Database requires migrations before startup: {path}")

    with sqlite3.connect(path) as conn:
        if not schema_migrations_exists(conn):
            raise MigrationRequired(f"Database requires migrations before startup: {path}")
        applied_versions = get_applied_versions(conn)

    missing = [version for version in required_versions() if version not in applied_versions]
    if missing:
        raise MigrationRequired(
            f"Database requires migrations before startup: missing {', '.join(missing)}"
        )
