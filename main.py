import os
import io
import json
from dataclasses import dataclass
from functools import lru_cache
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Dict
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from PIL import Image, ImageOps

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

    return [{
        "id": e.id,
        "username": e.owner.username,
        "drink_type": e.drink_type,
        "abv": e.abv,
        "quantity": e.quantity,
        "brand": e.brand,
        "latitude": e.latitude,
        "longitude": e.longitude,
        "image_path": normalize_image_path_for_response(e.image_path),
        "timestamp": e.timestamp.isoformat(),
        "timezone": e.timezone,
        "timezone_code": e.timezone_code
    } for e in entries]


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
