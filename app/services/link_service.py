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
from app.models.link import Link
from app.redis import publish_link_update, subscribe_to_user_updates
from app.repositories.link_repository import LinkRepository
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
    def __init__(self, db: AsyncSession, redis: Redis | None = None) -> None:
        self.link_repo = LinkRepository(db)
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
                break
            except IntegrityError:
                if custom_code:
                    # If custom code was taken between our check and create
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Custom short code already taken",
                    )
                # For auto-generated code, just retry if not last attempt
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
            # Should not happen due to break, but for safety
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create link",
            )

        logger.info(f"URL shortened: {original_url} -> {short_code} (user: {user_id})")

        # Publish SSE event
        await publish_link_update(
            user_id,
            {
                "type": "link_created",
                "link": {
                    **_link_to_dict(link),
                    "short_url": f"{settings.base_url}/s/{link.short_code}",
                },
            },
        )

        return {
            **_link_to_dict(link),
            "short_url": f"{settings.base_url}/s/{link.short_code}",
        }

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

    async def count_click(
        self,
        short_code: str,
        ip: str | None,
        user_agent: str | None,
        referer: str | None,
    ) -> None:
        """Increment click counter and record detailed analytics event."""
        link = await self.link_repo.get_by_code(short_code)
        if link:
            from app.models.click_event import ClickEvent
            from app.repositories.click_repository import ClickRepository

            click_repo = ClickRepository(self.link_repo.db)
            event = ClickEvent(
                link_id=link.id,
                ip_address=ip[:45] if ip else None,
                user_agent=user_agent[:512] if user_agent else None,
                referer=referer[:2048] if referer else None,
            )
            await click_repo.create(event)
            await self.link_repo.increment_clicks_by_code(short_code)

            # Fetch updated link to get current click count and user_id for SSE
            updated_link = await self.link_repo.get_by_code(short_code)
            if updated_link:
                await publish_link_update(
                    updated_link.user_id,
                    {
                        "type": "link_updated",
                        "short_code": short_code,
                        "clicks": updated_link.clicks,
                    },
                )

    async def get_stats(self, short_code: str, user_id: int):
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")
        return {
            **_link_to_dict(link),
            "short_url": f"{settings.base_url}/s/{link.short_code}",
        }

    async def get_clicks(
        self,
        short_code: str,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        ip: str | None = None,
        country: str | None = None,
    ):
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        from app.repositories.click_repository import ClickRepository

        click_repo = ClickRepository(self.link_repo.db)
        items, total = await click_repo.get_by_link_id(
            link.id, skip=skip, limit=limit, ip=ip, country=country
        )

        return {"items": items, "total": total}

    async def get_click_stats(
        self, short_code: str, user_id: int, granularity: str | None = None
    ):
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        from app.repositories.click_repository import ClickRepository

        click_repo = ClickRepository(self.link_repo.db)
        stats = await click_repo.get_aggregated_stats(link.id, granularity=granularity)
        stats["total_clicks"] = link.clicks

        return stats

    async def get_user_links(self, user_id: int):
        links = await self.link_repo.get_by_user_id(user_id)
        return [
            {
                **_link_to_dict(link),
                "short_url": f"{settings.base_url}/s/{link.short_code}",
            }
            for link in links
        ]

    async def get_updates_stream(self, user_id: int):
        """Generate SSE events from Redis Pub/Sub."""
        import json

        pubsub = await subscribe_to_user_updates(user_id)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield f"data: {json.dumps(data)}\n\n"
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
        await self.cache.delete_url(short_code)

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

    @staticmethod
    def _check_expiration(link: Link) -> None:
        if link.expires_at and link.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="This short link has expired",
            )


def _link_to_dict(link: Link) -> dict:
    return {
        "id": link.id,
        "original_url": link.original_url,
        "short_code": link.short_code,
        "clicks": link.clicks,
        "created_at": link.created_at.isoformat() if link.created_at else None,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
    }
