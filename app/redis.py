import json

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.config import settings

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
        return
    channel = f"sse:user:{user_id}"
    await redis_client.publish(channel, json.dumps(data))


async def subscribe_to_user_updates(user_id: int) -> PubSub:
    """Subscribe to user-specific SSE channel."""
    if redis_client is None:
        raise RuntimeError("Redis is not initialized")
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"sse:user:{user_id}")
    return pubsub
