"""Safe cleanup helpers for persisted beer-run entry photos."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import UUID

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
