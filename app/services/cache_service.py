import json
import logging
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    PREFIX_URL = "url"
    PREFIX_STATS = "stats"
    PREFIX_USER_LINKS = "user_links"

    def __init__(self, redis: Redis | None) -> None:
        self.redis = redis
        self.redirect_ttl = settings.cache_redirect_ttl
        self.stats_ttl = settings.cache_stats_ttl
        self.user_links_ttl = settings.cache_user_links_ttl

    def _url_key(self, short_code: str) -> str:
        return f"{self.PREFIX_URL}:{short_code}"

    def _stats_key(self, short_code: str, granularity: str | None) -> str:
        return f"{self.PREFIX_STATS}:{short_code}:{granularity or 'all'}"

    def _user_links_key(self, user_id: int) -> str:
        return f"{self.PREFIX_USER_LINKS}:{user_id}"

    # URL Redirection Cache (Long TTL)
    async def get_url(self, short_code: str) -> str | None:
        if not self.redis:
            return None
        url = await self.redis.get(self._url_key(short_code))
        if url:
            logger.info(f"Cache HIT [URL] for {short_code}")
        else:
            logger.info(f"Cache MISS [URL] for {short_code}")
        return url

    async def set_url(
        self,
        short_code: str,
        original_url: str,
        expires_at: datetime | None = None,
    ) -> None:
        if not self.redis:
            return

        ttl = self.redirect_ttl
        if expires_at:
            seconds_left = int(
                (expires_at - datetime.now(timezone.utc)).total_seconds()
            )
            if seconds_left <= 0:
                return
            ttl = min(self.redirect_ttl, seconds_left)
        await self.redis.set(self._url_key(short_code), original_url, ex=ttl)
        logger.info(f"Cache SET [URL] for {short_code} (TTL: {ttl}s)")

    async def delete_url(self, short_code: str) -> None:
        if not self.redis:
            return
        await self.redis.delete(self._url_key(short_code))
        logger.info(f"Cache DELETE [URL] for {short_code}")

    # Generic JSON Cache
    async def get_json(self, key: str) -> Any | None:
        if not self.redis:
            return None
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set_json(self, key: str, value: Any, ttl: int) -> None:
        if not self.redis:
            return
        await self.redis.set(key, json.dumps(value), ex=ttl)

    # Stats Cache (Short TTL)
    async def get_stats(self, short_code: str, granularity: str | None) -> Any | None:
        key = self._stats_key(short_code, granularity)
        data = await self.get_json(key)
        if data:
            logger.info(f"Cache HIT [STATS] for {short_code}:{granularity or 'all'}")
        return data

    async def set_stats(
        self, short_code: str, granularity: str | None, data: Any
    ) -> None:
        key = self._stats_key(short_code, granularity)
        await self.set_json(key, data, ttl=self.stats_ttl)
        logger.info(f"Cache SET [STATS] for {short_code}")

    # User Links Cache
    async def get_user_links(self, user_id: int) -> list[dict] | None:
        key = self._user_links_key(user_id)
        data = await self.get_json(key)
        if data:
            logger.info(f"Cache HIT [USER_LINKS] for user {user_id}")
        return data

    async def set_user_links(self, user_id: int, links: list[dict]) -> None:
        key = self._user_links_key(user_id)
        await self.set_json(key, links, ttl=self.user_links_ttl)
        logger.info(f"Cache SET [USER_LINKS] for user {user_id}")

    async def invalidate_user_links(self, user_id: int) -> None:
        if not self.redis:
            return
        await self.redis.delete(self._user_links_key(user_id))
        logger.info(f"Cache INVALIDATE [USER_LINKS] for user {user_id}")
