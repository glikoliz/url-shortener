from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click_event import ClickEvent


class ClickRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, click_event: ClickEvent) -> ClickEvent:
        self.db.add(click_event)
        await self.db.commit()
        await self.db.refresh(click_event)
        return click_event

    async def get_by_link_id(self, link_id: int, limit: int = 50) -> list[ClickEvent]:
        from sqlalchemy import select

        result = await self.db.execute(
            select(ClickEvent)
            .where(ClickEvent.link_id == link_id)
            .order_by(ClickEvent.clicked_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_aggregated_stats(self, link_id: int) -> dict:
        from sqlalchemy import func, select

        clicks_by_day_query = (
            select(
                func.date(ClickEvent.clicked_at).label("date"),
                func.count().label("clicks"),
            )
            .where(ClickEvent.link_id == link_id)
            .group_by(func.date(ClickEvent.clicked_at))
            .order_by("date")
        )

        referers_query = (
            select(ClickEvent.referer, func.count().label("clicks"))
            .where(ClickEvent.link_id == link_id)
            .group_by(ClickEvent.referer)
            .order_by(func.count().desc())
            .limit(10)
        )

        countries_query = (
            select(ClickEvent.country, func.count().label("clicks"))
            .where(ClickEvent.link_id == link_id)
            .group_by(ClickEvent.country)
            .order_by(func.count().desc())
            .limit(10)
        )

        clicks_by_day_result = await self.db.execute(clicks_by_day_query)
        referers_result = await self.db.execute(referers_query)
        countries_result = await self.db.execute(countries_query)

        return {
            "clicks_by_day": [
                {"date": str(r.date), "clicks": r.clicks}
                for r in clicks_by_day_result.all()
            ],
            "top_referers": [
                {"referer": r.referer or "Direct", "clicks": r.clicks}
                for r in referers_result.all()
            ],
            "top_countries": [
                {"country": r.country or "Unknown", "clicks": r.clicks}
                for r in countries_result.all()
            ],
        }
