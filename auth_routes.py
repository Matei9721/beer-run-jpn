import re
import sqlite3
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import legal
import models
import schemas
from upload_cleanup import (
    QuarantineRestoreError,
    collect_user_uploads,
    purge_quarantined_uploads,
    quarantine_uploads,
    restore_quarantined_uploads,
)
from database import get_db


router = APIRouter()

SIGNUP_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,32}\Z")
SIGNUP_PASSWORD_LETTER_PATTERN = re.compile(r"[A-Za-z]")
SIGNUP_PASSWORD_DIGIT_PATTERN = re.compile(r"[0-9]")
ACCOUNT_DELETE_CONFIRMATION = "DELETE MY ACCOUNT"
UPLOAD_ROOT = Path("static/uploads")
UPLOAD_PATH_ROOT = PurePosixPath("static/uploads")
ACCOUNT_DELETION_QUARANTINE_ROOT = Path(".account-deletion-quarantine")


async def sanitize_signup_validation_error(
    request: Request,
    exc: RequestValidationError,
):
    # Security: FastAPI's default RequestValidationError handler returns the
    # submitted input values in the error response (the "input" field).  If a
    # signup request fails Pydantic validation (e.g. password too short), the
    # raw password would be echoed back in the response body — visible to any
    # network observer, browser dev tools, or server logs that record response
    # payloads.  We strip the response to only type/loc/msg to prevent that.
    if request.url.path not in {"/api/signup", "/api/me"}:
        return await request_validation_exception_handler(request, exc)

    # Build a sanitised version of the errors: drop the "input" key that
    # carries the submitted value, along with any "ctx" metadata, so the
    # client only sees which field failed and why — never the value itself.
    safe_errors = [
        {
            "type": error.get("type", "value_error"),
            "loc": error.get("loc", ()),
            "msg": error.get("msg", "Invalid value"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": safe_errors},
    )


def _is_username_unique_violation(exc: IntegrityError) -> bool:
    # Check whether the IntegrityError is specifically a duplicate-username
    # collision.  We match the SQLite error string directly because SQLAlchemy
    # doesn't expose a portable exception type for "unique constraint on this
    # specific column" — the same operation on PostgreSQL would produce a
    # different error class and message.
    return (
        isinstance(exc.orig, sqlite3.IntegrityError)
        and str(exc.orig) == "UNIQUE constraint failed: users.username"
    )


def _validate_terms_agreement(terms_agreed: bool, terms_version: str) -> None:
    if not terms_agreed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="You must agree to the Terms of Service",
        )
    if terms_version != legal.TERMS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Review and agree to the current Terms of Service",
        )


@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = (
        db.query(models.User)
        .filter(func.lower(models.User.username) == func.lower(form_data.username))
        .first()
    )
    password_is_valid = False
    if user and user.hashed_password:
        try:
            password_is_valid = auth.verify_password(
                form_data.password,
                user.hashed_password,
            )
        except (TypeError, ValueError):
            password_is_valid = False

    if not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.auth_subject})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/api/signup",
    response_model=schemas.Token,
    status_code=status.HTTP_201_CREATED,
)
async def signup(request: schemas.SignupRequest, db: Session = Depends(get_db)):
    _validate_terms_agreement(request.terms_agreed, request.terms_version)
    if not auth.signup_code_matches(request.signup_code):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signup code",
        )

    username = request.username.strip()
    if not SIGNUP_USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Username must be 3-32 characters using only ASCII letters, "
                "numbers, underscores, or hyphens"
            ),
        )
    if (
        len(request.password) < 8
        or not SIGNUP_PASSWORD_LETTER_PATTERN.search(request.password)
        or not SIGNUP_PASSWORD_DIGIT_PATTERN.search(request.password)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Password must be at least 8 characters and include at least "
                "one ASCII letter and one number"
            ),
        )

    # Race-condition-safe duplicate check: we first query (cheap, most of the
    # time nobody races), then rely on the DB UNIQUE constraint as a hard
    # backstop.  If two requests for the same free username arrive concurrently
    # the query will pass for both, but the second .flush() will hit an
    # IntegrityError — caught below and turned into the same 409 response.
    try:
        existing_user = (
            db.query(models.User)
            .filter(models.User.username.collate("NOCASE") == username)
            .first()
        )
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create account",
        ) from None  # Don't leak internal exception details to the client.
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    try:
        user = models.User(
            username=username,
            hashed_password=auth.get_password_hash(request.password),
        )
        db.add(user)
        db.flush()
        db.add(
            models.TermsAcceptance(
                user_id=user.id,
                terms_version=legal.TERMS_VERSION,
                accepted_at=legal.utc_now(),
            )
        )
        db.flush()
        access_token = auth.create_access_token({"sub": user.auth_subject})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_username_unique_violation(exc):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            ) from None  # from None = don't leak the IntegrityError traceback to the API client.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create account",
        ) from None
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create account",
        ) from None  # Generic catch — only hit for unexpected errors; we still avoid leaking details.

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/api/me")
async def read_users_me(
    current_user: models.User | None = Depends(auth.get_current_user),
):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": current_user.username, "id": current_user.id}


def _require_current_user(current_user: models.User | None) -> models.User:
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def _owned_runs(db: Session, user_id: int) -> list[dict[str, object]]:
    rows = (
        db.query(models.BeerRun.id, models.BeerRun.name)
        .join(models.BeerRunMember)
        .filter(
            models.BeerRunMember.user_id == user_id,
            models.BeerRunMember.role == "owner",
        )
        .order_by(models.BeerRun.name, models.BeerRun.id)
        .all()
    )
    return [{"id": row.id, "name": row.name} for row in rows]


def _begin_account_deletion(db: Session) -> None:
    """Serialize the ownership, upload, and row-deletion decision in SQLite."""

    db.connection().exec_driver_sql("BEGIN IMMEDIATE")


def _restore_account_uploads(operation) -> None:
    if operation is None:
        return
    try:
        restore_quarantined_uploads(operation)
    except QuarantineRestoreError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete account; photo recovery is pending",
        ) from None


@router.get(
    "/api/me/deletion-summary",
    response_model=schemas.AccountDeletionSummary,
)
async def account_deletion_summary(
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    user = _require_current_user(current_user)
    return {
        "entry_count": db.query(models.Entry.id).filter(models.Entry.user_id == user.id).count(),
        "membership_count": db.query(models.BeerRunMember.id).filter(models.BeerRunMember.user_id == user.id).count(),
        "owned_runs": _owned_runs(db, user.id),
    }


@router.delete("/api/me", response_model=schemas.AccountDeleteResponse)
async def delete_account(
    request: schemas.AccountDeleteRequest,
    current_user: models.User | None = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    user = _require_current_user(current_user)
    if request.confirmation != ACCOUNT_DELETE_CONFIRMATION:
        raise HTTPException(status_code=422, detail="Type DELETE MY ACCOUNT to confirm")

    password_valid = False
    if user.hashed_password:
        try:
            password_valid = auth.verify_password(request.password, user.hashed_password)
        except (TypeError, ValueError):
            password_valid = False
    if not password_valid:
        raise HTTPException(status_code=401, detail="Incorrect password")

    quarantine = None
    try:
        _begin_account_deletion(db)
        blockers = _owned_runs(db, user.id)
        if blockers:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "owned_runs_block_deletion",
                    "message": "Delete these runs first.",
                    "owned_runs": blockers,
                },
            )
        candidates = collect_user_uploads(
            db,
            user.id,
            upload_root=UPLOAD_ROOT,
            upload_path_root=UPLOAD_PATH_ROOT,
        )
        quarantine = quarantine_uploads(
            candidates,
            upload_root=UPLOAD_ROOT,
            quarantine_root=ACCOUNT_DELETION_QUARANTINE_ROOT,
        )
        db.query(models.Entry).filter(models.Entry.user_id == user.id).delete(
            synchronize_session=False
        )
        db.query(models.BeerRunMember).filter(
            models.BeerRunMember.user_id == user.id
        ).delete(synchronize_session=False)
        db.query(models.TermsAcceptance).filter(
            models.TermsAcceptance.user_id == user.id
        ).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
    except HTTPException:
        raise
    except QuarantineRestoreError as exc:
        db.rollback()
        _restore_account_uploads(exc.operation)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete account",
        ) from None
    except Exception:
        db.rollback()
        _restore_account_uploads(quarantine)
        raise HTTPException(status_code=500, detail="Unable to delete account") from None

    purge_quarantined_uploads(quarantine)
    return {"deleted": True}
