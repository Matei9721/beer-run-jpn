import os
import re
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
EXAMPLE_SECRET = "replace-with-output-from-secrets-token_urlsafe-32"
FORMER_SECRET = "hidden-secret-but-not-really"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 30 days
TOKEN_VERSION = 2
MAX_USER_ID = (2**63) - 1
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
    elif secret_key in {FORMER_SECRET, EXAMPLE_SECRET}:
        problem = "uses a prohibited example or former signing value"
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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            validate_auth_configuration(),
            algorithms=[ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
        if type(payload.get("token_version")) is not int or payload["token_version"] != TOKEN_VERSION:
            raise ValueError("Invalid token version")
        user_id = _parse_user_id_subject(payload.get("sub"))
    except (JWTError, ValueError):
        raise credentials_exception from None

    user = db.get(models.User, user_id)
    if user is None:
        raise credentials_exception from None
    return user
