def test_login(client):
    # Login with the user created by sync_users.py
    response = client.post("/token", data={"username": "user", "password": "password"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_fail(client):
    response = client.post("/token", data={"username": "user", "password": "wrongpassword"})
    assert response.status_code == 401

def test_protected_route_fail(client):
    # Try to post entry without token
    response = client.post("/api/entries", data={
        "drink_type": "Beer",
        "abv": 5.0,
        "quantity": 0.5,
        "latitude": 0.0,
        "longitude": 0.0
    })
    assert response.status_code == 401

def test_protected_route_success(client):
    # Get token
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]
    
    # Post entry with token
    response = client.post("/api/entries", 
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 0.0,
            "longitude": 0.0
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_protected_route_success_no_image(client):
    # Get token
    login_res = client.post("/token", data={"username": "user", "password": "password"})
    token = login_res.json()["access_token"]
    
    # Post entry with token but NO image
    response = client.post("/api/entries", 
        data={
            "drink_type": "Beer",
            "abv": 5.0,
            "quantity": 0.5,
            "latitude": 0.0,
            "longitude": 0.0,
            # Explicitly omit image or send empty
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
