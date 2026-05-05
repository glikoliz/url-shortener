from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.cache_service import CacheService


@pytest.fixture
def mock_redis():
    return AsyncMock()


@pytest.fixture
def cache_service(mock_redis):
    return CacheService(mock_redis)


@pytest.mark.asyncio
async def test_get_url_hit(cache_service, mock_redis):
    mock_redis.get.return_value = "https://example.com"
    result = await cache_service.get_url("test")
    assert result == "https://example.com"
    mock_redis.get.assert_awaited_once_with("url:test")


@pytest.mark.asyncio
async def test_get_url_miss(cache_service, mock_redis):
    mock_redis.get.return_value = None
    result = await cache_service.get_url("test")
    assert result is None


@pytest.mark.asyncio
async def test_get_url_no_redis():
    service = CacheService(None)
    result = await service.get_url("test")
    assert result is None


@pytest.mark.asyncio
async def test_set_url_basic(cache_service, mock_redis):
    await cache_service.set_url("test", "https://example.com")
    mock_redis.set.assert_awaited_once_with("url:test", "https://example.com", ex=3600)


@pytest.mark.asyncio
async def test_set_url_with_expiration(cache_service, mock_redis):
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    await cache_service.set_url("test", "https://example.com", expires_at=expires_at)
    # TTL should be around 600s
    args, kwargs = mock_redis.set.call_args
    assert args[0] == "url:test"
    assert args[1] == "https://example.com"
    assert 590 <= kwargs["ex"] <= 601


@pytest.mark.asyncio
async def test_set_url_expired(cache_service, mock_redis):
    expires_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    await cache_service.set_url("test", "https://example.com", expires_at=expires_at)
    mock_redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_url(cache_service, mock_redis):
    await cache_service.delete_url("test")
    mock_redis.delete.assert_awaited_once_with("url:test")


@pytest.mark.asyncio
async def test_get_json_hit(cache_service, mock_redis):
    mock_redis.get.return_value = '{"foo": "bar"}'
    result = await cache_service.get_json("key")
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_get_json_miss(cache_service, mock_redis):
    mock_redis.get.return_value = None
    result = await cache_service.get_json("key")
    assert result is None


@pytest.mark.asyncio
async def test_invalidate_stats(cache_service, mock_redis):
    await cache_service.invalidate_stats("test")
    mock_redis.delete.assert_awaited_once()
    args = mock_redis.delete.call_args[0]
    assert "stats:test:all" in args
    assert "stats:test:day" in args
    assert "stats:test:hour" in args
    assert "stats:test:minute" in args


@pytest.mark.asyncio
async def test_user_links_cache(cache_service, mock_redis):
    links = [{"id": 1, "code": "abc"}]
    await cache_service.set_user_links(123, links)
    mock_redis.set.assert_awaited_once()

    mock_redis.get.return_value = '[{"id": 1, "code": "abc"}]'
    result = await cache_service.get_user_links(123)
    assert result == links


@pytest.mark.asyncio
async def test_invalidate_user_links(cache_service, mock_redis):
    await cache_service.invalidate_user_links(123)
    mock_redis.delete.assert_awaited_once_with("user_links:123")
