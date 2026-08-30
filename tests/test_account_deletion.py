"""Account self-deletion integration and data-isolation coverage."""

import os
import sqlite3
from pathlib import Path

from sqlalchemy.orm import Session

import auth_routes
import legal
import models
from upload_cleanup import (
    OwnedRunUpload,
    QuarantineRestoreError,
    purge_quarantined_uploads,
    quarantine_uploads,
)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client, username="user", password="password") -> str:
    response = client.post("/token", data={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _count(table: str, where: str = "", params: tuple = ()) -> int:
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        sql = f'SELECT COUNT(*) FROM "{table}"'
        if where:
            sql += f" WHERE {where}"
        return conn.execute(sql, params).fetchone()[0]


def _set_upload_roots(monkeypatch, tmp_path):
    upload_root = tmp_path / "static" / "uploads"
    quarantine_root = tmp_path / "private-account-deletion"
    monkeypatch.setattr(auth_routes, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(
        auth_routes,
        "ACCOUNT_DELETION_QUARANTINE_ROOT",
        quarantine_root,
    )
    return upload_root, quarantine_root


def test_summary_and_confirmation_failures_preserve_session_and_data(client):
    token = _login(client)
    headers = _bearer(token)

    summary = client.get("/api/me/deletion-summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json() == {
        "entry_count": 0,
        "membership_count": 1,
        "owned_runs": [],
    }

    wrong_phrase = client.request(
        "DELETE",
        "/api/me",
        headers=headers,
        json={"password": "password", "confirmation": "delete"},
    )
    assert wrong_phrase.status_code == 422
    wrong_password = client.request(
        "DELETE",
        "/api/me",
        headers=headers,
        json={"password": "not-password", "confirmation": "DELETE MY ACCOUNT"},
    )
    assert wrong_password.status_code == 401
    assert client.get("/api/me", headers=headers).status_code == 200
    assert _count("users", "username = ?", ("user",)) == 1


def test_owned_runs_return_structured_conflict_without_changes(client):
    token = _login(client)
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        user_id = conn.execute("SELECT id FROM users WHERE username = 'user'").fetchone()[0]
        run_id, run_name = conn.execute(
            "SELECT id, name FROM beer_runs WHERE name = 'BeerRunJPN'"
        ).fetchone()
        conn.execute(
            "UPDATE beer_run_members SET role = 'owner' WHERE user_id = ? AND beer_run_id = ?",
            (user_id, run_id),
        )

    response = client.request(
        "DELETE",
        "/api/me",
        headers=_bearer(token),
        json={"password": "password", "confirmation": "DELETE MY ACCOUNT"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "owned_runs_block_deletion",
        "message": "Delete these runs first.",
        "owned_runs": [{"id": run_id, "name": run_name}],
    }
    assert client.get("/api/me", headers=_bearer(token)).status_code == 200


def test_success_removes_only_caller_rows_and_exclusive_photos(
    client, owner_member_nonmember_run, tmp_path, monkeypatch
):
    data = owner_member_nonmember_run
    user = data["member"]
    other = data["owner"]
    run = data["private_run"]
    user_id = user.id
    other_id = other.id
    run_id = run.id
    token = _login(client, user.username)
    upload_root, quarantine_root = _set_upload_roots(monkeypatch, tmp_path)

    own_path = f"static/uploads/beer_runs/{run.id}/11111111-1111-4111-8111-111111111111.jpg"
    shared_path = f"static/uploads/beer_runs/{run.id}/22222222-2222-4222-8222-222222222222.jpg"
    own_file = upload_root / "beer_runs" / str(run.id) / own_path.rsplit("/", 1)[-1]
    shared_file = upload_root / "beer_runs" / str(run.id) / shared_path.rsplit("/", 1)[-1]
    own_file.parent.mkdir(parents=True)
    own_file.write_bytes(b"personal")
    shared_file.write_bytes(b"shared")
    data["db"].add_all([
        models.Entry(drink_type="Beer", abv=5, quantity=.5, latitude=1, longitude=1, image_path=own_path, user_id=user.id, beer_run_id=run.id),
        models.Entry(drink_type="Beer", abv=5, quantity=.5, latitude=1, longitude=1, image_path=shared_path, user_id=user.id, beer_run_id=run.id),
        models.Entry(drink_type="Beer", abv=5, quantity=.5, latitude=1, longitude=1, image_path=shared_path, user_id=other.id, beer_run_id=run.id),
        models.TermsAcceptance(user_id=user.id, terms_version=legal.TERMS_VERSION, accepted_at=legal.utc_now()),
        models.TermsAcceptance(user_id=other.id, terms_version=legal.TERMS_VERSION, accepted_at=legal.utc_now()),
    ])
    data["db"].commit()
    assert _count("terms_acceptances", "user_id = ?", (user_id,)) == 1
    assert _count("terms_acceptances", "user_id = ?", (other_id,)) == 1

    response = client.request(
        "DELETE",
        "/api/me",
        headers=_bearer(token),
        json={"password": "password", "confirmation": "DELETE MY ACCOUNT"},
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert client.get("/api/me", headers=_bearer(token)).status_code == 401
    assert _count("users", "id = ?", (user_id,)) == 0
    assert _count("entries", "user_id = ?", (user_id,)) == 0
    assert _count("beer_run_members", "user_id = ?", (user_id,)) == 0
    assert _count("terms_acceptances", "user_id = ?", (user_id,)) == 0
    assert _count("users", "id = ?", (other_id,)) == 1
    assert _count("terms_acceptances", "user_id = ?", (other_id,)) == 1
    assert _count("beer_runs", "id = ?", (run_id,)) == 1
    assert not own_file.exists()
    assert shared_file.read_bytes() == b"shared"
    assert not quarantine_root.exists()


def test_database_failure_restores_photo_and_account(
    client, owner_member_nonmember_run, tmp_path, monkeypatch
):
    data = owner_member_nonmember_run
    user = data["member"]
    run = data["private_run"]
    token = _login(client, user.username)
    upload_root, quarantine_root = _set_upload_roots(monkeypatch, tmp_path)
    image_path = f"static/uploads/beer_runs/{run.id}/33333333-3333-4333-8333-333333333333.jpg"
    image_file = upload_root / "beer_runs" / str(run.id) / image_path.rsplit("/", 1)[-1]
    image_file.parent.mkdir(parents=True)
    image_file.write_bytes(b"restore")
    data["db"].add(models.Entry(drink_type="Beer", abv=5, quantity=.5, latitude=1, longitude=1, image_path=image_path, user_id=user.id, beer_run_id=run.id))
    data["db"].commit()

    monkeypatch.setattr(Session, "commit", lambda _session: (_ for _ in ()).throw(RuntimeError("forced")))
    response = client.request(
        "DELETE",
        "/api/me",
        headers=_bearer(token),
        json={"password": "password", "confirmation": "DELETE MY ACCOUNT"},
    )
    assert response.status_code == 500
    assert image_file.read_bytes() == b"restore"
    assert _count("users", "id = ?", (user.id,)) == 1
    assert not quarantine_root.exists()


def test_deletion_locks_before_rechecking_ownership_and_collecting_uploads(
    client, owner_member_nonmember_run, tmp_path, monkeypatch
):
    data = owner_member_nonmember_run
    user = data["member"]
    token = _login(client, user.username)
    _set_upload_roots(monkeypatch, tmp_path)
    calls = []
    original_begin = auth_routes._begin_account_deletion
    original_owned_runs = auth_routes._owned_runs
    original_collect = auth_routes.collect_user_uploads

    def record_begin(db):
        calls.append("begin")
        return original_begin(db)

    def record_owned_runs(db, user_id):
        calls.append("owners")
        return original_owned_runs(db, user_id)

    def record_collect(db, user_id, **kwargs):
        calls.append("uploads")
        return original_collect(db, user_id, **kwargs)

    monkeypatch.setattr(auth_routes, "_begin_account_deletion", record_begin)
    monkeypatch.setattr(auth_routes, "_owned_runs", record_owned_runs)
    monkeypatch.setattr(auth_routes, "collect_user_uploads", record_collect)

    response = client.request(
        "DELETE",
        "/api/me",
        headers=_bearer(token),
        json={"password": "password", "confirmation": "DELETE MY ACCOUNT"},
    )

    assert response.status_code == 200
    assert calls == ["begin", "owners", "uploads"]


def test_quarantine_is_private_and_purge_removes_the_operation(tmp_path):
    upload_root = tmp_path / "static" / "uploads"
    quarantine_root = tmp_path / "private-account-deletion"
    photo = upload_root / "beer_runs" / "4" / "11111111-1111-4111-8111-111111111111.jpg"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"private")

    operation = quarantine_uploads(
        (OwnedRunUpload("static/uploads/beer_runs/4/11111111-1111-4111-8111-111111111111.jpg", photo),),
        upload_root=upload_root,
        quarantine_root=quarantine_root,
    )

    assert operation is not None
    assert not operation.operation_root.is_relative_to(tmp_path / "static")
    assert (operation.operation_root / "manifest.json").is_file()
    assert not photo.exists()

    purge_quarantined_uploads(operation)
    assert not quarantine_root.exists()


def test_partial_move_failure_preserves_recovery_manifest(
    tmp_path, monkeypatch
):
    upload_root = tmp_path / "static" / "uploads"
    quarantine_root = tmp_path / "private-account-deletion"
    first = upload_root / "beer_runs" / "4" / "11111111-1111-4111-8111-111111111111.jpg"
    second = upload_root / "beer_runs" / "4" / "22222222-2222-4222-8222-222222222222.jpg"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    original_replace = Path.replace

    def fail_second_move_and_restore(path, target):
        if path == second or (
            path.suffix == ".jpg" and path.is_relative_to(quarantine_root)
        ):
            raise OSError("forced move failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_second_move_and_restore)

    try:
        quarantine_uploads(
            (
                OwnedRunUpload("first", first),
                OwnedRunUpload("second", second),
            ),
            upload_root=upload_root,
            quarantine_root=quarantine_root,
        )
    except QuarantineRestoreError as exc:
        operation = exc.operation
    else:
        raise AssertionError("Expected quarantine restoration to fail")

    assert len(operation.uploads) == 1
    assert (operation.operation_root / "manifest.json").is_file()
    assert operation.uploads[0].quarantine_path.is_file()
    assert not first.exists()
    assert second.is_file()


def test_persistent_restore_failure_is_reported_as_recovery_pending(
    client, owner_member_nonmember_run, tmp_path, monkeypatch
):
    data = owner_member_nonmember_run
    user = data["member"]
    run = data["private_run"]
    token = _login(client, user.username)
    upload_root, quarantine_root = _set_upload_roots(monkeypatch, tmp_path)
    image_path = f"static/uploads/beer_runs/{run.id}/44444444-4444-4444-8444-444444444444.jpg"
    image_file = upload_root / "beer_runs" / str(run.id) / image_path.rsplit("/", 1)[-1]
    image_file.parent.mkdir(parents=True)
    image_file.write_bytes(b"recoverable")
    data["db"].add(models.Entry(
        drink_type="Beer", abv=5, quantity=.5, latitude=1, longitude=1,
        image_path=image_path, user_id=user.id, beer_run_id=run.id,
    ))
    data["db"].commit()
    original_replace = Path.replace

    def fail_restore(path, target):
        if path.suffix == ".jpg" and path.is_relative_to(quarantine_root):
            raise OSError("forced persistent restore failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_restore)
    monkeypatch.setattr(
        Session,
        "commit",
        lambda _session: (_ for _ in ()).throw(RuntimeError("forced database failure")),
    )

    response = client.request(
        "DELETE",
        "/api/me",
        headers=_bearer(token),
        json={"password": "password", "confirmation": "DELETE MY ACCOUNT"},
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Unable to delete account; photo recovery is pending"
    }
    assert _count("users", "id = ?", (user.id,)) == 1
    assert not image_file.exists()
    assert len(list(quarantine_root.glob("*/manifest.json"))) == 1
    assert len(list(quarantine_root.glob("*/*.jpg"))) == 1
