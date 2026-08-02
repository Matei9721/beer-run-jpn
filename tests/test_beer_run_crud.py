"""Tests for beer-run CRUD API — create, list, detail, update, delete.

Covers visibility rules, name validation, ownership checks, cascade delete,
and error sanitization.
"""

import os
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app

VALID_SIGNUP_CODE = os.environ["SIGNUP_CODE"]


# ── Helpers ──────────────────────────────────────────────────────────

def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login(client: TestClient, username: str = "user", password: str = "password") -> str:
    """Log in and return the access token."""
    response = client.post(
        "/token", data={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _db_rows(table: str) -> list[tuple]:
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        return conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()


def _signup(client: TestClient, username: str, password: str = "Password1") -> tuple[str, int]:
    """Sign up a user, return (token, user_id)."""
    response = client.post(
        "/api/signup",
        json={
            "username": username,
            "password": password,
            "signup_code": VALID_SIGNUP_CODE,
        },
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    me = client.get("/api/me", headers=_bearer(token))
    return token, me.json()["id"]


# ── Create ───────────────────────────────────────────────────────────

class TestCreateBeerRun:
    def test_create_succeeds_and_sets_owner(self, client):
        token = _login(client)
        response = client.post(
            "/api/beer-runs",
            json={"name": "Tokyo Run"},
            headers=_bearer(token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Tokyo Run"
        assert data["is_public"] is False
        assert data["member_count"] == 1
        assert data["current_user_role"] == "owner"
        assert "id" in data
        assert "created_at" in data

        # Verify owner membership row exists.
        rows = _db_rows("beer_run_members")
        owner_row = [r for r in rows if r[1] == data["id"]]
        assert len(owner_row) == 1
        assert owner_row[0][3] == "owner"  # role column

    def test_create_public_run_visible_to_logged_out(self, client):
        token = _login(client)
        client.post(
            "/api/beer-runs",
            json={"name": "Public Run", "is_public": True},
            headers=_bearer(token),
        )
        # Logged-out list sees it.
        response = client.get("/api/beer-runs")
        names = [r["name"] for r in response.json()]
        assert "Public Run" in names

    def test_create_defaults_to_private(self, client):
        token = _login(client)
        response = client.post(
            "/api/beer-runs",
            json={"name": "Private Run"},
            headers=_bearer(token),
        )
        assert response.json()["is_public"] is False

    def test_create_requires_auth(self, client):
        response = client.post("/api/beer-runs", json={"name": "No Auth"})
        assert response.status_code == 401

    def test_create_rejects_missing_name(self, client):
        token = _login(client)
        response = client.post(
            "/api/beer-runs",
            json={"is_public": True},
            headers=_bearer(token),
        )
        assert response.status_code == 422

    def test_create_trims_name(self, client):
        token = _login(client)
        response = client.post(
            "/api/beer-runs",
            json={"name": "  Tokyo Run  "},
            headers=_bearer(token),
        )
        assert response.status_code == 201
        assert response.json()["name"] == "Tokyo Run"


# ── Name Validation ──────────────────────────────────────────────────

class TestNameValidation:
    @pytest.mark.parametrize("name", ["Abc", "A" + "x" * 63, "Tokyo Run", "Party-1", "A_B C"])
    def test_valid_names_accepted(self, client, name):
        token = _login(client)
        response = client.post(
            "/api/beer-runs",
            json={"name": name},
            headers=_bearer(token),
        )
        assert response.status_code == 201, f"name={name!r}: {response.text}"

    @pytest.mark.parametrize("name", [
        "Ab",          # too short (2 chars)
        "x" * 65,      # too long (65 chars)
        "Bad!",        # disallowed character
        "Bad@Name",    # disallowed character
        "名古屋",       # non-ASCII
    ])
    def test_invalid_names_rejected(self, client, name):
        token = _login(client)
        before = _db_rows("beer_runs")
        response = client.post(
            "/api/beer-runs",
            json={"name": name},
            headers=_bearer(token),
        )
        assert response.status_code == 422, f"name={name!r}: {response.status_code}"
        assert _db_rows("beer_runs") == before

    def test_empty_after_trim_rejected(self, client):
        token = _login(client)
        response = client.post(
            "/api/beer-runs",
            json={"name": "   "},
            headers=_bearer(token),
        )
        assert response.status_code == 422


# ── Duplicate Names ──────────────────────────────────────────────────

class TestDuplicateNames:
    def test_duplicate_case_insensitive_rejected(self, client):
        token = _login(client)
        client.post(
            "/api/beer-runs",
            json={"name": "Tokyo Run"},
            headers=_bearer(token),
        )
        for variant in ("Tokyo Run", "tokyo run", "TOKYO RUN", "tOkYo RuN"):
            response = client.post(
                "/api/beer-runs",
                json={"name": variant},
                headers=_bearer(token),
            )
            assert response.status_code == 409, variant
            assert response.json()["detail"] == "A beer-run with this name already exists"

    def test_duplicate_name_does_not_create_row(self, client):
        token = _login(client)
        client.post(
            "/api/beer-runs",
            json={"name": "Unique Run"},
            headers=_bearer(token),
        )
        before = _db_rows("beer_runs")
        client.post(
            "/api/beer-runs",
            json={"name": "Unique Run"},
            headers=_bearer(token),
        )
        assert _db_rows("beer_runs") == before

    def test_concurrent_duplicate_protected(self, client):
        """Sequential duplicate request hits the DB constraint and returns 409."""
        token = _login(client)
        client.post(
            "/api/beer-runs",
            json={"name": "Race Run"},
            headers=_bearer(token),
        )
        second = client.post(
            "/api/beer-runs",
            json={"name": "Race Run"},
            headers=_bearer(token),
        )
        assert second.status_code == 409
        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM beer_runs WHERE name = ? COLLATE NOCASE",
                ("race run",),
            ).fetchone()[0]
        assert count == 1


# ── List ─────────────────────────────────────────────────────────────

class TestListBeerRuns:
    def test_list_includes_public_and_private_for_member(self, client):
        token_a, _ = _signup(client, "UserA")
        token_b, _ = _signup(client, "UserB")

        # User A: create 2 private runs + 1 public run.
        for name in ("A Private 1", "A Private 2"):
            client.post(
                "/api/beer-runs",
                json={"name": name},
                headers=_bearer(token_a),
            )
        client.post(
            "/api/beer-runs",
            json={"name": "A Public", "is_public": True},
            headers=_bearer(token_a),
        )

        # User A sees: 2 private + 1 public + BeerRunJPN = 4 runs.
        response = client.get("/api/beer-runs", headers=_bearer(token_a))
        assert response.status_code == 200
        names = [r["name"] for r in response.json()]
        assert len(names) == 4
        assert "A Private 1" in names
        assert "A Private 2" in names
        assert "A Public" in names
        assert "BeerRunJPN" in names

        # User B sees: 1 public + BeerRunJPN = 2 runs (no private access).
        response = client.get("/api/beer-runs", headers=_bearer(token_b))
        names = [r["name"] for r in response.json()]
        assert len(names) == 2
        assert "A Public" in names
        assert "BeerRunJPN" in names

    def test_logged_out_sees_only_public(self, client):
        token = _login(client)
        client.post(
            "/api/beer-runs",
            json={"name": "Public For All", "is_public": True},
            headers=_bearer(token),
        )
        client.post(
            "/api/beer-runs",
            json={"name": "Private Hidden"},
            headers=_bearer(token),
        )

        response = client.get("/api/beer-runs")
        assert response.status_code == 200
        names = [r["name"] for r in response.json()]
        assert "Public For All" in names
        assert "BeerRunJPN" in names
        assert "Private Hidden" not in names

    def test_list_member_count_and_role(self, client):
        token_a, _ = _signup(client, "OwnerA")
        token_b = _login(client)  # the default "user" fixture

        # Owner A creates a run.
        create_resp = client.post(
            "/api/beer-runs",
            json={"name": "Role Test"},
            headers=_bearer(token_a),
        )
        run_id = create_resp.json()["id"]

        # Owner sees member_count=1, role="owner".
        response = client.get("/api/beer-runs", headers=_bearer(token_a))
        run = [r for r in response.json() if r["id"] == run_id][0]
        assert run["member_count"] == 1
        assert run["current_user_role"] == "owner"

        # Logged-out cannot see the private run.
        response = client.get("/api/beer-runs")
        public_ids = [r["id"] for r in response.json()]
        assert run_id not in public_ids

    def test_beer_run_jpn_always_visible(self, client):
        # Logged-out.
        response = client.get("/api/beer-runs")
        names = [r["name"] for r in response.json()]
        assert "BeerRunJPN" in names
        bj = [r for r in response.json() if r["name"] == "BeerRunJPN"][0]
        assert bj["is_public"] is True
        assert bj["current_user_role"] is None  # logged-out

        # Authenticated (user fixture has a membership in BeerRunJPN).
        token = _login(client)
        response = client.get("/api/beer-runs", headers=_bearer(token))
        bj = [r for r in response.json() if r["name"] == "BeerRunJPN"][0]
        assert bj["current_user_role"] == "member"


# ── Detail ───────────────────────────────────────────────────────────

class TestDetailBeerRun:
    def test_detail_public_run_logged_out(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "Detail Public", "is_public": True},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.get(f"/api/beer-runs/{run_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Detail Public"
        assert response.json()["current_user_role"] is None

    def test_detail_private_run_non_member_404(self, client):
        token_a, _ = _signup(client, "DetailOwner")
        token_b, _ = _signup(client, "DetailStranger")

        resp = client.post(
            "/api/beer-runs",
            json={"name": "Secret Run"},
            headers=_bearer(token_a),
        )
        run_id = resp.json()["id"]

        # Non-member gets 404.
        response = client.get(
            f"/api/beer-runs/{run_id}", headers=_bearer(token_b)
        )
        assert response.status_code == 404

        # Logged-out gets 404.
        response = client.get(f"/api/beer-runs/{run_id}")
        assert response.status_code == 404

    def test_detail_private_run_member_200(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "My Private"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.get(
            f"/api/beer-runs/{run_id}", headers=_bearer(token)
        )
        assert response.status_code == 200
        assert response.json()["current_user_role"] == "owner"

    def test_detail_nonexistent_404(self, client):
        response = client.get("/api/beer-runs/99999")
        assert response.status_code == 404


# ── Update ───────────────────────────────────────────────────────────

class TestUpdateBeerRun:
    def test_owner_can_rename(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "Old Name"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.patch(
            f"/api/beer-runs/{run_id}",
            json={"name": "New Name"},
            headers=_bearer(token),
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    def test_owner_can_toggle_visibility(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "Toggle Run"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        # Make public.
        response = client.patch(
            f"/api/beer-runs/{run_id}",
            json={"is_public": True},
            headers=_bearer(token),
        )
        assert response.status_code == 200
        assert response.json()["is_public"] is True

        # Verify it appears in logged-out list.
        list_resp = client.get("/api/beer-runs")
        assert "Toggle Run" in [r["name"] for r in list_resp.json()]

    def test_non_owner_cannot_update(self, client):
        token_a, _ = _signup(client, "UpOwner")
        token_b, _ = _signup(client, "UpMember")

        resp = client.post(
            "/api/beer-runs",
            json={"name": "Owner Run"},
            headers=_bearer(token_a),
        )
        run_id = resp.json()["id"]

        response = client.patch(
            f"/api/beer-runs/{run_id}",
            json={"name": "Hijacked"},
            headers=_bearer(token_b),
        )
        assert response.status_code == 403

    def test_update_requires_auth(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "AuthTest"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.patch(
            f"/api/beer-runs/{run_id}",
            json={"name": "NoAuth"},
        )
        assert response.status_code == 401

    def test_update_empty_body_422(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "EmptyBody"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.patch(
            f"/api/beer-runs/{run_id}",
            json={},
            headers=_bearer(token),
        )
        assert response.status_code == 422

    def test_rename_to_duplicate_409(self, client):
        token = _login(client)
        client.post(
            "/api/beer-runs",
            json={"name": "First Run"},
            headers=_bearer(token),
        )
        resp = client.post(
            "/api/beer-runs",
            json={"name": "Second Run"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.patch(
            f"/api/beer-runs/{run_id}",
            json={"name": "first run"},  # case-insensitive duplicate
            headers=_bearer(token),
        )
        assert response.status_code == 409


# ── Delete ───────────────────────────────────────────────────────────

class TestDeleteBeerRun:
    def test_owner_can_delete(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "To Delete"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.delete(
            f"/api/beer-runs/{run_id}",
            headers=_bearer(token),
        )
        assert response.status_code == 200
        assert response.json() == {"status": "deleted", "beer_run_id": run_id}

        # Verify it's gone.
        assert client.get(f"/api/beer-runs/{run_id}").status_code == 404

    def test_delete_cascades_to_memberships_and_entries(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "Cascade Run"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        # Add an entry to this run (via DB since create-entry always uses BeerRunJPN).
        with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
            conn.execute(
                "INSERT INTO entries (drink_type, abv, quantity, latitude, longitude, user_id, beer_run_id, timestamp) "
                "VALUES ('Beer', 5.0, 0.5, 35.0, 139.0, 1, ?, datetime('now'))",
                (run_id,),
            )

        before_runs = len(_db_rows("beer_runs"))
        before_members = len(_db_rows("beer_run_members"))
        before_entries = len(_db_rows("entries"))

        client.delete(
            f"/api/beer-runs/{run_id}",
            headers=_bearer(token),
        )

        assert len(_db_rows("beer_runs")) == before_runs - 1
        assert len(_db_rows("beer_run_members")) == before_members - 1
        assert len(_db_rows("entries")) == before_entries - 1

    def test_non_owner_cannot_delete(self, client):
        token_a, _ = _signup(client, "DelOwner")
        token_b, _ = _signup(client, "DelMember")

        resp = client.post(
            "/api/beer-runs",
            json={"name": "Del Test"},
            headers=_bearer(token_a),
        )
        run_id = resp.json()["id"]

        response = client.delete(
            f"/api/beer-runs/{run_id}",
            headers=_bearer(token_b),
        )
        assert response.status_code == 403

    def test_delete_requires_auth(self, client):
        token = _login(client)
        resp = client.post(
            "/api/beer-runs",
            json={"name": "NoAuthDel"},
            headers=_bearer(token),
        )
        run_id = resp.json()["id"]

        response = client.delete(f"/api/beer-runs/{run_id}")
        assert response.status_code == 401

    def test_delete_nonexistent_404(self, client):
        token = _login(client)
        response = client.delete(
            "/api/beer-runs/99999",
            headers=_bearer(token),
        )
        assert response.status_code == 404


# ── Shared Authorization Integration ─────────────────────────────────
#
# These tests use the owner_member_nonmember_run fixture so the "member" caller
# has a genuine role="member" membership row and the "non_member" caller has
# none (FR-3.4). They also cover actual missing/invalid bearer-token composition
# through the dependency stack, since token decoding lives in auth.get_current_user
# rather than in the permission policies (FR-3.2).

class TestSharedAuthorizationIntegration:
    def test_member_reads_private_detail(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.get(
            f"/api/beer-runs/{run.id}",
            headers=_bearer(owner_member_nonmember_run["member_token"]),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == run.name
        assert data["current_user_role"] == "member"

    def test_member_cannot_update(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.patch(
            f"/api/beer-runs/{run.id}",
            json={"name": "Member Hijack"},
            headers=_bearer(owner_member_nonmember_run["member_token"]),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Beer-run owner access required"

    def test_member_cannot_delete(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.delete(
            f"/api/beer-runs/{run.id}",
            headers=_bearer(owner_member_nonmember_run["member_token"]),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Beer-run owner access required"

    def test_non_member_owner_rejection(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.patch(
            f"/api/beer-runs/{run.id}",
            json={"name": "Stranger Hijack"},
            headers=_bearer(owner_member_nonmember_run["non_member_token"]),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Beer-run owner access required"

    def test_owner_update_and_delete(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        update = client.patch(
            f"/api/beer-runs/{run.id}",
            json={"name": "Owner Rename"},
            headers=_bearer(owner_member_nonmember_run["owner_token"]),
        )
        assert update.status_code == 200
        assert update.json()["name"] == "Owner Rename"
        assert update.json()["current_user_role"] == "owner"

        delete = client.delete(
            f"/api/beer-runs/{run.id}",
            headers=_bearer(owner_member_nonmember_run["owner_token"]),
        )
        assert delete.status_code == 200
        assert client.get(f"/api/beer-runs/{run.id}").status_code == 404

    def test_invalid_token_public_read_succeeds(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["public_run"]
        response = client.get(
            f"/api/beer-runs/{run.id}",
            headers=_bearer("not-a-valid-token"),
        )
        assert response.status_code == 200
        assert response.json()["current_user_role"] is None

    def test_invalid_token_private_read_404(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.get(
            f"/api/beer-runs/{run.id}",
            headers=_bearer("not-a-valid-token"),
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Beer-run not found"

    def test_invalid_token_update_401(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.patch(
            f"/api/beer-runs/{run.id}",
            json={"name": "No Auth"},
            headers=_bearer("not-a-valid-token"),
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_invalid_token_delete_401(self, client, owner_member_nonmember_run):
        run = owner_member_nonmember_run["private_run"]
        response = client.delete(
            f"/api/beer-runs/{run.id}",
            headers=_bearer("not-a-valid-token"),
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"
        assert response.headers.get("WWW-Authenticate") == "Bearer"


# ── Error Sanitization ───────────────────────────────────────────────

class TestErrorSanitization:
    def test_500_does_not_leak_sql(self, client, monkeypatch):
        token = _login(client)

        def broken_commit(_session):
            raise RuntimeError("SQLITE INTERNAL: beer_runs.id constraint violation")

        monkeypatch.setattr(Session, "commit", broken_commit)

        response = client.post(
            "/api/beer-runs",
            json={"name": "Error Test"},
            headers=_bearer(token),
        )
        assert response.status_code == 500
        assert "SQLITE" not in response.text
        assert "constraint" not in response.text.lower()
        assert "beer_runs" not in response.text
