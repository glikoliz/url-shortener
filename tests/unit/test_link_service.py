from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def mock_resolve_url():
    with patch(
        "app.services.link_service._resolve_final_url", new_callable=AsyncMock
    ) as m:
        m.side_effect = lambda url: url
        yield m


@pytest.mark.asyncio
async def test_shorten_url_auto_code(link_service, mock_link):
    created_link = mock_link(short_code="AbC123")
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://google.com",
        user_id=1,
    )

    assert result.short_url
    link_service.link_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_shorten_url_auto_code_retry_on_collision(link_service, mock_link):
    created_link = mock_link(short_code="Free12")

    link_service.link_repo.get_by_code.side_effect = [mock_link(), None]
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://google.com",
        user_id=1,
    )

    assert link_service.link_repo.get_by_code.call_count == 2
    assert "Free12" in result.short_url


@pytest.mark.asyncio
async def test_shorten_url_custom_code(link_service, mock_link):
    created_link = mock_link(short_code="mylink")
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://example.com",
        user_id=1,
        custom_code="mylink",
    )

    assert "mylink" in result.short_url


@pytest.mark.asyncio
async def test_shorten_url_custom_code_taken(link_service, mock_link):
    link_service.link_repo.get_by_code.return_value = mock_link()

    with pytest.raises(HTTPException) as exc_info:
        await link_service.shorten_url(
            original_url="https://example.com",
            user_id=1,
            custom_code="abc123",
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_shorten_url_with_ttl(link_service, mock_link):
    created_link = mock_link(
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30)
    )
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://example.com",
        user_id=1,
        ttl_minutes=30,
    )

    assert result.expires_at is not None
    link_service.link_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_link_success(link_service, mock_link):
    link = mock_link(original_url="https://google.com")
    link_service.link_repo.get_by_code.return_value = link

    url = await link_service.resolve_link("abc123")

    assert url == "https://google.com"


@pytest.mark.asyncio
async def test_increment_click_redis(link_service, mock_link, mock_redis):
    link = mock_link(id=1, user_id=1, short_code="abc123", clicks=5)
    link_service.link_repo.get_by_code.return_value = link
    mock_redis.exists.return_value = False
    mock_redis.incr.return_value = 6

    with patch("app.services.link_service.publish_link_update") as mock_publish:
        new_count = await link_service.increment_click_redis("abc123")

        assert new_count == 6
        mock_redis.exists.assert_awaited_once()
        mock_redis.set.assert_awaited_once()
        mock_redis.incr.assert_awaited_once()
        mock_publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_click_db(link_service, mock_link):
    """Test only the DB recording part of click counting."""
    link = mock_link(id=1, short_code="abc123")
    link_service.link_repo.get_by_code.return_value = link

    await link_service.count_click("abc123", "1.2.3.4", "Mozilla", "https://ref.com")

    link_service.link_repo.increment_clicks_by_code.assert_awaited_once_with("abc123")
    link_service.click_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_clicks(link_service, mock_link):
    link = mock_link(id=1, user_id=1, short_code="test1")
    link_service.link_repo.get_by_code.return_value = link
    link_service.click_repo.get_by_link_id.return_value = ([], 0)

    result = await link_service.get_clicks("test1", user_id=1)

    assert result.items == []
    assert result.total == 0
    link_service.click_repo.get_by_link_id.assert_awaited_once_with(
        1, skip=0, limit=50, ip=None, country=None
    )


@pytest.mark.asyncio
async def test_get_click_stats(link_service, mock_link, mock_redis):
    link = mock_link(id=1, user_id=1, short_code="test1", clicks=5)
    link_service.link_repo.get_by_code.return_value = link

    # Use side_effect to return None for cache-miss on stats, but "10" for click count
    async def redis_get_side_effect(key):
        if ":clicks" in key:
            return "10"
        return None

    mock_redis.get.side_effect = redis_get_side_effect

    link_service.click_repo.get_aggregated_stats.return_value = {
        "total_clicks": 0,
        "unique_clicks": 0,
        "unique_ips": 0,
        "granularity": "day",
        "clicks_over_time": [],
        "clicks_by_day": [],
        "top_referers": [],
        "top_countries": [],
    }

    result = await link_service.get_click_stats("test1", user_id=1)

    assert result.total_clicks == 10  # Merged from Redis
    assert result.clicks_by_day is not None


@pytest.mark.asyncio
async def test_resolve_link_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await link_service.resolve_link("nonexistent")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_link_expired(link_service, mock_link):
    expired_link = mock_link(expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    link_service.link_repo.get_by_code.return_value = expired_link

    with pytest.raises(HTTPException) as exc_info:
        await link_service.resolve_link("abc123")

    assert exc_info.value.status_code == 410


@pytest.mark.asyncio
async def test_get_stats_success(link_service, mock_link, mock_redis):
    link = mock_link(id=1, clicks=42, short_code="test01")
    link_service.link_repo.get_by_code.return_value = link
    mock_redis.get.return_value = "50"

    result = await link_service.get_stats("test1", user_id=1)

    assert result.clicks == 50


@pytest.mark.asyncio
async def test_get_stats_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await link_service.get_stats("notfound", user_id=1)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_link_owner(link_service, mock_link):
    link = mock_link(user_id=1)
    link_service.link_repo.get_by_code.return_value = link

    await link_service.delete_link("abc123", user_id=1)

    link_service.link_repo.delete.assert_awaited_once_with(link)


@pytest.mark.asyncio
async def test_delete_link_non_owner(link_service, mock_link):
    link = mock_link(user_id=1)
    link_service.link_repo.get_by_code.return_value = link

    with pytest.raises(HTTPException) as exc_info:
        await link_service.delete_link("abc123", user_id=999)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_link_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await link_service.delete_link("nonexistent", user_id=1)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_link_cache_hit(link_service, mock_redis):
    mock_redis.get.return_value = "https://cached-url.com"

    url = await link_service.resolve_link("cache1")

    assert url == "https://cached-url.com"
    link_service.link_repo.get_by_code.assert_not_awaited()
    mock_redis.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_link_cache_miss(link_service, mock_link, mock_redis):
    mock_redis.get.return_value = None
    link = mock_link(original_url="https://db-url.com", short_code="miss1")
    link_service.link_repo.get_by_code.return_value = link

    url = await link_service.resolve_link("miss1")

    assert url == "https://db-url.com"
    link_service.link_repo.get_by_code.assert_awaited_once_with("miss1")
    mock_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_link_invalidates_cache(link_service, mock_link, mock_redis):
    link = mock_link(user_id=1, short_code="del1")
    link_service.link_repo.get_by_code.return_value = link

    await link_service.delete_link("del1", user_id=1)

    # One for the URL, one for the user's link list
    assert mock_redis.delete.await_count == 2


@pytest.mark.asyncio
async def test_shorten_url_indirect_self_reference(link_service, mock_resolve_url):
    from app.config import settings

    mock_resolve_url.side_effect = None
    mock_resolve_url.return_value = f"{settings.base_url}/s/xyz"

    with pytest.raises(HTTPException) as exc_info:
        await link_service.shorten_url(
            original_url="https://evil-proxy.com/redirect",
            user_id=1,
        )

    assert exc_info.value.status_code == 400
    assert "pointing to this service" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_shorten_url_self_redirect(link_service):
    with pytest.raises(HTTPException) as exc_info:
        await link_service.shorten_url(
            original_url="http://localhost:8000/s/abc123",
            user_id=1,
        )

    assert exc_info.value.status_code == 400
    assert "already a short link" in exc_info.value.detail
