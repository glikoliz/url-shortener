import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.redis import (
    close_redis,
    get_redis,
    init_redis,
    publish_link_update,
    subscribe_to_user_updates,
)


@pytest.mark.asyncio
async def test_init_and_close_redis():
    with patch("app.redis.Redis.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client

        client = await init_redis()
        assert client == mock_client
        mock_from_url.assert_called_once()

        retrieved_client = await get_redis()
        assert retrieved_client == mock_client

        await close_redis()
        mock_client.aclose.assert_awaited_once()

        with pytest.raises(RuntimeError, match="Redis is not initialized"):
            await get_redis()


@pytest.mark.asyncio
async def test_get_redis_not_initialized():
    await close_redis()
    with pytest.raises(RuntimeError, match="Redis is not initialized"):
        await get_redis()


@pytest.mark.asyncio
async def test_publish_link_update():
    with patch("app.redis.Redis.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        await init_redis()

        test_data = {"event": "test", "id": 123}
        user_id = 42

        await publish_link_update(user_id, test_data)

        expected_channel = f"sse:user:{user_id}"
        mock_client.publish.assert_awaited_once_with(
            expected_channel, json.dumps(test_data)
        )

        await close_redis()


@pytest.mark.asyncio
async def test_subscribe_to_user_updates():
    with patch("app.redis.Redis.from_url") as mock_from_url:
        mock_client = AsyncMock()
        mock_pubsub = AsyncMock()
        # pubsub() is not a coroutine
        mock_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_from_url.return_value = mock_client

        await init_redis()

        user_id = 10
        async with subscribe_to_user_updates(user_id) as ps:
            assert ps == mock_pubsub
            mock_pubsub.subscribe.assert_awaited_once_with(f"sse:user:{user_id}")

        mock_pubsub.unsubscribe.assert_awaited_once()
        mock_pubsub.close.assert_awaited_once()

        await close_redis()


@pytest.mark.asyncio
async def test_subscribe_not_initialized():
    await close_redis()
    with pytest.raises(RuntimeError, match="Redis is not initialized"):
        async with subscribe_to_user_updates(1):
            pass
