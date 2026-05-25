import os
from pathlib import Path
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = Path(tempfile.gettempdir()) / "beer-run-jpn-test.db"
os.environ["BOOZERUN_DATABASE_PATH"] = str(TEST_DB_PATH)
os.environ["SQLALCHEMY_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

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


@pytest.fixture(autouse=True)
def setup_db(request):
    if "client" not in request.fixturenames:
        yield
        return

    engine.dispose()
    reset_test_database()

    db = TestingSessionLocal()
    db.add(models.User(username="user", hashed_password=auth.get_password_hash("password")))
    db.commit()
    db.close()

    yield
    engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
