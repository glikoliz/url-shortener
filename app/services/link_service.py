import ipaddress
import logging
import secrets
import socket
import string
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, HTTPException, status
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

# Shared client pool to avoid handshake overhead
_http_client = httpx.AsyncClient(
    timeout=2.0,
    follow_redirects=True,
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
)


async def close_http_client():
    await _http_client.aclose()


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
        user_id: int | None,
        custom_code: str | None = None,
        expires_at: datetime | None = None,
        ttl_minutes: int | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> LinkResponse:
        if not user_id:
            # Anonymous users: no custom code, exactly 7 days TTL
            custom_code = None
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        elif ttl_minutes and not expires_at:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        # Basic protection against shortening our own links (shallow check)
        if settings.base_url in original_url:
            if "/s/" in original_url:
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
                    original_url=original_url,
                    short_code=short_code,
                    expires_at=expires_at,
                )

                try:
                    link = await self.uow.links.create(link)
                    await self.uow.commit()
                    await self.uow.session.refresh(link)

                    if self.cache and user_id:
                        await self.cache.invalidate_user_links(user_id)

                    # Notify frontend
                    if user_id:
                        await publish_link_update(
                            user_id, {"type": "link_created", "short_code": short_code}
                        )

                    # Run deep validation in background
                    if background_tasks:
                        background_tasks.add_task(
                            self._validate_link_bg,
                            link_id=link.id,
                            original_url=original_url,
                            user_id=user_id,
                            short_code=short_code,
                        )

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
        if self.cache:
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

            if self.cache:
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

            if link.user_id:
                await publish_link_update(
                    link.user_id,
                    {
                        "type": "link_updated",
                        "short_code": short_code,
                        "clicks": new_count,
                    },
                )

            if self.cache:
                await self.cache.invalidate_stats(short_code)
                if link.user_id:
                    await self.cache.invalidate_user_links(link.user_id)

            return new_count

    async def count_click(
        self,
        short_code: str,
        ip: str | None,
        country: str | None,
        user_agent: str | None,
        referer: str | None,
    ) -> None:
        async with self.uow:
            link = await self.uow.links.get_by_code(short_code)
            if link:
                # Record the click
                if link.user_id:
                    event = ClickEvent(
                        link_id=link.id,
                        ip_address=ip[:45] if ip else None,
                        country=country[:2] if country else None,
                        user_agent=user_agent[:512] if user_agent else None,
                        referer=referer[:2048] if referer else None,
                    )
                    await self.uow.clicks.create(event)

                    new_db_count = await self.uow.links.increment_clicks_by_code(
                        short_code
                    )

                    await self.uow.commit()

                    if self.cache:
                        await self.cache.invalidate_stats(short_code)
                        await self.cache.invalidate_user_links(link.user_id)

                    logger.info(
                        f"Click recorded for {short_code}. New count: {new_db_count}"
                    )
                else:
                    logger.debug(f"Skipping stats for anonymous link: {short_code}")
            else:
                logger.warning(f"Click for non-existent code: {short_code}")

    async def get_link_info(self, short_code: str, user_id: int) -> LinkResponse:
        async with self.uow:
            link = await self._get_link_or_404(short_code)
            is_owner = user_id is not None and link.user_id == user_id
            if not is_owner and not link.is_public_stats:
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
        sort_by: str = "clicked_at",
        sort_dir: str = "desc",
    ) -> PaginatedClickResponse:
        async with self.uow:
            link = await self._get_link_or_404(short_code)
            is_owner = user_id is not None and link.user_id == user_id
            if not is_owner and not link.is_public_stats:
                raise HTTPException(status_code=403, detail="Not your link")

            items, total = await self.uow.clicks.get_by_link_id(
                link.id,
                skip=skip,
                limit=limit,
                ip=ip,
                country=country,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
            return PaginatedClickResponse(items=items, total=total)

    async def get_click_stats(
        self, short_code: str, user_id: int, granularity: str | None = None
    ) -> ClickStatsResponse:
        # Force a refresh for hourly stats by changing the cache key slightly
        cache_granularity = granularity
        if granularity == "hour":
            cache_granularity = "hour_v2"

        if self.cache:
            cached_data = await self.cache.get_stats(short_code, cache_granularity)
            if cached_data:
                return ClickStatsResponse.model_validate(cached_data)

        async with self.uow:
            link = await self._get_link_or_404(short_code)
            is_owner = user_id is not None and link.user_id == user_id
            if not is_owner and not link.is_public_stats:
                raise HTTPException(status_code=403, detail="Not your link")

            stats = await self.uow.clicks.get_aggregated_stats(
                link.id, granularity=granularity
            )

            total_clicks = link.clicks
            if self.redis:
                redis_clicks = await self.redis.get(f"link:{link.id}:clicks")
                if redis_clicks is not None:
                    total_clicks = int(redis_clicks)

            stats.total_clicks = total_clicks
            stats.is_public = link.is_public_stats

            if self.cache:
                await self.cache.set_stats(
                    short_code, granularity, stats.model_dump(mode="json")
                )
            return stats

    async def get_user_links(self, user_id: int) -> list[LinkResponse]:
        if self.cache:
            cached_data = await self.cache.get_user_links(user_id)
            if cached_data:
                result = [LinkResponse.model_validate(item) for item in cached_data]
            else:
                async with self.uow:
                    links = await self.uow.links.get_by_user_id(user_id)
                    result = [LinkResponse.model_validate(link) for link in links]

                await self.cache.set_user_links(
                    user_id, [m.model_dump(mode="json") for m in result]
                )
        else:
            async with self.uow:
                links = await self.uow.links.get_by_user_id(user_id)
                result = [LinkResponse.model_validate(link) for link in links]

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

            if self.cache:
                await self.cache.delete_url(short_code)
                await self.cache.invalidate_user_links(user_id)

            await publish_link_update(
                user_id, {"type": "link_deleted", "short_code": short_code}
            )

    async def get_updates_stream(self, user_id: int):
        """Generator for Server-Sent Events."""
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

    async def _validate_link_bg(
        self, link_id: int, original_url: str, user_id: int | None, short_code: str
    ) -> None:
        final_url = await _resolve_final_url(original_url)

        is_recursive = False
        if settings.base_url in final_url:
            if "/s/" in final_url or any(
                p in final_url for p in ["/api/", "/dashboard"]
            ):
                is_recursive = True

        if is_recursive:
            logger.warning(
                f"Recursive or unsafe link detected for {link_id} ({short_code}). "
                f"Target: {final_url}. Deleting."
            )
            try:
                async with self.uow_factory() as uow:
                    link = await uow.links.get_by_code(short_code)
                    if not link:
                        return

                    await uow.links.delete(link)
                    await uow.commit()

                if self.cache:
                    await self.cache.delete_url(short_code)
                    if user_id:
                        await self.cache.invalidate_user_links(user_id)

                if user_id:
                    await publish_link_update(
                        user_id,
                        {
                            "type": "link_deleted",
                            "short_code": short_code,
                            "reason": "recursive_loop",
                        },
                    )
            except Exception as e:
                logger.error(f"Failed to delete recursive link {link_id}: {e}")

    async def record_click_bg(
        self,
        short_code: str,
        ip: str | None,
        country: str | None,
        user_agent: str | None,
        referer: str | None,
    ) -> None:
        """Background task wrapper to record a click."""
        try:
            async with self.uow_factory() as uow:
                service = LinkService(uow, self.redis, self.uow_factory)
                await service.count_click(short_code, ip, country, user_agent, referer)
        except Exception as e:
            logger.error(f"Background click recording failed for {short_code}: {e}")


async def _resolve_final_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not _is_safe_url(url):
        logger.warning(f"SSRF Protection: Blocked request to unsafe URL: {url}")
        return url

    try:
        response = await _http_client.head(url, follow_redirects=True)
        final_url = str(response.url)

        if not _is_safe_url(final_url):
            logger.warning(
                f"SSRF Protection: Blocked redirect to unsafe URL: {final_url}"
            )
            return url

        return final_url
    except Exception as e:
        logger.debug(f"URL resolution failed for {url}: {e}")
        return url


def _is_safe_url(url: str) -> bool:
    """Check if the URL points to a safe (non-internal) IP address."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        addr_infos = socket.getaddrinfo(hostname, None)
        for info in addr_infos:
            ip_str = info[4][0]
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        return True
    except Exception:
        return False


def _generate_short_code(length: int = 6) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))
