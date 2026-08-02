"""Focused tests for the shared beer-run authorization policies.

The three policies in ``permissions.py`` are exercised directly with
already-resolved users and a session (FR-3.2, AR-1.3). The identities come from
the ``owner_member_nonmember_run`` fixture so ``owner``, ``member``, and
``non_member`` reflect their real persisted membership state (FR-3.1).

Bearer-token decoding belongs to ``auth.get_current_user``, not to the policies
themselves, so actual missing/invalid-token composition is covered separately by
the endpoint integration tests in ``test_beer_run_crud.py``.
"""

import pytest
from fastapi import HTTPException

import permissions

MISSING_RUN_ID = 99999


@pytest.mark.parametrize(
    "error_factory",
    (
        permissions.unauthorized_error,
        permissions.forbidden_error,
        permissions.not_found_error,
    ),
)
def test_error_factories_return_fresh_exceptions(error_factory):
    """Shared error responses must not reuse traceback-bearing exceptions."""
    first = error_factory()
    second = error_factory()

    assert first is not second
    assert first.status_code == second.status_code
    assert first.detail == second.detail
    assert first.headers == second.headers


class TestPublicReadPolicy:
    """FR-1.1, FR-1.2, FR-1.5 — public-run access and private-run concealment."""

    def test_public_run_allows_everyone_with_truthful_membership(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db, run = data["db"], data["public_run"]

        for user, expected_role in (
            (None, None),                       # logged-out caller
            (data["owner"], "owner"),
            (data["member"], "member"),
            (data["non_member"], None),         # no fabricated membership
        ):
            result = permissions.authorize_public_read(run.id, current_user=user, db=db)
            assert result.beer_run.id == run.id
            if expected_role is None:
                assert result.membership is None
            else:
                assert result.membership is not None
                assert result.membership.role == expected_role

    def test_private_run_requires_membership(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        db, run = data["db"], data["private_run"]

        for user in (data["owner"], data["member"]):
            result = permissions.authorize_public_read(run.id, current_user=user, db=db)
            assert result.beer_run.id == run.id
            assert result.membership is not None

        for user in (None, data["non_member"]):
            with pytest.raises(HTTPException) as exc:
                permissions.authorize_public_read(run.id, current_user=user, db=db)
            assert exc.value.status_code == 404
            assert exc.value.detail == "Beer-run not found"

    def test_missing_run_404(self, owner_member_nonmember_run):
        db = owner_member_nonmember_run["db"]
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_public_read(MISSING_RUN_ID, current_user=None, db=db)
        assert exc.value.status_code == 404
        assert exc.value.detail == "Beer-run not found"

    def test_public_read_ignores_name_and_tracks_is_public(self, owner_member_nonmember_run):
        """FR-3.3 — authorization follows is_public, never the run name."""
        data = owner_member_nonmember_run
        db, run = data["db"], data["public_run"]
        assert run.name != "BeerRunJPN"

        # Renaming a public run must not change authorization.
        run.name = "Renamed Public Run"
        db.commit()
        result = permissions.authorize_public_read(run.id, current_user=None, db=db)
        assert result.beer_run.id == run.id
        assert result.beer_run.name == "Renamed Public Run"
        assert result.membership is None

        # Toggling private denies anonymous and non-member callers.
        run.is_public = False
        db.commit()
        for user in (None, data["non_member"]):
            with pytest.raises(HTTPException) as exc:
                permissions.authorize_public_read(run.id, current_user=user, db=db)
            assert exc.value.status_code == 404

        # Toggling back public restores access for a non-member.
        run.is_public = True
        db.commit()
        result = permissions.authorize_public_read(run.id, current_user=data["non_member"], db=db)
        assert result.beer_run.id == run.id
        assert result.membership is None


class TestMemberPolicy:
    """FR-1.3 — member access requires authentication and a membership row."""

    def test_requires_authentication_with_bearer_header(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_member_access(
                data["private_run"].id, current_user=None, db=data["db"]
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "Could not validate credentials"
        assert exc.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_allows_owner_and_member_on_public_and_private(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        for run in (data["private_run"], data["public_run"]):
            for user in (data["owner"], data["member"]):
                result = permissions.authorize_member_access(
                    run.id, current_user=user, db=data["db"]
                )
                assert result.beer_run.id == run.id
                assert result.membership is not None

    def test_401_takes_precedence_over_missing_run(self, owner_member_nonmember_run):
        """FR-1.3 — missing/invalid auth returns 401 without revealing run existence."""
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_member_access(
                MISSING_RUN_ID, current_user=None, db=data["db"]
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "Could not validate credentials"

    def test_is_public_does_not_bypass_membership(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_member_access(
                data["public_run"].id, current_user=data["non_member"], db=data["db"]
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "Beer-run not found"

    def test_missing_run_404(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_member_access(
                MISSING_RUN_ID, current_user=data["member"], db=data["db"]
            )
        assert exc.value.status_code == 404


class TestOwnerPolicy:
    """FR-1.4 — owner access requires the owner role; everyone else is denied."""

    def test_requires_authentication_with_bearer_header(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_owner_access(
                data["private_run"].id, current_user=None, db=data["db"]
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "Could not validate credentials"
        assert exc.value.headers == {"WWW-Authenticate": "Bearer"}

    def test_allows_owner(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        for run in (data["private_run"], data["public_run"]):
            result = permissions.authorize_owner_access(
                run.id, current_user=data["owner"], db=data["db"]
            )
            assert result.beer_run.id == run.id
            assert result.membership is not None
            assert result.membership.role == "owner"

    def test_member_and_non_member_403(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        for user in (data["member"], data["non_member"]):
            with pytest.raises(HTTPException) as exc:
                permissions.authorize_owner_access(
                    data["private_run"].id, current_user=user, db=data["db"]
                )
            assert exc.value.status_code == 403
            assert exc.value.detail == "Beer-run owner access required"

    def test_401_takes_precedence_over_missing_run(self, owner_member_nonmember_run):
        """FR-1.4 — missing/invalid auth returns 401 without revealing run existence."""
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_owner_access(
                MISSING_RUN_ID, current_user=None, db=data["db"]
            )
        assert exc.value.status_code == 401
        assert exc.value.detail == "Could not validate credentials"

    def test_public_visibility_does_not_weaken_ownership(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_owner_access(
                data["public_run"].id, current_user=data["member"], db=data["db"]
            )
        assert exc.value.status_code == 403
        assert exc.value.detail == "Beer-run owner access required"

    def test_missing_run_404(self, owner_member_nonmember_run):
        data = owner_member_nonmember_run
        with pytest.raises(HTTPException) as exc:
            permissions.authorize_owner_access(
                MISSING_RUN_ID, current_user=data["owner"], db=data["db"]
            )
        assert exc.value.status_code == 404
        assert exc.value.detail == "Beer-run not found"
