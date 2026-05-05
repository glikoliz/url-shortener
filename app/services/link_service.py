import asyncio
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.click_event import ClickEvent
from app.models.link import Link
from app.redis import publish_link_update, subscribe_to_user_updates
from app.repositories.click_repository import ClickRepository
from app.repositories.link_repository import LinkRepository
from app.schemas.click import ClickStatsResponse, PaginatedClickResponse
from app.schemas.link import LinkResponse
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


def _generate_short_code(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _resolve_final_url(url: str) -> str:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=2.0,
            max_redirects=3,
            headers={"User-Agent": "URLShortener/1.0"},
        ) as client:
            response = await client.head(url)
            return str(response.url)
    except Exception:
        return url


class LinkService:
    def __init__(
        self,
        db: AsyncSession,
        redis: Redis | None = None,
        link_repo: LinkRepository | None = None,
        click_repo: ClickRepository | None = None,
    ) -> None:
        self.db = db
        self.link_repo = link_repo or LinkRepository(db)
        self.click_repo = click_repo or ClickRepository(db)
        self.cache = CacheService(redis)

    async def shorten_url(
        self,
        original_url: str,
        user_id: int,
        custom_code: str | None = None,
        ttl_minutes: int | None = None,
    ):
        if str(original_url).startswith(settings.base_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This URL is already a short link from our service",
            )

        final_url = await _resolve_final_url(original_url)

        if final_url.startswith(settings.base_url):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot shorten URLs pointing to this service "
                    "(even through redirects)"
                ),
            )
        expires_at = None
        if ttl_minutes:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        max_retries = 5
        for attempt in range(max_retries):
            if custom_code:
                if not custom_code.isalnum():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Custom code must contain only alphanumeric characters",
                    )
                short_code = custom_code
                if await self.link_repo.get_by_code(short_code):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Custom short code already taken",
                    )
            else:
                short_code = _generate_short_code()
                if await self.link_repo.get_by_code(short_code):
                    continue

            link = Link(
                user_id=user_id,
                original_url=final_url,
                short_code=short_code,
                expires_at=expires_at,
            )

            try:
                link = await self.link_repo.create(link)
                await self.db.commit()
                await self.db.refresh(link)
                break
            except IntegrityError:
                if custom_code:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Custom short code already taken",
                    )
                if attempt == max_retries - 1:
                    logger.error(
                        "Failed to generate unique short code after max retries"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to generate unique short code",
                    )
                continue
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create link",
            )

        logger.info(f"URL shortened: {original_url} -> {short_code} (user: {user_id})")

        response_data = LinkResponse.model_validate(link).model_dump(mode="json")

        await publish_link_update(
            user_id,
            {
                "type": "link_created",
                "link": response_data,
            },
        )

        await self.cache.invalidate_user_links(user_id)
        return LinkResponse.model_validate(link)

    async def resolve_link(self, short_code: str) -> str:
        # Cache hit: Redis TTL handles expiration — zero DB queries
        cached_url = await self.cache.get_url(short_code)
        if cached_url:
            return cached_url

        # Cache miss: fetch from DB, check expiration, then populate cache
        link = await self._get_link_or_404(short_code)
        self._check_expiration(link)

        await self.cache.set_url(
            short_code, link.original_url, expires_at=link.expires_at
        )

        logger.info(f"Link resolved: {short_code} -> {link.original_url}")
        return link.original_url

    async def get_stats(self, short_code: str, user_id: int) -> LinkResponse:
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        response = LinkResponse.model_validate(link)

        # Get real-time click count from Redis if available
        if self.cache.redis:
            redis_clicks = await self.cache.redis.get(f"link:{link.id}:clicks")
            if redis_clicks is not None:
                response.clicks = int(redis_clicks)

        return response

    async def increment_click_redis(self, short_code: str) -> int | None:
        """Increment click count in Redis for instant feedback. Returns new count."""
        link = await self.link_repo.get_by_code(short_code)
        if not link or not self.cache.redis:
            return None

        key = f"link:{link.id}:clicks"
        # If key doesn't exist, initialize it from DB first
        exists = await self.cache.redis.exists(key)
        if not exists:
            await self.cache.redis.set(key, str(link.clicks), ex=86400)

        new_count = await self.cache.redis.incr(key)

        # Notify via SSE immediately
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
        """Record detailed analytics event in DB."""
        link = await self.link_repo.get_by_code(short_code)
        if link:
            is_unique = True
            if ip and self.cache.redis:
                unique_key = f"unique:link:{link.id}:ip:{ip}"
                was_set = await self.cache.redis.set(unique_key, "1", ex=86400, nx=True)
                if not was_set:
                    is_unique = False

            event = ClickEvent(
                link_id=link.id,
                ip_address=ip[:45] if ip else None,
                user_agent=user_agent[:512] if user_agent else None,
                referer=referer[:2048] if referer else None,
                is_unique=is_unique,
            )
            await self.click_repo.create(event)
            new_db_count = await self.link_repo.increment_clicks_by_code(short_code)
            await self.db.commit()
            logger.info(
                f"Click recorded in DB for {short_code}. New DB count: {new_db_count}"
            )
        else:
            logger.warning(
                f"Attempted to count click for non-existent code: {short_code}"
            )

    async def get_clicks(
        self,
        short_code: str,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        ip: str | None = None,
        country: str | None = None,
    ) -> PaginatedClickResponse:
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        # Optional: we could cache this, but pagination makes it tricky.
        # For now, let's keep it direct to DB as it's the 'detailed' view.
        items, total = await self.click_repo.get_by_link_id(
            link.id, skip=skip, limit=limit, ip=ip, country=country
        )

        return PaginatedClickResponse(items=items, total=total)

    async def get_click_stats(
        self, short_code: str, user_id: int, granularity: str | None = None
    ) -> ClickStatsResponse:
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        # Try cache first
        cached_data = await self.cache.get_stats(short_code, granularity)
        if cached_data:
            return ClickStatsResponse.model_validate(cached_data)

        stats = await self.click_repo.get_aggregated_stats(
            link.id, granularity=granularity
        )

        # Use Redis clicks for total count if available
        total_clicks = link.clicks
        if self.cache.redis:
            redis_clicks = await self.cache.redis.get(f"link:{link.id}:clicks")
            if redis_clicks is not None:
                total_clicks = int(redis_clicks)

        stats["total_clicks"] = total_clicks

        result = ClickStatsResponse.model_validate(stats)
        await self.cache.set_stats(
            short_code, granularity, result.model_dump(mode="json")
        )
        return result

    async def get_user_links(self, user_id: int) -> list[LinkResponse]:
        # Try cache first
        cached_data = await self.cache.get_user_links(user_id)
        if cached_data:
            return [LinkResponse.model_validate(item) for item in cached_data]

        links = await self.link_repo.get_by_user_id(user_id)
        result = [LinkResponse.model_validate(link) for link in links]

        await self.cache.set_user_links(
            user_id, [m.model_dump(mode="json") for m in result]
        )
        return result

    async def get_updates_stream(self, user_id: int):
        """Generate SSE events from Redis Pub/Sub with Heartbeat."""

        pubsub = await subscribe_to_user_updates(user_id)
        try:
            yield ": ok\n\n"

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=30.0
                )
                if message:
                    if message["type"] == "message":
                        yield f"data: {message['data']}\n\n"
                else:
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            logger.info(f"SSE stream cancelled for user {user_id}")
            raise
        finally:
            await pubsub.unsubscribe(f"sse:user:{user_id}")
            await pubsub.close()

    async def delete_link(self, short_code: str, user_id: int) -> None:
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own links",
            )
        await self.link_repo.delete(link)
        await self.db.commit()
        await self.cache.delete_url(short_code)
        await self.cache.invalidate_user_links(user_id)

        # Publish SSE event
        await publish_link_update(
            user_id,
            {
                "type": "link_deleted",
                "short_code": short_code,
            },
        )

    async def _get_link_or_404(self, short_code: str) -> Link:
        link = await self.link_repo.get_by_code(short_code)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Short link not found",
            )
        return link

    def _check_expiration(self, link: Link) -> None:
        if link.expires_at and link.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This short link has expired",
            )
