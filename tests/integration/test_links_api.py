import pytest


async def _get_token(client, email="links@test.com", password="secure123"):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_link(client):
    token = await _get_token(client)

    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://google.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_url"] == "https://google.com/"
    assert "short_code" in data
    assert "short_url" in data
    assert data["clicks"] == 0


@pytest.mark.asyncio
async def test_create_link_custom_code(client):
    token = await _get_token(client, email="custom@test.com")

    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "mycode"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["short_code"] == "mycode"


@pytest.mark.asyncio
async def test_create_link_unauthorized(client):
    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://google.com"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_redirect_link(client):
    token = await _get_token(client, email="redirect@test.com")

    create_response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "go123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_response.status_code == 201

    redirect_response = await client.get("/s/go123", follow_redirects=False)
    assert redirect_response.status_code == 302
    assert redirect_response.headers["location"] == "https://example.com/"


@pytest.mark.asyncio
async def test_get_link_stats(client):
    token = await _get_token(client, email="stats@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "stats1"},
        headers={"Authorization": f"Bearer {token}"},
    )

    await client.get("/s/stats1", follow_redirects=False)
    await client.get("/s/stats1", follow_redirects=False)

    response = await client.get("/api/v1/links/stats1")
    assert response.status_code == 200
    assert response.json()["clicks"] == 2


@pytest.mark.asyncio
async def test_delete_link(client):
    token = await _get_token(client, email="delete@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "del01"},
        headers={"Authorization": f"Bearer {token}"},
    )

    delete_response = await client.delete(
        "/api/v1/links/del01",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_response.status_code == 204

    get_response = await client.get("/api/v1/links/del01")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_link_forbidden(client):
    token_owner = await _get_token(client, email="owner@test.com")
    token_other = await _get_token(client, email="other@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "own01"},
        headers={"Authorization": f"Bearer {token_owner}"},
    )

    response = await client.delete(
        "/api/v1/links/own01",
        headers={"Authorization": f"Bearer {token_other}"},
    )
    assert response.status_code == 403
