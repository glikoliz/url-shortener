from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.config import settings
from app.schemas.click import ClickStatsResponse


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
    expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    created_link = mock_link(expires_at=expires)
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    result = await link_service.shorten_url(
        original_url="https://example.com",
        user_id=1,
        expires_at=expires,
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
    mock_redis.incr.return_value = 6

    with patch("app.services.link_service.publish_link_update") as mock_publish:
        new_count = await link_service.increment_click_redis("abc123")

        assert new_count == 6
        mock_redis.set.assert_awaited_once_with(
            f"link:{link.id}:clicks", str(link.clicks), ex=86400, nx=True
        )
        mock_redis.incr.assert_awaited_once()
        mock_publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_click_db(link_service, mock_link):
    """Test only the DB recording part of click counting."""
    link = mock_link(id=1, short_code="abc123")
    link_service.link_repo.get_by_code.return_value = link
    link_service.link_repo.increment_clicks_by_code.return_value = 1

    await link_service.count_click(
        "abc123", "1.2.3.4", "US", "Mozilla", "https://ref.com"
    )

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
        1,
        skip=0,
        limit=50,
        ip=None,
        country=None,
        sort_by="clicked_at",
        sort_dir="desc",
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

    link_service.click_repo.get_aggregated_stats.return_value = ClickStatsResponse(
        total_clicks=0,
        unique_ips=0,
        granularity="day",
        clicks_over_time=[],
        clicks_by_day=[],
        top_referers=[],
        top_countries=[],
    )

    result = await link_service.get_click_stats("test1", user_id=1)

    assert result.total_clicks == 10  # Merged from Redis
    assert result.clicks_by_day is not None
    assert isinstance(result, ClickStatsResponse)


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
    # Set CacheService to return something
    with patch.object(link_service.cache, "get_url", return_value="https://cached.com"):
        url = await link_service.resolve_link("cache1")
        assert url == "https://cached.com"
        link_service.link_repo.get_by_code.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_link_cache_miss(link_service, mock_link, mock_redis):
    link = mock_link(original_url="https://db-url.com", short_code="miss1")
    link_service.link_repo.get_by_code.return_value = link

    with patch.object(link_service.cache, "get_url", return_value=None):
        with patch.object(link_service.cache, "set_url") as mock_set_cache:
            url = await link_service.resolve_link("miss1")

            assert url == "https://db-url.com"
            link_service.link_repo.get_by_code.assert_awaited_once_with("miss1")
            mock_set_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_link_invalidates_cache(link_service, mock_link, mock_redis):
    link = mock_link(user_id=1, short_code="del1")
    link_service.link_repo.get_by_code.return_value = link

    with patch.object(link_service.cache, "delete_url") as m1:
        with patch.object(link_service.cache, "invalidate_user_links") as m2:
            await link_service.delete_link("del1", user_id=1)
            m1.assert_awaited_once_with("del1")
            m2.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_shorten_url_indirect_self_reference(
    link_service, mock_resolve_url, mock_link
):
    created_link = mock_link(id=123, short_code="xyz123")
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    mock_resolve_url.side_effect = None
    mock_resolve_url.return_value = f"{settings.base_url}/s/xyz"
    bg_tasks = BackgroundTasks()

    res = await link_service.shorten_url(
        user_id=1,
        original_url="https://evil-proxy.com/redirect",
        background_tasks=bg_tasks,
    )
    assert res.short_code == "xyz123"

    link_service.link_repo.get_by_code.return_value = created_link

    await link_service._validate_link_bg(
        123, "https://evil-proxy.com/redirect", 1, "xyz123"
    )
    link_service.link_repo.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_shorten_url_anonymous(link_service, mock_link):
    created_link = mock_link(id=456, short_code="anon123", user_id=None)
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = created_link

    res = await link_service.shorten_url(
        user_id=None,
        original_url="https://google.com",
    )

    assert res.short_code == "anon123"
    assert res.user_id is None
    link_service.link_repo.create.assert_called_once()

    link_service.link_repo.get_by_code.return_value = created_link
    await link_service.count_click("anon123", "1.2.3.4", "US", "agent", "referer")

    link_service.click_repo.create.assert_not_called()
    link_service.link_repo.increment_clicks_by_code.assert_not_called()


@pytest.mark.asyncio
async def test_shorten_url_self_redirect(link_service):
    from app.config import settings

    with pytest.raises(HTTPException) as exc_info:
        await link_service.shorten_url(
            original_url=f"{settings.base_url}/s/abc123",
            user_id=1,
        )

    assert exc_info.value.status_code == 400
    assert "already a short link" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_link_info_sync(link_service, mock_link, mock_redis):
    link = mock_link(id=1, user_id=1, short_code="abc", clicks=5)
    link_service.link_repo.get_by_code.return_value = link
    mock_redis.get.return_value = "10"

    result = await link_service.get_link_info("abc", user_id=1)

    assert result.clicks == 10
    mock_redis.get.assert_awaited_once_with("link:1:clicks")


@pytest.mark.asyncio
async def test_get_user_links_hybrid_cache(link_service, mock_link, mock_redis):
    now = datetime.now(timezone.utc)
    cached_links = [
        {
            "id": 1,
            "short_code": "abc",
            "clicks": 5,
            "original_url": "http://a.com",
            "user_id": 1,
            "created_at": now.isoformat(),
        }
    ]

    with patch.object(link_service.cache, "get_user_links", return_value=cached_links):
        mock_redis.mget.return_value = ["10"]

        result = await link_service.get_user_links(user_id=1)

        assert len(result) == 1
        assert result[0].clicks == 10
        mock_redis.mget.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_updates_stream(link_service):
    user_id = 1
    mock_pubsub = AsyncMock()
    messages = [{"type": "message", "data": '{"test": "data"}'}]

    async def mock_listen():
        for m in messages:
            yield m

    mock_pubsub.listen = mock_listen

    with patch("app.services.link_service.subscribe_to_user_updates") as mock_sub:
        mock_sub.return_value.__aenter__.return_value = mock_pubsub

        stream = link_service.get_updates_stream(user_id)
        events = []
        async for event in stream:
            events.append(event)

        assert ": ping\n\n" in events
        assert 'data: {"test": "data"}\n\n' in events


@pytest.mark.asyncio
async def test_get_user_links_cache_miss(link_service, mock_link, mock_redis):
    with patch.object(link_service.cache, "get_user_links", return_value=None):
        link_service.link_repo.get_by_user_id.return_value = [
            mock_link(id=1, short_code="abc")
        ]
        mock_redis.mget.return_value = ["10"]

        result = await link_service.get_user_links(user_id=1)

        assert len(result) == 1
        assert result[0].clicks == 10
        link_service.link_repo.get_by_user_id.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_resolve_link_not_found_helper(link_service):
    link_service.link_repo.get_by_code.return_value = None
    with pytest.raises(HTTPException) as exc:
        await link_service.resolve_link("missing")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_link_expired_helper(link_service, mock_link):
    expired = datetime.now(timezone.utc) - timedelta(days=1)
    link = mock_link(expires_at=expired)
    link_service.link_repo.get_by_code.return_value = link

    with pytest.raises(HTTPException) as exc:
        await link_service.resolve_link("expired")
    assert exc.value.status_code == 410


@pytest.mark.asyncio
async def test_record_click_bg_error(link_service):
    with patch(
        "app.services.link_service.LinkService.count_click",
        side_effect=Exception("DB Error"),
    ):
        with patch("app.services.link_service.logger.error") as mock_log:
            await link_service.record_click_bg("abc", "1.1.1.1", "US", "UA", "ref")
            mock_log.assert_called()


@pytest.mark.asyncio
async def test_get_link_info_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None
    with pytest.raises(HTTPException) as exc:
        await link_service.get_link_info("nonexistent", 1)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_record_click_bg(link_service, mock_redis):
    with patch("app.services.link_service.LinkService.count_click") as mock_count:
        await link_service.record_click_bg("abc", "1.2.3.4", "US", "UA", "ref")
        mock_count.assert_awaited_once_with("abc", "1.2.3.4", "US", "UA", "ref")


@pytest.mark.asyncio
async def test_count_click_db_recording(link_service, mock_link):
    link = mock_link(id=1, short_code="abc")
    link_service.link_repo.get_by_code.return_value = link

    await link_service.count_click("abc", "1.2.3.4", "US", None, None)

    link_service.click_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_shorten_url_with_ttl_minutes(link_service, mock_link):
    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.return_value = mock_link()

    await link_service.shorten_url("http://example.com", 1, ttl_minutes=60)
    args, kwargs = link_service.link_repo.create.call_args
    link = args[0]
    assert link.expires_at is not None
    diff = link.expires_at - datetime.now(timezone.utc)
    assert 3500 < diff.total_seconds() < 3700


@pytest.mark.asyncio
async def test_shorten_url_already_our_service(link_service):
    from app.config import settings

    with pytest.raises(HTTPException) as exc:
        await link_service.shorten_url(f"{settings.base_url}/dashboard", 1)
    assert exc.value.status_code == 400
    assert "Original URL is already pointing" in exc.value.detail


@pytest.mark.asyncio
async def test_shorten_url_integrity_error_retry(link_service, mock_link):
    from sqlalchemy.exc import IntegrityError

    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.side_effect = [
        IntegrityError(None, None, None),
        mock_link(),
    ]

    await link_service.shorten_url("http://example.com", 1)
    assert link_service.link_repo.create.call_count == 2


@pytest.mark.asyncio
async def test_get_click_stats_cache_hit(link_service):
    stats = {
        "total_clicks": 100,
        "unique_ips": 30,
        "granularity": "all",
        "clicks_over_time": [],
        "clicks_by_day": [],
        "top_referers": [],
        "top_countries": [],
    }
    with patch.object(link_service.cache, "get_stats", return_value=stats):
        result = await link_service.get_click_stats("abc", 1)
        assert result.total_clicks == 100
        link_service.link_repo.get_by_code.assert_not_awaited()


@pytest.mark.asyncio
async def test_increment_click_redis_no_redis(link_service):
    link_service.redis = None
    result = await link_service.increment_click_redis("abc")
    assert result == 0


@pytest.mark.asyncio
async def test_increment_click_redis_not_found(link_service):
    link_service.link_repo.get_by_code.return_value = None
    result = await link_service.increment_click_redis("nonexistent")
    assert result == 0


@pytest.mark.asyncio
async def test_count_click_not_found_log(link_service):
    link_service.link_repo.get_by_code.return_value = None
    with patch("app.services.link_service.logger.warning") as mock_log:
        await link_service.count_click("nonexistent", None, None, None, None)
        mock_log.assert_called_once()


@pytest.mark.asyncio
async def test_shorten_url_custom_code_integrity_error(link_service):
    from sqlalchemy.exc import IntegrityError

    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.side_effect = IntegrityError(None, None, None)

    with pytest.raises(HTTPException) as exc:
        await link_service.shorten_url("http://ex.com", 1, custom_code="taken")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_shorten_url_max_retries_reached(link_service):
    from sqlalchemy.exc import IntegrityError

    link_service.link_repo.get_by_code.return_value = None
    link_service.link_repo.create.side_effect = IntegrityError(None, None, None)

    link_service.link_repo.create.side_effect = [IntegrityError(None, None, None)] * 5

    with pytest.raises(HTTPException) as exc:
        await link_service.shorten_url("http://ex.com", 1)
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_get_link_info_not_owner(link_service, mock_link):
    link = mock_link(user_id=1)
    link_service.link_repo.get_by_code.return_value = link
    with pytest.raises(HTTPException) as exc:
        await link_service.get_link_info("abc", user_id=99)
    assert exc.value.status_code == 403
