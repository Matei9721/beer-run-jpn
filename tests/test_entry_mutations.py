"""Focused coverage for owner-scoped entry updates and deletion.

Every database request uses the isolated test override. Every filesystem case
redirects the upload root to ``tmp_path`` so repository uploads remain untouched.
"""

from __future__ import annotations

import io
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy import event
from sqlalchemy.orm import Session

import auth
import main
import models


EXPECTED_ENTRY_FIELDS = {
    "id",
    "username",
    "drink_type",
    "abv",
    "quantity",
    "brand",
    "latitude",
    "longitude",
    "image_path",
    "timestamp",
    "timezone",
    "timezone_code",
}
MISSING_RUN_ID = 99999


def _bearer(user) -> dict[str, str]:
    token = auth.create_access_token({"sub": user.auth_subject})
    return {"Authorization": f"Bearer {token}"}


def _add_entry(
    db,
    user,
    run,
    *,
    drink_type="Beer",
    abv=5.0,
    quantity=0.5,
    brand="Original",
    latitude=35.0,
    longitude=139.0,
    image_path=None,
    timestamp=None,
    timezone="Asia/Tokyo",
    timezone_code="JST",
):
    entry = models.Entry(
        drink_type=drink_type,
        abv=abv,
        quantity=quantity,
        brand=brand,
        latitude=latitude,
        longitude=longitude,
        image_path=image_path,
        timestamp=timestamp or datetime(2026, 8, 23, 12, 34, 56),
        timezone=timezone,
        timezone_code=timezone_code,
        user_id=user.id,
        beer_run_id=run.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _multipart_parts(fields=None, image=None):
    parts = []
    for key, value in (fields or {}).items():
        parts.append((key, (None, value)))
    if image is not None:
        parts.append(("image", image))
    return parts


def _patch(client, run_id, entry_id, user, *, fields=None, image=None):
    return client.patch(
        f"/api/beer-runs/{run_id}/entries/{entry_id}",
        files=_multipart_parts(fields, image),
        headers=_bearer(user),
    )


def _row(entry_id: int):
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()


def _entry_count(entry_id: int) -> int:
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM entries WHERE id = ?", (entry_id,)
        ).fetchone()[0]


def _jpeg_bytes(*, size=(20, 10), mode="RGB", image_format="JPEG") -> bytes:
    buffer = io.BytesIO()
    color = (200, 10, 10, 128) if mode == "RGBA" else "red"
    Image.new(mode, size, color=color).save(buffer, image_format)
    return buffer.getvalue()


def _canonical_path(run_id: int, value="11111111-1111-4111-8111-111111111111"):
    return f"static/uploads/beer_runs/{run_id}/{value}.jpg"


def _physical_path(upload_root: Path, app_path: str) -> Path:
    relative = Path(*app_path.split("/")[2:])
    return upload_root / relative


class TestAuthorizationAndAddressing:
    @pytest.mark.parametrize("run_key", ("public_run", "private_run"))
    @pytest.mark.parametrize("user_key", ("owner", "member"))
    def test_owner_and_member_can_patch_their_own_entry(
        self, client, owner_member_nonmember_run, run_key, user_key
    ):
        data = owner_member_nonmember_run
        run = data[run_key]
        user = data[user_key]
        entry = _add_entry(data["db"], user, run)

        response = _patch(
            client, run.id, entry.id, user, fields={"brand": "Corrected"}
        )

        assert response.status_code == 200
        assert response.json()["brand"] == "Corrected"

    @pytest.mark.parametrize("run_key", ("public_run", "private_run"))
    @pytest.mark.parametrize("user_key", ("owner", "member"))
    def test_owner_and_member_can_delete_their_own_entry(
        self, client, owner_member_nonmember_run, run_key, user_key
    ):
        data = owner_member_nonmember_run
        run = data[run_key]
        user = data[user_key]
        entry = _add_entry(data["db"], user, run)

        response = client.delete(
            f"/api/beer-runs/{run.id}/entries/{entry.id}", headers=_bearer(user)
        )

        assert response.status_code == 200
        assert response.json() == {"status": "deleted", "entry_id": entry.id}
        assert _entry_count(entry.id) == 0
        repeated = client.delete(
            f"/api/beer-runs/{run.id}/entries/{entry.id}", headers=_bearer(user)
        )
        assert repeated.status_code == 404
        assert repeated.json() == {"detail": "Entry not found"}

    @pytest.mark.parametrize("method", ("PATCH", "DELETE"))
    @pytest.mark.parametrize("authorization", (None, "Bearer invalid.token.value"))
    def test_missing_and_invalid_auth_are_challenged_before_body_work(
        self, client, owner_member_nonmember_run, method, authorization
    ):
        run = owner_member_nonmember_run["public_run"]
        headers = {
            "Content-Type": "multipart/form-data; boundary=broken",
        }
        if authorization is not None:
            headers["Authorization"] = authorization

        response = client.request(
            method,
            f"/api/beer-runs/{run.id}/entries/1",
            content=b"malformed multipart bytes",
            headers=headers,
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Could not validate credentials"}
        assert response.headers["www-authenticate"] == "Bearer"

    @pytest.mark.parametrize("method", ("PATCH", "DELETE"))
    def test_nonmember_and_missing_run_are_concealed(
        self, client, owner_member_nonmember_run, method
    ):
        data = owner_member_nonmember_run
        malformed_headers = _bearer(data["non_member"])
        malformed_headers["Content-Type"] = "multipart/form-data; boundary=broken"
        public = client.request(
            method,
            f"/api/beer-runs/{data['public_run'].id}/entries/1",
            content=b"broken",
            headers=malformed_headers,
        )
        missing_headers = _bearer(data["member"])
        missing_headers["Content-Type"] = "multipart/form-data; boundary=broken"
        missing = client.request(
            method,
            f"/api/beer-runs/{MISSING_RUN_ID}/entries/1",
            content=b"broken",
            headers=missing_headers,
        )

        assert public.status_code == missing.status_code == 404
        assert public.json() == missing.json() == {"detail": "Beer-run not found"}

    @pytest.mark.parametrize("method", ("PATCH", "DELETE"))
    @pytest.mark.parametrize("case", ("missing", "negative", "wrong_run", "other_user"))
    @pytest.mark.parametrize("caller_key", ("owner", "member"))
    def test_entry_scope_failures_are_identical(
        self, client, owner_member_nonmember_run, method, case, caller_key
    ):
        data = owner_member_nonmember_run
        caller = data[caller_key]
        target_id = MISSING_RUN_ID
        if case == "negative":
            target_id = -1
        elif case == "wrong_run":
            target_id = _add_entry(data["db"], caller, data["private_run"]).id
        elif case == "other_user":
            other = data["member"] if caller_key == "owner" else data["owner"]
            target_id = _add_entry(data["db"], other, data["public_run"]).id

        url = f"/api/beer-runs/{data['public_run'].id}/entries/{target_id}"
        if method == "PATCH":
            response = client.patch(
                url,
                content=b"broken",
                headers={
                    **_bearer(caller),
                    "Content-Type": "multipart/form-data; boundary=broken",
                },
            )
        else:
            response = client.delete(url, headers=_bearer(caller))

        assert response.status_code == 404
        assert response.json() == {"detail": "Entry not found"}

    @pytest.mark.parametrize("method", ("PATCH", "DELETE"))
    def test_non_integer_entry_id_uses_standard_validation(
        self, client, owner_member_nonmember_run, method
    ):
        data = owner_member_nonmember_run
        response = client.request(
            method,
            f"/api/beer-runs/{data['public_run'].id}/entries/not-an-integer",
            headers=_bearer(data["member"]),
        )
        assert response.status_code == 422

    def test_patch_performs_one_ownership_scoped_entry_lookup(
        self, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        entry = _add_entry(data["db"], data["member"], data["public_run"])
        bind = data["db"].get_bind()
        entry_selects = []

        def _record(conn, cursor, statement, parameters, context, executemany):
            normalized = " ".join(statement.lower().split())
            if normalized.startswith("select") and " from entries" in normalized:
                entry_selects.append(normalized)

        event.listen(bind, "before_cursor_execute", _record)
        try:
            response = _patch(
                client,
                data["public_run"].id,
                entry.id,
                data["member"],
                fields={"brand": "One lookup"},
            )
        finally:
            event.remove(bind, "before_cursor_execute", _record)

        assert response.status_code == 200
        assert len(entry_selects) == 1
        assert "entries.id = ?" in entry_selects[0]
        assert "entries.beer_run_id = ?" in entry_selects[0]
        assert "entries.user_id = ?" in entry_selects[0]


class TestPartialUpdateContract:
    @pytest.mark.parametrize(
        "fields,column,expected",
        [
            ({"drink_type": "Sake"}, "drink_type", "Sake"),
            ({"abv": "13.5"}, "abv", 13.5),
            ({"quantity": "0.72"}, "quantity", 0.72),
            ({"brand": "New Brand"}, "brand", "New Brand"),
            ({"brand": ""}, "brand", None),
            ({"client_timezone": "Europe/Amsterdam"}, "timezone", "Europe/Amsterdam"),
            ({"client_timezone": ""}, "timezone", None),
            ({"client_timezone_code": "CEST"}, "timezone_code", "CEST"),
            ({"client_timezone_code": ""}, "timezone_code", None),
        ],
    )
    def test_each_scalar_field_updates_without_changing_omitted_values(
        self, client, owner_member_nonmember_run, fields, column, expected
    ):
        data = owner_member_nonmember_run
        entry = _add_entry(data["db"], data["member"], data["public_run"])
        before = dict(_row(entry.id))

        response = _patch(
            client, data["public_run"].id, entry.id, data["member"], fields=fields
        )

        assert response.status_code == 200
        after = dict(_row(entry.id))
        assert after[column] == expected
        for immutable in ("id", "user_id", "beer_run_id", "timestamp"):
            assert after[immutable] == before[immutable]
        unchanged = {
            "drink_type",
            "abv",
            "quantity",
            "brand",
            "latitude",
            "longitude",
            "timezone",
            "timezone_code",
        } - {column}
        for field_name in unchanged:
            assert after[field_name] == before[field_name]

    def test_coordinate_pair_and_timezone_update_preserve_timestamp(
        self, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        entry = _add_entry(data["db"], data["member"], data["public_run"])
        before_timestamp = _row(entry.id)["timestamp"]

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={
                "latitude": "52.3676",
                "longitude": "4.9041",
                "client_timezone": "Europe/Amsterdam",
                "client_timezone_code": "CEST",
            },
        )

        assert response.status_code == 200
        row = _row(entry.id)
        assert row["latitude"] == 52.3676
        assert row["longitude"] == 4.9041
        assert row["timezone"] == "Europe/Amsterdam"
        assert row["timezone_code"] == "CEST"
        assert row["timestamp"] == before_timestamp

    def test_spoofed_immutable_fields_are_ignored_alongside_valid_edit(
        self, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        entry = _add_entry(
            data["db"],
            data["member"],
            data["public_run"],
            image_path="static/uploads/legacy.jpg",
        )
        before = dict(_row(entry.id))

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={
                "quantity": "1.0",
                "id": "999",
                "user_id": str(data["owner"].id),
                "beer_run_id": str(data["private_run"].id),
                "username": data["owner"].username,
                "timestamp": "2030-01-01T00:00:00",
                "client_timestamp": "2030-01-01T00:00:00",
                "image_path": "static/uploads/attacker.jpg",
            },
        )

        assert response.status_code == 200
        after = dict(_row(entry.id))
        assert after["quantity"] == 1.0
        for field_name in ("id", "user_id", "beer_run_id", "timestamp", "image_path"):
            assert after[field_name] == before[field_name]

    def test_patch_response_is_exact_existing_contract_and_normalizes_only_output(
        self, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        legacy_path = r"static\uploads\legacy.jpg"
        entry = _add_entry(
            data["db"],
            data["member"],
            data["public_run"],
            image_path=legacy_path,
        )

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"brand": "Serialized"},
        )

        assert response.status_code == 200
        assert set(response.json()) == EXPECTED_ENTRY_FIELDS
        assert response.json()["image_path"] == "static/uploads/legacy.jpg"
        assert _row(entry.id)["image_path"] == legacy_path
        get_response = client.get(
            f"/api/beer-runs/{data['public_run'].id}/entries"
        )
        assert get_response.status_code == 200
        assert get_response.json()[0] == response.json()

    @pytest.mark.parametrize(
        "fields",
        [
            {"id": "10", "user_id": "20", "timestamp": "2030-01-01"},
            {"photo_action": "keep"},
            {"photo_action": "unknown"},
            {"latitude": "1.0"},
            {"longitude": "1.0"},
            {"latitude": "", "longitude": "2.0"},
            {"drink_type": ""},
            {"abv": "not-a-number"},
            {"quantity": ""},
        ],
    )
    def test_empty_and_invalid_edit_contracts_return_422_without_change(
        self, client, owner_member_nonmember_run, fields
    ):
        data = owner_member_nonmember_run
        entry = _add_entry(
            data["db"],
            data["member"],
            data["public_run"],
            timezone=None if "client_timezone" in fields else "Asia/Tokyo",
        )
        before = dict(_row(entry.id))

        response = _patch(
            client, data["public_run"].id, entry.id, data["member"], fields=fields
        )

        assert response.status_code == 422
        assert dict(_row(entry.id)) == before

    def test_non_multipart_and_empty_multipart_are_rejected(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        entry = _add_entry(data["db"], data["member"], data["public_run"])
        url = f"/api/beer-runs/{data['public_run'].id}/entries/{entry.id}"

        encoded = client.patch(url, data={"brand": "Wrong encoding"}, headers=_bearer(data["member"]))
        empty = client.patch(
            url,
            content=b"--empty--\r\n",
            headers={
                **_bearer(data["member"]),
                "Content-Type": "multipart/form-data; boundary=empty",
            },
        )

        assert encoded.status_code == 422
        assert empty.status_code == 422


class TestPhotoOperations:
    def test_default_keep_retains_photo_and_explicit_keep_rejects_upload(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )

        kept = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"brand": "Kept"},
        )
        contradictory = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "keep"},
            image=("new.jpg", _jpeg_bytes(), "image/jpeg"),
        )

        assert kept.status_code == 200
        assert kept.json()["image_path"] == old_path
        assert contradictory.status_code == 422
        assert _row(entry.id)["image_path"] == old_path
        assert old_file.read_bytes() == b"old"

    def test_replace_normalizes_new_image_and_removes_unique_old_file(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=(
                "../../hostile.png",
                _jpeg_bytes(size=(1200, 600), mode="RGBA", image_format="PNG"),
                "image/png",
            ),
        )

        assert response.status_code == 200
        new_path = response.json()["image_path"]
        prefix = f"static/uploads/beer_runs/{data['public_run'].id}/"
        assert new_path.startswith(prefix) and new_path.endswith(".jpg")
        UUID(new_path.removeprefix(prefix).removesuffix(".jpg"))
        assert "hostile" not in new_path
        new_file = _physical_path(upload_root, new_path)
        with Image.open(new_file) as stored:
            assert stored.format == "JPEG"
            assert stored.mode == "RGB"
            assert stored.size == (1080, 540)
        assert not old_file.exists()
        assert _row(entry.id)["image_path"] == new_path

    def test_remove_clears_reference_and_removes_unique_old_file(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "remove"},
        )

        assert response.status_code == 200
        assert response.json()["image_path"] is None
        assert _row(entry.id)["image_path"] is None
        assert not old_file.exists()

    @pytest.mark.parametrize(
        "fields,image",
        [
            ({"photo_action": "replace"}, None),
            ({"photo_action": "replace"}, ("empty.jpg", b"", "image/jpeg")),
            ({"photo_action": "replace"}, ("", _jpeg_bytes(), "image/jpeg")),
            ({"photo_action": "remove"}, ("new.jpg", _jpeg_bytes(), "image/jpeg")),
        ],
    )
    def test_invalid_photo_combinations_allocate_nothing(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch, fields, image
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        entry = _add_entry(data["db"], data["member"], data["public_run"])

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields=fields,
            image=image,
        )

        assert response.status_code == 422
        assert _row(entry.id)["image_path"] is None
        assert not upload_root.exists()

    def test_remove_without_current_photo_is_empty_unless_a_scalar_changes(
        self, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        entry = _add_entry(data["db"], data["member"], data["public_run"])

        empty = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "remove"},
        )
        with_scalar = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "remove", "brand": "Changed"},
        )

        assert empty.status_code == 422
        assert with_scalar.status_code == 200
        assert with_scalar.json()["brand"] == "Changed"

    def test_zero_byte_upload_is_ignored_for_keep_with_a_scalar_edit(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        entry = _add_entry(data["db"], data["member"], data["public_run"])

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"brand": "No image", "photo_action": "keep"},
            image=("empty.jpg", b"", "image/jpeg"),
        )

        assert response.status_code == 200
        assert response.json()["brand"] == "No image"
        assert response.json()["image_path"] is None
        assert not upload_root.exists()

    def test_writer_failure_is_sanitized_without_changing_the_entry(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        entry = _add_entry(data["db"], data["member"], data["public_run"])

        def _fail_writer(contents, beer_run_id):
            raise OSError(r"secret writer path C:\private\replacement.jpg")

        monkeypatch.setattr(main, "write_upload_image", _fail_writer)
        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=("new.jpg", _jpeg_bytes(), "image/jpeg"),
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to update entry"}
        assert "private" not in response.text
        assert _row(entry.id)["image_path"] is None

    def test_invalid_image_and_uuid_exhaustion_are_sanitized(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        entry = _add_entry(data["db"], data["member"], data["public_run"])

        invalid = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=("broken.jpg", b"not an image", "image/jpeg"),
        )
        assert invalid.status_code == 500
        assert invalid.json() == {"detail": "Unable to update entry"}
        assert _row(entry.id)["image_path"] is None

        fixed = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        run_dir = upload_root / "beer_runs" / str(data["public_run"].id)
        run_dir.mkdir(parents=True, exist_ok=True)
        sentinel = run_dir / f"{fixed}.jpg"
        sentinel.write_bytes(b"sentinel")
        monkeypatch.setattr(main, "uuid4", lambda: fixed)
        monkeypatch.setattr(main, "UPLOAD_ALLOCATION_ATTEMPTS", 1)
        exhausted = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=("valid.jpg", _jpeg_bytes(), "image/jpeg"),
        )
        assert exhausted.status_code == 500
        assert exhausted.json() == {"detail": "Unable to update entry"}
        assert sentinel.read_bytes() == b"sentinel"
        assert list(run_dir.iterdir()) == [sentinel]


class TestTransactionBoundaries:
    def test_update_flush_failure_rolls_back_and_removes_new_upload(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )
        bind = data["db"].get_bind()

        def _fail_update(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("UPDATE"):
                raise RuntimeError(r"secret update path C:\private\entry.jpg")

        event.listen(bind, "before_cursor_execute", _fail_update)
        try:
            response = _patch(
                client,
                data["public_run"].id,
                entry.id,
                data["member"],
                fields={"brand": "Never", "photo_action": "replace"},
                image=("new.jpg", _jpeg_bytes(), "image/jpeg"),
            )
        finally:
            event.remove(bind, "before_cursor_execute", _fail_update)

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to update entry"}
        assert "private" not in response.text
        assert _row(entry.id)["brand"] == "Original"
        assert _row(entry.id)["image_path"] == old_path
        assert old_file.read_bytes() == b"old"
        assert list(old_file.parent.iterdir()) == [old_file]

    def test_commit_failure_after_replacement_removes_only_new_upload(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )

        def _broken_commit(_session):
            raise RuntimeError("forced commit failure")

        monkeypatch.setattr(Session, "commit", _broken_commit)
        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=("new.jpg", _jpeg_bytes(), "image/jpeg"),
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to update entry"}
        assert _row(entry.id)["image_path"] == old_path
        assert old_file.read_bytes() == b"old"
        assert list(old_file.parent.iterdir()) == [old_file]

    def test_new_upload_cleanup_failure_does_not_replace_database_error(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        entry = _add_entry(data["db"], data["member"], data["public_run"])
        monkeypatch.setattr(
            main,
            "_prepare_entry_response",
            lambda entry, username: (_ for _ in ()).throw(RuntimeError("database response")),
        )
        monkeypatch.setattr(
            main,
            "cleanup_owned_upload",
            lambda upload: (_ for _ in ()).throw(OSError(r"C:\secret\new.jpg")),
        )

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=("new.jpg", _jpeg_bytes(), "image/jpeg"),
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to update entry"}
        assert "secret" not in response.text
        assert _row(entry.id)["image_path"] is None
        assert len(list(upload_root.rglob("*.jpg"))) == 1

    @pytest.mark.parametrize("method", ("PATCH", "DELETE"))
    def test_commit_failure_rolls_back_row_and_preserves_old_file(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch, method
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )

        def _broken_commit(_session):
            raise RuntimeError("SQLITE SECRET COMMIT")

        monkeypatch.setattr(Session, "commit", _broken_commit)
        if method == "PATCH":
            response = _patch(
                client,
                data["public_run"].id,
                entry.id,
                data["member"],
                fields={"brand": "Never"},
            )
            expected = "Unable to update entry"
        else:
            response = client.delete(
                f"/api/beer-runs/{data['public_run'].id}/entries/{entry.id}",
                headers=_bearer(data["member"]),
            )
            expected = "Unable to delete entry"

        assert response.status_code == 500
        assert response.json() == {"detail": expected}
        assert "SQLITE" not in response.text
        assert _entry_count(entry.id) == 1
        assert _row(entry.id)["brand"] == "Original"
        assert old_file.read_bytes() == b"old"

    def test_response_preparation_failure_rolls_back_and_removes_replacement(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )
        monkeypatch.setattr(
            main,
            "_prepare_entry_response",
            lambda entry, username: (_ for _ in ()).throw(RuntimeError("secret response")),
        )

        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "replace"},
            image=("new.jpg", _jpeg_bytes(), "image/jpeg"),
        )

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to update entry"}
        assert _row(entry.id)["image_path"] == old_path
        assert old_file.read_bytes() == b"old"
        assert list(old_file.parent.iterdir()) == [old_file]

    @pytest.mark.parametrize("method", ("PATCH", "DELETE"))
    def test_postcommit_cleanup_failure_keeps_success_final(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch, method
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )
        monkeypatch.setattr(
            main,
            "_cleanup_persisted_upload",
            lambda *args: (_ for _ in ()).throw(OSError(r"C:\secret\old.jpg")),
        )

        if method == "PATCH":
            response = _patch(
                client,
                data["public_run"].id,
                entry.id,
                data["member"],
                fields={"photo_action": "remove"},
            )
            assert response.status_code == 200
            assert _row(entry.id)["image_path"] is None
        else:
            response = client.delete(
                f"/api/beer-runs/{data['public_run'].id}/entries/{entry.id}",
                headers=_bearer(data["member"]),
            )
            assert response.status_code == 200
            assert _entry_count(entry.id) == 0
        assert "secret" not in response.text
        assert old_file.read_bytes() == b"old"

    def test_old_file_unlink_failure_keeps_committed_success(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        old_path = _canonical_path(data["public_run"].id)
        old_file = _physical_path(upload_root, old_path)
        old_file.parent.mkdir(parents=True)
        old_file.write_bytes(b"old")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=old_path
        )
        original_unlink = Path.unlink

        def _fail_old_unlink(path, missing_ok=False):
            if path == old_file.resolve():
                raise PermissionError(r"secret locked path C:\uploads\old.jpg")
            return original_unlink(path, missing_ok=missing_ok)

        monkeypatch.setattr(Path, "unlink", _fail_old_unlink)
        response = _patch(
            client,
            data["public_run"].id,
            entry.id,
            data["member"],
            fields={"photo_action": "remove"},
        )

        assert response.status_code == 200
        assert response.json()["image_path"] is None
        assert _row(entry.id)["image_path"] is None
        assert "secret" not in response.text
        assert old_file.read_bytes() == b"old"


class TestPersistedPathSafety:
    @pytest.mark.parametrize(
        "stored_path,file_relative",
        [
            ("static/uploads/legacy.jpg", "legacy.jpg"),
            (
                r"static\uploads\beer_runs\{run_id}\22222222-2222-4222-8222-222222222222.jpg",
                "beer_runs/{run_id}/22222222-2222-4222-8222-222222222222.jpg",
            ),
            (
                "static/uploads/beer_runs/{run_id}/not-a-uuid.jpg",
                "beer_runs/{run_id}/not-a-uuid.jpg",
            ),
            (
                "static/uploads/beer_runs/{other_run}/33333333-3333-4333-8333-333333333333.jpg",
                "beer_runs/{other_run}/33333333-3333-4333-8333-333333333333.jpg",
            ),
        ],
    )
    def test_legacy_malformed_and_wrong_run_files_are_retained(
        self,
        client,
        owner_member_nonmember_run,
        tmp_path,
        monkeypatch,
        stored_path,
        file_relative,
    ):
        data = owner_member_nonmember_run
        run_id = data["public_run"].id
        other_run = data["private_run"].id
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        stored_path = stored_path.format(run_id=run_id, other_run=other_run)
        physical = upload_root / Path(
            *file_relative.format(run_id=run_id, other_run=other_run).split("/")
        )
        physical.parent.mkdir(parents=True)
        physical.write_bytes(b"retain")
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=stored_path
        )

        response = client.delete(
            f"/api/beer-runs/{run_id}/entries/{entry.id}", headers=_bearer(data["member"])
        )

        assert response.status_code == 200
        assert physical.read_bytes() == b"retain"

    def test_traversal_absolute_directory_missing_and_sentinels_are_safe(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        run_id = data["public_run"].id
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        upload_root.mkdir()
        root_sentinel = upload_root / "sentinel.jpg"
        root_sentinel.write_bytes(b"root")
        outside = tmp_path / "outside.jpg"
        outside.write_bytes(b"outside")
        run_dir = upload_root / "beer_runs" / str(run_id)
        run_dir.mkdir(parents=True)
        run_sentinel = run_dir / "sentinel.jpg"
        run_sentinel.write_bytes(b"run")
        directory_path = _canonical_path(run_id, "44444444-4444-4444-8444-444444444444")
        directory = _physical_path(upload_root, directory_path)
        directory.mkdir()

        paths = [
            "static/uploads/../outside.jpg",
            str(outside.resolve()),
            directory_path,
            _canonical_path(run_id, "55555555-5555-4555-8555-555555555555"),
        ]
        entries = [
            _add_entry(
                data["db"], data["member"], data["public_run"], image_path=stored_path
            )
            for stored_path in paths
        ]
        for entry in entries:
            response = client.delete(
                f"/api/beer-runs/{run_id}/entries/{entry.id}",
                headers=_bearer(data["member"]),
            )
            assert response.status_code == 200

        assert outside.read_bytes() == b"outside"
        assert directory.is_dir()
        assert root_sentinel.read_bytes() == b"root"
        assert run_sentinel.read_bytes() == b"run"

    def test_shared_canonical_file_is_removed_only_after_last_reference(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        run_id = data["public_run"].id
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        shared_path = _canonical_path(run_id, "66666666-6666-4666-8666-666666666666")
        shared_file = _physical_path(upload_root, shared_path)
        shared_file.parent.mkdir(parents=True)
        shared_file.write_bytes(b"shared")
        first = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=shared_path
        )
        second = _add_entry(
            data["db"], data["owner"], data["public_run"], image_path=shared_path
        )

        first_response = client.delete(
            f"/api/beer-runs/{run_id}/entries/{first.id}", headers=_bearer(data["member"])
        )
        assert first_response.status_code == 200
        assert shared_file.read_bytes() == b"shared"

        second_response = client.delete(
            f"/api/beer-runs/{run_id}/entries/{second.id}", headers=_bearer(data["owner"])
        )
        assert second_response.status_code == 200
        assert not shared_file.exists()

    @pytest.mark.parametrize("photo_action", ("remove", "replace"))
    def test_shared_canonical_file_survives_patch(
        self,
        client,
        owner_member_nonmember_run,
        tmp_path,
        monkeypatch,
        photo_action,
    ):
        data = owner_member_nonmember_run
        run_id = data["public_run"].id
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        shared_path = _canonical_path(run_id, "99999999-9999-4999-8999-999999999999")
        shared_file = _physical_path(upload_root, shared_path)
        shared_file.parent.mkdir(parents=True)
        shared_file.write_bytes(b"shared")
        target = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=shared_path
        )
        _add_entry(
            data["db"], data["owner"], data["public_run"], image_path=shared_path
        )
        image = (
            ("new.jpg", _jpeg_bytes(), "image/jpeg")
            if photo_action == "replace"
            else None
        )

        response = _patch(
            client,
            run_id,
            target.id,
            data["member"],
            fields={"photo_action": photo_action},
            image=image,
        )

        assert response.status_code == 200
        assert shared_file.read_bytes() == b"shared"
        assert _row(target.id)["image_path"] != shared_path

    def test_backslash_reference_prevents_canonical_file_cleanup(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        run_id = data["public_run"].id
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        canonical = _canonical_path(run_id, "77777777-7777-4777-8777-777777777777")
        physical = _physical_path(upload_root, canonical)
        physical.parent.mkdir(parents=True)
        physical.write_bytes(b"shared")
        canonical_entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=canonical
        )
        _add_entry(
            data["db"],
            data["owner"],
            data["public_run"],
            image_path=canonical.replace("/", "\\"),
        )

        response = client.delete(
            f"/api/beer-runs/{run_id}/entries/{canonical_entry.id}",
            headers=_bearer(data["member"]),
        )

        assert response.status_code == 200
        assert physical.read_bytes() == b"shared"

    def test_symlink_escape_is_never_unlinked(
        self, client, owner_member_nonmember_run, tmp_path, monkeypatch
    ):
        data = owner_member_nonmember_run
        run_id = data["public_run"].id
        upload_root = tmp_path / "uploads"
        monkeypatch.setattr(main, "UPLOAD_ROOT", upload_root)
        canonical = _canonical_path(run_id, "88888888-8888-4888-8888-888888888888")
        link = _physical_path(upload_root, canonical)
        link.parent.mkdir(parents=True)
        outside = tmp_path / "outside.jpg"
        outside.write_bytes(b"outside")
        simulated_escape = False
        try:
            link.symlink_to(outside)
        except OSError:
            simulated_escape = True
            link.write_bytes(b"simulated link")
            original_resolve = Path.resolve

            def _resolve(path, strict=False):
                if path == link:
                    return original_resolve(outside, strict=strict)
                return original_resolve(path, strict=strict)

            monkeypatch.setattr(Path, "resolve", _resolve)
        entry = _add_entry(
            data["db"], data["member"], data["public_run"], image_path=canonical
        )

        response = client.delete(
            f"/api/beer-runs/{run_id}/entries/{entry.id}", headers=_bearer(data["member"])
        )

        assert response.status_code == 200
        if simulated_escape:
            assert link.read_bytes() == b"simulated link"
        else:
            assert link.is_symlink()
        assert outside.read_bytes() == b"outside"


class TestDerivedViews:
    def test_patch_and_delete_update_scoped_get_and_leaderboard(
        self, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        run = data["public_run"]
        member_entry = _add_entry(
            data["db"], data["member"], run, quantity=0.5, abv=5.0, brand="Member"
        )
        _add_entry(
            data["db"], data["owner"], run, quantity=1.0, abv=8.0, brand="Owner"
        )

        patched = _patch(
            client,
            run.id,
            member_entry.id,
            data["member"],
            fields={"quantity": "2.0", "abv": "10.0", "brand": "Updated"},
        )
        assert patched.status_code == 200
        entries = client.get(f"/api/beer-runs/{run.id}/entries").json()
        by_id = {entry["id"]: entry for entry in entries}
        assert by_id[member_entry.id]["brand"] == "Updated"
        leaderboard = client.get(f"/api/beer-runs/{run.id}/leaderboard").json()
        assert [row["username"] for row in leaderboard] == [
            data["member"].username,
            data["owner"].username,
        ]
        assert leaderboard[0]["total_alcohol"] == pytest.approx(0.2)

        deleted = client.delete(
            f"/api/beer-runs/{run.id}/entries/{member_entry.id}",
            headers=_bearer(data["member"]),
        )
        assert deleted.status_code == 200
        remaining = client.get(f"/api/beer-runs/{run.id}/entries").json()
        assert member_entry.id not in {entry["id"] for entry in remaining}
        leaderboard = client.get(f"/api/beer-runs/{run.id}/leaderboard").json()
        assert [row["username"] for row in leaderboard] == [data["owner"].username]
