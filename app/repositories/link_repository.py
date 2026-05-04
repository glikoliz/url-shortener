from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import Link


class LinkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, link: Link) -> Link:
        self.db.add(link)
        return link

    async def get_by_code(self, short_code: str) -> Link | None:
        result = await self.db.execute(
            select(Link).where(Link.short_code == short_code)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> list[Link]:
        result = await self.db.execute(
            select(Link).where(Link.user_id == user_id).order_by(Link.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, link: Link) -> None:
        await self.db.delete(link)

    async def increment_clicks(self, link_id: int) -> int:
        result = await self.db.execute(
            update(Link)
            .where(Link.id == link_id)
            .values(clicks=Link.clicks + 1)
            .returning(Link.clicks)
        )
        return result.scalar_one()

    async def increment_clicks_by_code(self, short_code: str) -> int:
        """Used in background tasks where only short_code is available."""
        result = await self.db.execute(
            update(Link)
            .where(Link.short_code == short_code)
            .values(clicks=Link.clicks + 1)
            .returning(Link.clicks)
        )
        return result.scalar_one()
