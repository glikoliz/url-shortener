from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.link import Link


class LinkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, link: Link) -> Link:
        self.db.add(link)
        await self.db.commit()
        await self.db.refresh(link)
        return link

    async def get_by_code(self, short_code: str) -> Link | None:
        result = await self.db.execute(
            select(Link).where(Link.short_code == short_code)
        )
        return result.scalar_one_or_none()

    async def delete(self, link: Link) -> None:
        await self.db.delete(link)
        await self.db.commit()

    async def increment_clicks(self, link_id: int) -> None:
        await self.db.execute(
            update(Link).where(Link.id == link_id).values(clicks=Link.clicks + 1)
        )
        await self.db.commit()

    async def increment_clicks_by_code(self, short_code: str) -> None:
        """Used in background tasks where only short_code is available."""
        await self.db.execute(
            update(Link)
            .where(Link.short_code == short_code)
            .values(clicks=Link.clicks + 1)
        )
        await self.db.commit()
