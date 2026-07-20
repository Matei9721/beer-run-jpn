import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db


router = APIRouter()

SIGNUP_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_-]{3,32}\Z")
SIGNUP_PASSWORD_LETTER_PATTERN = re.compile(r"[A-Za-z]")
SIGNUP_PASSWORD_DIGIT_PATTERN = re.compile(r"[0-9]")


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
    if request.url.path != "/api/signup":
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
    access_token = auth.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post(
    "/api/signup",
    response_model=schemas.Token,
    status_code=status.HTTP_201_CREATED,
)
async def signup(request: schemas.SignupRequest, db: Session = Depends(get_db)):
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
        access_token = auth.create_access_token({"sub": str(user.id)})
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
    current_user: models.User = Depends(auth.get_current_user),
):
    return {"username": current_user.username, "id": current_user.id}
