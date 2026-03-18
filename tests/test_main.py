import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from main import app
import models

# Setup test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_create_entry_and_leaderboard():
    # Create entry
    response = client.post(
        "/api/entries",
        data={
            "username": "testuser",
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 35.6895,
            "longitude": 139.6917
        }
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Check leaderboard
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["username"] == "testuser"
    assert data[0]["total_liters"] == 0.5
    assert data[0]["total_alcohol"] == 0.5 * (5.0 / 100.0)
