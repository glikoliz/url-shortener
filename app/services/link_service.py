import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.core.uow import AbstractUnitOfWork
from app.models.click_event import ClickEvent
from app.models.link import Link
from app.redis import publish_link_update, subscribe_to_user_updates
from app.schemas.click import ClickStatsResponse, PaginatedClickResponse
from app.schemas.link import LinkResponse
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class LinkService:
    def __init__(
        self,
        uow: AbstractUnitOfWork,
        redis: Redis | None = None,
        uow_factory: Callable[[], AbstractUnitOfWork] | None = None,
    ) -> None:
        self.uow = uow
        self.redis = redis
        self.uow_factory = uow_factory or (lambda: uow)
        self.cache = CacheService(redis) if redis else None

    async def shorten_url(
        self,
        original_url: str,
        user_id: int,
        custom_code: str | None = None,
        expires_at: datetime | None = None,
        ttl_minutes: int | None = None,
    ) -> LinkResponse:
        if ttl_minutes and not expires_at:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        final_url = await _resolve_final_url(original_url)

        # Basic protection against shortening our own links
        if settings.base_url in final_url:
            if "/s/" in final_url:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This is already a short link",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Original URL is already pointing to this service",
            )

        max_retries = 5
        for attempt in range(max_retries):
            short_code = custom_code or _generate_short_code()

            async with self.uow:
                if await self.uow.links.get_by_code(short_code):
                    if custom_code:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Custom short code already taken",
                        )
                    continue

                link = Link(
                    user_id=user_id,
                    original_url=final_url,
                    short_code=short_code,
                    expires_at=expires_at,
                )

                try:
                    link = await self.uow.links.create(link)
                    await self.uow.commit()
                    await self.uow.session.refresh(link)
                    await self.cache.invalidate_user_links(user_id)
                    return LinkResponse.model_validate(link)
                except IntegrityError:
                    if custom_code:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Custom short code already taken",
                        )
                    if attempt == max_retries - 1:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to generate unique short code",
                        )
                    continue

    async def resolve_link(self, short_code: str) -> str:
        # Try cache first
        cached_url = await self.cache.get_url(short_code)
        if cached_url:
            return cached_url

        async with self.uow:
            link = await self.uow.links.get_by_code(short_code)
            if not link:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Short link not found",
                )

            self._check_expiration(link)

            # Cache the result
            await self.cache.set_url(
                short_code, link.original_url, expires_at=link.expires_at
            )
            return link.original_url

    async def increment_click_redis(self, short_code: str) -> int:
        if not self.redis:
            return 0

        async with self.uow:
            link = await self.uow.links.get_by_code(short_code)
            if not link:
                return 0

            key = f"link:{link.id}:clicks"
            await self.redis.set(key, str(link.clicks), ex=86400, nx=True)

            new_count = await self.redis.incr(key)

            await publish_link_update(
                link.user_id,
                {
                    "type": "link_updated",
                    "short_code": short_code,
                    "clicks": new_count,
                },
            )
            await self.cache.invalidate_stats(short_code)
            await self.cache.invalidate_user_links(link.user_id)
            return new_count

    async def count_click(
        self,
        short_code: str,
        ip: str | None,
        user_agent: str | None,
        referer: str | None,
    ) -> None:
        async with self.uow:
            link = await self.uow.links.get_by_code(short_code)
            if link:
                is_unique = True
                if ip and self.redis:
                    unique_key = f"unique:link:{link.id}:ip:{ip}"
                    was_set = await self.redis.set(unique_key, "1", ex=86400, nx=True)
                    if not was_set:
                        is_unique = False

                event = ClickEvent(
                    link_id=link.id,
                    ip_address=ip[:45] if ip else None,
                    user_agent=user_agent[:512] if user_agent else None,
                    referer=referer[:2048] if referer else None,
                    is_unique=is_unique,
                )
                await self.uow.clicks.create(event)
                new_db_count = await self.uow.links.increment_clicks_by_code(short_code)

                await self.uow.commit()

                # Invalidate cache again after DB commit to prevent race conditions
                await self.cache.invalidate_stats(short_code)
                await self.cache.invalidate_user_links(link.user_id)

                logger.info(
                    f"Click recorded for {short_code}. New count: {new_db_count}"
                )
            else:
                logger.warning(f"Click for non-existent code: {short_code}")

    async def get_link_info(self, short_code: str, user_id: int) -> LinkResponse:
        async with self.uow:
            link = await self._get_link_or_404(short_code)
            if link.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Not your link"
                )

            response = LinkResponse.model_validate(link)
            if self.redis:
                redis_clicks = await self.redis.get(f"link:{link.id}:clicks")
                if redis_clicks is not None:
                    response.clicks = int(redis_clicks)

            return response

    async def get_clicks(
        self,
        short_code: str,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        ip: str | None = None,
        country: str | None = None,
    ) -> PaginatedClickResponse:
        async with self.uow:
            link = await self._get_link_or_404(short_code)
            if link.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not your link")

            items, total = await self.uow.clicks.get_by_link_id(
                link.id, skip=skip, limit=limit, ip=ip, country=country
            )
            return PaginatedClickResponse(items=items, total=total)

    async def get_click_stats(
        self, short_code: str, user_id: int, granularity: str | None = None
    ) -> ClickStatsResponse:
        cached_data = await self.cache.get_stats(short_code, granularity)
        if cached_data:
            return ClickStatsResponse.model_validate(cached_data)

        async with self.uow:
            link = await self._get_link_or_404(short_code)
            if link.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not your link")

            stats = await self.uow.clicks.get_aggregated_stats(
                link.id, granularity=granularity
            )

            total_clicks = link.clicks
            if self.redis:
                redis_clicks = await self.redis.get(f"link:{link.id}:clicks")
                if redis_clicks is not None:
                    total_clicks = int(redis_clicks)

            stats["total_clicks"] = total_clicks
            result = ClickStatsResponse.model_validate(stats)
            await self.cache.set_stats(
                short_code, granularity, result.model_dump(mode="json")
            )
            return result

    async def get_user_links(self, user_id: int) -> list[LinkResponse]:
        # 1. Try to get link list from cache
        cached_data = await self.cache.get_user_links(user_id)
        if cached_data:
            result = [LinkResponse.model_validate(item) for item in cached_data]
        else:
            # 2. If not in cache, get from DB
            async with self.uow:
                links = await self.uow.links.get_by_user_id(user_id)
                result = [LinkResponse.model_validate(link) for link in links]

            # 3. Store baseline in cache
            await self.cache.set_user_links(
                user_id, [m.model_dump(mode="json") for m in result]
            )

        # 4. ALWAYS sync with real-time Redis clicks if available.
        # This ensures counts are accurate even if the link list itself is cached.
        if self.redis and result:
            keys = [f"link:{m.id}:clicks" for m in result]
            redis_counts = await self.redis.mget(keys)

            for model, count in zip(result, redis_counts):
                if count is not None:
                    model.clicks = int(count)

        return result

    async def delete_link(self, short_code: str, user_id: int) -> None:
        async with self.uow:
            link = await self._get_link_or_404(short_code)
            if link.user_id != user_id:
                raise HTTPException(status_code=403, detail="Not your link")

            await self.uow.links.delete(link)
            await self.uow.commit()

            await self.cache.delete_url(short_code)
            await self.cache.invalidate_user_links(user_id)
            await publish_link_update(
                user_id, {"type": "link_deleted", "short_code": short_code}
            )

    async def get_updates_stream(self, user_id: int):
        """
        Generator for Server-Sent Events.
        Listen to Redis pubsub and yield formatted events.
        """
        async with subscribe_to_user_updates(user_id) as pubsub:
            yield ": ping\n\n"

            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"

    async def _get_link_or_404(self, short_code: str) -> Link:
        link = await self.uow.links.get_by_code(short_code)
        if not link:
            raise HTTPException(status_code=404, detail="Short link not found")
        return link

    def _check_expiration(self, link: Link) -> None:
        if link.expires_at and link.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Short link expired")

    async def record_click_bg(
        self,
        short_code: str,
        ip: str | None,
        user_agent: str | None,
        referer: str | None,
    ) -> None:
        """
        Background task wrapper to record a click.
        Creates its own UnitOfWork to run outside of request scope.
        """
        try:
            async with self.uow_factory() as uow:
                service = LinkService(uow, self.redis)
                await service.count_click(short_code, ip, user_agent, referer)
        except Exception as e:
            logger.error(
                f"Background click recording failed for {short_code}: {e}",
                exc_info=True,
            )


async def _resolve_final_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.head(url, follow_redirects=True)
            return str(response.url)
    except Exception:
        return url


def _generate_short_code(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))
