import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import get_db

# --- Configuration ---
ENV_FILE_PATH = Path(__file__).resolve().parent / ".env"
FORMER_SECRET = "former-secret-key-that-should-never-be-used"
EXAMPLE_SECRET = "replace-with-output-from-secrets-token_urlsafe-32"
EXAMPLE_SIGNUP_CODE = "replace-with-private-signup-code"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 30 days
TOKEN_VERSION = 2
MAX_USER_ID = (2**63) - 1
# Allow digits only, no leading zero — matches the auto-increment integer
# primary key format SQLite produces, while rejecting ambiguous / padded
# representations that might bypass a naive "is this numeric?" check.
_CANONICAL_USER_ID = re.compile(r"[1-9][0-9]*\Z")


def validate_auth_configuration() -> str:
    """Load and validate the JWT signing key without exposing its value."""
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)
    secret_key = os.environ.get("SECRET_KEY")
    if secret_key is None:
        problem = "is missing"
    elif not secret_key.strip():
        problem = "is blank"
    elif secret_key != secret_key.strip():
        problem = "has leading or trailing whitespace"
    elif secret_key == EXAMPLE_SECRET:
        problem = "uses the example secret"
    elif secret_key == FORMER_SECRET:
        problem = "prohibited"
    elif len(secret_key.encode("utf-8")) < 32:
        problem = "is shorter than 32 UTF-8 bytes"
    else:
        problem = None

    if problem:
        raise RuntimeError(
            f"SECRET_KEY {problem}. Set a strong value of at least "
            "32 UTF-8 bytes in the repository-root .env file or the process "
            "environment."
        )
    return secret_key


def validate_signup_configuration() -> str:
    """Load and validate the private signup code without exposing its value."""
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)
    signup_code = os.environ.get("SIGNUP_CODE")
    if signup_code is None:
        problem = "is missing"
    elif not signup_code.strip():
        problem = "is blank"
    elif signup_code != signup_code.strip():
        problem = "has leading or trailing whitespace"
    elif signup_code == EXAMPLE_SIGNUP_CODE:
        problem = "uses the example signup code"
    else:
        problem = None

    if problem:
        raise RuntimeError(
            f"SIGNUP_CODE {problem}. Set a private value in the repository-root "
            ".env file or the process environment."
        )
    return signup_code


def signup_code_matches(submitted_code: str) -> bool:
    """Compare a submitted signup code exactly using constant-time equality.

    We use secrets.compare_digest instead of a plain == comparison to prevent
    timing side-channels: a naive string comparison short-circuits on the
    first mismatched character, revealing how many characters matched.  An
    attacker close to the server could measure response times to brute-force
    the code character by character.  compare_digest always takes the same
    amount of time regardless of how much of the input differs.
    """
    configured_code = validate_signup_configuration()
    return secrets.compare_digest(
        submitted_code.encode("utf-8"),
        configured_code.encode("utf-8"),
    )

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)


def _parse_user_id_subject(subject: object) -> int:
    if not isinstance(subject, str) or not _CANONICAL_USER_ID.fullmatch(subject):
        raise ValueError("Invalid token subject")
    user_id = int(subject)
    if user_id > MAX_USER_ID:
        raise ValueError("Invalid token subject")
    return user_id


# --- JWT Logic ---
def create_access_token(data: dict):
    to_encode = data.copy()
    _parse_user_id_subject(to_encode.get("sub"))
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "token_version": TOKEN_VERSION})
    return jwt.encode(to_encode, validate_auth_configuration(), algorithm=ALGORITHM)

# --- Dependencies ---
# auto_error=False so the dependency returns None instead of short-circuiting
# with 401 when no Authorization header is present.  Each endpoint decides
# whether to reject (raise 401) or treat the caller as logged-out.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User | None:
    """Resolve the current user, or None when unauthenticated.

    Returns None (never raises 401) when the token is missing, invalid,
    expired, or belongs to a deleted account.  Write endpoints that
    require authentication check for None themselves.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            validate_auth_configuration(),
            algorithms=[ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
        if type(payload.get("token_version")) is not int or payload["token_version"] != TOKEN_VERSION:
            return None
        user_id = _parse_user_id_subject(payload.get("sub"))
        return db.get(models.User, user_id)
    except (JWTError, ValueError):
        return None
