import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.config import settings

logger = logging.getLogger(__name__)

redis_client: Redis | None = None


async def init_redis() -> Redis:
    global redis_client
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None


async def get_redis() -> Redis:
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")
    return redis_client


async def publish_link_update(user_id: int, data: dict) -> None:
    """Publish link update event to Redis for SSE."""
    if redis_client is None:
        logger.warning(
            f"Redis not initialized. Cannot publish update for user {user_id}"
        )
        return

    try:
        channel = f"sse:user:{user_id}"

        def datetime_handler(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        await redis_client.publish(channel, json.dumps(data, default=datetime_handler))
    except Exception as e:
        logger.error(
            f"Failed to publish link update for user {user_id}: {e}", exc_info=True
        )


@asynccontextmanager
async def subscribe_to_user_updates(user_id: int) -> AsyncGenerator[PubSub, None]:
    """Subscribe to user-specific SSE channel with automatic cleanup."""
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")

    pubsub = redis_client.pubsub()
    try:
        await pubsub.subscribe(f"sse:user:{user_id}")
        yield pubsub
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
