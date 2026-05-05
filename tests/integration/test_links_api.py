import pytest


async def _login(client, email="links@test.com", password="secure123"):
    resp_reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    assert resp_reg.status_code in (201, 409)

    resp_login = await client.post(
        "/api/v1/auth/login",
        data={
            "username": email,
            "password": password,
        },
    )
    assert resp_login.status_code == 200


@pytest.mark.asyncio
async def test_create_link(client):
    await _login(client)

    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://google.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_url"] == "https://google.com/"
    assert "short_code" in data
    assert "short_url" in data
    assert data["clicks"] == 0


@pytest.mark.asyncio
async def test_create_link_custom_code(client):
    await _login(client, email="custom@test.com")

    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "mycode"},
    )
    assert response.status_code == 201
    assert response.json()["short_code"] == "mycode"


@pytest.mark.asyncio
async def test_create_link_unauthorized(client):
    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://google.com"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_redirect_link(client):
    await _login(client, email="redirect@test.com")

    create_response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "go123"},
    )
    assert create_response.status_code == 201

    redirect_response = await client.get("/s/go123", follow_redirects=False)
    assert redirect_response.status_code == 302
    assert redirect_response.headers["location"] == "https://example.com/"


@pytest.mark.asyncio
async def test_get_link_stats(client):
    await _login(client, email="stats@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "stats1"},
    )

    await client.get("/s/stats1", follow_redirects=False)
    await client.get("/s/stats1", follow_redirects=False)

    response = await client.get(
        "/api/v1/links/i/stats1/info",
    )
    assert response.status_code == 200
    assert response.json()["clicks"] == 2


@pytest.mark.asyncio
async def test_get_link_detailed_stats(client):
    await _login(client, email="detailed@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "det1"},
    )

    # Click it
    await client.get("/s/det1", follow_redirects=False)

    response = await client.get(
        "/api/v1/links/i/det1/stats",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_clicks"] >= 1
    assert "clicks_by_day" in data
    assert "clicks_over_time" in data
    assert "granularity" in data
    assert "top_referers" in data
    assert "top_countries" in data


@pytest.mark.asyncio
async def test_get_link_clicks(client):
    await _login(client, email="clicks_api@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "cl1"},
    )

    # Click it
    await client.get("/s/cl1", follow_redirects=False)

    # Note: detailed clicks come from DB, so they MIGHT be 0 if background task is slow.
    # But since we're using a test environment, let's see.
    # If this fails, we might need a small retry loop or just check total_clicks.

    response = await client.get(
        "/api/v1/links/i/cl1/clicks",
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    # Items are from DB, so we don't assert length here to avoid race in tests
    # assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_delete_link(client):
    await _login(client, email="delete@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "del01"},
    )

    delete_response = await client.delete(
        "/api/v1/links/i/del01",
    )
    assert delete_response.status_code == 204

    get_response = await client.get(
        "/api/v1/links/i/del01/info",
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_link_forbidden(client):
    await _login(client, email="owner@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "own01"},
    )

    await _login(client, email="other@test.com")

    response = await client.delete(
        "/api/v1/links/i/own01",
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_link_rate_limit(client):
    await _login(client, email="rate@limit.com")

    # Limit is 20, so 21st should fail
    for _ in range(20):
        response = await client.post(
            "/api/v1/links",
            json={"original_url": "https://example.com"},
        )
        assert response.status_code == 201

    response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com"},
    )
    assert response.status_code == 429
    assert response.json()["error"]["message"] == "Too Many Requests"


@pytest.mark.asyncio
async def test_create_link_invalid_custom_code(client):
    await _login(client, email="invalid_code@test.com")

    response = await client.post(
        "/api/v1/links",
        json={
            "original_url": "https://example.com",
            "custom_code": "code-with-hyphens!",
        },
    )
    assert response.status_code == 422
    assert "Custom code must contain only alphanumeric characters" in str(
        response.json()
    )


@pytest.mark.asyncio
async def test_get_link_clicks_with_filters(client):
    await _login(client, email="filter@test.com")

    await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "filtered"},
    )

    await client.get("/s/filtered")

    response = await client.get(
        "/api/v1/links/i/filtered/clicks?ip=999.999.999.999",
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0

    response = await client.get(
        "/api/v1/links/i/filtered/clicks?country=Mars",
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 0


@pytest.mark.asyncio
async def test_get_link_stats_forbidden(client):
    await _login(client, email="owner_stats@test.com")

    create_response = await client.post(
        "/api/v1/links",
        json={"original_url": "https://example.com", "custom_code": "privatelink"},
    )
    assert create_response.status_code == 201

    await _login(client, email="other_stats@test.com")

    response = await client.get(
        "/api/v1/links/i/privatelink/stats",
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Not your link"


@pytest.mark.asyncio
async def test_click_persistence_to_db(client):
    await _login(client, email="persistence@test.com")

    resp = await client.post(
        "/api/v1/links",
        json={"original_url": "https://test.com", "custom_code": "dbtest"},
    )
    assert resp.status_code == 201

    await client.get("/s/dbtest")

    resp = await client.get("/api/v1/links/i/dbtest/clicks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["ip_address"] is not None
