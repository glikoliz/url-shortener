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
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


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
