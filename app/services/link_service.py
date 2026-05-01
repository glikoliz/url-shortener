import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.link import Link
from app.repositories.link_repository import LinkRepository
from app.services.cache_service import CacheService


def _generate_short_code(length: int = 6) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class LinkService:
    def __init__(self, db: AsyncSession, redis: Redis | None = None) -> None:
        self.link_repo = LinkRepository(db)
        self.cache = CacheService(redis) if redis else None

    async def shorten_url(
        self,
        original_url: str,
        user_id: int,
        custom_code: str | None = None,
        ttl_minutes: int | None = None,
    ):
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
            original_url=str(original_url),
            short_code=short_code,
            expires_at=expires_at,
        )
        link = await self.link_repo.create(link)

        if self.cache:
            await self.cache.set_url(
                link.short_code, link.original_url, expires_at=link.expires_at
            )

        return {
            **_link_to_dict(link),
            "short_url": f"{settings.base_url}/s/{link.short_code}",
        }

    async def resolve_link(self, short_code: str) -> str:
        # Cache hit: Redis TTL handles expiration — zero DB queries
        if self.cache:
            cached_url = await self.cache.get_url(short_code)
            if cached_url:
                return cached_url

        # Cache miss: fetch from DB, check expiration, then populate cache
        link = await self._get_link_or_404(short_code)
        self._check_expiration(link)

        if self.cache:
            await self.cache.set_url(
                short_code, link.original_url, expires_at=link.expires_at
            )

        return link.original_url

    async def count_click(self, short_code: str) -> None:
        """Increment click counter. Runs as a background task after redirect."""
        await self.link_repo.increment_clicks_by_code(short_code)

    async def get_stats(self, short_code: str):
        link = await self._get_link_or_404(short_code)
        return {
            **_link_to_dict(link),
            "short_url": f"{settings.base_url}/s/{link.short_code}",
        }

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

