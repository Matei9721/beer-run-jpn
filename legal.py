"""Legal-policy configuration, rendering, and Terms-acceptance helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
import os
from pathlib import Path
import re

from dotenv import load_dotenv
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE_PATH = BASE_DIR / ".env"
TERMS_VERSION = "2026-08-30"
PRIVACY_NOTICE_VERSION = "2026-08-30"
LEGAL_EFFECTIVE_DATE = "2026-08-30"
TERMS_URL = "/terms"
PRIVACY_URL = "/privacy"
EXAMPLE_CONTROLLER_NAME = "replace-with-controller-legal-name"
EXAMPLE_CONTACT_EMAIL = "replace-with-controller-contact-email"

_EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\Z"
)


@dataclass(frozen=True)
class LegalSettings:
    controller_name: str
    contact_email: str


def _configuration_problem(variable: str, value: str | None) -> str | None:
    if value is None:
        return "is missing"
    if not value.strip():
        return "is blank"
    if value != value.strip():
        return "has leading or trailing whitespace"
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return "contains control characters"
    if len(value) > 200:
        return "is too long"
    if variable == "LEGAL_CONTROLLER_NAME":
        if value == EXAMPLE_CONTROLLER_NAME:
            return "uses the example placeholder"
        if len(value) < 2:
            return "is too short"
    if variable == "LEGAL_CONTACT_EMAIL":
        if value == EXAMPLE_CONTACT_EMAIL:
            return "uses the example placeholder"
        if not _EMAIL_PATTERN.fullmatch(value):
            return "is not a valid email address"
    return None


def validate_legal_configuration() -> LegalSettings:
    """Load controller details without exposing their values in failures."""

    load_dotenv(dotenv_path=ENV_FILE_PATH, override=False)
    values = {
        "LEGAL_CONTROLLER_NAME": os.environ.get("LEGAL_CONTROLLER_NAME"),
        "LEGAL_CONTACT_EMAIL": os.environ.get("LEGAL_CONTACT_EMAIL"),
    }
    for variable, value in values.items():
        problem = _configuration_problem(variable, value)
        if problem:
            raise RuntimeError(
                f"{variable} {problem}. Set the controller's real legal identity "
                "and working contact email in the repository-root .env file or "
                "the process environment."
            )
    return LegalSettings(
        controller_name=values["LEGAL_CONTROLLER_NAME"],
        contact_email=values["LEGAL_CONTACT_EMAIL"],
    )


def public_metadata() -> dict[str, str]:
    return {
        "terms_version": TERMS_VERSION,
        "privacy_notice_version": PRIVACY_NOTICE_VERSION,
        "effective_date": LEGAL_EFFECTIVE_DATE,
        "terms_url": TERMS_URL,
        "privacy_url": PRIVACY_URL,
    }


def render_document(filename: str) -> str:
    """Render one tracked legal template with escaped private configuration."""

    if filename not in {"terms.html", "privacy.html"}:
        raise ValueError("Unknown legal document")
    settings = validate_legal_configuration()
    template = (BASE_DIR / "templates" / filename).read_text(encoding="utf-8")
    replacements = {
        "__LEGAL_CONTROLLER_NAME__": escape(settings.controller_name, quote=True),
        "__LEGAL_CONTACT_EMAIL__": escape(settings.contact_email, quote=True),
    }
    for token, value in replacements.items():
        template = template.replace(token, value)
    return template


def utc_now() -> datetime:
    return datetime.now(UTC)
