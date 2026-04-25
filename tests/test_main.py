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
