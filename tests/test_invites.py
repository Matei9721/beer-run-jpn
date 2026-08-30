"""Endpoint tests for invite creation, public preview, and acceptance.

Uses the ``client`` + ``owner_member_nonmember_run`` fixtures from conftest.py:
``owner`` / ``member`` / ``non_member`` reflect their real persisted membership
state in the private and public runs. Covers the Feature 2 creation/preview
matrix, the Feature 3 acceptance matrix, and the concurrency/rollback branches
forced deterministically through monkeypatched helpers.
"""

import re
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from sqlalchemy.orm import Session

import auth
import invite_routes
import models

INVITE_CODE_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
MISSING_RUN_ID = 99999


def owner_headers(data):
    return {"Authorization": f"Bearer {data['owner_token']}"}


def member_headers(data):
    return {"Authorization": f"Bearer {data['member_token']}"}


def non_member_headers(data):
    return {"Authorization": f"Bearer {data['non_member_token']}"}


def create_invite(client, data, run=None):
    """Create an invite as owner and return its code."""
    run = run or data["private_run"]
    resp = client.post(f"/api/beer-runs/{run.id}/invites", headers=owner_headers(data))
    assert resp.status_code == 201
    return resp.json()["code"]


def new_user(data, username):
    """Create a fresh user and token outside the fixed identities."""
    db = data["db"]
    user = models.User(username=username, hashed_password="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, auth.create_access_token({"sub": user.auth_subject})


# ── Feature 2: Owner create-or-retrieve ───────────────────────────────


class TestCreateAuthorization:
    """FR-2.1 — only the run owner can create/retrieve an invite."""

    def test_owner_creates_invite_then_retrieves_same(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        run = data["private_run"]
        url = f"/api/beer-runs/{run.id}/invites"

        first = client.post(url, headers=owner_headers(data))
        assert first.status_code == 201
        body = first.json()
        assert set(body) == {"code", "invite_url", "beer_run_id", "beer_run_name", "created_at"}

        second = client.post(url, headers=owner_headers(data))
        assert second.status_code == 200
        assert second.json() == body

    def test_member_and_non_member_get_owner_403(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        url = f"/api/beer-runs/{data['private_run'].id}/invites"
        for headers in (member_headers(data), non_member_headers(data)):
            resp = client.post(url, headers=headers)
            assert resp.status_code == 403
            assert resp.json() == {"detail": "Beer-run owner access required"}

    def test_missing_auth_gets_shared_401(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        resp = client.post(f"/api/beer-runs/{data['private_run'].id}/invites")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Could not validate credentials"}
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_invalid_token_gets_shared_401(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        resp = client.post(
            f"/api/beer-runs/{data['private_run'].id}/invites",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Could not validate credentials"}
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_owner_missing_run_gets_404(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        resp = client.post(f"/api/beer-runs/{MISSING_RUN_ID}/invites", headers=owner_headers(data))
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Beer-run not found"}


class TestCreateResponseContract:
    """FR-2.2, FR-2.3 — stable fields, root-relative link, permanent reuse."""

    def test_code_is_43_url_safe_characters(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        codes = {create_invite(client, data, run) for run in (data["private_run"], data["public_run"])}
        assert len(codes) == 2  # distinct runs, distinct codes
        for code in codes:
            assert len(code) == 43
            assert INVITE_CODE_RE.fullmatch(code)

    def test_invite_url_is_root_relative_and_decodes_to_code(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        resp = client.post(
            f"/api/beer-runs/{data['private_run'].id}/invites",
            headers=owner_headers(data),
        )
        body = resp.json()
        assert body["invite_url"] == f"/?invite={body['code']}"
        parsed = urlparse(body["invite_url"])
        assert parsed.netloc == ""
        assert parsed.path == "/"
        assert unquote(parse_qs(parsed.query)["invite"][0]) == body["code"]

    def test_invite_url_ignores_host_and_forwarded_headers(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        headers = owner_headers(data)
        headers["Host"] = "attacker.example.com"
        headers["X-Forwarded-Host"] = "attacker.example.com"
        headers["X-Forwarded-Proto"] = "https"
        resp = client.post(
            f"/api/beer-runs/{data['private_run'].id}/invites",
            headers=headers,
        )
        body = resp.json()
        assert body["invite_url"].startswith("/?invite=")
        assert "attacker.example.com" not in body["invite_url"]

    def test_created_at_is_parsable_datetime(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        resp = client.post(
            f"/api/beer-runs/{data['private_run'].id}/invites",
            headers=owner_headers(data),
        )
        assert isinstance(datetime.fromisoformat(resp.json()["created_at"]), datetime)

    def test_permanent_invite_follows_rename_without_changing_code(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        first = client.post(f"/api/beer-runs/{run.id}/invites", headers=owner_headers(data))
        body = first.json()

        run.name = "Renamed Trip Run"
        db.commit()

        later = client.post(f"/api/beer-runs/{run.id}/invites", headers=owner_headers(data))
        assert later.status_code == 200
        assert later.json()["code"] == body["code"]
        assert later.json()["invite_url"] == body["invite_url"]
        assert later.json()["created_at"] == body["created_at"]
        assert later.json()["beer_run_id"] == body["beer_run_id"]
        assert later.json()["beer_run_name"] == "Renamed Trip Run"

    def test_one_invite_row_per_run(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        create_invite(client, data, data["private_run"])
        create_invite(client, data, data["public_run"])
        assert db.query(models.BeerRunInvite).count() == 2

        # Re-requesting the first run never creates another row.
        client.post(f"/api/beer-runs/{data['private_run'].id}/invites", headers=owner_headers(data))
        assert db.query(models.BeerRunInvite).count() == 2


# ── Feature 2: Public preview ─────────────────────────────────────────


class TestPreview:
    """FR-2.4, FR-2.5 — minimal public disclosure and uniform invalid codes."""

    def test_preview_private_run_unauthenticated(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data, data["private_run"])
        resp = client.get(f"/api/invites/{code}")
        assert resp.status_code == 200
        assert resp.json() == {
            "beer_run_id": data["private_run"].id,
            "beer_run_name": data["private_run"].name,
        }

    def test_preview_public_run_unauthenticated(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data, data["public_run"])
        resp = client.get(f"/api/invites/{code}")
        assert resp.status_code == 200
        assert set(resp.json()) == {"beer_run_id", "beer_run_name"}

    def test_preview_reflects_current_name_after_rename(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        code = create_invite(client, data, run)

        run.name = "Renamed Private Run"
        db.commit()

        resp = client.get(f"/api/invites/{code}")
        assert resp.status_code == 200
        assert resp.json()["beer_run_name"] == "Renamed Private Run"

    @pytest.mark.parametrize(
        "bad_code",
        (
            "short",
            "A" * 44,
            "A" * 42 + "!",
            "!" * 43,
            "~" * 43,
            "A" * 42,
        ),
    )
    def test_preview_malformed_codes_return_404(self, client, owner_member_nonmember_run, bad_code):
        resp = client.get(f"/api/invites/{bad_code}")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Invite not found"}

    def test_preview_case_changed_code_returns_404(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data)
        resp = client.get(f"/api/invites/{code.swapcase()}")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Invite not found"}

    def test_preview_random_unknown_code_returns_404(self, client, owner_member_nonmember_run):
        resp = client.get(f"/api/invites/{'Z' * 43}")
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Invite not found"}

    def test_preview_deleted_run_code_returns_404(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data)
        resp = client.delete(
            f"/api/beer-runs/{data['private_run'].id}",
            headers=owner_headers(data),
        )
        assert resp.status_code == 200
        assert client.get(f"/api/invites/{code}").status_code == 404


# ── Feature 3: Authenticated acceptance ───────────────────────────────


class TestAcceptAuthorization:
    """FR-3.1 — authentication precedes any code-validity disclosure."""

    def test_missing_auth_401_for_valid_code(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data)
        resp = client.post(f"/api/invites/{code}/accept")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Could not validate credentials"}
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_missing_auth_401_for_invalid_code(self, client, owner_member_nonmember_run):
        resp = client.post("/api/invites/not-a-valid-code/accept")
        assert resp.status_code == 401
        assert resp.json() == {"detail": "Could not validate credentials"}

    def test_invalid_token_401_for_valid_and_invalid_codes(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data)
        headers = {"Authorization": "Bearer garbage-token"}
        for path in (f"/api/invites/{code}/accept", "/api/invites/short/accept"):
            resp = client.post(path, headers=headers)
            assert resp.status_code == 401
            assert resp.json() == {"detail": "Could not validate credentials"}


class TestAcceptBehavior:
    """FR-3.2, FR-3.3, FR-3.4 — join, idempotency, and role preservation."""

    def test_non_member_accepts_private_run_invite(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        code = create_invite(client, data, run)

        resp = client.post(f"/api/invites/{code}/accept", headers=non_member_headers(data))
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == run.id
        assert body["name"] == run.name
        assert body["is_public"] is False
        assert body["current_user_role"] == "member"
        assert body["member_count"] == 3  # owner + member + new member

        memberships = (
            db.query(models.BeerRunMember)
            .filter(models.BeerRunMember.beer_run_id == run.id)
            .all()
        )
        new = next(m for m in memberships if m.user_id == data["non_member"].id)
        assert new.role == "member"

        # Invite remains valid and reusable.
        assert client.get(f"/api/invites/{code}").status_code == 200

    def test_accept_twice_keeps_one_membership(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        code = create_invite(client, data, run)

        first = client.post(f"/api/invites/{code}/accept", headers=non_member_headers(data))
        second = client.post(f"/api/invites/{code}/accept", headers=non_member_headers(data))
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["current_user_role"] == "member"
        assert second.json()["member_count"] == 3

        count = (
            db.query(models.BeerRunMember)
            .filter(
                models.BeerRunMember.beer_run_id == run.id,
                models.BeerRunMember.user_id == data["non_member"].id,
            )
            .count()
        )
        assert count == 1

    def test_existing_member_accept_preserves_member_role(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data)
        resp = client.post(f"/api/invites/{code}/accept", headers=member_headers(data))
        assert resp.status_code == 200
        assert resp.json()["current_user_role"] == "member"
        assert resp.json()["member_count"] == 2  # owner + member, unchanged

    def test_owner_accept_preserves_owner_role(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data)
        resp = client.post(f"/api/invites/{code}/accept", headers=owner_headers(data))
        assert resp.status_code == 200
        assert resp.json()["current_user_role"] == "owner"
        assert resp.json()["member_count"] == 2

    def test_two_recipients_join_same_invite(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        code = create_invite(client, data, run)

        stranger_a, tok_a = new_user(data, "InviteStrangerA")
        stranger_b, tok_b = new_user(data, "InviteStrangerB")

        for headers in (
            {"Authorization": f"Bearer {tok_a}"},
            {"Authorization": f"Bearer {tok_b}"},
        ):
            resp = client.post(f"/api/invites/{code}/accept", headers=headers)
            assert resp.status_code == 200
            assert resp.json()["current_user_role"] == "member"

        count = (
            db.query(models.BeerRunMember)
            .filter(models.BeerRunMember.beer_run_id == run.id)
            .count()
        )
        assert count == 4  # owner + member + two strangers

    def test_accept_public_run_invite(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        code = create_invite(client, data, data["public_run"])
        resp = client.post(f"/api/invites/{code}/accept", headers=non_member_headers(data))
        assert resp.status_code == 200
        assert resp.json()["is_public"] is True
        assert resp.json()["current_user_role"] == "member"

    @pytest.mark.parametrize(
        "bad_code",
        (
            "short",
            "A" * 44,
            "A" * 42 + "!",
            "!" * 43,
        ),
    )
    def test_invalid_codes_create_no_membership(self, client, owner_member_nonmember_run, bad_code):
        data = owner_member_nonmember_run
        db = data["db"]
        resp = client.post(f"/api/invites/{bad_code}/accept", headers=non_member_headers(data))
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Invite not found"}
        assert db.query(models.BeerRunMember).count() == 5  # BeerRunJPN + 4 fixture rows

    def test_case_changed_code_accept_404(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        code = create_invite(client, data)
        resp = client.post(f"/api/invites/{code.swapcase()}/accept", headers=non_member_headers(data))
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Invite not found"}
        assert db.query(models.BeerRunMember).count() == 5  # BeerRunJPN + 4 fixture rows


# ── Concurrency and rollback (AR-1.3, AR-3.2) ─────────────────────────


class TestConcurrentCreation:
    """AR-1.3 — code-collision retry, lost-race re-read, sanitized rollback."""

    def test_code_collision_rolls_back_and_retries_with_fresh_code(
        self, monkeypatch, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        db = data["db"]
        collide_code = "X" * 43
        fresh_code = "Y" * 43
        db.add(models.BeerRunInvite(beer_run_id=data["public_run"].id, code=collide_code))
        db.commit()

        calls = {"n": 0}
        real_gen = invite_routes._generate_code

        def flaky():
            calls["n"] += 1
            return collide_code if calls["n"] == 1 else fresh_code

        monkeypatch.setattr(invite_routes, "_generate_code", flaky)

        resp = client.post(
            f"/api/beer-runs/{data['private_run'].id}/invites",
            headers=owner_headers(data),
        )
        assert resp.status_code == 201
        assert resp.json()["code"] == fresh_code
        assert calls["n"] == 2

    def test_lost_concurrent_first_create_returns_winner(
        self, monkeypatch, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        winner_code = "W" * 43
        db.add(models.BeerRunInvite(beer_run_id=run.id, code=winner_code))
        db.commit()

        real_find = invite_routes._find_invite_for_run
        calls = {"n": 0}

        def flaky(db_session, beer_run_id):
            calls["n"] += 1
            if calls["n"] == 1:
                return None  # pre-check ran before the winner was visible
            return real_find(db_session, beer_run_id)

        monkeypatch.setattr(invite_routes, "_find_invite_for_run", flaky)
        monkeypatch.setattr(invite_routes, "_generate_code", lambda: "Q" * 43)

        resp = client.post(f"/api/beer-runs/{run.id}/invites", headers=owner_headers(data))
        assert resp.status_code == 200
        assert resp.json()["code"] == winner_code
        assert resp.json()["beer_run_id"] == run.id
        assert calls["n"] >= 2

    def test_exhausted_code_collisions_return_sanitized_500(
        self, monkeypatch, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        collide_code = "X" * 43
        db.add(models.BeerRunInvite(beer_run_id=data["public_run"].id, code=collide_code))
        db.commit()

        monkeypatch.setattr(invite_routes, "_generate_code", lambda: collide_code)

        resp = client.post(f"/api/beer-runs/{run.id}/invites", headers=owner_headers(data))
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Unable to create invite"}
        assert db.query(models.BeerRunInvite).filter(
            models.BeerRunInvite.beer_run_id == run.id
        ).count() == 0

    def test_unrelated_create_failure_returns_sanitized_500(
        self, monkeypatch, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]

        def boom(self):
            raise RuntimeError("unexpected persistence failure")

        monkeypatch.setattr(Session, "commit", boom)

        resp = client.post(f"/api/beer-runs/{run.id}/invites", headers=owner_headers(data))
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Unable to create invite"}
        assert "RuntimeError" not in resp.text
        assert db.query(models.BeerRunInvite).count() == 0


class TestConcurrentAcceptance:
    """AR-3.2, AR-3.3 — duplicate-insert race re-read and sanitized rollback."""

    def test_lost_duplicate_membership_race_preserves_committed_role(
        self, monkeypatch, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        db = data["db"]
        run = data["private_run"]
        code = create_invite(client, data, run)

        # A concurrent accept already committed this membership.
        db.add(
            models.BeerRunMember(
                beer_run_id=run.id, user_id=data["non_member"].id, role="member"
            )
        )
        db.commit()

        real_find = invite_routes._find_membership
        calls = {"n": 0}

        def flaky(db_session, beer_run_id, user_id):
            calls["n"] += 1
            if calls["n"] == 1:
                return None  # pre-check missed the committed membership
            return real_find(db_session, beer_run_id, user_id)

        monkeypatch.setattr(invite_routes, "_find_membership", flaky)

        resp = client.post(f"/api/invites/{code}/accept", headers=non_member_headers(data))
        assert resp.status_code == 200
        assert resp.json()["current_user_role"] == "member"
        assert calls["n"] >= 2
        count = (
            db.query(models.BeerRunMember)
            .filter(
                models.BeerRunMember.beer_run_id == run.id,
                models.BeerRunMember.user_id == data["non_member"].id,
            )
            .count()
        )
        assert count == 1

    def test_unrelated_accept_failure_returns_sanitized_500(
        self, monkeypatch, client, owner_member_nonmember_run
    ):
        data = owner_member_nonmember_run
        db = data["db"]
        code = create_invite(client, data)

        def boom(self):
            raise RuntimeError("unexpected persistence failure")

        monkeypatch.setattr(Session, "commit", boom)

        resp = client.post(f"/api/invites/{code}/accept", headers=non_member_headers(data))
        assert resp.status_code == 500
        assert resp.json() == {"detail": "Unable to accept invite"}
        assert "RuntimeError" not in resp.text
        assert db.query(models.BeerRunMember).count() == 5  # no partial insert


# ── Run deletion integration ───────────────────────────────────────────


class TestRunDeletion:
    """Run deletion removes its invites while preserving unrelated ones."""

    def test_delete_run_removes_invites_and_memberships(self, client, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db = data["db"]
        code_private = create_invite(client, data, data["private_run"])
        code_public = create_invite(client, data, data["public_run"])

        resp = client.delete(
            f"/api/beer-runs/{data['private_run'].id}",
            headers=owner_headers(data),
        )
        assert resp.status_code == 200

        # The deleted run's code is now uniformly 404.
        assert client.get(f"/api/invites/{code_private}").status_code == 404

        # The unrelated invite and its run remain intact.
        preview = client.get(f"/api/invites/{code_public}")
        assert preview.status_code == 200
        assert preview.json()["beer_run_id"] == data["public_run"].id

        # Memberships for the deleted run are gone; the public run's remain.
        assert db.query(models.BeerRunMember).filter(
            models.BeerRunMember.beer_run_id == data["private_run"].id
        ).count() == 0
        assert db.query(models.BeerRunMember).filter(
            models.BeerRunMember.beer_run_id == data["public_run"].id
        ).count() == 2
