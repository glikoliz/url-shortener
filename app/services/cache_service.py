from datetime import datetime, timezone

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

    async def set_url(
        self,
        short_code: str,
        original_url: str,
        expires_at: datetime | None = None,
    ) -> None:
        ttl = self.ttl
        if expires_at:
            seconds_left = int(
                (expires_at - datetime.now(timezone.utc)).total_seconds()
            )
            if seconds_left <= 0:
                return  # Already expired, skip caching
            ttl = min(self.ttl, seconds_left)
        await self.redis.set(self._key(short_code), original_url, ex=ttl)

    async def delete_url(self, short_code: str) -> None:
        await self.redis.delete(self._key(short_code))
