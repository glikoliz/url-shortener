import logging
import secrets
import string
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.link import Link
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
        if custom_code:
            existing = await self.link_repo.get_by_code(custom_code)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Custom short code already taken",
                )
            short_code = custom_code
        else:
            # Generate unique code, retry on collision
            for _ in range(10):
                short_code = _generate_short_code()
                if not await self.link_repo.get_by_code(short_code):
                    break
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to generate unique short code",
                )

        expires_at = None
        if ttl_minutes:
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

        link = Link(
            user_id=user_id,
            original_url=final_url,
            short_code=short_code,
            expires_at=expires_at,
        )
        link = await self.link_repo.create(link)
        logger.info(f"URL shortened: {original_url} -> {short_code} (user: {user_id})")

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
        cache_key = f"clicks:{short_code}:{skip}:{limit}:{ip}:{country}"
        if self.cache.redis:
            cached_data = await self.cache.redis.get(cache_key)
            if cached_data:
                import json

                result = json.loads(cached_data)
                if result.get("owner_id") == user_id:
                    return result["data"]

        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        from app.repositories.click_repository import ClickRepository

        click_repo = ClickRepository(self.link_repo.db)
        items, total = await click_repo.get_by_link_id(
            link.id, skip=skip, limit=limit, ip=ip, country=country
        )

        response_data = {"items": items, "total": total}

        if self.cache.redis:
            import json

            from app.schemas.click import ClickEventResponse

            items_dict = [
                ClickEventResponse.model_validate(i).model_dump(mode="json")
                for i in items
            ]
            cache_payload = {
                "owner_id": link.user_id,
                "data": {"items": items_dict, "total": total},
            }
            await self.cache.redis.set(cache_key, json.dumps(cache_payload), ex=10)

        return response_data

    async def get_click_stats(
        self, short_code: str, user_id: int, granularity: str | None = None
    ):
        cache_key = f"stats:{short_code}:{granularity}"
        if self.cache.redis:
            cached_data = await self.cache.redis.get(cache_key)
            if cached_data:
                import json

                result = json.loads(cached_data)
                if result.get("owner_id") == user_id:
                    return result["data"]

        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not your link")

        from app.repositories.click_repository import ClickRepository

        click_repo = ClickRepository(self.link_repo.db)
        stats = await click_repo.get_aggregated_stats(link.id, granularity=granularity)
        stats["total_clicks"] = link.clicks

        if self.cache.redis:
            import json

            cache_payload = {"owner_id": link.user_id, "data": stats}
            await self.cache.redis.set(cache_key, json.dumps(cache_payload), ex=30)

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

    async def delete_link(self, short_code: str, user_id: int) -> None:
        link = await self._get_link_or_404(short_code)
        if link.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own links",
            )
        await self.link_repo.delete(link)
        if self.cache:
            await self.cache.delete_url(short_code)

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
        "created_at": link.created_at,
        "expires_at": link.expires_at,
    }
