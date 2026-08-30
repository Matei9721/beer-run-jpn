"""Beer-run CRUD routes — create, list, detail, update, delete.

Registered on the app in main.py via app.include_router(router).
Follows the same APIRouter pattern as auth_routes.py.
"""

from __future__ import annotations

import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import models
import permissions
import schemas
from database import get_db
from upload_cleanup import cleanup_run_uploads, collect_run_uploads

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

def _beer_run_response(
    beer_run: models.BeerRun,
    membership: models.BeerRunMember | None,
) -> schemas.BeerRunResponse:
    """Build a BeerRunResponse with computed member_count and caller role.

    ``membership`` is the caller's membership in ``beer_run``, or None when the
    caller is logged out or not a member. The caller role is read from that
    membership rather than re-derived by scanning the run's memberships, so
    authorization and response construction agree on one trusted source.
    """
    member_count = len(beer_run.memberships)
    role = membership.role if membership is not None else None
    return schemas.BeerRunResponse(
        id=beer_run.id,
        name=beer_run.name,
        is_public=beer_run.is_public,
        has_wrapped=beer_run.has_wrapped,
        created_at=beer_run.created_at,
        member_count=member_count,
        current_user_role=role,
    )


def _caller_membership(
    beer_run: models.BeerRun,
    user: models.User | None,
) -> models.BeerRunMember | None:
    """Return the caller's membership in a run, or None when not a member."""
    if user is None:
        return None
    return next(
        (m for m in beer_run.memberships if m.user_id == user.id),
        None,
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


def _selector_query_error() -> HTTPException:
    """Return the shared sanitized validation error for selector query modes."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Invalid beer-run selector query",
    )


def _escape_like_prefix(value: str) -> str:
    """Escape SQLite LIKE metacharacters for a literal prefix comparison."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _selector_runs_query(db: Session, user: models.User | None):
    """Return beer-run rows with bounded member metadata for selector modes."""
    member_count = (
        db.query(func.count(models.BeerRunMember.id))
        .filter(models.BeerRunMember.beer_run_id == models.BeerRun.id)
        .correlate(models.BeerRun)
        .scalar_subquery()
    )
    if user is None:
        caller_role = literal(None)
    else:
        caller_role = (
            db.query(models.BeerRunMember.role)
            .filter(
                models.BeerRunMember.beer_run_id == models.BeerRun.id,
                models.BeerRunMember.user_id == user.id,
            )
            .correlate(models.BeerRun)
            .scalar_subquery()
        )
    return db.query(
        models.BeerRun,
        member_count.label("member_count"),
        caller_role.label("current_user_role"),
    )


def _selector_response(row) -> schemas.BeerRunResponse:
    """Build a list response from the selector query's projected metadata."""
    beer_run, member_count, current_user_role = row
    return schemas.BeerRunResponse(
        id=beer_run.id,
        name=beer_run.name,
        is_public=beer_run.is_public,
        has_wrapped=beer_run.has_wrapped,
        created_at=beer_run.created_at,
        member_count=member_count,
        current_user_role=current_user_role,
    )

# --- Routes ---

# ── Create (Feature 2) ──────────────────────────────────────────────

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
        raise permissions.unauthorized_error()

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

    return _beer_run_response(beer_run, membership)


# ── List (Feature 3) ─────────────────────────────────────────────────

@router.get(
    "/api/beer-runs",
    response_model=list[schemas.BeerRunResponse],
)
async def list_beer_runs(
    view: str | None = None,
    name: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Return every beer-run visible to the caller.

    Authenticated callers see their own private runs plus all public runs.
    Logged-out callers see only public runs.
    """
    if view is None and name is None and q is None and limit is None:
        runs = _visible_runs_query(db, current_user).all()
        return [_beer_run_response(r, _caller_membership(r, current_user)) for r in runs]

    if view not in {"mine", "public"}:
        raise _selector_query_error()
    if view == "mine":
        if name is not None or q is not None or limit is not None:
            raise _selector_query_error()
        if current_user is None:
            raise permissions.unauthorized_error()
        rows = (
            _selector_runs_query(db, current_user)
            .filter(
                models.BeerRunMember.user_id == current_user.id,
                models.BeerRunMember.beer_run_id == models.BeerRun.id,
            )
            .order_by(models.BeerRun.name.collate("NOCASE"), models.BeerRun.id)
            .all()
        )
        return [_selector_response(row) for row in rows]

    if (name is None) == (q is None):
        raise _selector_query_error()
    if name is not None:
        if limit is not None:
            raise _selector_query_error()
        exact_name = name.strip()
        if not BEER_RUN_NAME_PATTERN.fullmatch(exact_name):
            raise _selector_query_error()
        rows = (
            _selector_runs_query(db, current_user)
            .filter(
                models.BeerRun.is_public == True,  # noqa: E712
                models.BeerRun.name.collate("NOCASE") == exact_name,
            )
            .all()
        )
        return [_selector_response(row) for row in rows]

    search_query = q.strip()
    if not 2 <= len(search_query) <= 64:
        raise _selector_query_error()
    if limit is None:
        limit = 20
    if not 1 <= limit <= 20:
        raise _selector_query_error()
    rows = (
        _selector_runs_query(db, current_user)
        .filter(
            models.BeerRun.is_public == True,  # noqa: E712
            models.BeerRun.name.collate("NOCASE").like(
                f"{_escape_like_prefix(search_query)}%",
                escape="\\",
            ),
        )
        .order_by(models.BeerRun.name.collate("NOCASE"), models.BeerRun.id)
        .limit(limit)
        .all()
    )
    return [_selector_response(row) for row in rows]


# ── Detail (Feature 3) ───────────────────────────────────────────────

@router.get(
    "/api/beer-runs/{beer_run_id}",
    response_model=schemas.BeerRunResponse,
)
async def get_beer_run(
    access: permissions.PublicReadAccess = Depends(permissions.authorize_public_read),
):
    """Return a single beer-run if visible to the caller.

    Authorization is delegated to the shared public-read policy: public runs are
    readable by any caller, and private runs return the shared 404 for
    non-members, indistinguishable from non-existent runs.
    """
    return _beer_run_response(access.beer_run, access.membership)


@router.get(
    "/api/beer-runs/{beer_run_id}/members",
    response_model=list[schemas.BeerRunMemberResponse],
)
async def list_beer_run_members(
    access: permissions.PublicReadAccess = Depends(permissions.authorize_public_read),
    db: Session = Depends(get_db),
):
    """Return the roster when the caller can read the beer-run.

    Public runs expose their roster to the same callers who can read the run;
    private runs remain limited to members by the shared public-read policy.
    """
    rows = (
        db.query(models.BeerRunMember, models.User)
        .join(models.User, models.User.id == models.BeerRunMember.user_id)
        .filter(models.BeerRunMember.beer_run_id == access.beer_run.id)
        .order_by(models.User.username.collate("NOCASE"), models.User.id)
        .all()
    )
    return [
        schemas.BeerRunMemberResponse(
            user_id=member.user_id,
            username=user.username,
            role=member.role,
        )
        for member, user in rows
    ]


# ── Leave (Release 2) ───────────────────────────────────────────────

@router.delete("/api/beer-runs/{beer_run_id}/members/me")
async def leave_beer_run(
    access: permissions.MemberAccess = Depends(permissions.authorize_member_access),
    db: Session = Depends(get_db),
):
    """Remove the caller's regular membership without changing run history.

    Owners must resolve ownership before leaving. The conditional delete also
    re-checks the role at mutation time so a stale request cannot remove a
    membership that was promoted to owner after authorization completed.
    """
    if access.membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Owners must transfer ownership or delete the beer-run before leaving.",
        )

    beer_run_id_val = access.beer_run.id
    try:
        deleted = (
            db.query(models.BeerRunMember)
            .filter(
                models.BeerRunMember.id == access.membership.id,
                models.BeerRunMember.beer_run_id == beer_run_id_val,
                models.BeerRunMember.user_id == access.membership.user_id,
                models.BeerRunMember.role == "member",
            )
            .delete(synchronize_session=False)
        )
        if deleted != 1:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This membership changed. Refresh the run before trying again.",
            )
        db.commit()
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to leave beer-run",
        ) from None

    return {"status": "left", "beer_run_id": beer_run_id_val}


# ── Update (Feature 4) ───────────────────────────────────────────────

@router.patch(
    "/api/beer-runs/{beer_run_id}",
    response_model=schemas.BeerRunResponse,
)
async def update_beer_run(
    request: schemas.BeerRunUpdateRequest,
    access: permissions.OwnerAccess = Depends(permissions.authorize_owner_access),
    db: Session = Depends(get_db),
):
    """Update a beer-run's name and/or visibility.  Owner-only.

    Authorization is delegated to the shared owner policy, which returns the
    already-authorized run and membership. Validation, duplicate-name handling,
    and transaction behavior are unchanged.
    """
    beer_run = access.beer_run

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

    return _beer_run_response(beer_run, access.membership)


# ── Delete (Feature 5) ───────────────────────────────────────────────

@router.delete(
    "/api/beer-runs/{beer_run_id}",
    response_model=schemas.BeerRunDeleteResponse,
)
async def delete_beer_run(
    access: permissions.OwnerAccess = Depends(permissions.authorize_owner_access),
    db: Session = Depends(get_db),
):
    """Delete a beer-run and all its entries + memberships. Owner-only.

    Authorization is delegated to the shared owner policy, which returns the
    already-authorized run. Files are removed only after the database commit so a
    failed transaction cannot leave a live entry pointing at a deleted photo.
    """
    beer_run = access.beer_run
    beer_run_id_val = beer_run.id

    if beer_run.is_public and beer_run.name.casefold() == "beerrunjpn".casefold():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The canonical BeerRunJPN run cannot be deleted",
        )

    # Importing the application module here avoids the existing route-registration
    # cycle while keeping test and operator upload-root overrides authoritative.
    import main as app_module

    try:
        owned_uploads = collect_run_uploads(
            db,
            beer_run_id_val,
            upload_root=app_module.UPLOAD_ROOT,
            upload_path_root=app_module.UPLOAD_PATH_ROOT,
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete beer-run",
        ) from None

    try:
        # Cascade delete in explicit order: invites and entries first,
        # then memberships, then the run itself — all in one transaction.
        db.query(models.BeerRunInvite).filter(
            models.BeerRunInvite.beer_run_id == beer_run_id_val
        ).delete(synchronize_session="fetch")
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

    try:
        cleanup_run_uploads(
            db,
            beer_run_id_val,
            owned_uploads,
            upload_root=app_module.UPLOAD_ROOT,
            upload_path_root=app_module.UPLOAD_PATH_ROOT,
        )
    except Exception:
        # The database commit succeeded; cleanup failure must not turn that
        # success into a misleading error or expose a broken live reference.
        pass

    return {"status": "deleted", "beer_run_id": beer_run_id_val}
