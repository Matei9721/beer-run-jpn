import sqlite3
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import models
from migrations.runner import apply_migrations


def make_session(tmp_path):
    db_path = tmp_path / "beer_run_schema.db"
    apply_migrations(db_path)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Session = sessionmaker(bind=engine)
    return Session(), engine


def add_user(session, username):
    user = models.User(username=username, hashed_password="hash")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def add_beer_run(session, name="BeerRunJPN", is_public=False):
    existing = session.query(models.BeerRun).filter(models.BeerRun.name == name).first()
    if existing:
        existing.is_public = is_public
        session.commit()
        session.refresh(existing)
        return existing

    beer_run = models.BeerRun(name=name, is_public=is_public)
    session.add(beer_run)
    session.commit()
    session.refresh(beer_run)
    return beer_run


def add_membership(session, beer_run, user, role="member"):
    membership = models.BeerRunMember(beer_run_id=beer_run.id, user_id=user.id, role=role)
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return membership


def add_owner_backed_run(session, name="BeerRunJPN", owner_name="owner", is_public=False):
    owner = add_user(session, owner_name)
    beer_run = add_beer_run(session, name=name, is_public=is_public)
    add_membership(session, beer_run, owner, "owner")
    return beer_run, owner


def add_entry(session, user, beer_run, drink_type="Beer"):
    entry = models.Entry(
        drink_type=drink_type,
        abv=5.0,
        quantity=0.5,
        brand="Test",
        latitude=35.0,
        longitude=139.0,
        timestamp=datetime.now(UTC),
        user_id=user.id,
        beer_run_id=beer_run.id,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def beer_runs_without_owner(session):
    return [
        beer_run
        for beer_run in session.query(models.BeerRun).all()
        if not any(member.role == "owner" for member in beer_run.memberships)
    ]


def test_beer_run_with_two_entries_exposes_entries_relationship(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        add_entry(session, owner, beer_run, "Beer")
        add_entry(session, owner, beer_run, "Sake")

        session.refresh(beer_run)

        assert len(beer_run.entries) == 2
        assert {entry.drink_type for entry in beer_run.entries} == {"Beer", "Sake"}
    finally:
        session.close()
        engine.dispose()


def test_entry_exposes_beer_run_and_rejects_invalid_beer_run_id(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        entry = add_entry(session, owner, beer_run)

        assert entry.beer_run.name == "BeerRunJPN"

        bad_entry = models.Entry(
            drink_type="Beer",
            abv=5.0,
            quantity=0.5,
            latitude=35.0,
            longitude=139.0,
            user_id=owner.id,
            beer_run_id=9999,
        )
        session.add(bad_entry)
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_one_user_can_belong_to_two_beer_runs(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        user = add_user(session, "tamei")
        run_one = add_beer_run(session, "BeerRunJPN")
        run_two = add_beer_run(session, "Second Run")
        add_membership(session, run_one, user, "owner")
        add_membership(session, run_two, user, "owner")

        session.refresh(user)

        assert {membership.beer_run.name for membership in user.memberships} == {"BeerRunJPN", "Second Run"}
    finally:
        session.close()
        engine.dispose()


def test_two_users_can_belong_to_one_beer_run_with_roles(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        owner = add_user(session, "owner")
        member = add_user(session, "member")
        beer_run = add_beer_run(session)
        add_membership(session, beer_run, owner, "owner")
        add_membership(session, beer_run, member, "member")

        session.refresh(beer_run)

        assert {membership.user.username for membership in beer_run.memberships} == {"owner", "member"}
        assert {membership.role for membership in beer_run.memberships} == {"owner", "member"}
    finally:
        session.close()
        engine.dispose()


def test_duplicate_membership_is_rejected(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        duplicate = models.BeerRunMember(beer_run_id=beer_run.id, user_id=owner.id, role="member")
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_invalid_membership_role_is_rejected(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        user = add_user(session, "user")
        beer_run = add_beer_run(session)
        session.add(models.BeerRunMember(beer_run_id=beer_run.id, user_id=user.id, role="admin"))

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_valid_beer_run_fixtures_have_owner(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        add_owner_backed_run(session)

        assert beer_runs_without_owner(session) == []
    finally:
        session.close()
        engine.dispose()


def test_new_beer_run_defaults_to_private(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run = add_beer_run(session, "Private Run")

        assert beer_run.is_public is False
    finally:
        session.close()
        engine.dispose()


def test_duplicate_beer_run_name_is_rejected(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        add_beer_run(session, "BeerRunJPN")
        session.add(models.BeerRun(name="BeerRunJPN"))

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_beer_run_jpn_can_be_only_public_run_in_post_backfill_fixture(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        add_owner_backed_run(session, name="BeerRunJPN", is_public=True)
        add_owner_backed_run(session, name="Private Run", owner_name="second-owner")

        public_runs = session.query(models.BeerRun).filter(models.BeerRun.is_public.is_(True)).all()

        assert [run.name for run in public_runs] == ["BeerRunJPN"]
    finally:
        session.close()
        engine.dispose()


def test_additional_explicitly_public_beer_runs_are_representable(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        add_owner_backed_run(session, name="BeerRunJPN", is_public=True)
        add_owner_backed_run(session, name="Future Public Run", owner_name="future-owner", is_public=True)

        public_names = {
            run.name
            for run in session.query(models.BeerRun).filter(models.BeerRun.is_public.is_(True)).all()
        }

        assert public_names == {"BeerRunJPN", "Future Public Run"}
    finally:
        session.close()
        engine.dispose()


def test_sqlite_defaults_new_beer_run_to_private(tmp_path):
    db_path = tmp_path / "defaults.db"
    apply_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO beer_runs (name) VALUES ('Default Private')")
        assert conn.execute("SELECT is_public FROM beer_runs WHERE name = 'Default Private'").fetchone()[0] == 0


# ── Beer-run invites (Spec 008) ──────────────────────────────────────


def add_invite(session, beer_run, code):
    invite = models.BeerRunInvite(beer_run_id=beer_run.id, code=code)
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def test_beer_run_exposes_singular_invite_relationship(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        invite = add_invite(session, beer_run, "A" * 43)

        session.refresh(beer_run)

        # FR-1.1: singular beer-run-to-invite relationship.
        assert beer_run.invites.id == invite.id
        assert beer_run.invites.code == "A" * 43
        assert invite.beer_run.id == beer_run.id
        assert invite.beer_run.name == "BeerRunJPN"
    finally:
        session.close()
        engine.dispose()


def test_one_invite_per_run_is_enforced(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        add_invite(session, beer_run, "A" * 43)
        duplicate = models.BeerRunInvite(beer_run_id=beer_run.id, code="B" * 43)
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_invite_code_is_globally_unique(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        run_one, owner = add_owner_backed_run(session, name="Run One")
        run_two = add_beer_run(session, name="Run Two")
        add_invite(session, run_one, "A" * 43)
        duplicate = models.BeerRunInvite(beer_run_id=run_two.id, code="A" * 43)
        session.add(duplicate)

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_invite_must_reference_an_existing_run(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        session.add(models.BeerRunInvite(beer_run_id=9999, code="A" * 43))

        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_invite_rejects_malformed_codes(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        for bad_code in ("short", "A" * 44, "!" * 43, "A" * 42 + "!"):
            session.add(models.BeerRunInvite(beer_run_id=beer_run.id, code=bad_code))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        session.close()
        engine.dispose()


def test_invite_requires_code_and_run(tmp_path):
    session, engine = make_session(tmp_path)
    try:
        beer_run, owner = add_owner_backed_run(session)
        session.add(models.BeerRunInvite(beer_run_id=beer_run.id, code=None))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(models.BeerRunInvite(beer_run_id=None, code="A" * 43))
        with pytest.raises(IntegrityError):
            session.commit()
    finally:
        session.rollback()
        session.close()
        engine.dispose()
