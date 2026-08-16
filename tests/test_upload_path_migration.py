from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3

import pytest

from migrations.runner import apply_migrations
from scripts import migrate_upload_paths as upload_migration


def _database_and_uploads(tmp_path: Path) -> tuple[Path, Path, int, int]:
    database = tmp_path / "trip.db"
    uploads = tmp_path / "static" / "uploads"
    uploads.mkdir(parents=True)
    apply_migrations(database)

    with sqlite3.connect(database) as conn:
        first_run = conn.execute(
            "SELECT id FROM beer_runs WHERE name = 'BeerRunJPN'"
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO beer_runs (name, is_public, created_at) VALUES (?, ?, ?)",
            ("Second Run", 0, "2026-08-13 10:00:00"),
        )
        second_run = cursor.lastrowid
    return database, uploads, first_run, second_run


def _add_entry(
    database: Path,
    beer_run_id: int | None,
    image_path: str | None,
    *,
    enforce_foreign_keys: bool = True,
) -> int:
    with sqlite3.connect(database) as conn:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if enforce_foreign_keys else 'OFF'}")
        cursor = conn.execute(
            "INSERT INTO entries (beer_run_id, image_path) VALUES (?, ?)",
            (beer_run_id, image_path),
        )
        return cursor.lastrowid


def _entry_path(database: Path, entry_id: int) -> str | None:
    with sqlite3.connect(database) as conn:
        return conn.execute(
            "SELECT image_path FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()[0]


def _snapshot_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _run_args(database: Path, uploads: Path, mode: str) -> list[str]:
    return [
        "--database",
        str(database),
        "--upload-root",
        str(uploads),
        mode,
    ]


def test_preflight_reports_exact_categories_without_changes(tmp_path, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    (uploads / "valid.jpg").write_bytes(b"valid-image")
    (uploads / "empty.jpg").write_bytes(b"")
    (uploads / "folder.jpg").mkdir()

    canonical = f"static/uploads/beer_runs/{run_id}/12345678-1234-4234-8234-123456789abc.jpg"
    canonical_file = uploads / "beer_runs" / str(run_id) / "12345678-1234-4234-8234-123456789abc.jpg"
    canonical_file.parent.mkdir(parents=True)
    canonical_file.write_bytes(b"canonical")

    _add_entry(database, run_id, None)
    _add_entry(database, run_id, "static/uploads/valid.jpg")
    _add_entry(database, run_id, canonical)
    _add_entry(database, run_id, "static/uploads/missing.jpg")
    _add_entry(database, run_id, "static/uploads/empty.jpg")
    _add_entry(database, run_id, "static/uploads/folder.jpg")
    _add_entry(database, run_id, "static/uploads/../outside.jpg")
    _add_entry(database, run_id, f"static/uploads/beer_runs/{run_id}/not-a-uuid.jpg")
    _add_entry(database, 99999, "static/uploads/valid.jpg", enforce_foreign_keys=False)

    database_before = hashlib.sha256(database.read_bytes()).hexdigest()
    files_before = _snapshot_tree(uploads)
    capsys.readouterr()

    assert upload_migration.main(_run_args(database, uploads, "--preflight")) == 1

    captured = capsys.readouterr()
    assert captured.out.strip() == (
        "mode=preflight planned=7 migratable=1 already_canonical=1 null=1 "
        "missing=1 invalid=5 conflicting=0 migrated=0 copied=0 reused=0 stale=0 failed=0"
    )
    assert "outside.jpg" not in captured.err
    assert hashlib.sha256(database.read_bytes()).hexdigest() == database_before
    assert _snapshot_tree(uploads) == files_before


def test_plans_are_deterministic_for_shared_sources_and_two_runs(tmp_path):
    database, uploads, first_run, second_run = _database_and_uploads(tmp_path)
    (uploads / "shared.jpg").write_bytes(b"shared-image")
    first = _add_entry(database, first_run, "static/uploads/shared.jpg")
    second = _add_entry(database, first_run, "static\\uploads\\shared.jpg")
    third = _add_entry(database, second_run, "static/uploads/shared.jpg")

    database_path = upload_migration._validate_explicit_database(database)
    upload_root = upload_migration._validate_upload_root(uploads)
    plans_one, report_one = upload_migration._build_plan(database_path, upload_root)
    plans_two, report_two = upload_migration._build_plan(database_path, upload_root)

    by_entry_one = {plan.entry_id: plan.canonical_relative for plan in plans_one}
    by_entry_two = {plan.entry_id: plan.canonical_relative for plan in plans_two}
    assert report_one.migratable == report_two.migratable == 3
    assert by_entry_one == by_entry_two
    assert by_entry_one[first] == by_entry_one[second]
    assert by_entry_one[first] != by_entry_one[third]
    assert f"/beer_runs/{first_run}/" in by_entry_one[first]
    assert f"/beer_runs/{second_run}/" in by_entry_one[third]

    copied_root = tmp_path / "copied-machine"
    copied_uploads = copied_root / "static" / "uploads"
    copied_uploads.parent.mkdir(parents=True)
    shutil.copytree(uploads, copied_uploads)
    copied_database = copied_root / "trip.db"
    shutil.copy2(database, copied_database)
    copied_plans, _ = upload_migration._build_plan(
        upload_migration._validate_explicit_database(copied_database),
        upload_migration._validate_upload_root(copied_uploads),
    )
    assert {plan.entry_id: plan.canonical_relative for plan in copied_plans} == by_entry_one


def test_apply_copies_once_reuses_for_shared_rows_and_is_idempotent(tmp_path, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    source = uploads / "shared.jpg"
    source.write_bytes(b"irreplaceable-image")
    first = _add_entry(database, run_id, "static/uploads/shared.jpg")
    second = _add_entry(database, run_id, "static\\uploads\\shared.jpg")
    capsys.readouterr()

    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 0
    first_output = capsys.readouterr().out.strip()
    assert first_output == (
        "mode=apply planned=2 migratable=2 already_canonical=0 null=0 "
        "missing=0 invalid=0 conflicting=0 migrated=2 copied=1 reused=1 stale=0 failed=0"
    )

    first_path = _entry_path(database, first)
    second_path = _entry_path(database, second)
    assert first_path == second_path
    assert first_path.startswith(f"static/uploads/beer_runs/{run_id}/")
    destination = tmp_path / first_path
    assert destination.read_bytes() == source.read_bytes() == b"irreplaceable-image"
    assert source.read_bytes() == b"irreplaceable-image"

    state_after_success = _snapshot_tree(uploads)
    rows_after_success = (first_path, second_path)
    for _ in range(3):
        assert upload_migration.main(_run_args(database, uploads, "--apply")) == 0
        rerun_output = capsys.readouterr().out.strip()
        assert "planned=0 migratable=0 already_canonical=2" in rerun_output
        assert _snapshot_tree(uploads) == state_after_success
        assert (_entry_path(database, first), _entry_path(database, second)) == rows_after_success


def test_identical_destination_is_reused_without_reencoding(tmp_path, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    source = uploads / "legacy.png"
    source.write_bytes(b"original-format-bytes")
    entry_id = _add_entry(database, run_id, "static/uploads/legacy.png")
    canonical = upload_migration._canonical_relative(run_id, "static/uploads/legacy.png")
    destination = tmp_path / canonical
    destination.parent.mkdir(parents=True)
    destination.write_bytes(source.read_bytes())

    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 0
    assert "migrated=1 copied=0 reused=1" in capsys.readouterr().out
    assert _entry_path(database, entry_id) == canonical
    assert destination.read_bytes() == b"original-format-bytes"
    assert source.read_bytes() == b"original-format-bytes"


def test_conflicting_destination_is_preserved_and_row_stays_legacy(tmp_path, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    source = uploads / "legacy.jpg"
    source.write_bytes(b"source")
    legacy_path = "static/uploads/legacy.jpg"
    entry_id = _add_entry(database, run_id, legacy_path)
    canonical = upload_migration._canonical_relative(run_id, legacy_path)
    destination = tmp_path / canonical
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"sentinel")

    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 1
    captured = capsys.readouterr()
    assert "conflicting=1" in captured.out
    assert "canonical destination conflicts" in captured.err
    assert destination.read_bytes() == b"sentinel"
    assert source.read_bytes() == b"source"
    assert _entry_path(database, entry_id) == legacy_path


def test_guarded_update_rejects_a_row_changed_after_planning(tmp_path, monkeypatch, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    (uploads / "first.jpg").write_bytes(b"first")
    (uploads / "replacement.jpg").write_bytes(b"replacement")
    entry_id = _add_entry(database, run_id, "static/uploads/first.jpg")
    original_begin = upload_migration._begin_immediate
    changed = False

    def change_then_begin(conn):
        nonlocal changed
        if not changed:
            with sqlite3.connect(database) as other:
                other.execute(
                    "UPDATE entries SET image_path = ? WHERE id = ?",
                    ("static/uploads/replacement.jpg", entry_id),
                )
            changed = True
        original_begin(conn)

    monkeypatch.setattr(upload_migration, "_begin_immediate", change_then_begin)

    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 1
    captured = capsys.readouterr()
    assert "stale=1" in captured.out
    assert "row changed after planning" in captured.err
    assert _entry_path(database, entry_id) == "static/uploads/replacement.jpg"
    assert not (uploads / "beer_runs").exists()


def test_database_lock_fails_before_any_filesystem_side_effect(tmp_path, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    (uploads / "legacy.jpg").write_bytes(b"source")
    entry_id = _add_entry(database, run_id, "static/uploads/legacy.jpg")

    blocker = sqlite3.connect(database, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    try:
        assert upload_migration.main(_run_args(database, uploads, "--apply")) == 1
    finally:
        blocker.rollback()
        blocker.close()

    captured = capsys.readouterr()
    assert "database write lock unavailable" in captured.err
    assert "failed=1" in captured.out
    assert _entry_path(database, entry_id) == "static/uploads/legacy.jpg"
    assert not (uploads / "beer_runs").exists()


def test_failure_after_copy_is_resumable_without_duplicate_destination(
    tmp_path, monkeypatch, capsys
):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    (uploads / "one.jpg").write_bytes(b"one")
    (uploads / "two.jpg").write_bytes(b"two")
    first = _add_entry(database, run_id, "static/uploads/one.jpg")
    second = _add_entry(database, run_id, "static/uploads/two.jpg")
    original_update = upload_migration._update_entry

    def fail_second_update(conn, plan):
        if plan.entry_id == second:
            raise RuntimeError("forced boundary failure")
        return original_update(conn, plan)

    monkeypatch.setattr(upload_migration, "_update_entry", fail_second_update)
    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 1
    first_run_output = capsys.readouterr().out
    assert "migrated=1" in first_run_output and "failed=1" in first_run_output
    first_path = _entry_path(database, first)
    assert first_path.startswith("static/uploads/beer_runs/")
    assert _entry_path(database, second) == "static/uploads/two.jpg"
    copied_files = list((uploads / "beer_runs" / str(run_id)).glob("*.jpg"))
    assert len(copied_files) == 2

    monkeypatch.setattr(upload_migration, "_update_entry", original_update)
    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 0
    rerun_output = capsys.readouterr().out
    assert "migrated=1 copied=0 reused=1" in rerun_output
    assert len(list((uploads / "beer_runs" / str(run_id)).glob("*.jpg"))) == 2
    assert _entry_path(database, second).startswith("static/uploads/beer_runs/")


def test_failure_reported_after_commit_is_safe_to_rerun(tmp_path, monkeypatch, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    (uploads / "legacy.jpg").write_bytes(b"legacy")
    entry_id = _add_entry(database, run_id, "static/uploads/legacy.jpg")
    original_commit = upload_migration._commit

    def commit_then_fail(conn):
        original_commit(conn)
        raise RuntimeError("simulated process interruption")

    monkeypatch.setattr(upload_migration, "_commit", commit_then_fail)
    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 1
    assert "failed=1" in capsys.readouterr().out
    canonical = _entry_path(database, entry_id)
    assert canonical.startswith("static/uploads/beer_runs/")
    assert (tmp_path / canonical).read_bytes() == b"legacy"

    monkeypatch.setattr(upload_migration, "_commit", original_commit)
    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 0
    assert "planned=0 migratable=0 already_canonical=1" in capsys.readouterr().out


def test_copy_failure_leaves_legacy_row_and_no_destination(tmp_path, monkeypatch, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    (uploads / "legacy.jpg").write_bytes(b"legacy")
    legacy_path = "static/uploads/legacy.jpg"
    entry_id = _add_entry(database, run_id, legacy_path)

    def fail_copy(source, destination):
        raise OSError("private absolute path")

    monkeypatch.setattr(upload_migration, "_copy_or_reuse", fail_copy)
    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 1
    captured = capsys.readouterr()
    assert "failed=1" in captured.out
    assert "private absolute path" not in captured.err
    assert _entry_path(database, entry_id) == legacy_path
    assert not (uploads / "beer_runs").exists()


def test_interrupted_partial_staging_copy_is_replaced_on_rerun(tmp_path, capsys):
    database, uploads, run_id, _ = _database_and_uploads(tmp_path)
    source = uploads / "legacy.jpg"
    source.write_bytes(b"complete-irreplaceable-image")
    legacy_path = "static/uploads/legacy.jpg"
    entry_id = _add_entry(database, run_id, legacy_path)
    canonical = upload_migration._canonical_relative(run_id, legacy_path)
    destination = tmp_path / canonical
    destination.parent.mkdir(parents=True)
    staging = upload_migration._staging_path(destination)
    staging.write_bytes(b"partial")

    assert upload_migration.main(_run_args(database, uploads, "--apply")) == 0

    assert "migrated=1 copied=1" in capsys.readouterr().out
    assert _entry_path(database, entry_id) == canonical
    assert destination.read_bytes() == source.read_bytes()
    assert not staging.exists()


def test_missing_database_is_not_created_and_cli_requires_explicit_paths(tmp_path, capsys):
    uploads = tmp_path / "static" / "uploads"
    uploads.mkdir(parents=True)
    missing_database = tmp_path / "missing.db"

    assert upload_migration.main(
        _run_args(missing_database, uploads, "--preflight")
    ) == 1
    assert "Database is not ready" in capsys.readouterr().err
    assert not missing_database.exists()

    with pytest.raises(SystemExit) as missing_args:
        upload_migration.main([])
    assert missing_args.value.code == 2


def test_only_the_explicit_temporary_database_is_opened(tmp_path, monkeypatch):
    database, uploads, _, _ = _database_and_uploads(tmp_path)
    opened: list[Path] = []
    original_open = upload_migration._open_connection

    def record_open(path, *, readonly):
        opened.append(path)
        return original_open(path, readonly=readonly)

    monkeypatch.setattr(upload_migration, "_open_connection", record_open)
    assert upload_migration.main(_run_args(database, uploads, "--preflight")) == 0
    assert opened == [database.resolve()]
    assert all(path != (Path.cwd() / "boozerun.db").resolve() for path in opened)
