"""Absolute source and runtime paths anchored at the repository root."""

import os
from pathlib import Path, PurePosixPath


PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parent
REPOSITORY_ROOT = SOURCE_ROOT.parent


def _runtime_path(environment_variable: str, default: Path) -> Path:
    configured = Path(os.environ.get(environment_variable, default))
    if not configured.is_absolute():
        configured = REPOSITORY_ROOT / configured
    return configured.resolve()


FRONTEND_SOURCE_ROOT = SOURCE_ROOT / "frontend"
FRONTEND_APP_ROOT = FRONTEND_SOURCE_ROOT / "app"
FRONTEND_PAGE_ROOT = FRONTEND_SOURCE_ROOT / "pages"
FRONTEND_STATIC_ROOT = FRONTEND_SOURCE_ROOT / "static"
RUNTIME_STATIC_ROOT = REPOSITORY_ROOT / "static"
PERSISTED_UPLOAD_ROOT = PurePosixPath("static/uploads")

ENV_FILE_PATH = _runtime_path("BOOZERUN_ENV_PATH", REPOSITORY_ROOT / ".env")
DEFAULT_DATABASE_PATH = _runtime_path(
    "BOOZERUN_DATABASE_PATH", REPOSITORY_ROOT / "boozerun.db"
)
DATA_ROOT = _runtime_path("BOOZERUN_DATA_ROOT", REPOSITORY_ROOT / "data")
WRAPPED_DATA_ROOT = DATA_ROOT / "wrapped"
UPLOAD_ROOT = _runtime_path(
    "BOOZERUN_UPLOAD_ROOT", RUNTIME_STATIC_ROOT / "uploads"
)
ACCOUNT_DELETION_QUARANTINE_ROOT = _runtime_path(
    "BOOZERUN_QUARANTINE_ROOT",
    REPOSITORY_ROOT / ".account-deletion-quarantine",
)
