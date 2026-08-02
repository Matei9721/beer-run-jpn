"""Beer-run access policies — the single shared source of authorization.

The three dependencies here own every run-scoped access decision:

  * ``authorize_public_read`` — any caller may read a run whose persisted
    ``is_public`` is ``true``; a private run is readable only by an
    authenticated member (owner or member role). The result carries the
    caller's membership when one exists and ``None`` otherwise.
  * ``authorize_member_access`` — requires a valid authenticated user who is a
    member of the run. ``is_public`` never bypasses membership.
  * ``authorize_owner_access`` — requires a valid authenticated user whose
    membership role is ``"owner"``.

JWT decoding, bearer-token parsing, and current-user lookup stay in
``auth.py``. This module composes ``auth.get_current_user`` and
``database.get_db`` and only combines the resolved user with direct
SQLAlchemy reads of the target ``BeerRun`` and the caller's matching
``BeerRunMember``. No authorization decision is based on the mutable run name.
"""

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import auth
import models
from database import get_db

# --- Shared authorization errors ---
#
# Constructed through shared factories so every consuming route returns the
# exact same response for a policy failure while each request receives a fresh
# exception object and traceback.

def unauthorized_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Beer-run owner access required",
    )


def not_found_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Beer-run not found",
    )


# --- Typed access results ---

@dataclass(frozen=True)
class PublicReadAccess:
    """Result of the public-read policy.

    ``membership`` is the caller's membership in ``beer_run`` when one exists
    and ``None`` for a logged-out caller or an authenticated non-member reading
    a public run. Endpoints must not fabricate a role from its absence.
    """
    beer_run: models.BeerRun
    membership: models.BeerRunMember | None


@dataclass(frozen=True)
class MemberAccess:
    """Result of the member-only policy; membership is always present."""
    beer_run: models.BeerRun
    membership: models.BeerRunMember


@dataclass(frozen=True)
class OwnerAccess:
    """Result of the owner-only policy; membership is always present."""
    beer_run: models.BeerRun
    membership: models.BeerRunMember


def _membership_for(
    db: Session,
    beer_run_id: int,
    user: models.User | None,
) -> models.BeerRunMember | None:
    """Return the caller's membership row for a run, or ``None``."""
    if user is None:
        return None
    return (
        db.query(models.BeerRunMember)
        .filter(
            models.BeerRunMember.beer_run_id == beer_run_id,
            models.BeerRunMember.user_id == user.id,
        )
        .first()
    )


# --- Dependencies ---

def authorize_public_read(
    beer_run_id: int,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> PublicReadAccess:
    """Authorize reading a beer-run: public runs for anyone, private for members.

    A missing run and a private run the caller cannot read both raise the shared
    ``404`` so private existence is never disclosed. The decision is based on the
    persisted ``is_public`` value only — the run's name never matters. An
    invalid token is resolved by ``auth.get_current_user`` as a logged-out
    caller, so it reads public runs and is denied private runs.
    """
    beer_run = db.get(models.BeerRun, beer_run_id)
    if beer_run is None:
        raise not_found_error()
    membership = _membership_for(db, beer_run_id, current_user)
    if not beer_run.is_public and membership is None:
        raise not_found_error()
    return PublicReadAccess(beer_run=beer_run, membership=membership)


def authorize_member_access(
    beer_run_id: int,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> MemberAccess:
    """Require a valid authenticated user who is a member of the run.

    Authentication is resolved before target-run existence, so missing or
    invalid credentials return ``401`` without revealing whether the run
    exists. After authentication succeeds, a missing run or a run the caller is
    not a member of returns the shared ``404``. ``is_public`` never bypasses
    membership for member-only operations.
    """
    if current_user is None:
        raise unauthorized_error()
    beer_run = db.get(models.BeerRun, beer_run_id)
    if beer_run is None:
        raise not_found_error()
    membership = _membership_for(db, beer_run_id, current_user)
    if membership is None:
        raise not_found_error()
    return MemberAccess(beer_run=beer_run, membership=membership)


def authorize_owner_access(
    beer_run_id: int,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
) -> OwnerAccess:
    """Require a valid authenticated user whose membership role is ``owner``.

    Authentication is resolved before target-run existence, so missing or
    invalid credentials return ``401`` without revealing whether the run
    exists. After authentication succeeds, a missing run returns ``404`` and a
    normal member or authenticated non-member returns the shared ``403``.
    Public visibility does not weaken ownership.
    """
    if current_user is None:
        raise unauthorized_error()
    beer_run = db.get(models.BeerRun, beer_run_id)
    if beer_run is None:
        raise not_found_error()
    membership = _membership_for(db, beer_run_id, current_user)
    if membership is None or membership.role != "owner":
        raise forbidden_error()
    return OwnerAccess(beer_run=beer_run, membership=membership)
