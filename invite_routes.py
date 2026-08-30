"""Invite routes — owner create-or-retrieve, public preview, authenticated accept.

Registered on the app in main.py via app.include_router(router). Follows the
same APIRouter pattern as auth_routes.py and beer_run_routes.py. Shared
beer-run authorization stays in permissions.py, JWT identity in auth.py,
persistent entities in models.py, and public data shapes in schemas.py
(AR-2.1).
"""

from __future__ import annotations

import re
import secrets
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import models
import permissions
import schemas
from database import get_db

router = APIRouter()

# Invite codes are exactly 43 unpadded URL-safe characters from [A-Za-z0-9_-].
INVITE_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
# 32 bytes = 256 bits of cryptographically secure randomness (FR-1.2).
INVITE_CODE_BYTES = 32
MAX_CODE_GENERATION_ATTEMPTS = 3


def _generate_code() -> str:
    """Return a fresh 43-character URL-safe invite code.

    ``secrets.token_urlsafe(32)`` draws 256 bits from the operating-system
    randomness source and encodes them as exactly 43 unpadded base64url
    characters from ``[A-Za-z0-9_-]``. Codes are never derived from run IDs,
    names, timestamps, usernames, passwords, JWTs, or the global signup code.
    """
    return secrets.token_urlsafe(INVITE_CODE_BYTES)


def _invite_not_found() -> HTTPException:
    """Uniform 404 for every invalid invite state (FR-2.5, FR-3.5)."""
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Invite not found",
    )


def _is_valid_code(code: str) -> bool:
    """Return True only for an exact 43-character URL-safe code."""
    return bool(INVITE_CODE_PATTERN.fullmatch(code))


def _find_invite_for_run(db: Session, beer_run_id: int) -> models.BeerRunInvite | None:
    return (
        db.query(models.BeerRunInvite)
        .filter(models.BeerRunInvite.beer_run_id == beer_run_id)
        .first()
    )


def _find_invite_by_code(db: Session, code: str) -> models.BeerRunInvite | None:
    # Codes are case-sensitive: the code column uses the default BINARY
    # collation, so an exact-equality lookup never matches a case variant.
    return (
        db.query(models.BeerRunInvite)
        .filter(models.BeerRunInvite.code == code)
        .first()
    )


def _find_membership(
    db: Session,
    beer_run_id: int,
    user_id: int,
) -> models.BeerRunMember | None:
    return (
        db.query(models.BeerRunMember)
        .filter(
            models.BeerRunMember.beer_run_id == beer_run_id,
            models.BeerRunMember.user_id == user_id,
        )
        .first()
    )


def _is_code_unique_violation(exc: IntegrityError) -> bool:
    return (
        isinstance(exc.orig, sqlite3.IntegrityError)
        and "beer_run_invites.code" in str(exc.orig)
    )


def _is_run_invite_unique_violation(exc: IntegrityError) -> bool:
    return (
        isinstance(exc.orig, sqlite3.IntegrityError)
        and "beer_run_invites.beer_run_id" in str(exc.orig)
    )


def _invite_create_response(
    beer_run: models.BeerRun,
    invite: models.BeerRunInvite,
) -> schemas.InviteCreateResponse:
    """Build the owner-only create-or-retrieve response (FR-2.2, FR-2.3).

    ``beer_run_name`` is resolved from the run's current name so a rename
    updates only that field and never the code, link, invite ID, or creation
    timestamp. ``invite_url`` stays origin-independent and root-relative —
    never derived from the request host, forwarded headers, or a configured
    public base URL.
    """
    return schemas.InviteCreateResponse(
        code=invite.code,
        invite_url=f"/?invite={quote(invite.code, safe='')}",
        beer_run_id=beer_run.id,
        beer_run_name=beer_run.name,
        created_at=invite.created_at,
    )


def _beer_run_response(
    db: Session,
    beer_run: models.BeerRun,
    membership: models.BeerRunMember | None,
) -> schemas.BeerRunResponse:
    """Build a BeerRunResponse from fresh committed data (AR-3.3).

    ``member_count`` is counted directly from the database so the response
    reflects the committed membership set rather than a possibly stale
    in-session relationship collection. ``membership`` carries the caller's
    preserved actual role.
    """
    member_count = (
        db.query(models.BeerRunMember)
        .filter(models.BeerRunMember.beer_run_id == beer_run.id)
        .count()
    )
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


# ── Owner create-or-retrieve (Feature 2) ─────────────────────────────

@router.post(
    "/api/beer-runs/{beer_run_id}/invites",
    response_model=schemas.InviteCreateResponse,
)
async def create_or_get_invite(
    beer_run_id: int,
    response: Response,
    access: permissions.OwnerAccess = Depends(permissions.authorize_owner_access),
    db: Session = Depends(get_db),
):
    """Create or retrieve the run's single permanent invite.  Owner-only.

    The first successful request creates exactly one invite and returns
    ``201 Created``; every later request returns the same persisted
    code/link/ID/timestamp unchanged with ``200 OK`` (FR-2.1, FR-2.3). The
    endpoint accepts no request body and uses the shared owner policy
    (AR-2.2).

    The DB unique indexes on ``beer_run_id`` and ``code`` are the concurrency
    backstops (AR-1.3): a code collision with another run rolls back and
    retries with a fresh code; a lost concurrent first-create for this run
    rolls back, re-reads the winner's invite, and returns it as a normal
    idempotent success.
    """
    beer_run = access.beer_run

    existing = _find_invite_for_run(db, beer_run.id)
    if existing is not None:
        return _invite_create_response(beer_run, existing)

    for _ in range(MAX_CODE_GENERATION_ATTEMPTS):
        invite = models.BeerRunInvite(beer_run_id=beer_run.id, code=_generate_code())
        db.add(invite)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if _is_code_unique_violation(exc):
                continue  # cross-run code collision — retry with a fresh code
            if _is_run_invite_unique_violation(exc):
                break  # lost a concurrent first-create — re-read the winner
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create invite",
            ) from None
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create invite",
            ) from None

        db.refresh(invite)
        response.status_code = status.HTTP_201_CREATED
        return _invite_create_response(beer_run, invite)

    # Exhausted code collisions or lost a concurrent first-create: re-read the
    # winner's invite and return it; if this run genuinely has no invite yet,
    # creation has failed and no partial invite may remain (AR-1.3).
    winner = _find_invite_for_run(db, beer_run.id)
    if winner is not None:
        return _invite_create_response(beer_run, winner)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unable to create invite",
    ) from None


# ── Public preview (Feature 2) ───────────────────────────────────────

@router.get(
    "/api/invites/{code}",
    response_model=schemas.InvitePreviewResponse,
)
async def preview_invite(code: str, db: Session = Depends(get_db)):
    """Publicly preview the target run of a valid invite code (FR-2.4).

    Publicly accessible with no authentication, including for private runs and
    logged-out or non-member callers. Returns only the run's id and current
    name (resolved at request time so a rename is reflected), with no
    visibility, ownership, membership, or entry data. Malformed, unknown,
    case-changed, and orphaned codes all return the same ``404 Invite not
    found`` (FR-2.5).
    """
    if not _is_valid_code(code):
        raise _invite_not_found()
    invite = _find_invite_by_code(db, code)
    if invite is None:
        raise _invite_not_found()
    beer_run = db.get(models.BeerRun, invite.beer_run_id)
    if beer_run is None:
        raise _invite_not_found()
    return schemas.InvitePreviewResponse(
        beer_run_id=beer_run.id,
        beer_run_name=beer_run.name,
    )


# ── Authenticated acceptance (Feature 3) ─────────────────────────────

@router.post(
    "/api/invites/{code}/accept",
    response_model=schemas.BeerRunResponse,
)
async def accept_invite(
    code: str,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Accept an invite and join its run as a ``member`` (Feature 3).

    Authentication is resolved before the code's validity is revealed: missing
    or invalid credentials return the shared ``401`` for both valid and invalid
    codes (FR-3.1). The endpoint uses ``auth.get_current_user`` directly rather
    than the member/public policies because the caller intentionally may not be
    a member yet (AR-3.1).

    Acceptance is idempotent and role-preserving (FR-3.3): an existing
    membership is returned unchanged, and the ``(beer_run_id, user_id)`` unique
    constraint is the authoritative guard against concurrent duplicate inserts
    (AR-3.2). The response is built from fresh committed membership data
    (AR-3.3).
    """
    if current_user is None:
        raise permissions.unauthorized_error()

    if not _is_valid_code(code):
        raise _invite_not_found()
    invite = _find_invite_by_code(db, code)
    if invite is None:
        raise _invite_not_found()
    beer_run = db.get(models.BeerRun, invite.beer_run_id)
    if beer_run is None:
        raise _invite_not_found()

    existing = _find_membership(db, beer_run.id, current_user.id)
    if existing is not None:
        return _beer_run_response(db, beer_run, existing)

    membership = models.BeerRunMember(
        beer_run_id=beer_run.id,
        user_id=current_user.id,
        role="member",
    )
    db.add(membership)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Lost a concurrent duplicate-membership race — re-read the committed
        # membership and preserve its role (AR-3.2).
        winner = _find_membership(db, beer_run.id, current_user.id)
        if winner is not None:
            return _beer_run_response(db, beer_run, winner)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to accept invite",
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to accept invite",
        ) from None

    db.refresh(membership)
    return _beer_run_response(db, beer_run, membership)
