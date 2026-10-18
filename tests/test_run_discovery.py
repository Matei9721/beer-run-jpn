from datetime import datetime

import pytest

from beer_run import models
from conftest import TestingSessionLocal


def test_discovery_pages_are_public_bounded_and_stable(client):
    with TestingSessionLocal() as db:
        # Identical timestamps need a deterministic ID tie-breaker.
        runs = [models.BeerRun(name=f"Crew {i:02}", is_public=True, created_at=datetime(2030, 1, 1)) for i in range(14)]
        db.add_all(runs)
        db.add(models.BeerRun(name="Hidden Crew", is_public=False, created_at=datetime(2031, 1, 1)))
        db.commit()
        expected = [run.id for run in reversed(runs)]
    first = client.get("/api/beer-runs", params={"view": "discover", "limit": 7}).json()
    second = client.get("/api/beer-runs", params={"view": "discover", "limit": 7, "offset": 7}).json()
    assert [run["id"] for run in first + second] == expected
    assert all(run["is_public"] and run["current_user_role"] is None for run in first + second)
    latest = client.get("/api/beer-runs", params={"view": "discover", "limit": 3}).json()
    assert [run["id"] for run in latest] == expected[:3]
    assert client.get("/api/beer-runs", params={"view": "discover", "offset": 100}).json() == []


def test_discovery_search_is_literal_case_insensitive_and_public(client):
    with TestingSessionLocal() as db:
        db.add_all([
            models.BeerRun(name="Kyoto Weekend", is_public=True),
            models.BeerRun(name="Secret Weekend", is_public=False),
            models.BeerRun(name="Trip_One", is_public=True),
        ])
        db.commit()
    rows = client.get("/api/beer-runs", params={"view": "discover", "q": " WEEKend "}).json()
    assert [run["name"] for run in rows] == ["Kyoto Weekend"]
    assert client.get("/api/beer-runs", params={"view": "discover", "q": "%_"}).json() == []
    token = client.post("/token", data={"username": "user", "password": "password"}).json()["access_token"]
    rows = client.get("/api/beer-runs?view=discover", headers={"Authorization": f"Bearer {token}"}).json()
    assert all(run["is_public"] for run in rows)


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 22}, {"offset": -1}, {"offset": 100001},
    {"q": "x"}, {"q": " "}, {"q": "x" * 65}, {"name": "BeerRunJPN"},
])
def test_discovery_rejects_invalid_bounds(client, params):
    assert client.get("/api/beer-runs", params={"view": "discover", **params}).status_code == 422


def test_discovery_reflects_new_public_runs(client):
    token = client.post("/token", data={"username": "user", "password": "password"}).json()["access_token"]
    created = client.post("/api/beer-runs", json={"name": "Newly Started Trip", "is_public": True}, headers={"Authorization": f"Bearer {token}"})
    assert created.status_code == 201
    latest = client.get("/api/beer-runs?view=discover&limit=3").json()
    assert latest[0]["id"] == created.json()["id"]
