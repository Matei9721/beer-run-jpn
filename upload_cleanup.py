"""Safe cleanup helpers for persisted beer-run entry photos."""

from __future__ import annotations

import re
import shutil
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import models


_CANONICAL_UPLOAD_RE = re.compile(
    r"^static/uploads/beer_runs/([1-9][0-9]*)/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jpg$"
)


@dataclass(frozen=True)
class OwnedRunUpload:
    """A validated persisted path that may belong exclusively to one run."""

    image_path: str
    physical_path: Path


@dataclass(frozen=True)
class QuarantinedUpload:
    original_path: Path
    quarantine_path: Path


@dataclass(frozen=True)
class UploadQuarantine:
    """A private recoverable staging operation for account-owned photos."""

    operation_root: Path
    upload_root: Path
    uploads: tuple[QuarantinedUpload, ...]


class QuarantineRestoreError(RuntimeError):
    """Raised when live photo paths could not be restored safely."""

    def __init__(self, operation: UploadQuarantine):
        super().__init__("Unable to restore quarantined uploads")
        self.operation = operation


def persisted_upload_target(
    image_path: str | None,
    beer_run_id: int,
    *,
    upload_root: Path,
    upload_path_root: PurePosixPath,
) -> Path | None:
    """Resolve one exact canonical same-run file beneath the configured root."""

    if not isinstance(image_path, str) or "\\" in image_path:
        return None
    match = _CANONICAL_UPLOAD_RE.fullmatch(image_path)
    if match is None or int(match.group(1)) != beer_run_id:
        return None
    try:
        parsed_uuid = UUID(match.group(2))
    except ValueError:
        return None
    if str(parsed_uuid) != match.group(2):
        return None

    try:
        relative = PurePosixPath(image_path).relative_to(upload_path_root)
        resolved_root = upload_root.resolve(strict=False)
        candidate = upload_root.joinpath(*relative.parts)
        resolved_target = candidate.resolve(strict=False)
        if not resolved_target.is_relative_to(resolved_root):
            return None
        if candidate.is_symlink() or not resolved_target.is_file():
            return None
        if resolved_target.stat().st_nlink != 1:
            return None
    except (OSError, ValueError):
        return None
    return resolved_target


def _normalized_path(image_path: str) -> str:
    return image_path.replace("\\", "/")


def _has_external_reference(
    db: Session,
    image_path: str,
    beer_run_id: int,
) -> bool:
    return (
        db.query(models.Entry.id)
        .filter(
            func.replace(models.Entry.image_path, "\\", "/") == _normalized_path(image_path),
            or_(
                models.Entry.beer_run_id != beer_run_id,
                models.Entry.beer_run_id.is_(None),
            ),
        )
        .first()
        is not None
    )


def collect_run_uploads(
    db: Session,
    beer_run_id: int,
    *,
    upload_root: Path,
    upload_path_root: PurePosixPath,
) -> tuple[OwnedRunUpload, ...]:
    """Collect validated files before the run's rows are changed."""

    uploads: dict[Path, OwnedRunUpload] = {}
    image_paths = (
        db.query(models.Entry.image_path)
        .filter(models.Entry.beer_run_id == beer_run_id)
        .all()
    )
    for (image_path,) in image_paths:
        target = persisted_upload_target(
            image_path,
            beer_run_id,
            upload_root=upload_root,
            upload_path_root=upload_path_root,
        )
        if target is None or _has_external_reference(db, image_path, beer_run_id):
            continue
        uploads[target] = OwnedRunUpload(
            image_path=_normalized_path(image_path),
            physical_path=target,
        )
    return tuple(uploads.values())


def collect_user_uploads(
    db: Session,
    user_id: int,
    *,
    upload_root: Path,
    upload_path_root: PurePosixPath,
) -> tuple[OwnedRunUpload, ...]:
    """Collect canonical files referenced only by the deleting user's rows."""

    uploads: dict[Path, OwnedRunUpload] = {}
    rows = (
        db.query(models.Entry.image_path, models.Entry.beer_run_id)
        .filter(models.Entry.user_id == user_id)
        .all()
    )
    for image_path, beer_run_id in rows:
        if not isinstance(beer_run_id, int):
            continue
        target = persisted_upload_target(
            image_path,
            beer_run_id,
            upload_root=upload_root,
            upload_path_root=upload_path_root,
        )
        if target is None:
            continue
        surviving_reference = (
            db.query(models.Entry.id)
            .filter(
                func.replace(models.Entry.image_path, "\\", "/")
                == _normalized_path(image_path),
                or_(models.Entry.user_id != user_id, models.Entry.user_id.is_(None)),
            )
            .first()
        )
        if surviving_reference is not None:
            continue
        uploads[target] = OwnedRunUpload(_normalized_path(image_path), target)
    return tuple(uploads.values())


def quarantine_uploads(
    uploads: tuple[OwnedRunUpload, ...],
    *,
    upload_root: Path,
    quarantine_root: Path,
) -> UploadQuarantine | None:
    """Move proven-exclusive files aside, restoring all moves on failure."""

    if not uploads:
        return None

    resolved_upload_root = upload_root.resolve(strict=True)
    resolved_quarantine_root = quarantine_root.resolve(strict=False)
    if resolved_quarantine_root.is_relative_to(resolved_upload_root):
        raise ValueError("Account-deletion quarantine must be outside uploads")

    quarantine_root.mkdir(parents=True, exist_ok=True)
    if resolved_upload_root.stat().st_dev != quarantine_root.resolve(strict=True).stat().st_dev:
        raise ValueError("Account-deletion quarantine must share the upload filesystem")

    operation_root = quarantine_root / str(uuid4())
    operation_root.mkdir(parents=False, exist_ok=False)
    moved: list[QuarantinedUpload] = []
    try:
        for index, upload in enumerate(uploads):
            destination = operation_root / f"{index}-{upload.physical_path.name}"
            upload.physical_path.replace(destination)
            moved.append(QuarantinedUpload(upload.physical_path, destination))
            _write_quarantine_manifest(
                UploadQuarantine(operation_root, resolved_upload_root, tuple(moved))
            )
    except Exception:
        operation = UploadQuarantine(
            operation_root,
            resolved_upload_root,
            tuple(moved),
        )
        if moved:
            restore_quarantined_uploads(operation)
        else:
            _remove_operation_root(operation_root)
        raise
    return UploadQuarantine(operation_root, resolved_upload_root, tuple(moved))


def _write_quarantine_manifest(operation: UploadQuarantine) -> None:
    manifest = operation.operation_root / "manifest.json"
    pending = manifest.with_suffix(".pending")
    payload = {
        "version": 1,
        "files": [
            {
                "original": upload.original_path.relative_to(
                    operation.upload_root
                ).as_posix(),
                "quarantined": upload.quarantine_path.name,
            }
            for upload in operation.uploads
        ],
    }
    pending.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    pending.replace(manifest)


def _remove_operation_root(operation_root: Path) -> None:
    try:
        shutil.rmtree(operation_root)
        operation_root.parent.rmdir()
    except OSError:
        pass


def restore_quarantined_uploads(
    operation: UploadQuarantine,
    *,
    attempts: int = 2,
) -> None:
    """Restore quarantined files; raise if a live reference cannot be repaired."""

    for _ in range(max(1, attempts)):
        failed = False
        for upload in reversed(operation.uploads):
            if upload.original_path.is_file() and not upload.quarantine_path.exists():
                continue
            try:
                upload.original_path.parent.mkdir(parents=True, exist_ok=True)
                upload.quarantine_path.replace(upload.original_path)
            except Exception:
                failed = True
        if not failed:
            _remove_operation_root(operation.operation_root)
            return
    raise QuarantineRestoreError(operation)


def purge_quarantined_uploads(operation: UploadQuarantine | None) -> None:
    """Best-effort purge after the database commit is authoritative."""

    if operation is not None:
        _remove_operation_root(operation.operation_root)


def _run_directory(
    beer_run_id: int,
    *,
    upload_root: Path,
) -> Path | None:
    try:
        resolved_root = upload_root.resolve(strict=False)
        candidate = upload_root / "beer_runs" / str(beer_run_id)
        resolved_candidate = candidate.resolve(strict=False)
        if not resolved_candidate.is_relative_to(resolved_root):
            return None
        if candidate.is_symlink() or not candidate.is_dir():
            return None
        return candidate
    except (OSError, ValueError):
        return None


def cleanup_run_uploads(
    db: Session,
    beer_run_id: int,
    uploads: tuple[OwnedRunUpload, ...],
    *,
    upload_root: Path,
    upload_path_root: PurePosixPath,
) -> None:
    """Remove only still-valid, unshared files after the database commit."""

    for upload in uploads:
        try:
            target = persisted_upload_target(
                upload.image_path,
                beer_run_id,
                upload_root=upload_root,
                upload_path_root=upload_path_root,
            )
            if target is None or target != upload.physical_path:
                continue
            if _has_external_reference(db, upload.image_path, beer_run_id):
                continue
            target.unlink(missing_ok=True)
        except Exception:
            # The database is already authoritative. An orphan is safer than a
            # request that reports failure after its rows have been removed.
            continue

    directory = _run_directory(beer_run_id, upload_root=upload_root)
    if directory is None:
        return
    try:
        directory.rmdir()
    except OSError:
        # Non-empty or inaccessible directories must remain untouched.
        pass
