from redis.asyncio import Redis

from app.config import settings


class CacheService:
    PREFIX = "link"

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.ttl = settings.cache_ttl_seconds

    def _key(self, short_code: str) -> str:
        return f"{self.PREFIX}:{short_code}"

    async def get_url(self, short_code: str) -> str | None:
        return await self.redis.get(self._key(short_code))

    async def set_url(self, short_code: str, original_url: str) -> None:
        await self.redis.set(self._key(short_code), original_url, ex=self.ttl)

    async def delete_url(self, short_code: str) -> None:
        await self.redis.delete(self._key(short_code))
