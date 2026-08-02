"""Beer-run CRUD routes — create, list, detail, update, delete.

Registered on the app in main.py via app.include_router(router).
Follows the same APIRouter pattern as auth_routes.py.
"""

from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

router = APIRouter()

# --- Name validation ---

# 3-64 chars, ASCII letters/digits, spaces, underscores, hyphens.
# We use fullmatch so the entire string must match (no leading/trailing
# whitespace sneaking past a partial match — the route still trims, but
# this is belt-and-suspenders).
BEER_RUN_NAME_PATTERN = re.compile(r"[A-Za-z0-9 _-]{3,64}\Z")

# --- IntegrityError helper (patterned after auth_routes._is_username_unique_violation) ---

def _is_beer_run_name_unique_violation(exc: IntegrityError) -> bool:
    """Return True when the IntegrityError is a beer-run name duplicate.

    After the NOCASE migration the constraint name is
    'uq_beer_runs_name_nocase', but SQLite's IntegrityError string sometimes
    references the column rather than the index, so we match on either.
    """
    if not isinstance(exc.orig, sqlite3.IntegrityError):
        return False
    message = str(exc.orig)
    return (
        "beer_runs.name" in message
        or "uq_beer_runs_name_nocase" in message
    )

# --- Response builder ---

def _beer_run_response(beer_run: models.BeerRun, user: models.User | None) -> schemas.BeerRunResponse:
    """Build a BeerRunResponse with computed member_count and caller role."""
    member_count = len(beer_run.memberships)
    if user is None:
        role: str | None = None
    else:
        role = next(
            (m.role for m in beer_run.memberships if m.user_id == user.id),
            None,
        )
    return schemas.BeerRunResponse(
        id=beer_run.id,
        name=beer_run.name,
        is_public=beer_run.is_public,
        created_at=beer_run.created_at,
        member_count=member_count,
        current_user_role=role,
    )

# --- Visibility helper ---

def _visible_runs_query(db: Session, user: models.User | None):
    """Return a SQLAlchemy query for all beer-runs visible to *user*.

    Visibility rules:
      - Everyone sees public runs.
      - Authenticated users additionally see private runs they are a member of.
    """
    if user is None:
        return (
            db.query(models.BeerRun)
            .filter(models.BeerRun.is_public == True)  # noqa: E712
            .order_by(models.BeerRun.created_at.desc())
        )
    # Subquery: IDs of runs the user is a member of.
    member_run_ids = (
        db.query(models.BeerRunMember.beer_run_id)
        .filter(models.BeerRunMember.user_id == user.id)
        .subquery()
    )
    return (
        db.query(models.BeerRun)
        .outerjoin(
            member_run_ids,
            models.BeerRun.id == member_run_ids.c.beer_run_id,
        )
        .filter(
            (models.BeerRun.is_public == True)  # noqa: E712
            | (member_run_ids.c.beer_run_id.isnot(None))
        )
        .order_by(models.BeerRun.created_at.desc())
    )

# --- Routes ---

# ── Create (Feature 2) ──────────────────────────────────────────────

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@router.post(
    "/api/beer-runs",
    response_model=schemas.BeerRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_beer_run(
    request: schemas.BeerRunCreateRequest,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new beer-run with the authenticated user as owner."""
    if current_user is None:
        raise _UNAUTHORIZED

    # Validate name.
    name = request.name.strip()
    if not BEER_RUN_NAME_PATTERN.fullmatch(name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Beer-run name must be 3-64 characters using only ASCII letters, "
                "numbers, spaces, underscores, or hyphens"
            ),
        )

    # Race-condition-safe duplicate check: pre-check then rely on the DB
    # unique constraint as a hard backstop for concurrent requests.
    try:
        existing = (
            db.query(models.BeerRun)
            .filter(models.BeerRun.name.collate("NOCASE") == name)
            .first()
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create beer-run",
        ) from None

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A beer-run with this name already exists",
        )

    try:
        beer_run = models.BeerRun(name=name, is_public=request.is_public)
        db.add(beer_run)
        db.flush()  # get the generated id

        membership = models.BeerRunMember(
            beer_run_id=beer_run.id,
            user_id=current_user.id,
            role="owner",
        )
        db.add(membership)
        db.commit()
        db.refresh(beer_run)
    except IntegrityError as exc:
        db.rollback()
        if _is_beer_run_name_unique_violation(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A beer-run with this name already exists",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create beer-run",
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create beer-run",
        ) from None

    return _beer_run_response(beer_run, current_user)


# ── List (Feature 3) ─────────────────────────────────────────────────

@router.get(
    "/api/beer-runs",
    response_model=list[schemas.BeerRunResponse],
)
async def list_beer_runs(
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return every beer-run visible to the caller.

    Authenticated callers see their own private runs plus all public runs.
    Logged-out callers see only public runs.
    """
    runs = _visible_runs_query(db, current_user).all()
    return [_beer_run_response(r, current_user) for r in runs]


# ── Detail (Feature 3) ───────────────────────────────────────────────

@router.get(
    "/api/beer-runs/{beer_run_id}",
    response_model=schemas.BeerRunResponse,
)
async def get_beer_run(
    beer_run_id: int,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return a single beer-run if visible to the caller.

    Private runs return 404 for non-members (indistinguishable from
    non-existent — no information leak).
    """
    beer_run = db.get(models.BeerRun, beer_run_id)
    if beer_run is None:
        raise HTTPException(status_code=404, detail="Beer-run not found")

    if not beer_run.is_public and (
        current_user is None
        or not any(
            m.user_id == current_user.id for m in beer_run.memberships
        )
    ):
        raise HTTPException(status_code=404, detail="Beer-run not found")

    return _beer_run_response(beer_run, current_user)


# ── Update (Feature 4) ───────────────────────────────────────────────

@router.patch(
    "/api/beer-runs/{beer_run_id}",
    response_model=schemas.BeerRunResponse,
)
async def update_beer_run(
    beer_run_id: int,
    request: schemas.BeerRunUpdateRequest,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Update a beer-run's name and/or visibility.  Owner-only."""
    if current_user is None:
        raise _UNAUTHORIZED

    beer_run = db.get(models.BeerRun, beer_run_id)
    if beer_run is None:
        raise HTTPException(status_code=404, detail="Beer-run not found")

    # Ownership check.
    if not any(
        m.user_id == current_user.id and m.role == "owner"
        for m in beer_run.memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the beer-run owner can update it",
        )

    # At-least-one-field check.
    if request.name is None and request.is_public is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one of 'name' or 'is_public' must be provided",
        )

    # Name update.
    if request.name is not None:
        new_name = request.name.strip()
        if not BEER_RUN_NAME_PATTERN.fullmatch(new_name):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Beer-run name must be 3-64 characters using only ASCII "
                    "letters, numbers, spaces, underscores, or hyphens"
                ),
            )
        # Only check for conflicts if the name is actually changing
        # (case-insensitively).
        if new_name != beer_run.name:
            try:
                colliding = (
                    db.query(models.BeerRun)
                    .filter(models.BeerRun.name.collate("NOCASE") == new_name)
                    .first()
                )
            except Exception:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Unable to update beer-run",
                ) from None

            if colliding is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A beer-run with this name already exists",
                )
            beer_run.name = new_name

    # Visibility update.
    if request.is_public is not None:
        beer_run.is_public = request.is_public

    try:
        db.commit()
        db.refresh(beer_run)
    except IntegrityError as exc:
        db.rollback()
        if _is_beer_run_name_unique_violation(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A beer-run with this name already exists",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update beer-run",
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update beer-run",
        ) from None

    return _beer_run_response(beer_run, current_user)


# ── Delete (Feature 5) ───────────────────────────────────────────────

@router.delete("/api/beer-runs/{beer_run_id}")
async def delete_beer_run(
    beer_run_id: int,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a beer-run and all its entries + memberships.  Owner-only."""
    if current_user is None:
        raise _UNAUTHORIZED

    beer_run = db.get(models.BeerRun, beer_run_id)
    if beer_run is None:
        raise HTTPException(status_code=404, detail="Beer-run not found")

    # Ownership check.
    if not any(
        m.user_id == current_user.id and m.role == "owner"
        for m in beer_run.memberships
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the beer-run owner can delete it",
        )

    try:
        # Cascade delete in explicit order: entries first,
        # then memberships, then the run itself — all in one transaction.
        beer_run_id_val = beer_run.id
        db.query(models.Entry).filter(
            models.Entry.beer_run_id == beer_run_id_val
        ).delete(synchronize_session="fetch")
        db.query(models.BeerRunMember).filter(
            models.BeerRunMember.beer_run_id == beer_run_id_val
        ).delete(synchronize_session="fetch")
        db.delete(beer_run)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete beer-run",
        ) from None

    return {"status": "deleted", "beer_run_id": beer_run_id_val}
