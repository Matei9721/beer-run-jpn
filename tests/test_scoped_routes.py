"""Focused tests for the scoped entry and leaderboard routes.

Covers run-scoped reads with the shared visibility policy, entrants-only
leaderboards, run-scoped entry lists, member-only creation, the isolated image
writer seam, sanitized failures, commit finality, and removal of the old
unscoped routes.

All database state uses the isolated test override; upload writes are redirected
to ``tmp_path`` through the image-writer seam and never touch
``static/uploads``.
"""

import io
import os
import sqlite3
from datetime import datetime

import pytest
from PIL import Image
from sqlalchemy import event

import models

# The shared concealed 404 detail for missing or inaccessible runs.
MISSING_RUN_ID = 99999
CONCEALED_404 = "Beer-run not found"

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


def auth_token_for(user) -> str:
    """Create a valid bearer token for a User object (mirrors conftest)."""
    import auth
    return auth.create_access_token({"sub": str(user.id)})


# Sentinel so callers can explicitly request a NULL beer_run_id entry.
_UNSET = object()


def _add_entry(
    db,
    user,
    run,
    *,
    quantity=0.5,
    abv=5.0,
    drink_type="Beer",
    brand=None,
    latitude=35.0,
    longitude=139.0,
    timestamp=None,
    beer_run_id=_UNSET,
    image_path=None,
):
    if beer_run_id is _UNSET:
        beer_run_id = run.id
    entry = models.Entry(
        drink_type=drink_type,
        abv=abv,
        quantity=quantity,
        brand=brand,
        latitude=latitude,
        longitude=longitude,
        image_path=image_path,
        timestamp=timestamp or datetime(2026, 1, 1, 12, 0, 0),
        user_id=user.id,
        beer_run_id=beer_run_id,
    )
    db.add(entry)
    db.flush()
    return entry


def _valid_entry_form(**overrides):
    data = {
        "drink_type": "Beer",
        "abv": "5.0",
        "quantity": "0.5",
        "latitude": "35.6895",
        "longitude": "139.6917",
    }
    data.update(overrides)
    return data


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, "JPEG")
    return buf.getvalue()


# ── Feature 1: scoped reads ─────────────────────────────────────────


class TestScopedLeaderboard:
    def test_leaderboard_totals_are_isolated_per_run(self, client, owner_member_nonmember_run):
        """An overlapping user across two runs sees only each run's totals."""
        data = owner_member_nonmember_run
        db = data["db"]
        owner = data["owner"]
        _add_entry(db, owner, data["public_run"], quantity=0.5, abv=5.0)
        _add_entry(db, owner, data["private_run"], quantity=1.0, abv=10.0)
        db.commit()

        public = client.get(f"/api/beer-runs/{data['public_run'].id}/leaderboard")
        assert public.status_code == 200
        assert set(public.json()[0]) == {"username", "total_liters", "total_alcohol"}
        assert public.json()[0]["username"] == owner.username
        assert public.json()[0]["total_liters"] == 0.5
        assert public.json()[0]["total_alcohol"] == 0.5 * (5.0 / 100.0)

        private = client.get(
            f"/api/beer-runs/{data['private_run'].id}/leaderboard",
            headers={"Authorization": f"Bearer {auth_token_for(data['owner'])}"},
        )
        assert private.status_code == 200
        assert private.json()[0]["total_liters"] == 1.0
        assert private.json()[0]["total_alcohol"] == 1.0 * (10.0 / 100.0)

    def test_leaderboard_includes_entrants_only(self, client, owner_member_nonmember_run):
        """Zero-entry members and non-member owners are absent."""
        data = owner_member_nonmember_run
        db = data["db"]
        # owner: member with zero entries; member: one entry; non_member: an
        # inconsistent entry owned by someone without membership in this run.
        _add_entry(db, data["member"], data["public_run"], quantity=0.5, abv=5.0)
        _add_entry(db, data["non_member"], data["public_run"], quantity=2.0, abv=40.0)
        db.commit()

        response = client.get(f"/api/beer-runs/{data['public_run'].id}/leaderboard")
        assert response.status_code == 200
        rows = response.json()
        assert [r["username"] for r in rows] == [data["member"].username]
        assert rows[0]["total_liters"] == 0.5

    def test_new_run_with_only_owner_returns_empty_array(self, client, owner_member_nonmember_run):
        """Membership without any scoped entry yields []."""
        data = owner_member_nonmember_run
        db = data["db"]
        fresh = models.BeerRun(name="Fresh Empty Run", is_public=True)
        db.add(fresh)
        db.flush()
        db.add(models.BeerRunMember(beer_run_id=fresh.id, user_id=data["owner"].id, role="owner"))
        db.commit()

        response = client.get(f"/api/beer-runs/{fresh.id}/leaderboard")
        assert response.status_code == 200
        assert response.json() == []

    def test_leaderboard_ranking_by_alcohol_within_run(self, client, owner_member_nonmember_run):
        """Ordered by total_alcohol desc; other-run entries don't interfere."""
        data = owner_member_nonmember_run
        db = data["db"]
        # Same requested run: owner total_alcohol = 0.5, member total_alcohol = 0.9.
        _add_entry(db, data["owner"], data["public_run"], quantity=0.5, abv=5.0)
        _add_entry(db, data["member"], data["public_run"], quantity=1.0, abv=9.0)
        # Bigger entries in the *other* run must not influence ordering or totals.
        _add_entry(db, data["member"], data["private_run"], quantity=5.0, abv=99.0)
        db.commit()

        response = client.get(f"/api/beer-runs/{data['public_run'].id}/leaderboard")
        rows = response.json()
        assert [r["username"] for r in rows] == [data["member"].username, data["owner"].username]
        assert rows[0]["total_alcohol"] == 1.0 * (9.0 / 100.0)
        assert rows[1]["total_alcohol"] == 0.5 * (5.0 / 100.0)


class TestScopedEntries:
    def test_entries_isolated_shape_and_ordering(self, client, owner_member_nonmember_run):
        """Run scope, NULL exclusion, newest-first ordering, exact 12 fields."""
        data = owner_member_nonmember_run
        db = data["db"]
        _add_entry(
            db, data["owner"], data["public_run"],
            drink_type="Beer", timestamp=datetime(2026, 1, 2, 12, 0, 0),
        )
        _add_entry(
            db, data["owner"], data["public_run"],
            drink_type="Sake", timestamp=datetime(2026, 1, 1, 12, 0, 0),
        )
        # Other-run entry (must be excluded).
        _add_entry(db, data["owner"], data["private_run"], drink_type="Highball")
        # Unassigned (NULL beer_run_id) entry (must be excluded).
        _add_entry(db, data["owner"], data["public_run"], drink_type="Chu-hi", beer_run_id=None)
        # Inconsistent non-member-owned entry in the requested run (stays listed).
        _add_entry(db, data["non_member"], data["public_run"], drink_type="Ume-shu")
        db.commit()

        response = client.get(f"/api/beer-runs/{data['public_run'].id}/entries")
        assert response.status_code == 200
        rows = response.json()
        assert [r["drink_type"] for r in rows] == ["Beer", "Sake", "Ume-shu"]
        assert set(rows[0]) == EXPECTED_ENTRY_FIELDS
        assert "beer_run_id" not in rows[0]
        assert rows[0]["timestamp"] == "2026-01-02T12:00:00"

    def test_username_filter_is_case_insensitive_and_run_scoped(self, client, owner_member_nonmember_run):
        """The filter stays inside the requested run with case-insensitive identity."""
        data = owner_member_nonmember_run
        db = data["db"]
        _add_entry(db, data["owner"], data["public_run"], drink_type="Beer")
        # Same user also has an entry in the other run (must never be matched).
        _add_entry(db, data["owner"], data["private_run"], drink_type="Sake")
        db.commit()

        base = f"/api/beer-runs/{data['public_run'].id}/entries"
        canonical = client.get(f"{base}?username={data['owner'].username}")
        assert canonical.status_code == 200
        assert [r["drink_type"] for r in canonical.json()] == ["Beer"]

        varied = client.get(f"{base}?username={data['owner'].username.upper()}")
        assert varied.status_code == 200
        assert [r["drink_type"] for r in varied.json()] == ["Beer"]

        missing = client.get(f"{base}?username=NoSuchUser")
        assert missing.status_code == 200
        assert missing.json() == []

    def test_empty_entries_list(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        response = client.get(f"/api/beer-runs/{data['public_run'].id}/entries")
        assert response.status_code == 200
        assert response.json() == []


class TestScopedReadAuthorization:
    """Visibility matrix and concealed private runs."""

    def _caller(self, data, kind):
        if kind == "logged_out":
            return {}
        if kind == "invalid_token":
            return {"Authorization": "Bearer invalid.token.value"}
        return {"Authorization": f"Bearer {auth_token_for(data[kind])}"}

    @pytest.mark.parametrize("endpoint", ("entries", "leaderboard"))
    @pytest.mark.parametrize(
        "kind,expected_public,expected_private",
        [
            ("logged_out", 200, 404),
            ("invalid_token", 200, 404),
            ("owner", 200, 200),
            ("member", 200, 200),
            ("non_member", 200, 404),
        ],
    )
    def test_visibility_matrix(
        self, client, owner_member_nonmember_run, endpoint, kind, expected_public, expected_private
    ):
        data = owner_member_nonmember_run
        headers = self._caller(data, kind)
        path = f"/api/beer-runs/{{}}/{endpoint}"

        public_resp = client.get(path.format(data["public_run"].id), headers=headers)
        assert public_resp.status_code == expected_public

        private_resp = client.get(path.format(data["private_run"].id), headers=headers)
        assert private_resp.status_code == expected_private
        if expected_private == 404:
            assert private_resp.json() == {"detail": CONCEALED_404}

    @pytest.mark.parametrize("endpoint", ("entries", "leaderboard"))
    def test_missing_run_and_inaccessible_private_are_identical(self, client, owner_member_nonmember_run, endpoint):
        """A missing run and a private-inaccessible run both return the same 404."""
        data = owner_member_nonmember_run
        headers = self._caller(data, "non_member")
        missing = client.get(f"/api/beer-runs/{MISSING_RUN_ID}/{endpoint}", headers=headers)
        private = client.get(f"/api/beer-runs/{data['private_run'].id}/{endpoint}", headers=headers)

        assert missing.status_code == 404
        assert missing.json() == private.json() == {"detail": CONCEALED_404}

    @pytest.mark.parametrize("endpoint", ("entries", "leaderboard"))
    def test_negative_and_non_integer_ids(self, client, owner_member_nonmember_run, endpoint):
        data = owner_member_nonmember_run
        negative = client.get(f"/api/beer-runs/-1/{endpoint}")
        assert negative.status_code == 404
        assert negative.json() == {"detail": CONCEALED_404}

        non_integer = client.get(f"/api/beer-runs/abc/{endpoint}")
        assert non_integer.status_code == 422


class TestScopedReadPerformance:
    """Bounded query count and run-scope index usage."""

    def test_leaderboard_query_count_does_not_grow_with_entrants(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        bind = db.get_bind()

        def _count_for(num_entrants):
            run = models.BeerRun(name=f"Count Run {num_entrants}", is_public=True)
            db.add(run)
            db.flush()
            for i in range(num_entrants):
                user = models.User(username=f"Counter{num_entrants}_{i}", hashed_password="x")
                db.add(user)
                db.flush()
                db.add(models.BeerRunMember(beer_run_id=run.id, user_id=user.id, role="member"))
                _add_entry(db, user, run, quantity=0.5 + i, abv=5.0)
            db.commit()

            counter = {"n": 0}

            def _count(conn, cursor, statement, parameters, context, executemany):
                counter["n"] += 1

            event.listen(bind, "before_cursor_execute", _count)
            try:
                response = client.get(f"/api/beer-runs/{run.id}/leaderboard")
            finally:
                event.remove(bind, "before_cursor_execute", _count)
            assert response.status_code == 200
            assert len(response.json()) == num_entrants
            return counter["n"]

        single = _count_for(1)
        many = _count_for(5)
        assert single == many
        assert many <= 3

    def test_entries_use_run_scope_index(self):
        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            plan = conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM entries WHERE beer_run_id = ?", (1,)
            ).fetchall()
        assert any("ix_entries_beer_run_id" in str(row) for row in plan)


# ── Feature 2: scoped creation ──────────────────────────────────────


class TestScopedCreate:
    def test_owner_and_member_succeed_in_public_and_private(self, client, owner_member_nonmember_run):
        """Success shape across visibility modes."""
        data = owner_member_nonmember_run
        for run_key in ("public_run", "private_run"):
            for user_key in ("owner", "member"):
                run = data[run_key]
                response = client.post(
                    f"/api/beer-runs/{run.id}/entries",
                    data=_valid_entry_form(),
                    headers={"Authorization": f"Bearer {auth_token_for(data[user_key])}"},
                )
                assert response.status_code == 200
                body = response.json()
                assert body == {"status": "success", "entry_id": body["entry_id"]}
                assert isinstance(body["entry_id"], int)

    def test_non_member_denied_even_when_public(self, client, owner_member_nonmember_run):
        """Public visibility never permits an authenticated non-member."""
        data = owner_member_nonmember_run
        response = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries",
            data=_valid_entry_form(),
            headers={"Authorization": f"Bearer {auth_token_for(data['non_member'])}"},
        )
        assert response.status_code == 404
        assert response.json() == {"detail": CONCEALED_404}

    def test_missing_auth_returns_401_with_bearer_challenge(self, client, owner_member_nonmember_run):
        """Missing/invalid auth is 401 before run existence is revealed."""
        data = owner_member_nonmember_run
        missing = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries", data=_valid_entry_form()
        )
        assert missing.status_code == 401
        assert missing.json() == {"detail": "Could not validate credentials"}
        assert missing.headers["www-authenticate"] == "Bearer"

        invalid = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries",
            data=_valid_entry_form(),
            headers={"Authorization": "Bearer invalid.token.value"},
        )
        assert invalid.status_code == 401
        assert invalid.json() == {"detail": "Could not validate credentials"}
        assert invalid.headers["www-authenticate"] == "Bearer"

    def test_missing_run_concealed_after_auth(self, client, owner_member_nonmember_run):
        """Valid auth to a missing run returns the concealed 404."""
        data = owner_member_nonmember_run
        response = client.post(
            f"/api/beer-runs/{MISSING_RUN_ID}/entries",
            data=_valid_entry_form(),
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert response.status_code == 404
        assert response.json() == {"detail": CONCEALED_404}

    def test_spoofed_identity_fields_are_ignored(self, client, owner_member_nonmember_run):
        """The server derives user_id and beer_run_id from auth + path."""
        data = owner_member_nonmember_run
        other_run_id = data["private_run"].id
        response = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries",
            data=_valid_entry_form(
                user_id=str(data["owner"].id),
                username=data["owner"].username,
                beer_run_id=str(other_run_id),
            ),
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert response.status_code == 200
        entry_id = response.json()["entry_id"]

        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            row = conn.execute(
                "SELECT user_id, beer_run_id FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
        assert row == (data["member"].id, data["public_run"].id)

        # The other run's endpoints must be unchanged.
        private_entries = client.get(
            f"/api/beer-runs/{other_run_id}/entries",
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert private_entries.status_code == 200
        assert private_entries.json() == []

    def test_multipart_validation_retains_422(self, client, owner_member_nonmember_run):
        """Missing required form fields keep the standard 422."""
        data = owner_member_nonmember_run
        incomplete = _valid_entry_form()
        del incomplete["quantity"]
        response = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries",
            data=incomplete,
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert response.status_code == 422

    def test_create_entry_with_image_uses_isolated_writer_seam(self, client, owner_member_nonmember_run, tmp_path, monkeypatch):
        """Uploads go through the image-writer seam into tmp_path; row + file persisted."""
        import main as main_mod

        def _write_to_tmp(contents):
            path = tmp_path / "proof.jpg"
            path.write_bytes(contents)
            return str(path)

        monkeypatch.setattr(main_mod, "write_upload_image", _write_to_tmp)
        data = owner_member_nonmember_run
        response = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries",
            data=_valid_entry_form(),
            files={"image": ("proof.jpg", _jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert response.status_code == 200
        entry_id = response.json()["entry_id"]

        written = list(tmp_path.glob("*.jpg"))
        assert len(written) == 1
        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            row = conn.execute(
                "SELECT image_path, user_id, beer_run_id FROM entries WHERE id = ?", (entry_id,)
            ).fetchone()
        assert row[0] == str(written[0])
        assert row[1] == data["member"].id
        assert row[2] == data["public_run"].id

    def test_denied_create_writes_no_entry_and_no_upload(self, client, owner_member_nonmember_run, monkeypatch):
        """Auth/membership completes before any upload or row is written."""
        import main as main_mod

        writer_calls = {"n": 0}

        def _must_not_run(contents):
            writer_calls["n"] += 1
            raise AssertionError("image writer must not run for a denied request")

        monkeypatch.setattr(main_mod, "write_upload_image", _must_not_run)
        data = owner_member_nonmember_run
        before_entries = client.get(f"/api/beer-runs/{data['public_run'].id}/entries").json()

        for headers in (
            {},  # logged-out
            {"Authorization": f"Bearer {auth_token_for(data['non_member'])}"},
        ):
            response = client.post(
                f"/api/beer-runs/{data['public_run'].id}/entries",
                data=_valid_entry_form(),
                files={"image": ("proof.jpg", _jpeg_bytes(), "image/jpeg")},
                headers=headers,
            )
            assert response.status_code in (401, 404)

        assert writer_calls["n"] == 0
        after_entries = client.get(f"/api/beer-runs/{data['public_run'].id}/entries").json()
        assert after_entries == before_entries

    def test_image_failure_is_sanitized_and_rolls_back(self, client, owner_member_nonmember_run, monkeypatch):
        """Image failure: exact detail, no entry row, no raw internals."""
        import main as main_mod

        def _boom(contents):
            raise RuntimeError("secret local path /var/tmp/leak.jpg")

        monkeypatch.setattr(main_mod, "write_upload_image", _boom)
        data = owner_member_nonmember_run
        before = client.get(f"/api/beer-runs/{data['public_run'].id}/entries").json()

        response = client.post(
            f"/api/beer-runs/{data['public_run'].id}/entries",
            data=_valid_entry_form(),
            files={"image": ("proof.jpg", _jpeg_bytes(), "image/jpeg")},
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to create entry"}
        assert "leak" not in response.text and "RuntimeError" not in response.text

        after = client.get(f"/api/beer-runs/{data['public_run'].id}/entries").json()
        assert after == before

    def test_pre_commit_database_failure_rolls_back(self, client, owner_member_nonmember_run):
        """A failing insert rolls back with the exact sanitized detail."""
        data = owner_member_nonmember_run
        bind = data["db"].get_bind()

        def _raise_on_insert(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("INSERT"):
                raise RuntimeError("forced insert failure")

        event.listen(bind, "before_cursor_execute", _raise_on_insert)
        try:
            response = client.post(
                f"/api/beer-runs/{data['public_run'].id}/entries",
                data=_valid_entry_form(),
                headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
            )
        finally:
            event.remove(bind, "before_cursor_execute", _raise_on_insert)

        assert response.status_code == 500
        assert response.json() == {"detail": "Unable to create entry"}
        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM entries WHERE beer_run_id = ?", (data["public_run"].id,)
            ).fetchone()[0]
        assert count == 0

    def test_commit_is_final_without_post_commit_refresh(self, client, owner_member_nonmember_run):
        """A successful create performs no SELECT after the entry insert."""
        data = owner_member_nonmember_run
        bind = data["db"].get_bind()
        inserted = {"seen": False}
        post_insert_selects = {"n": 0}

        def _track(conn, cursor, statement, parameters, context, executemany):
            s = statement.lstrip().upper()
            if s.startswith("INSERT"):
                inserted["seen"] = True
            elif inserted["seen"] and s.startswith("SELECT"):
                post_insert_selects["n"] += 1

        event.listen(bind, "before_cursor_execute", _track)
        try:
            response = client.post(
                f"/api/beer-runs/{data['public_run'].id}/entries",
                data=_valid_entry_form(),
                headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
            )
        finally:
            event.remove(bind, "before_cursor_execute", _track)

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert post_insert_selects["n"] == 0

    def test_non_integer_path_id_validation(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        response = client.post(
            "/api/beer-runs/abc/entries",
            data=_valid_entry_form(),
            headers={"Authorization": f"Bearer {auth_token_for(data['member'])}"},
        )
        assert response.status_code == 422


# ── Old route removal ───────────────────────────────────────────────


class TestOldRouteRemoval:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("GET", "/api/leaderboard"),
            ("GET", "/api/entries"),
            ("POST", "/api/entries"),
        ],
    )
    def test_old_routes_return_404(self, client, method, path):
        response = client.request(method, path)
        assert response.status_code == 404
