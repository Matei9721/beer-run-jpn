import asyncio
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys

import pytest
from jose import JWTError, jwt

import auth


ROOT_PATH = Path(__file__).resolve().parents[1]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signed_token(claims: dict, secret: str | None = None, *, include_exp: bool = True) -> str:
    payload = dict(claims)
    if include_exp:
        payload["exp"] = datetime.now(UTC) + timedelta(minutes=5)
    return jwt.encode(
        payload,
        secret or auth.validate_auth_configuration(),
        algorithm=auth.ALGORITHM,
    )


def _assert_generic_unauthorized(response) -> None:
    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_secret_loads_from_root_env_file(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    configured_secret = secrets.token_urlsafe(32)
    env_path.write_text(f"SECRET_KEY={configured_secret}\n", encoding="utf-8")
    monkeypatch.setattr(auth, "ENV_FILE_PATH", env_path)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    assert auth.validate_auth_configuration() == configured_secret


def test_process_secret_takes_precedence_over_env_file(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    process_secret = secrets.token_urlsafe(32)
    file_secret = secrets.token_urlsafe(32)
    env_path.write_text(f"SECRET_KEY={file_secret}\n", encoding="utf-8")
    monkeypatch.setattr(auth, "ENV_FILE_PATH", env_path)
    monkeypatch.setenv("SECRET_KEY", process_secret)

    token = auth.create_access_token({"sub": "1"})

    assert jwt.decode(token, process_secret, algorithms=[auth.ALGORITHM])["sub"] == "1"
    with pytest.raises(JWTError):
        jwt.decode(token, file_secret, algorithms=[auth.ALGORITHM])


@pytest.mark.parametrize(
    ("candidate", "problem"),
    [
        (None, "missing"),
        ("", "blank"),
        (" " * 32, "blank"),
        (f"{'x' * 32} ", "leading or trailing whitespace"),
        ("x" * 31, "shorter than 32 UTF-8 bytes"),
        (auth.FORMER_SECRET, "prohibited"),
        (auth.EXAMPLE_SECRET, "prohibited"),
    ],
)
def test_invalid_secret_is_rejected_without_echoing_value(monkeypatch, tmp_path, candidate, problem):
    monkeypatch.setattr(auth, "ENV_FILE_PATH", tmp_path / "missing.env")
    if candidate is None:
        monkeypatch.delenv("SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("SECRET_KEY", candidate)

    with pytest.raises(RuntimeError) as exc_info:
        auth.validate_auth_configuration()

    message = str(exc_info.value)
    assert "SECRET_KEY" in message
    assert problem in message
    assert ".env" in message
    assert "process environment" in message
    if candidate and candidate.strip():
        assert candidate not in message


def test_secret_minimum_is_measured_in_utf8_bytes(monkeypatch, tmp_path):
    exactly_32_bytes = "\u00e9" * 16
    monkeypatch.setattr(auth, "ENV_FILE_PATH", tmp_path / "missing.env")
    monkeypatch.setenv("SECRET_KEY", exactly_32_bytes)

    assert len(exactly_32_bytes.encode("utf-8")) == 32
    assert auth.validate_auth_configuration() == exactly_32_bytes


def test_example_secret_matches_tracked_placeholder():
    example_lines = (ROOT_PATH / ".env.example").read_text(encoding="utf-8").splitlines()

    assert f"SECRET_KEY={auth.EXAMPLE_SECRET}" in example_lines


def test_jwt_encode_and_decode_refuse_invalid_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "ENV_FILE_PATH", tmp_path / "missing.env")
    monkeypatch.setenv("SECRET_KEY", "short")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth.create_access_token({"sub": "1"})
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        asyncio.run(auth.get_current_user("not-a-token", db=object()))


def test_password_hashing_does_not_require_jwt_configuration(tmp_path):
    missing_env = tmp_path / "missing.env"
    child_env = os.environ.copy()
    child_env.pop("SECRET_KEY", None)
    script = (
        "from pathlib import Path; import auth; "
        f"auth.ENV_FILE_PATH = Path({str(missing_env)!r}); "
        "assert auth.get_password_hash('password')"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT_PATH,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_main_import_refuses_missing_secret_with_safe_message(tmp_path):
    missing_env = tmp_path / "missing.env"
    child_env = os.environ.copy()
    child_env.pop("SECRET_KEY", None)
    script = (
        "from pathlib import Path; import auth; "
        f"auth.ENV_FILE_PATH = Path({str(missing_env)!r}); "
        "import main"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT_PATH,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "SECRET_KEY" in output
    assert "repository-root .env" in output
    assert auth.FORMER_SECRET not in output


def test_login_is_case_insensitive_and_issues_versioned_id_token(client):
    response = client.post("/token", data={"username": "UsEr", "password": "password"})

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    payload = jwt.decode(
        response.json()["access_token"],
        auth.validate_auth_configuration(),
        algorithms=[auth.ALGORITHM],
    )
    assert payload["sub"] == "1"
    assert payload["token_version"] == 2
    assert type(payload["token_version"]) is int
    assert "exp" in payload
    assert "username" not in payload


def test_login_failure_verifies_existing_password_only_once(client, monkeypatch):
    calls = []
    original_verify = auth.verify_password

    def tracked_verify(plain_password, hashed_password):
        calls.append((plain_password, hashed_password))
        return original_verify(plain_password, hashed_password)

    monkeypatch.setattr(auth, "verify_password", tracked_verify)

    response = client.post("/token", data={"username": "user", "password": "wrongpassword"})

    assert response.status_code == 401
    assert len(calls) == 1


def test_unknown_user_does_not_attempt_password_verification(client, monkeypatch):
    def unexpected_verify(*_args):
        raise AssertionError("password verification should not run for an unknown user")

    monkeypatch.setattr(auth, "verify_password", unexpected_verify)

    response = client.post("/token", data={"username": "missing", "password": "password"})

    assert response.status_code == 401


@pytest.mark.parametrize("stored_hash", [None, "not-a-password-hash"])
def test_missing_or_malformed_password_hash_fails_without_diagnostics(client, capsys, stored_hash):
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        conn.execute("UPDATE users SET hashed_password = ? WHERE id = 1", (stored_hash,))
    capsys.readouterr()

    response = client.post("/token", data={"username": "user", "password": "password"})

    captured = capsys.readouterr()
    assert response.status_code == 401
    assert "user" not in captured.out
    assert "user" not in captured.err
    assert "password" not in captured.out
    assert "password" not in captured.err


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "1"},
        {"sub": "1", "token_version": 1},
        {"sub": "1", "token_version": 2.0},
        {"sub": "1", "token_version": "2"},
        {"sub": "1", "token_version": True},
        {"token_version": 2},
        {"sub": 1, "token_version": 2},
        {"sub": "user", "token_version": 2},
        {"sub": "0", "token_version": 2},
        {"sub": "-1", "token_version": 2},
        {"sub": "+1", "token_version": 2},
        {"sub": " 1", "token_version": 2},
        {"sub": "1.0", "token_version": 2},
        {"sub": "01", "token_version": 2},
        {"sub": "999999", "token_version": 2},
        {"sub": str(2**63), "token_version": 2},
    ],
)
def test_invalid_identity_claims_share_generic_unauthorized_response(client, claims):
    response = client.get("/api/me", headers=_bearer(_signed_token(claims)))

    _assert_generic_unauthorized(response)


def test_missing_expiration_is_rejected_generically(client):
    token = _signed_token({"sub": "1", "token_version": 2}, include_exp=False)

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


def test_expired_token_is_rejected_generically(client):
    token = jwt.encode(
        {
            "sub": "1",
            "token_version": 2,
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        auth.validate_auth_configuration(),
        algorithm=auth.ALGORITHM,
    )

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


@pytest.mark.parametrize("token", ["not-a-token", "one.two.three"])
def test_malformed_token_is_rejected_generically(client, token):
    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


def test_invalid_signature_is_rejected_generically(client):
    token = _signed_token(
        {"sub": "1", "token_version": 2},
        secret=secrets.token_urlsafe(32),
    )

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


@pytest.mark.parametrize("legacy_subject", ["user", "123"])
def test_legacy_username_tokens_are_rejected_without_fallback(client, legacy_subject):
    token = _signed_token({"sub": legacy_subject})

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


def test_token_resolves_user_by_id_after_username_changes(client):
    login_response = client.post("/token", data={"username": "user", "password": "password"})
    token = login_response.json()["access_token"]
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        conn.execute("UPDATE users SET username = 'renamed' WHERE id = 1")

    response = client.get("/api/me", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == {"username": "renamed", "id": 1}


@pytest.mark.parametrize(
    "subject",
    [None, "user", "0", "-1", "+1", " 1", "1.0", "01", str(auth.MAX_USER_ID + 1)],
)
def test_access_token_creation_requires_canonical_positive_user_id(subject):
    with pytest.raises(ValueError, match="subject"):
        auth.create_access_token({"sub": subject})


def test_protected_route_fail(client):
    response = client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 0.0,
            "longitude": 0.0,
        },
    )
    assert response.status_code == 401


def test_protected_route_success(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]

    response = client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 0.0,
            "longitude": 0.0,
        },
        headers=_bearer(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_protected_route_success_no_image(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]

    response = client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 0.0,
            "longitude": 0.0,
        },
        headers=_bearer(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
