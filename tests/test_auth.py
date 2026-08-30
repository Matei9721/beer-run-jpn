import asyncio
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from jose import JWTError, jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

import auth
from main import app


ROOT_PATH = Path(__file__).resolve().parents[1]
VALID_SIGNUP_CODE = os.environ["SIGNUP_CODE"]
VALID_AUTH_SUBJECT = "A" * 43


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


def _beer_run_jpn_id() -> int:
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        row = conn.execute("SELECT id FROM beer_runs WHERE name = 'BeerRunJPN'").fetchone()
    assert row is not None
    return row[0]


def _entry_form():
    return {
        "drink_type": "Beer",
        "abv": 5.0,
        "quantity": 0.5,
        "latitude": 0.0,
        "longitude": 0.0,
    }


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

    token = auth.create_access_token({"sub": VALID_AUTH_SUBJECT})

    assert jwt.decode(token, process_secret, algorithms=[auth.ALGORITHM])["sub"] == VALID_AUTH_SUBJECT
    with pytest.raises(JWTError):
        jwt.decode(token, file_secret, algorithms=[auth.ALGORITHM])


def test_signup_code_loads_from_root_env_file(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SIGNUP_CODE=file-private-code\n", encoding="utf-8")
    monkeypatch.setattr(auth, "ENV_FILE_PATH", env_path)
    monkeypatch.delenv("SIGNUP_CODE", raising=False)

    assert auth.validate_signup_configuration() == "file-private-code"


def test_process_signup_code_takes_precedence_over_env_file(monkeypatch, tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("SIGNUP_CODE=file-private-code\n", encoding="utf-8")
    monkeypatch.setattr(auth, "ENV_FILE_PATH", env_path)
    monkeypatch.setenv("SIGNUP_CODE", "process-private-code")

    assert auth.validate_signup_configuration() == "process-private-code"
    assert auth.signup_code_matches("process-private-code")
    assert not auth.signup_code_matches("file-private-code")


@pytest.mark.parametrize(
    ("candidate", "problem"),
    [
        (None, "missing"),
        ("", "blank"),
        ("   ", "blank"),
        ("padded-code ", "leading or trailing whitespace"),
        (auth.EXAMPLE_SIGNUP_CODE, "uses the example signup code"),
    ],
)
def test_invalid_signup_code_configuration_is_rejected_safely(
    monkeypatch, tmp_path, candidate, problem
):
    monkeypatch.setattr(auth, "ENV_FILE_PATH", tmp_path / "missing.env")
    if candidate is None:
        monkeypatch.delenv("SIGNUP_CODE", raising=False)
    else:
        monkeypatch.setenv("SIGNUP_CODE", candidate)

    with pytest.raises(RuntimeError) as exc_info:
        auth.validate_signup_configuration()

    message = str(exc_info.value)
    assert "SIGNUP_CODE" in message
    assert problem in message
    assert ".env" in message
    assert "process environment" in message
    if candidate and candidate.strip():
        assert candidate not in message


def test_signup_code_comparison_is_exact_and_supports_unicode(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "ENV_FILE_PATH", tmp_path / "missing.env")
    monkeypatch.setenv("SIGNUP_CODE", "Invite-私-42")

    assert auth.signup_code_matches("Invite-私-42")
    assert not auth.signup_code_matches("invite-私-42")
    assert not auth.signup_code_matches("Invite-私-42 ")


@pytest.mark.parametrize(
    ("candidate", "problem"),
    [
        (None, "missing"),
        ("", "blank"),
        (" " * 32, "blank"),
        (f"{'x' * 32} ", "leading or trailing whitespace"),
        ("x" * 31, "shorter than 32 UTF-8 bytes"),
        (auth.FORMER_SECRET, "prohibited"),
        (auth.EXAMPLE_SECRET, "uses the example secret"),
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


def test_documented_signup_codes_use_only_the_rejected_placeholder():
    expected_assignment = f"SIGNUP_CODE={auth.EXAMPLE_SIGNUP_CODE}"
    for path in (ROOT_PATH / ".env.example", ROOT_PATH / "README.md"):
        documented_assignments = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("SIGNUP_CODE=")
        ]
        assert documented_assignments == [expected_assignment]


def test_jwt_encode_and_decode_refuse_invalid_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "ENV_FILE_PATH", tmp_path / "missing.env")
    monkeypatch.setenv("SECRET_KEY", "short")

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        auth.create_access_token({"sub": VALID_AUTH_SUBJECT})
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


def test_password_hashing_does_not_require_signup_configuration(tmp_path):
    missing_env = tmp_path / "missing.env"
    child_env = os.environ.copy()
    child_env.pop("SIGNUP_CODE", None)
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


@pytest.mark.parametrize(
    ("candidate", "problem"),
    [
        (None, "missing"),
        ("", "blank"),
        ("padded-code ", "leading or trailing whitespace"),
        (auth.EXAMPLE_SIGNUP_CODE, "uses the example signup code"),
    ],
)
def test_main_import_refuses_unsafe_signup_code_with_safe_message(
    tmp_path, candidate, problem
):
    missing_env = tmp_path / "missing.env"
    child_env = os.environ.copy()
    if candidate is None:
        child_env.pop("SIGNUP_CODE", None)
    else:
        child_env["SIGNUP_CODE"] = candidate
    configured_secret = child_env["SECRET_KEY"]
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
    assert "SIGNUP_CODE" in output
    assert problem in output
    assert "repository-root .env" in output
    assert configured_secret not in output
    if candidate and candidate.strip():
        assert candidate not in output


def _signup_payload(
    username: object = "Alice_1",
    password: object = "Password1",
    signup_code: object = VALID_SIGNUP_CODE,
) -> dict[str, object]:
    return {
        "username": username,
        "password": password,
        "signup_code": signup_code,
    }


def _database_rows(table: str) -> list[tuple]:
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        return conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()


def test_signup_creates_hashed_account_and_immediately_authenticates(client):
    response = client.post(
        "/api/signup",
        json=_signup_payload(username="  Alice_1  ", password="Password1"),
    )

    assert response.status_code == 201
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    token = response.json()["access_token"]
    payload = jwt.decode(
        token,
        auth.validate_auth_configuration(),
        algorithms=[auth.ALGORITHM],
    )
    assert set(payload) == {"sub", "exp", "token_version"}
    assert payload["token_version"] == 3
    assert type(payload["token_version"]) is int

    me_response = client.get("/api/me", headers=_bearer(token))
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "Alice_1"

    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        stored = conn.execute(
            "SELECT username, hashed_password FROM users WHERE auth_subject = ?",
            (payload["sub"],),
        ).fetchone()
    assert stored is not None
    assert stored[0] == "Alice_1"
    assert stored[1] != "Password1"
    assert auth.verify_password("Password1", stored[1])


@pytest.mark.parametrize("username", ["Ab1", f"A1{'a' * 30}", "A_b-c1"])
def test_signup_accepts_username_boundaries_and_allowed_characters(client, username):
    response = client.post("/api/signup", json=_signup_payload(username=username))

    assert response.status_code == 201
    assert client.get(
        "/api/me", headers=_bearer(response.json()["access_token"])
    ).json()["username"] == username


@pytest.mark.parametrize(
    "username",
    ["Ab", f"A1{'a' * 31}", "Ab 1", "Alïce1", "Ab.1", "Ab\n1"],
)
def test_signup_rejects_invalid_usernames_without_echoing_credentials(
    client, username, capsys
):
    password = "PrivatePassword1"
    before = _database_rows("users")
    capsys.readouterr()

    response = client.post(
        "/api/signup",
        json=_signup_payload(username=username, password=password),
    )

    captured = capsys.readouterr()
    assert response.status_code == 422
    assert "access_token" not in response.text
    assert password not in response.text
    assert password not in captured.out
    assert password not in captured.err
    assert _database_rows("users") == before


@pytest.mark.parametrize(
    "password",
    ["Abcdef1", "abcdefgh", "12345678", "秘密123456"],
)
def test_signup_rejects_invalid_passwords_without_echoing_them(client, password, capsys):
    before = _database_rows("users")
    capsys.readouterr()

    response = client.post("/api/signup", json=_signup_payload(password=password))

    captured = capsys.readouterr()
    assert response.status_code == 422
    assert "access_token" not in response.text
    assert password not in response.text
    assert password not in captured.out
    assert password not in captured.err
    assert _database_rows("users") == before


def test_signup_password_is_not_trimmed_or_mutated(client):
    password = " Valid123 "
    response = client.post("/api/signup", json=_signup_payload(password=password))

    assert response.status_code == 201
    assert client.post(
        "/token", data={"username": "alice_1", "password": password}
    ).status_code == 200
    assert client.post(
        "/token", data={"username": "alice_1", "password": password.strip()}
    ).status_code == 401


@pytest.mark.parametrize("missing_field", ["username", "password", "signup_code"])
def test_signup_requires_every_json_field(client, missing_field):
    payload = _signup_payload()
    del payload[missing_field]
    before = _database_rows("users")

    response = client.post("/api/signup", json=payload)

    assert response.status_code == 422
    assert _database_rows("users") == before


@pytest.mark.parametrize("field", ["username", "password", "signup_code"])
def test_signup_rejects_non_string_fields(client, field):
    payload = _signup_payload()
    payload[field] = 123
    before = _database_rows("users")

    response = client.post("/api/signup", json=payload)

    assert response.status_code == 422
    assert _database_rows("users") == before


@pytest.mark.parametrize("field", ["password", "signup_code"])
def test_signup_structural_validation_never_echoes_private_nested_values(
    client, field, capsys
):
    private_value = f"Private-{field}-Value1"
    payload = _signup_payload()
    payload[field] = {private_value: [private_value]}
    before = _database_rows("users")
    capsys.readouterr()

    response = client.post("/api/signup", json=payload)

    captured = capsys.readouterr()
    assert response.status_code == 422
    assert response.json()["detail"]
    assert private_value not in response.text
    assert private_value not in captured.out
    assert private_value not in captured.err
    assert _database_rows("users") == before


def test_signup_rejects_malformed_json_without_echoing_body(client, capsys):
    private_value = "Private-Malformed-Value1"
    before = _database_rows("users")
    capsys.readouterr()

    response = client.post(
        "/api/signup",
        content=f'{{"password":"{private_value}",'.encode(),
        headers={"content-type": "application/json"},
    )

    captured = capsys.readouterr()
    assert response.status_code == 422
    assert response.json()["detail"]
    assert private_value not in response.text
    assert private_value not in captured.out
    assert private_value not in captured.err
    assert _database_rows("users") == before


@pytest.mark.parametrize("submitted_code", ["", "wrong-code", VALID_SIGNUP_CODE.swapcase()])
def test_bad_signup_code_is_rejected_before_user_lookup(
    client, monkeypatch, submitted_code
):
    def unexpected_query(*_args, **_kwargs):
        raise AssertionError("username lookup must not run for an invalid signup code")

    monkeypatch.setattr(Session, "query", unexpected_query)

    response = client.post(
        "/api/signup",
        json=_signup_payload(username="user", signup_code=submitted_code),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signup code"}
    assert "access_token" not in response.text


def test_signup_duplicate_case_variants_share_one_identity_and_login(client):
    first_response = client.post(
        "/api/signup", json=_signup_payload(username="Alice")
    )
    assert first_response.status_code == 201
    original_identity = client.get(
        "/api/me", headers=_bearer(first_response.json()["access_token"])
    ).json()

    for username in ("Alice", "alice", "ALICE", "aLiCe"):
        response = client.post("/api/signup", json=_signup_payload(username=username))
        assert response.status_code == 409
        assert response.json() == {"detail": "Username already exists"}
        assert "access_token" not in response.text

    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        matching_users = conn.execute(
            "SELECT id, username FROM users WHERE username = ? COLLATE NOCASE",
            ("alice",),
        ).fetchall()
    assert matching_users == [(original_identity["id"], "Alice")]

    login_response = client.post(
        "/token", data={"username": "aLiCe", "password": "Password1"}
    )
    assert login_response.status_code == 200
    assert client.get(
        "/api/me", headers=_bearer(login_response.json()["access_token"])
    ).json() == original_identity


def test_overlapping_case_variant_signups_create_exactly_one_identity(
    client, monkeypatch
):
    barrier = threading.Barrier(2, timeout=10)
    original_first = Query.first

    def synchronized_first(query):
        result = original_first(query)
        barrier.wait()
        return result

    monkeypatch.setattr(Query, "first", synchronized_first)

    def submit(test_client, username):
        return test_client.post(
            "/api/signup", json=_signup_payload(username=username)
        )

    with TestClient(app) as second_client:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(submit, client, "ConcurrentAlice"),
                executor.submit(submit, second_client, "concurrentalice"),
            ]
            responses = [future.result(timeout=20) for future in futures]

    assert sorted(response.status_code for response in responses) == [201, 409]
    assert sum("access_token" in response.json() for response in responses) == 1
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        identities = conn.execute(
            "SELECT id, username FROM users WHERE username = ? COLLATE NOCASE",
            ("concurrentalice",),
        ).fetchall()
    assert len(identities) == 1


def test_signup_does_not_change_beer_run_memberships_entries_or_existing_users(client):
    before = {
        table: _database_rows(table)
        for table in ("beer_runs", "beer_run_members", "entries", "users")
    }

    response = client.post(
        "/api/signup", json=_signup_payload(username="New_User1")
    )

    assert response.status_code == 201
    assert _database_rows("beer_runs") == before["beer_runs"]
    assert _database_rows("beer_run_members") == before["beer_run_members"]
    assert _database_rows("entries") == before["entries"]
    assert _database_rows("users")[:-1] == before["users"]
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        membership_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM beer_run_members
            JOIN users ON users.id = beer_run_members.user_id
            WHERE users.username = ? COLLATE NOCASE
            """,
            ("new_user1",),
        ).fetchone()[0]
    assert membership_count == 0


def test_signup_commit_time_uniqueness_race_rolls_back_without_token(
    client, monkeypatch
):
    before = _database_rows("users")

    def conflicting_commit(_session):
        raise IntegrityError(
            "INSERT users",
            {},
            sqlite3.IntegrityError("UNIQUE constraint failed: users.username"),
        )

    monkeypatch.setattr(Session, "commit", conflicting_commit)

    response = client.post("/api/signup", json=_signup_payload(username="Race_User1"))

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}
    assert "access_token" not in response.text
    assert _database_rows("users") == before


def test_signup_unrelated_integrity_error_is_sanitized_500(client, monkeypatch):
    before = _database_rows("users")

    def unrelated_integrity_failure(_session):
        raise IntegrityError(
            "INSERT users",
            {},
            sqlite3.IntegrityError(
                "NOT NULL constraint failed: users.hashed_password"
            ),
        )

    monkeypatch.setattr(Session, "commit", unrelated_integrity_failure)

    response = client.post(
        "/api/signup", json=_signup_payload(username="Integrity_Failure1")
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create account"}
    assert "hashed_password" not in response.text
    assert "access_token" not in response.text
    assert _database_rows("users") == before


def test_signup_hashing_failure_is_sanitized_without_partial_user(
    client, monkeypatch, capsys
):
    password = "PrivatePassword1"
    before = _database_rows("users")

    def hashing_failure(_password):
        raise RuntimeError(f"do not expose {password}")

    monkeypatch.setattr(auth, "get_password_hash", hashing_failure)
    capsys.readouterr()

    response = client.post(
        "/api/signup",
        json=_signup_payload(username="Hash_Failure1", password=password),
    )

    captured = capsys.readouterr()
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create account"}
    assert password not in response.text
    assert password not in captured.out
    assert password not in captured.err
    assert _database_rows("users") == before


def test_signup_lookup_failure_is_sanitized_and_rolls_back(client, monkeypatch):
    before = _database_rows("users")

    def lookup_failure(*_args, **_kwargs):
        raise RuntimeError("private database diagnostics")

    monkeypatch.setattr(Session, "query", lookup_failure)

    response = client.post(
        "/api/signup", json=_signup_payload(username="Lookup_Failure1")
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create account"}
    assert "private database diagnostics" not in response.text
    assert _database_rows("users") == before


def test_signup_unexpected_failure_is_sanitized_and_rolled_back(
    client, monkeypatch, capsys
):
    username = "Failure_User1"
    password = "PrivatePassword1"
    signup_code = VALID_SIGNUP_CODE
    before = _database_rows("users")

    def token_failure(_data):
        raise RuntimeError(f"do not expose {username} {password} {signup_code}")

    monkeypatch.setattr(auth, "create_access_token", token_failure)
    capsys.readouterr()

    response = client.post(
        "/api/signup",
        json=_signup_payload(username=username, password=password),
    )

    captured = capsys.readouterr()
    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create account"}
    assert "access_token" not in response.text
    for secret_value in (username, password, signup_code):
        assert secret_value not in response.text
        assert secret_value not in captured.out
        assert secret_value not in captured.err
    assert _database_rows("users") == before


def test_login_is_case_insensitive_and_issues_versioned_auth_subject_token(client):
    response = client.post("/token", data={"username": "UsEr", "password": "password"})

    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert response.json()["token_type"] == "bearer"
    payload = jwt.decode(
        response.json()["access_token"],
        auth.validate_auth_configuration(),
        algorithms=[auth.ALGORITHM],
    )
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        expected_subject = conn.execute(
            "SELECT auth_subject FROM users WHERE id = 1"
        ).fetchone()[0]
    assert payload["sub"] == expected_subject
    assert len(payload["sub"]) == 43
    assert payload["token_version"] == 3
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
        {"sub": VALID_AUTH_SUBJECT, "token_version": 2.0},
        {"sub": VALID_AUTH_SUBJECT, "token_version": "3"},
        {"sub": VALID_AUTH_SUBJECT, "token_version": True},
        {"token_version": 3},
        {"sub": 1, "token_version": 3},
        {"sub": "user", "token_version": 3},
        {"sub": "A" * 42, "token_version": 3},
        {"sub": "A" * 44, "token_version": 3},
        {"sub": "!" * 43, "token_version": 3},
        {"sub": " " + "A" * 42, "token_version": 3},
        {"sub": "999999", "token_version": 3},
    ],
)
def test_invalid_identity_claims_share_generic_unauthorized_response(client, claims):
    response = client.get("/api/me", headers=_bearer(_signed_token(claims)))

    _assert_generic_unauthorized(response)


def test_missing_expiration_is_rejected_generically(client):
    token = _signed_token({"sub": VALID_AUTH_SUBJECT, "token_version": 3}, include_exp=False)

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


def test_expired_token_is_rejected_generically(client):
    token = jwt.encode(
        {
            "sub": VALID_AUTH_SUBJECT,
            "token_version": 3,
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
        {"sub": VALID_AUTH_SUBJECT, "token_version": 3},
        secret=secrets.token_urlsafe(32),
    )

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


@pytest.mark.parametrize("legacy_subject", ["user", "123"])
def test_legacy_username_tokens_are_rejected_without_fallback(client, legacy_subject):
    token = _signed_token({"sub": legacy_subject})

    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(token)))


def test_token_resolves_user_by_auth_subject_after_username_changes(client):
    login_response = client.post("/token", data={"username": "user", "password": "password"})
    token = login_response.json()["access_token"]
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        conn.execute("UPDATE users SET username = 'renamed' WHERE id = 1")

    response = client.get("/api/me", headers=_bearer(token))

    assert response.status_code == 200
    assert response.json() == {"username": "renamed", "id": 1}


def test_deleted_users_token_cannot_authenticate_reused_numeric_id(client):
    login_response = client.post(
        "/token", data={"username": "user", "password": "password"}
    )
    old_token = login_response.json()["access_token"]
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        old_subject, password_hash = conn.execute(
            "SELECT auth_subject, hashed_password FROM users WHERE id = 1"
        ).fetchone()
        conn.execute("DELETE FROM entries WHERE user_id = 1")
        conn.execute("DELETE FROM beer_run_members WHERE user_id = 1")
        conn.execute("DELETE FROM users WHERE id = 1")
        conn.execute(
            """
            INSERT INTO users (id, username, hashed_password, auth_subject)
            VALUES (1, 'replacement', ?, ?)
            """,
            (password_hash, "Z" * 43),
        )

    assert old_subject != "Z" * 43
    _assert_generic_unauthorized(client.get("/api/me", headers=_bearer(old_token)))


@pytest.mark.parametrize(
    "subject",
    [None, "user", "0", "A" * 42, "A" * 44, "!" * 43, " " + "A" * 42],
)
def test_access_token_creation_requires_canonical_auth_subject(subject):
    with pytest.raises(ValueError, match="subject"):
        auth.create_access_token({"sub": subject})


def test_protected_route_fail(client):
    beer_run_id = _beer_run_jpn_id()
    response = client.post(
        f"/api/beer-runs/{beer_run_id}/entries",
        data=_entry_form(),
    )
    assert response.status_code == 401


def test_protected_route_success(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]
    beer_run_id = _beer_run_jpn_id()

    response = client.post(
        f"/api/beer-runs/{beer_run_id}/entries",
        data=_entry_form(),
        headers=_bearer(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_protected_route_success_no_image(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]
    beer_run_id = _beer_run_jpn_id()

    response = client.post(
        f"/api/beer-runs/{beer_run_id}/entries",
        data=_entry_form(),
        headers=_bearer(token),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
