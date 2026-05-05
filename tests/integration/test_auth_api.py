import pytest


@pytest.mark.asyncio
async def test_register_and_login(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "integration@test.com",
            "password": "secure123",
        },
    )
    assert register_response.status_code == 201
    data = register_response.json()
    assert data["email"] == "integration@test.com"
    assert "id" in data

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "integration@test.com",
            "password": "secure123",
        },
    )
    assert login_response.status_code == 200
    assert login_response.json()["message"] == "Logged in successfully"
    assert "access_token" in client.cookies
    assert "refresh_token" in client.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@test.com",
            "password": "secure123",
        },
    )

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "dup@test.com",
            "password": "secure123",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrongpw@test.com",
            "password": "secure123",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "wrongpw@test.com",
            "password": "totallywrong",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "nobody@test.com",
            "password": "whatever",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_success(client):
    email = "me@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )

    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == email


@pytest.mark.asyncio
async def test_refresh_token_success(client):
    email = "refresh@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )

    old_access_token = client.cookies.get("access_token")
    old_refresh_token = client.cookies.get("refresh_token")

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert response.json()["message"] == "Token refreshed"

    new_access_token = client.cookies.get("access_token")
    new_refresh_token = client.cookies.get("refresh_token")

    assert new_access_token != old_access_token
    assert new_refresh_token != old_refresh_token


@pytest.mark.asyncio
async def test_refresh_token_missing(client):
    # Call refresh without any cookies
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["message"] == "Refresh token missing"


@pytest.mark.asyncio
async def test_logout_success(client):
    email = "logout@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password123"},
    )

    assert "access_token" in client.cookies

    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

    access_cookie = client.cookies.get("access_token")
    assert not access_cookie
