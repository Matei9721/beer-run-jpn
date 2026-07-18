import pytest
import os
import sqlite3

from migrations.runner import MigrationRequired, validate_database_ready


def test_login_and_me_response_shape_are_unchanged(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"username": "user", "id": 1}


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_create_entry_and_leaderboard(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]

    # Create entry
    response = client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 35.6895,
            "longitude": 139.6917
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Check leaderboard
    response = client.get("/api/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["username"] == "user"
    assert data[0]["total_liters"] == 0.5
    assert data[0]["total_alcohol"] == 0.5 * (5.0 / 100.0)


def test_create_entry_assigns_beer_run_jpn_without_run_field(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]

    response = client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 35.6895,
            "longitude": 139.6917
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    entry_id = response.json()["entry_id"]
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        row = conn.execute(
            """
            SELECT beer_runs.name
            FROM entries
            JOIN beer_runs ON beer_runs.id = entries.beer_run_id
            WHERE entries.id = ?
            """,
            (entry_id,),
        ).fetchone()
    assert row[0] == "BeerRunJPN"


def test_entries_endpoint_keeps_payload_shape_and_filters_to_beer_run_jpn(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]
    client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 35.6895,
            "longitude": 139.6917
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        conn.execute("INSERT INTO beer_runs (name, is_public) VALUES ('Private Run', 0)")
        private_run_id = conn.execute("SELECT id FROM beer_runs WHERE name = 'Private Run'").fetchone()[0]
        conn.execute(
            """
            INSERT INTO entries
                (drink_type, abv, quantity, brand, latitude, longitude, image_path, timestamp, timezone, timezone_code, user_id, beer_run_id)
            VALUES
                ('Sake', 15.0, 0.2, 'Hidden', 1.0, 2.0, NULL, '2026-05-25 14:00:00', NULL, NULL, 1, ?)
            """,
            (private_run_id,),
        )

    response = client.get("/api/entries")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert set(data[0]) == {
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
    assert data[0]["drink_type"] == "Beer"


def test_leaderboard_totals_use_beer_run_jpn_entries_only(client):
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]
    client.post(
        "/api/entries",
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 35.6895,
            "longitude": 139.6917
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    with sqlite3.connect(os.environ["BOOZERUN_DATABASE_PATH"]) as conn:
        conn.execute("INSERT INTO beer_runs (name, is_public) VALUES ('Private Run', 0)")
        private_run_id = conn.execute("SELECT id FROM beer_runs WHERE name = 'Private Run'").fetchone()[0]
        conn.execute(
            """
            INSERT INTO entries
                (drink_type, abv, quantity, brand, latitude, longitude, timestamp, user_id, beer_run_id)
            VALUES
                ('Whiskey', 40.0, 1.0, 'Hidden', 1.0, 2.0, '2026-05-25 14:00:00', 1, ?)
            """,
            (private_run_id,),
        )

    response = client.get("/api/leaderboard")

    assert response.status_code == 200
    assert response.json() == [
        {
            "username": "user",
            "total_liters": 0.5,
            "total_alcohol": 0.5 * (5.0 / 100.0),
        }
    ]


def test_startup_readiness_blocks_missing_migration_history(tmp_path):
    db_path = tmp_path / "outdated.db"
    db_path.touch()

    with pytest.raises(MigrationRequired):
        validate_database_ready(db_path)
