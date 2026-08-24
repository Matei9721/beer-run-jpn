import os
import io
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Dict
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session
from PIL import Image, ImageOps
from starlette.datastructures import UploadFile as StarletteUploadFile

import models
import auth
import auth_routes
import beer_run_routes
import invite_routes
import permissions
import schemas
from database import get_db
from migrations.runner import MigrationRequired, validate_database_ready

auth.validate_auth_configuration()
auth.validate_signup_configuration()

try:
    validate_database_ready()
except MigrationRequired as exc:
    raise RuntimeError(f"Database migration required: {exc}") from exc

app = FastAPI(title="BoozeRunJpn")
# Register the signup validation handler globally (FastAPI exception handlers
# are route-agnostic — the filter inside the function ensures it only applies
# to /api/signup, while other routes still use the default handler).
app.add_exception_handler(
    RequestValidationError,
    auth_routes.sanitize_signup_validation_error,
)
app.include_router(auth_routes.router)
app.include_router(beer_run_routes.router)
app.include_router(invite_routes.router)

# Ensure static directories exist
os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/audio", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


UPLOAD_ROOT = Path("static/uploads")
UPLOAD_PATH_ROOT = PurePosixPath("static/uploads")
UPLOAD_ALLOCATION_ATTEMPTS = 10
_FORM_FLOAT = TypeAdapter(float)
_PHOTO_ACTIONS = frozenset({"keep", "replace", "remove"})
_CANONICAL_UPLOAD_RE = re.compile(
    r"^static/uploads/beer_runs/([1-9][0-9]*)/"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jpg$"
)


@dataclass(frozen=True)
class _OwnedUpload:
    """A canonical image path and the one physical file this request owns."""

    image_path: str
    physical_path: Path


class UploadAllocationError(RuntimeError):
    """Raised when no exclusive upload destination can be allocated."""


@lru_cache()
def get_drink_config() -> Dict[str, Any]:
    try:
        with open("data/drinks.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"types": [], "quantities": []}

def parse_client_timestamp(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone().replace(tzinfo=None)

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now().astimezone().replace(tzinfo=None)

    return parsed.replace(tzinfo=None)

def save_optimized_image(contents: bytes, image_path: str | os.PathLike | BinaryIO) -> None:
    img = Image.open(io.BytesIO(contents))
    img = ImageOps.exif_transpose(img)

    # Convert to RGB (in case of RGBA/PNG)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if too large (max 1080px on longest side)
    max_size = 1080
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    # Save as optimized JPEG with the orientation baked into the pixels.
    img.save(image_path, "JPEG", quality=85, optimize=True)


def cleanup_owned_upload(upload: _OwnedUpload) -> None:
    """Remove only the exclusively allocated file represented by ``upload``."""

    upload.physical_path.unlink(missing_ok=True)


def _cleanup_owned_upload_safely(upload: _OwnedUpload) -> None:
    try:
        cleanup_owned_upload(upload)
    except Exception:
        # Cleanup must never replace the original sanitized request failure.
        pass


def write_upload_image(contents: bytes, beer_run_id: int) -> _OwnedUpload:
    """Normalize an image into a request-owned, run-scoped destination."""

    if isinstance(beer_run_id, bool) or not isinstance(beer_run_id, int) or beer_run_id <= 0:
        raise ValueError("beer_run_id must be a positive integer")

    run_directory = UPLOAD_ROOT / "beer_runs" / str(beer_run_id)
    run_directory.mkdir(parents=True, exist_ok=True)

    for _ in range(UPLOAD_ALLOCATION_ATTEMPTS):
        candidate_uuid = UUID(str(uuid4()))
        filename = f"{candidate_uuid}.jpg"
        physical_path = run_directory / filename
        image_path = str(
            UPLOAD_PATH_ROOT / "beer_runs" / str(beer_run_id) / filename
        )
        upload = _OwnedUpload(image_path=image_path, physical_path=physical_path)

        try:
            destination = physical_path.open("xb")
        except FileExistsError:
            continue

        try:
            with destination:
                save_optimized_image(contents, destination)
        except Exception:
            _cleanup_owned_upload_safely(upload)
            raise

        return upload

    raise UploadAllocationError("Unable to allocate an upload destination")


def normalize_image_path_for_response(image_path: str | None) -> str | None:
    """Return browser-facing separators without mutating the stored value."""

    return image_path.replace("\\", "/") if image_path is not None else None


def _prepare_entry_response(entry: models.Entry, username: str) -> dict[str, Any]:
    """Materialize the public entry response while the database state is usable."""

    return schemas.Entry(
        id=entry.id,
        username=username,
        drink_type=entry.drink_type,
        abv=entry.abv,
        quantity=entry.quantity,
        brand=entry.brand,
        latitude=entry.latitude,
        longitude=entry.longitude,
        image_path=normalize_image_path_for_response(entry.image_path),
        timestamp=entry.timestamp,
        timezone=entry.timezone,
        timezone_code=entry.timezone_code,
    ).model_dump(mode="json")


def _owned_entry_for_mutation(
    db: Session,
    *,
    entry_id: int,
    beer_run_id: int,
    user_id: int,
) -> tuple[models.Entry, str] | None:
    """Return one entry and username only when all mutation scopes match."""

    return (
        db.query(models.Entry, models.User.username)
        .join(models.User, models.User.id == models.Entry.user_id)
        .filter(
            models.Entry.id == entry_id,
            models.Entry.beer_run_id == beer_run_id,
            models.Entry.user_id == user_id,
        )
        .first()
    )


def _entry_not_found_error() -> HTTPException:
    return HTTPException(status_code=404, detail="Entry not found")


def _invalid_entry_update_error() -> HTTPException:
    return HTTPException(status_code=422, detail="Invalid entry update")


def _form_string(form, field_name: str, *, allow_clear: bool) -> str | None:
    value = form.get(field_name)
    if not isinstance(value, str):
        raise _invalid_entry_update_error()
    if value == "":
        if allow_clear:
            return None
        raise _invalid_entry_update_error()
    return value


def _form_float(form, field_name: str) -> float:
    value = form.get(field_name)
    if not isinstance(value, str) or value == "":
        raise _invalid_entry_update_error()
    try:
        return _FORM_FLOAT.validate_python(value)
    except ValidationError:
        raise _invalid_entry_update_error() from None


def _persisted_upload_target(
    image_path: str | None,
    beer_run_id: int,
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
        relative = PurePosixPath(image_path).relative_to(UPLOAD_PATH_ROOT)
        resolved_root = UPLOAD_ROOT.resolve(strict=False)
        candidate = UPLOAD_ROOT.joinpath(*relative.parts)
        resolved_target = candidate.resolve(strict=False)
        if not resolved_target.is_relative_to(resolved_root):
            return None
        if candidate.is_symlink() or not resolved_target.is_file():
            return None
    except (OSError, ValueError):
        return None
    return resolved_target


def _cleanup_persisted_upload(
    db: Session,
    image_path: str | None,
    beer_run_id: int,
) -> None:
    """Unlink one eligible old file only when no entry still references it."""

    target = _persisted_upload_target(image_path, beer_run_id)
    if target is None:
        return

    remaining_reference = (
        db.query(models.Entry.id)
        .filter(func.replace(models.Entry.image_path, "\\", "/") == image_path)
        .first()
    )
    if remaining_reference is not None:
        return
    target.unlink(missing_ok=True)


def _cleanup_persisted_upload_safely(
    db: Session,
    image_path: str | None,
    beer_run_id: int,
) -> None:
    try:
        _cleanup_persisted_upload(db, image_path, beer_run_id)
    except Exception:
        # A committed database mutation remains successful if cleanup cannot run.
        pass


@app.get("/")
async def root():
    return FileResponse("templates/index.html")

@app.get("/wrapped")
async def wrapped():
    return FileResponse("templates/wrapped.html")

@app.get("/api/config")
async def get_config():
    return get_drink_config()

@app.get("/api/wrapped")
async def get_wrapped():
    try:
        with open("data/wrapped.json", "r", encoding="utf-8") as f:
            return JSONResponse(json.load(f))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Wrapped data has not been generated yet")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"Wrapped data is invalid JSON: {exc}")

@app.get(
    "/api/beer-runs/{beer_run_id}/leaderboard",
    response_model=list[schemas.LeaderboardUser],
)
async def get_scoped_leaderboard(
    access: permissions.PublicReadAccess = Depends(permissions.authorize_public_read),
    db: Session = Depends(get_db),
):
    """Return the leaderboard for a single authorized beer-run.

    Only run members with at least one entry in this run appear, and totals
    include only entries assigned to the requested run. The aggregation runs as
    one run-scoped SQL query, so query count never grows with the number of
    entrants. Rows are ordered by total alcohol, highest first.
    """
    rows = (
        db.query(
            models.User.username,
            func.sum(models.Entry.quantity).label("total_liters"),
            func.sum(models.Entry.quantity * (models.Entry.abv / 100.0)).label("total_alcohol"),
        )
        .join(models.BeerRunMember, models.BeerRunMember.user_id == models.User.id)
        .join(models.Entry, models.Entry.user_id == models.User.id)
        .filter(
            models.BeerRunMember.beer_run_id == access.beer_run.id,
            models.Entry.beer_run_id == access.beer_run.id,
        )
        .group_by(models.User.id)
        .order_by(func.sum(models.Entry.quantity * (models.Entry.abv / 100.0)).desc())
        .all()
    )
    return [
        {
            "username": username,
            "total_liters": total_liters,
            "total_alcohol": total_alcohol,
        }
        for username, total_liters, total_alcohol in rows
    ]


@app.get(
    "/api/beer-runs/{beer_run_id}/entries",
    response_model=list[schemas.Entry],
)
async def get_scoped_entries(
    username: str = None,
    access: permissions.PublicReadAccess = Depends(permissions.authorize_public_read),
    db: Session = Depends(get_db),
):
    """Return the entries of a single authorized beer-run, newest first.

    The optional username filter is conjoined with the requested run scope
    using the existing case-insensitive username semantics. Entries with a
    NULL ``beer_run_id`` are excluded because the filter requires an exact run
    match.
    """
    query = db.query(models.Entry).filter(models.Entry.beer_run_id == access.beer_run.id)
    if username:
        query = query.join(models.User).filter(
            func.lower(models.User.username) == func.lower(username)
        )
    entries = query.order_by(models.Entry.timestamp.desc()).all()

    return [_prepare_entry_response(entry, entry.owner.username) for entry in entries]


@app.post("/api/beer-runs/{beer_run_id}/entries")
async def create_scoped_entry(
    drink_type: str = Form(...),
    abv: float = Form(...),
    quantity: float = Form(...),
    brand: str = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    client_timestamp: str = Form(None),
    client_timezone: str = Form(None),
    client_timezone_code: str = Form(None),
    image: UploadFile = File(None),
    access: permissions.MemberAccess = Depends(permissions.authorize_member_access),
    db: Session = Depends(get_db),
):
    """Create an entry in a single authorized beer-run (member-only).

    Membership authorization completes before any upload is written or row is
    created. The entry is bound to the authenticated user and the authorized
    path run; caller-supplied ``user_id``/``username``/``beer_run_id`` form
    fields are not part of the multipart contract and have no effect. Commit is
    the final fallible boundary.
    """
    image_path = None
    owned_upload = None
    if image and image.filename and image.filename.strip():
        try:
            contents = await image.read()
            if contents:
                owned_upload = write_upload_image(contents, access.beer_run.id)
                image_path = owned_upload.image_path
        except Exception:
            raise HTTPException(status_code=500, detail="Unable to create entry")

    try:
        new_entry = models.Entry(
            drink_type=drink_type,
            abv=abv,
            quantity=quantity,
            brand=brand,
            latitude=latitude,
            longitude=longitude,
            image_path=image_path,
            timestamp=parse_client_timestamp(client_timestamp),
            timezone=client_timezone,
            timezone_code=client_timezone_code,
            user_id=access.membership.user_id,
            beer_run_id=access.beer_run.id,
        )
        db.add(new_entry)
        db.flush()  # assign the entry id before the final commit boundary
        entry_id = new_entry.id
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        if owned_upload is not None:
            _cleanup_owned_upload_safely(owned_upload)
        raise HTTPException(status_code=500, detail="Unable to create entry")

    return {"status": "success", "entry_id": entry_id}


@app.patch(
    "/api/beer-runs/{beer_run_id}/entries/{entry_id}",
    response_model=schemas.Entry,
)
async def update_scoped_entry(
    request: Request,
    entry_id: int,
    access: permissions.MemberAccess = Depends(permissions.authorize_member_access),
    db: Session = Depends(get_db),
):
    """Partially update one entry owned by the authenticated run member."""

    authorized_run_id = access.beer_run.id
    authorized_user_id = access.membership.user_id
    owned_row = _owned_entry_for_mutation(
        db,
        entry_id=entry_id,
        beer_run_id=authorized_run_id,
        user_id=authorized_user_id,
    )
    if owned_row is None:
        raise _entry_not_found_error()
    entry, username = owned_row

    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("multipart/form-data"):
        raise _invalid_entry_update_error()
    try:
        form = await request.form()
    except Exception:
        raise _invalid_entry_update_error() from None

    scalar_updates: dict[str, Any] = {}
    if "drink_type" in form:
        scalar_updates["drink_type"] = _form_string(
            form, "drink_type", allow_clear=False
        )
    if "abv" in form:
        scalar_updates["abv"] = _form_float(form, "abv")
    if "quantity" in form:
        scalar_updates["quantity"] = _form_float(form, "quantity")
    if "brand" in form:
        scalar_updates["brand"] = _form_string(form, "brand", allow_clear=True)

    latitude_present = "latitude" in form
    longitude_present = "longitude" in form
    if latitude_present != longitude_present:
        raise _invalid_entry_update_error()
    if latitude_present:
        scalar_updates["latitude"] = _form_float(form, "latitude")
        scalar_updates["longitude"] = _form_float(form, "longitude")

    if "client_timezone" in form:
        scalar_updates["timezone"] = _form_string(
            form, "client_timezone", allow_clear=True
        )
    if "client_timezone_code" in form:
        scalar_updates["timezone_code"] = _form_string(
            form, "client_timezone_code", allow_clear=True
        )

    if "photo_action" in form:
        raw_photo_action = form.get("photo_action")
        if not isinstance(raw_photo_action, str) or raw_photo_action not in _PHOTO_ACTIONS:
            raise _invalid_entry_update_error()
        photo_action = raw_photo_action
    else:
        photo_action = "keep"

    raw_image = form.get("image")
    if raw_image is not None and not isinstance(raw_image, StarletteUploadFile):
        raise _invalid_entry_update_error()

    image_contents: bytes | None = None
    if (
        isinstance(raw_image, StarletteUploadFile)
        and raw_image.filename
        and raw_image.filename.strip()
    ):
        try:
            contents = await raw_image.read()
        except Exception:
            raise HTTPException(status_code=500, detail="Unable to update entry") from None
        if contents:
            image_contents = contents

    if photo_action == "replace" and image_contents is None:
        raise _invalid_entry_update_error()
    if photo_action in {"keep", "remove"} and image_contents is not None:
        raise _invalid_entry_update_error()

    photo_changes = photo_action == "replace" or (
        photo_action == "remove" and entry.image_path is not None
    )
    if not scalar_updates and not photo_changes:
        raise _invalid_entry_update_error()

    old_image_path = entry.image_path
    owned_upload = None
    if photo_action == "replace":
        try:
            owned_upload = write_upload_image(image_contents, authorized_run_id)
        except Exception:
            raise HTTPException(status_code=500, detail="Unable to update entry") from None

    try:
        for field_name, value in scalar_updates.items():
            setattr(entry, field_name, value)
        if photo_action == "replace":
            entry.image_path = owned_upload.image_path
        elif photo_action == "remove":
            entry.image_path = None

        db.flush()
        response = _prepare_entry_response(entry, username)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        if owned_upload is not None:
            _cleanup_owned_upload_safely(owned_upload)
        raise HTTPException(status_code=500, detail="Unable to update entry") from None

    if photo_action in {"replace", "remove"}:
        _cleanup_persisted_upload_safely(
            db,
            old_image_path,
            authorized_run_id,
        )
    return response


@app.delete("/api/beer-runs/{beer_run_id}/entries/{entry_id}")
async def delete_scoped_entry(
    entry_id: int,
    access: permissions.MemberAccess = Depends(permissions.authorize_member_access),
    db: Session = Depends(get_db),
):
    """Delete one entry owned by the authenticated run member."""

    authorized_run_id = access.beer_run.id
    authorized_user_id = access.membership.user_id
    owned_row = _owned_entry_for_mutation(
        db,
        entry_id=entry_id,
        beer_run_id=authorized_run_id,
        user_id=authorized_user_id,
    )
    if owned_row is None:
        raise _entry_not_found_error()
    entry, _username = owned_row

    deleted_entry_id = entry.id
    old_image_path = entry.image_path
    response = {"status": "deleted", "entry_id": deleted_entry_id}
    try:
        db.delete(entry)
        db.flush()
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Unable to delete entry") from None

    _cleanup_persisted_upload_safely(db, old_image_path, authorized_run_id)
    return response
