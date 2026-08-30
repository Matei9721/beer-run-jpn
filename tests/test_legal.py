"""Legal-policy and new-account Terms-acceptance coverage."""

from __future__ import annotations

import os
import sqlite3

import legal
import pytest
from sqlalchemy.orm import Session


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client) -> str:
    response = client.post(
        "/token",
        data={"username": "user", "password": "password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_public_legal_metadata_and_documents_are_available_without_auth(client):
    metadata = client.get("/api/legal/metadata")
    assert metadata.status_code == 200
    assert metadata.json() == {
        "terms_version": legal.TERMS_VERSION,
        "privacy_notice_version": legal.PRIVACY_NOTICE_VERSION,
        "effective_date": legal.LEGAL_EFFECTIVE_DATE,
        "terms_url": "/terms",
        "privacy_url": "/privacy",
    }

    for path, title in (("/terms", "Terms of Service"), ("/privacy", "Privacy Notice")):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert title in response.text
        assert response.text.count("Test Controller") == 1
        assert response.text.count("privacy@example.test") == 1
        assert "__LEGAL_CONTROLLER_NAME__" not in response.text
        assert "__LEGAL_CONTACT_EMAIL__" not in response.text

    privacy = " ".join(client.get("/privacy").text.split())
    assert "Creating an account is optional" in privacy
    assert "These choices are voluntary, but they are not blanket consent" in privacy
    assert "Account settings without emailing us" in privacy
    assert "If you own a beer run, you must delete that run first" in privacy
    assert "photos uploaded for your entries" in privacy
    assert "Other users' accounts, entries, and photos are not deleted" in privacy
    assert "lawfully references" not in privacy
    assert "shared file still" not in privacy
    assert "SQLite" not in privacy
    assert "Autoriteit Persoonsgegevens" not in privacy
    assert "practical baseline" not in privacy
    assert "qualified Dutch/EU legal review" not in privacy
    assert "transfer ownership" not in privacy.lower()

    terms = " ".join(client.get("/terms").text.split())
    assert "Creating an account is" in terms
    assert "optional and is needed only if you choose" in terms
    assert "delete your account through Account settings without contacting us" in terms
    assert "If you own a beer run, you must delete that run first" in terms
    assert "photos uploaded for your entries" in terms
    assert "Other users' accounts, entries, and photos are not deleted" in terms
    assert "shared file still" not in terms
    assert "source code is available under the MIT License" in terms
    assert "practical baseline" not in terms
    assert "qualified Dutch/EU legal review" not in terms
    assert "transfer ownership" not in terms.lower()


def test_legal_document_configuration_is_html_escaped(client, monkeypatch):
    monkeypatch.setenv("LEGAL_CONTROLLER_NAME", "Operator <script>alert(1)</script>")

    response = client.get("/privacy")

    assert response.status_code == 200
    assert "Operator &lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert "Operator <script>alert(1)</script>" not in response.text


def test_legal_configuration_failures_do_not_echo_private_values(monkeypatch):
    private_value = " private-controller-name "
    monkeypatch.setenv("LEGAL_CONTROLLER_NAME", private_value)

    try:
        legal.validate_legal_configuration()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("Invalid legal configuration unexpectedly passed")

    assert "LEGAL_CONTROLLER_NAME" in message
    assert "leading or trailing whitespace" in message
    assert private_value not in message


def test_signup_requires_explicit_current_terms_and_records_acceptance_atomically(client):
    base = {
        "username": "Legal_User",
        "password": "Password1",
        "signup_code": os.environ["SIGNUP_CODE"],
    }

    declined = client.post(
        "/api/signup",
        json={**base, "terms_agreed": False, "terms_version": legal.TERMS_VERSION},
    )
    stale = client.post(
        "/api/signup",
        json={**base, "terms_agreed": True, "terms_version": "older-version"},
    )

    assert declined.status_code == 422
    assert stale.status_code == 422
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM users WHERE username = 'Legal_User'"
        ).fetchone()[0] == 0

    accepted = client.post(
        "/api/signup",
        json={**base, "terms_agreed": True, "terms_version": legal.TERMS_VERSION},
    )
    assert accepted.status_code == 201
    token = accepted.json()["access_token"]
    assert client.get("/api/me", headers=_bearer(token)).status_code == 200
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        row = conn.execute(
            "SELECT terms_acceptances.terms_version, terms_acceptances.accepted_at "
            "FROM terms_acceptances JOIN users ON users.id = terms_acceptances.user_id "
            "WHERE users.username = 'Legal_User'"
        ).fetchone()
    assert row is not None
    assert row[0] == legal.TERMS_VERSION
    assert row[1]


@pytest.mark.parametrize("terms_agreed", [1, "true", None])
def test_signup_rejects_non_boolean_terms_values(client, terms_agreed):
    response = client.post(
        "/api/signup",
        json={
            "username": "StrictTerms",
            "password": "Password1",
            "signup_code": os.environ["SIGNUP_CODE"],
            "terms_agreed": terms_agreed,
            "terms_version": legal.TERMS_VERSION,
        },
    )

    assert response.status_code == 422
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM users WHERE username = 'StrictTerms'"
        ).fetchone()[0] == 0


def test_existing_account_needs_no_terms_record_or_interstitial(client):
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM terms_acceptances").fetchone()[0] == 0

    token = _login(client)
    headers = _bearer(token)

    assert client.get("/api/me", headers=headers).status_code == 200
    assert client.get("/api/beer-runs", headers=headers).status_code == 200
    assert client.get("/api/me/deletion-summary", headers=headers).status_code == 200

    page = client.get("/").text
    assert 'id="signup-terms-agreement"' in page
    assert 'id="terms-acceptance-modal"' not in page
    assert "Terms-acceptance records, and photos uploaded for your entries" in page


def test_signup_failure_rolls_back_account_and_acceptance(client, monkeypatch):
    def fail_commit(_session):
        raise RuntimeError("private database failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post(
        "/api/signup",
        json={
            "username": "AtomicTerms",
            "password": "Password1",
            "signup_code": os.environ["SIGNUP_CODE"],
            "terms_agreed": True,
            "terms_version": legal.TERMS_VERSION,
        },
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create account"}
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM users WHERE username = 'AtomicTerms'"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM terms_acceptances").fetchone()[0] == 0
