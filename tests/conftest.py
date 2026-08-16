import os
from pathlib import Path
import secrets
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = Path(tempfile.gettempdir()) / "beer-run-jpn-test.db"
os.environ["BOOZERUN_DATABASE_PATH"] = str(TEST_DB_PATH)
os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)
TEST_SIGNUP_CODE = "test-only-private-signup-code"
os.environ["SIGNUP_CODE"] = TEST_SIGNUP_CODE

import auth
import models
from database import get_db
from migrations.runner import apply_migrations

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
apply_migrations(TEST_DB_PATH)

from main import app


SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def reset_test_database():
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(TEST_DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        tables = [
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        ]
        for table in tables:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.execute("PRAGMA foreign_keys = ON")
    apply_migrations(TEST_DB_PATH)


def add_default_user_fixture():
    db = TestingSessionLocal()
    try:
        user = models.User(username="user", hashed_password=auth.get_password_hash("password"))
        db.add(user)
        db.commit()
        db.refresh(user)

        beer_run = db.query(models.BeerRun).filter(models.BeerRun.name == "BeerRunJPN").one()
        db.add(models.BeerRunMember(beer_run_id=beer_run.id, user_id=user.id, role="member"))
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db(request):
    if "client" not in request.fixturenames:
        yield
        return

    engine.dispose()
    reset_test_database()
    add_default_user_fixture()

    yield
    engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def owner_member_nonmember_run(client):
    """Create a private and a public run with three distinct identities.

    The three users reflect their persisted membership state in the runs:
      - ``owner``: role = "owner" membership in both runs.
      - ``member``: role = "member" membership in both runs (a genuine normal
        member, not a mislabeled non-member).
      - ``non_member``: no membership row in either run.

    Yields a dict with an open ``db`` session (closed by this fixture), the two
    runs, the three User objects, and a bearer token per identity so tests can
    use the same setup for both direct policy calls and endpoint integration.
    """
    db = TestingSessionLocal()

    def _user(username: str) -> models.User:
        user = models.User(
            username=username,
            hashed_password=auth.get_password_hash("password"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    owner = _user("RunOwner")
    member = _user("RunMember")
    non_member = _user("RunStranger")

    private_run = models.BeerRun(name="Private Permission Run", is_public=False)
    public_run = models.BeerRun(name="Public Permission Run", is_public=True)
    db.add_all([private_run, public_run])
    db.commit()
    db.refresh(private_run)
    db.refresh(public_run)

    db.add_all([
        models.BeerRunMember(beer_run_id=private_run.id, user_id=owner.id, role="owner"),
        models.BeerRunMember(beer_run_id=private_run.id, user_id=member.id, role="member"),
        models.BeerRunMember(beer_run_id=public_run.id, user_id=owner.id, role="owner"),
        models.BeerRunMember(beer_run_id=public_run.id, user_id=member.id, role="member"),
    ])
    db.commit()

    def _token(user: models.User) -> str:
        return auth.create_access_token({"sub": str(user.id)})

    yield {
        "db": db,
        "private_run": private_run,
        "public_run": public_run,
        "owner": owner,
        "member": member,
        "non_member": non_member,
        "owner_token": _token(owner),
        "member_token": _token(member),
        "non_member_token": _token(non_member),
    }
    db.close()
