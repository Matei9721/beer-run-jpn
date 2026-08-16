from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import sys
import uuid


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from migrations.runner import MigrationError, validate_database_ready


STATIC_UPLOAD_PREFIX = "static/uploads"
CANONICAL_PREFIX = f"{STATIC_UPLOAD_PREFIX}/beer_runs"
# This namespace is part of the persisted migration contract. Do not change it:
# the same run ID and normalized legacy path must map to the same destination on
# every machine and every rerun.
LEGACY_UPLOAD_NAMESPACE = uuid.UUID("4c8b0ef4-6837-5cda-9b5f-cd5c57da58e8")

_CANONICAL_RE = re.compile(
    rf"^{re.escape(CANONICAL_PREFIX)}/([1-9][0-9]*)/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jpg$"
)
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class UploadMigrationError(Exception):
    """A safe, operator-facing upload migration failure."""


class DestinationConflict(UploadMigrationError):
    """The deterministic destination exists with unverified or different bytes."""


@dataclass(frozen=True)
class FileFingerprint:
    size: int
    sha256: str


@dataclass(frozen=True)
class RowPlan:
    entry_id: int
    beer_run_id: int
    legacy_value: str
    source_relative: str
    source_path: Path
    canonical_relative: str
    destination_path: Path


@dataclass
class MigrationReport:
    planned: int = 0
    migratable: int = 0
    already_canonical: int = 0
    null: int = 0
    missing: int = 0
    invalid: int = 0
    conflicting: int = 0
    migrated: int = 0
    copied: int = 0
    reused: int = 0
    stale: int = 0
    failed: int = 0

    def has_unresolved(self) -> bool:
        return any((self.missing, self.invalid, self.conflicting, self.stale, self.failed))

    def summary(self, mode: str) -> str:
        return (
            f"mode={mode} planned={self.planned} migratable={self.migratable} "
            f"already_canonical={self.already_canonical} null={self.null} "
            f"missing={self.missing} invalid={self.invalid} "
            f"conflicting={self.conflicting} migrated={self.migrated} "
            f"copied={self.copied} reused={self.reused} stale={self.stale} "
            f"failed={self.failed}"
        )


def _diagnostic(entry_id: int, message: str, relative_path: str | None = None) -> None:
    suffix = f" ({relative_path})" if relative_path else ""
    print(f"entry {entry_id}: {message}{suffix}", file=sys.stderr)


def _validate_explicit_database(database_path: str | Path) -> Path:
    path = Path(database_path).expanduser()
    if not path.exists() or not path.is_file():
        raise UploadMigrationError("Database is not ready.")

    try:
        validate_database_ready(path)
    except MigrationError as exc:
        raise UploadMigrationError("Database is not ready.") from exc

    return path.resolve()


def _validate_upload_root(upload_root: str | Path) -> Path:
    root = Path(upload_root).expanduser()
    if not root.exists() or not root.is_dir():
        raise UploadMigrationError("Upload root is not ready.")
    return root.resolve()


def _sqlite_uri(path: Path, mode: str) -> str:
    return f"{path.as_uri()}?mode={mode}"


def _open_connection(database_path: Path, *, readonly: bool) -> sqlite3.Connection:
    mode = "ro" if readonly else "rw"
    conn = sqlite3.connect(
        _sqlite_uri(database_path, mode),
        uri=True,
        timeout=0,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _validate_required_schema(conn: sqlite3.Connection) -> None:
    entry_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(entries)").fetchall()
    }
    beer_run_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(beer_runs)").fetchall()
    }
    if not {"id", "beer_run_id", "image_path"}.issubset(entry_columns):
        raise UploadMigrationError("Database is not ready.")
    if "id" not in beer_run_columns:
        raise UploadMigrationError("Database is not ready.")


def _normalize_app_relative(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("invalid path")

    normalized = value.replace("\\", "/")
    if normalized != normalized.strip() or normalized.startswith("/"):
        raise ValueError("invalid path")
    if _WINDOWS_DRIVE_RE.match(normalized):
        raise ValueError("invalid path")

    raw_parts = normalized.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        raise ValueError("invalid path")
    if any(re.search(r'[<>:"|?*]', part) for part in raw_parts):
        raise ValueError("invalid path")

    path = PurePosixPath(normalized)
    if path.is_absolute() or len(path.parts) < 3:
        raise ValueError("invalid path")
    if path.parts[:2] != ("static", "uploads"):
        raise ValueError("invalid path")
    return path.as_posix()


def _confined_path(upload_root: Path, app_relative: str) -> Path:
    relative_below_root = PurePosixPath(app_relative).relative_to(STATIC_UPLOAD_PREFIX)
    candidate = upload_root.joinpath(*relative_below_root.parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(upload_root):
        raise ValueError("path outside upload root")
    return candidate


def _is_nonempty_regular_file(path: Path) -> bool:
    try:
        return not path.is_symlink() and path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _fingerprint(path: Path) -> FileFingerprint:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return FileFingerprint(size=size, sha256=digest.hexdigest())


def _canonical_relative(beer_run_id: int, source_relative: str) -> str:
    identity = f"{beer_run_id}\x00{source_relative}"
    destination_uuid = uuid.uuid5(LEGACY_UPLOAD_NAMESPACE, identity)
    return f"{CANONICAL_PREFIX}/{beer_run_id}/{destination_uuid}.jpg"


def _canonical_run_id(app_relative: str) -> int | None:
    match = _CANONICAL_RE.fullmatch(app_relative)
    if not match:
        return None
    try:
        parsed = uuid.UUID(match.group(2))
    except ValueError:
        return None
    if str(parsed) != match.group(2):
        return None
    return int(match.group(1))


def _destination_matches(source: Path, destination: Path) -> bool:
    if not _is_nonempty_regular_file(source) or not _is_nonempty_regular_file(destination):
        return False
    try:
        return _fingerprint(source) == _fingerprint(destination)
    except OSError:
        return False


def _staging_path(destination: Path) -> Path:
    """Return the deterministic, never-persisted path used while copying."""

    return destination.with_name(f".{destination.name}.migrating")


def _discard_staging_file(staging: Path) -> None:
    """Remove only the migration-owned staging file, never a directory."""

    if staging.is_dir() and not staging.is_symlink():
        raise DestinationConflict("Staging path conflict.")
    staging.unlink(missing_ok=True)


def _load_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT entries.id,
               entries.beer_run_id,
               entries.image_path,
               beer_runs.id AS valid_beer_run_id
        FROM entries
        LEFT JOIN beer_runs ON beer_runs.id = entries.beer_run_id
        ORDER BY entries.id
        """
    ).fetchall()


def _build_plan(
    database_path: Path,
    upload_root: Path,
) -> tuple[list[RowPlan], MigrationReport]:
    report = MigrationReport()
    plans: list[RowPlan] = []

    with _open_connection(database_path, readonly=True) as conn:
        _validate_required_schema(conn)
        rows = _load_rows(conn)

    for row in rows:
        entry_id = int(row["id"])
        legacy_value = row["image_path"]
        if legacy_value is None:
            report.null += 1
            continue

        valid_run_id = row["valid_beer_run_id"]
        beer_run_id = row["beer_run_id"]
        try:
            normalized = _normalize_app_relative(legacy_value)
        except ValueError:
            report.planned += 1
            report.invalid += 1
            _diagnostic(entry_id, "invalid image path")
            continue

        canonical_run_id = _canonical_run_id(normalized)
        if canonical_run_id is not None:
            if valid_run_id is None or canonical_run_id != beer_run_id:
                report.planned += 1
                report.invalid += 1
                _diagnostic(entry_id, "canonical path does not match a valid beer-run", normalized)
                continue
            try:
                canonical_file = _confined_path(upload_root, normalized)
            except ValueError:
                report.planned += 1
                report.invalid += 1
                _diagnostic(entry_id, "canonical path is outside the upload root")
                continue
            if not canonical_file.exists():
                report.planned += 1
                report.missing += 1
                _diagnostic(entry_id, "canonical image is missing", normalized)
            elif not _is_nonempty_regular_file(canonical_file):
                report.planned += 1
                report.invalid += 1
                _diagnostic(entry_id, "canonical image is not a non-empty regular file", normalized)
            else:
                report.already_canonical += 1
            continue
        if normalized.startswith(f"{CANONICAL_PREFIX}/"):
            report.planned += 1
            report.invalid += 1
            _diagnostic(entry_id, "malformed canonical image path")
            continue

        report.planned += 1
        if valid_run_id is None or not isinstance(beer_run_id, int) or beer_run_id <= 0:
            report.invalid += 1
            _diagnostic(entry_id, "entry has no valid beer-run", normalized)
            continue

        try:
            source_path = _confined_path(upload_root, normalized)
        except ValueError:
            report.invalid += 1
            _diagnostic(entry_id, "legacy image is outside the upload root")
            continue

        if not source_path.exists():
            report.missing += 1
            _diagnostic(entry_id, "legacy image is missing", normalized)
            continue
        if not _is_nonempty_regular_file(source_path):
            report.invalid += 1
            _diagnostic(entry_id, "legacy image is not a non-empty regular file", normalized)
            continue

        canonical_relative = _canonical_relative(beer_run_id, normalized)
        try:
            destination_path = _confined_path(upload_root, canonical_relative)
        except ValueError:
            report.invalid += 1
            _diagnostic(entry_id, "canonical destination is outside the upload root")
            continue

        if destination_path.exists() and not _destination_matches(source_path, destination_path):
            report.conflicting += 1
            _diagnostic(entry_id, "canonical destination conflicts", canonical_relative)
            continue

        report.migratable += 1
        plans.append(
            RowPlan(
                entry_id=entry_id,
                beer_run_id=beer_run_id,
                legacy_value=legacy_value,
                source_relative=normalized,
                source_path=source_path,
                canonical_relative=canonical_relative,
                destination_path=destination_path,
            )
        )

    return plans, report


def _begin_immediate(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")


def _copy_or_reuse(source: Path, destination: Path) -> str:
    staging = _staging_path(destination)
    if destination.exists():
        if _destination_matches(source, destination):
            _discard_staging_file(staging)
            return "reused"
        raise DestinationConflict("Destination conflict.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    _discard_staging_file(staging)
    created_staging = False
    published = False
    try:
        with source.open("rb") as input_file:
            output = staging.open("xb")
            created_staging = True
            with output:
                shutil.copyfileobj(input_file, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())

        if not _destination_matches(source, staging):
            raise UploadMigrationError("Copy verification failed.")

        try:
            # Publishing a hard link is atomic and fails rather than replacing
            # a destination created by another process after planning.
            os.link(staging, destination)
            published = True
        except FileExistsError:
            if _destination_matches(source, destination):
                return "reused"
            raise DestinationConflict("Destination conflict.")

        if not _destination_matches(source, destination):
            if published:
                destination.unlink(missing_ok=True)
            raise UploadMigrationError("Copy verification failed.")
        return "copied"
    finally:
        if created_staging or staging.exists() or staging.is_symlink():
            try:
                _discard_staging_file(staging)
            except OSError:
                pass


def _update_entry(conn: sqlite3.Connection, plan: RowPlan) -> bool:
    cursor = conn.execute(
        """
        UPDATE entries
        SET image_path = ?
        WHERE id = ? AND image_path = ? AND beer_run_id = ?
        """,
        (
            plan.canonical_relative,
            plan.entry_id,
            plan.legacy_value,
            plan.beer_run_id,
        ),
    )
    return cursor.rowcount == 1


def _commit(conn: sqlite3.Connection) -> None:
    conn.commit()


def _apply_plans(
    database_path: Path,
    upload_root: Path,
    plans: list[RowPlan],
    report: MigrationReport,
) -> None:
    for index, plan in enumerate(plans):
        conn: sqlite3.Connection | None = None
        try:
            conn = _open_connection(database_path, readonly=False)
            _begin_immediate(conn)

            current = conn.execute(
                """
                SELECT entries.image_path, entries.beer_run_id, beer_runs.id AS valid_beer_run_id
                FROM entries
                LEFT JOIN beer_runs ON beer_runs.id = entries.beer_run_id
                WHERE entries.id = ?
                """,
                (plan.entry_id,),
            ).fetchone()
            if (
                current is None
                or current["image_path"] != plan.legacy_value
                or current["beer_run_id"] != plan.beer_run_id
                or current["valid_beer_run_id"] is None
            ):
                conn.rollback()
                report.stale += 1
                _diagnostic(plan.entry_id, "row changed after planning")
                continue

            try:
                current_normalized = _normalize_app_relative(current["image_path"])
                current_source = _confined_path(upload_root, current_normalized)
            except ValueError:
                conn.rollback()
                report.stale += 1
                _diagnostic(plan.entry_id, "row changed after planning")
                continue
            if current_normalized != plan.source_relative or current_source != plan.source_path:
                conn.rollback()
                report.stale += 1
                _diagnostic(plan.entry_id, "row changed after planning")
                continue
            if not _is_nonempty_regular_file(current_source):
                conn.rollback()
                report.failed += 1
                _diagnostic(plan.entry_id, "legacy image became unavailable", plan.source_relative)
                continue

            try:
                current_destination = _confined_path(upload_root, plan.canonical_relative)
            except ValueError as exc:
                raise UploadMigrationError("Destination confinement failed.") from exc
            if current_destination != plan.destination_path:
                raise UploadMigrationError("Destination confinement failed.")

            copy_result = _copy_or_reuse(current_source, current_destination)
            if not _destination_matches(current_source, current_destination):
                raise UploadMigrationError("Copy verification failed.")
            if not _update_entry(conn, plan):
                conn.rollback()
                report.stale += 1
                _diagnostic(plan.entry_id, "row changed before update")
                continue
            if not _destination_matches(current_source, current_destination):
                raise UploadMigrationError("Copy verification failed.")

            _commit(conn)
            report.migrated += 1
            if copy_result == "copied":
                report.copied += 1
            else:
                report.reused += 1
        except DestinationConflict:
            if conn is not None:
                conn.rollback()
            report.conflicting += 1
            _diagnostic(plan.entry_id, "canonical destination conflicts", plan.canonical_relative)
        except sqlite3.OperationalError as exc:
            if conn is not None:
                conn.rollback()
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                report.failed += len(plans) - index
                print("Upload migration failed: database write lock unavailable.", file=sys.stderr)
                break
            report.failed += 1
            _diagnostic(plan.entry_id, "database operation failed")
        except Exception:
            if conn is not None:
                conn.rollback()
            report.failed += 1
            _diagnostic(plan.entry_id, "migration operation failed")
        finally:
            if conn is not None:
                conn.close()


def run_upload_migration(
    database_path: str | Path,
    upload_root: str | Path,
    *,
    apply: bool,
) -> MigrationReport:
    database = _validate_explicit_database(database_path)
    root = _validate_upload_root(upload_root)
    plans, report = _build_plan(database, root)
    if apply:
        _apply_plans(database, root, plans, report)
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preflight or apply the BoozeRunJpn legacy upload-path migration."
    )
    parser.add_argument("--database", required=True, help="Existing SQLite database path.")
    parser.add_argument(
        "--upload-root",
        required=True,
        help="Existing static/uploads directory corresponding to the database.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true", help="Report only; make no changes.")
    mode.add_argument("--apply", action="store_true", help="Copy verified files and update rows.")
    return parser


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    mode = "apply" if args.apply else "preflight"
    try:
        report = run_upload_migration(
            args.database,
            args.upload_root,
            apply=args.apply,
        )
    except UploadMigrationError as exc:
        print(f"Upload migration failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error):
        print("Upload migration failed: unable to inspect configured data.", file=sys.stderr)
        return 1

    print(report.summary(mode))
    return 1 if report.has_unresolved() else 0


if __name__ == "__main__":
    raise SystemExit(main())
