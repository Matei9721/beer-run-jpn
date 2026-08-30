"""Integration tests for owner beer-run deletion and upload safety."""

import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

import models


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_entry(
    db,
    user: models.User,
    beer_run: models.BeerRun,
    *,
    image_path: str | None = None,
) -> models.Entry:
    entry = models.Entry(
        drink_type="Beer",
        abv=5.0,
        quantity=0.5,
        latitude=35.0,
        longitude=139.0,
        image_path=image_path,
        user_id=user.id,
        beer_run_id=beer_run.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _canonical_path(beer_run_id: int, filename: str) -> str:
    return f"static/uploads/beer_runs/{beer_run_id}/{filename}"


def _physical_path(upload_root: Path, image_path: str) -> Path:
    return upload_root / Path(*image_path.split("/")[2:])


def _row_count(table: str, where: str = "", params: tuple = ()) -> int:
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        query = f'SELECT COUNT(*) FROM "{table}"'
        if where:
            query += f" WHERE {where}"
        return conn.execute(query, params).fetchone()[0]


class TestDeleteBeerRunSafety:
    def test_owner_delete_removes_owned_rows_and_files_but_preserves_other_run_data(
        self,
        client,
        owner_member_nonmember_run,
        tmp_path,
        monkeypatch,
    ):
        data = owner_member_nonmember_run
        target = data["private_run"]
        other = data["public_run"]
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(__import__("main"), "UPLOAD_ROOT", upload_root)

        owned_path = _canonical_path(
            target.id,
            "11111111-1111-4111-8111-111111111111.jpg",
        )
        shared_path = _canonical_path(
            target.id,
            "22222222-2222-4222-8222-222222222222.jpg",
        )
        owned_file = _physical_path(upload_root, owned_path)
        shared_file = _physical_path(upload_root, shared_path)
        owned_file.parent.mkdir(parents=True)
        owned_file.write_bytes(b"owned")
        shared_file.write_bytes(b"shared")

        _add_entry(data["db"], data["owner"], target, image_path=owned_path)
        _add_entry(data["db"], data["member"], target, image_path=shared_path)
        other_entry = _add_entry(
            data["db"], data["owner"], other, image_path=shared_path
        )
        invite = client.post(
            f"/api/beer-runs/{target.id}/invites",
            headers=_bearer(data["owner_token"]),
        )
        assert invite.status_code == 201

        response = client.delete(
            f"/api/beer-runs/{target.id}",
            headers=_bearer(data["owner_token"]),
        )

        assert response.status_code == 200
        assert response.json() == {"status": "deleted", "beer_run_id": target.id}
        assert client.get(
            f"/api/beer-runs/{target.id}",
            headers=_bearer(data["owner_token"]),
        ).status_code == 404
        assert client.get(f"/api/invites/{invite.json()['code']}").status_code == 404
        assert _row_count("beer_runs", "id = ?", (target.id,)) == 0
        assert _row_count("beer_run_members", "beer_run_id = ?", (target.id,)) == 0
        assert _row_count("beer_run_invites", "beer_run_id = ?", (target.id,)) == 0
        assert _row_count("entries", "beer_run_id = ?", (target.id,)) == 0
        assert _row_count("entries", "id = ?", (other_entry.id,)) == 1
        assert not owned_file.exists()
        assert shared_file.read_bytes() == b"shared"
        assert shared_file.parent.is_dir()

    def test_canonical_public_fallback_cannot_be_deleted(self, client):
        token = client.post(
            "/token",
            data={"username": "user", "password": "password"},
        ).json()["access_token"]
        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            user_id = conn.execute(
                "SELECT id FROM users WHERE username = 'user'"
            ).fetchone()[0]
            run_id = conn.execute(
                "SELECT id FROM beer_runs WHERE name = 'BeerRunJPN'"
            ).fetchone()[0]
            conn.execute(
                "UPDATE beer_run_members SET role = 'owner' "
                "WHERE beer_run_id = ? AND user_id = ?",
                (run_id, user_id),
            )

        response = client.delete(
            f"/api/beer-runs/{run_id}",
            headers=_bearer(token),
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "The canonical BeerRunJPN run cannot be deleted"
        }
        assert client.get(f"/api/beer-runs/{run_id}").status_code == 200

    @pytest.mark.parametrize(
        "stored_path,relative_path",
        [
            ("static/uploads/legacy.jpg", "legacy.jpg"),
            (
                r"static\uploads\beer_runs\{run_id}\33333333-3333-4333-8333-333333333333.jpg",
                "beer_runs/{run_id}/33333333-3333-4333-8333-333333333333.jpg",
            ),
            (
                "static/uploads/beer_runs/{run_id}/not-a-uuid.jpg",
                "beer_runs/{run_id}/not-a-uuid.jpg",
            ),
            (
                "static/uploads/beer_runs/{run_id}/44444444-4444-4444-8444-444444444444.jpg",
                None,
            ),
            (
                "static/uploads/beer_runs/{other_run}/55555555-5555-4555-8555-555555555555.jpg",
                "beer_runs/{other_run}/55555555-5555-4555-8555-555555555555.jpg",
            ),
        ],
    )
    def test_unproven_upload_paths_are_retained(
        self,
        client,
        owner_member_nonmember_run,
        tmp_path,
        monkeypatch,
        stored_path,
        relative_path,
    ):
        data = owner_member_nonmember_run
        target = data["private_run"]
        other = data["public_run"]
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(__import__("main"), "UPLOAD_ROOT", upload_root)
        stored_path = stored_path.format(run_id=target.id, other_run=other.id)

        if relative_path is None:
            outside = tmp_path / "missing.jpg"
            stored_path = stored_path
        else:
            relative = relative_path.format(run_id=target.id, other_run=other.id)
            physical = upload_root / Path(*relative.split("/"))
            physical.parent.mkdir(parents=True)
            physical.write_bytes(b"retain")
            outside = physical
        _add_entry(data["db"], data["owner"], target, image_path=stored_path)

        response = client.delete(
            f"/api/beer-runs/{target.id}",
            headers=_bearer(data["owner_token"]),
        )

        assert response.status_code == 200
        assert not (tmp_path / "missing.jpg").exists()
        if relative_path is not None:
            assert outside.read_bytes() == b"retain"

    def test_database_failure_rolls_back_before_file_cleanup(
        self,
        client,
        owner_member_nonmember_run,
        tmp_path,
        monkeypatch,
    ):
        data = owner_member_nonmember_run
        target = data["private_run"]
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(__import__("main"), "UPLOAD_ROOT", upload_root)
        image_path = _canonical_path(
            target.id,
            "66666666-6666-4666-8666-666666666666.jpg",
        )
        image_file = _physical_path(upload_root, image_path)
        image_file.parent.mkdir(parents=True)
        image_file.write_bytes(b"keep on rollback")
        entry = _add_entry(data["db"], data["owner"], target, image_path=image_path)

        def fail_commit(_session):
            raise RuntimeError("forced database failure")

        monkeypatch.setattr(Session, "commit", fail_commit)
        response = client.delete(
            f"/api/beer-runs/{target.id}",
            headers=_bearer(data["owner_token"]),
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to delete beer-run"}
        assert client.get(
            f"/api/beer-runs/{target.id}",
            headers=_bearer(data["owner_token"]),
        ).status_code == 200
        assert _row_count("entries", "id = ?", (entry.id,)) == 1
        assert image_file.read_bytes() == b"keep on rollback"

    def test_postcommit_file_failure_keeps_success_and_rows_consistent(
        self,
        client,
        owner_member_nonmember_run,
        tmp_path,
        monkeypatch,
    ):
        data = owner_member_nonmember_run
        target = data["private_run"]
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(__import__("main"), "UPLOAD_ROOT", upload_root)
        image_path = _canonical_path(
            target.id,
            "77777777-7777-4777-8777-777777777777.jpg",
        )
        image_file = _physical_path(upload_root, image_path)
        image_file.parent.mkdir(parents=True)
        image_file.write_bytes(b"orphan is safe")
        _add_entry(data["db"], data["owner"], target, image_path=image_path)

        original_unlink = Path.unlink

        def fail_owned_unlink(path, missing_ok=False):
            if path == image_file:
                raise OSError("forced cleanup failure")
            return original_unlink(path, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", fail_owned_unlink)
        response = client.delete(
            f"/api/beer-runs/{target.id}",
            headers=_bearer(data["owner_token"]),
        )

        assert response.status_code == 200
        assert _row_count("beer_runs", "id = ?", (target.id,)) == 0
        assert _row_count("entries", "beer_run_id = ?", (target.id,)) == 0
        assert image_file.read_bytes() == b"orphan is safe"
