from sqlalchemy import func, or_, select
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

    async def get_by_link_id(
        self,
        link_id: int,
        skip: int = 0,
        limit: int = 50,
        ip: str | None = None,
        country: str | None = None,
    ) -> tuple[list[ClickEvent], int]:
        query = select(ClickEvent).where(ClickEvent.link_id == link_id)
        count_query = (
            select(func.count(ClickEvent.id))
            .select_from(ClickEvent)
            .where(ClickEvent.link_id == link_id)
        )

        if ip and ip.strip():
            query = query.where(ClickEvent.ip_address.ilike(f"%{ip}%"))
            count_query = count_query.where(ClickEvent.ip_address.ilike(f"%{ip}%"))

        if country and country.strip():
            if country == "null":
                query = query.where(
                    or_(ClickEvent.country.is_(None), ClickEvent.country == "")
                )
                count_query = count_query.where(
                    or_(ClickEvent.country.is_(None), ClickEvent.country == "")
                )
            else:
                query = query.where(ClickEvent.country == country)
                count_query = count_query.where(ClickEvent.country == country)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(ClickEvent.clicked_at.desc()).offset(skip).limit(limit)
        )
        items = list(result.scalars().all())

        return items, total

    async def get_aggregated_stats(
        self, link_id: int, granularity: str | None = None
    ) -> dict:
        from sqlalchemy import func, select

        if not granularity:
            range_query = select(
                func.min(ClickEvent.clicked_at).label("min_t"),
                func.max(ClickEvent.clicked_at).label("max_t"),
            ).where(ClickEvent.link_id == link_id)

            range_result = await self.db.execute(range_query)
            r = range_result.one()
            min_t, max_t = r.min_t, r.max_t

            granularity = "day"
            if min_t and max_t:
                diff = max_t - min_t
                if diff.total_seconds() < 7200:  # < 2 hours -> minutes
                    granularity = "minute"
                elif diff.total_seconds() < 172800:  # < 48 hours -> hours
                    granularity = "hour"

        if granularity == "minute":
            group_func = func.date_trunc("minute", ClickEvent.clicked_at)
            date_format = "%H:%M"
        elif granularity == "hour":
            group_func = func.date_trunc("hour", ClickEvent.clicked_at)
            date_format = "%m-%d %H:00"
        else:
            granularity = "day"
            group_func = func.date(ClickEvent.clicked_at)
            date_format = "%Y-%m-%d"

        clicks_query = (
            select(
                group_func.label("period"),
                func.count().label("clicks"),
            )
            .where(ClickEvent.link_id == link_id)
            .group_by("period")
            .order_by("period")
        )

        referers_query = (
            select(ClickEvent.referer, func.count().label("clicks"))
            .where(ClickEvent.link_id == link_id)
            .group_by(ClickEvent.referer)
            .order_by(func.count().desc())
            .limit(20)
        )

        countries_query = (
            select(ClickEvent.country, func.count().label("clicks"))
            .where(ClickEvent.link_id == link_id)
            .group_by(ClickEvent.country)
            .order_by(func.count().desc())
            .limit(20)
        )

        # Total clicks, Unique clicks summary, and Distinct IPs
        summary_query = select(
            func.count().label("total"),
            func.count().filter(ClickEvent.is_unique.is_(True)).label("unique"),
            func.count(func.distinct(ClickEvent.ip_address)).label("unique_ips"),
        ).where(ClickEvent.link_id == link_id)

        summary_result = await self.db.execute(summary_query)
        summary = summary_result.one()

        clicks_result = await self.db.execute(clicks_query)
        referers_result = await self.db.execute(referers_query)
        countries_result = await self.db.execute(countries_query)

        clicks_over_time = [
            {"date": r.period.strftime(date_format), "clicks": r.clicks}
            for r in clicks_result.all()
        ]

        return {
            "total_clicks": summary.total,
            "unique_clicks": summary.unique,
            "unique_ips": summary.unique_ips,
            "clicks_over_time": clicks_over_time,
            "clicks_by_day": clicks_over_time,
            "granularity": granularity,
            "top_referers": [
                {"referer": r.referer or "Direct", "clicks": r.clicks}
                for r in referers_result.all()
            ],
            "top_countries": [
                {"country": r.country, "clicks": r.clicks}
                for r in countries_result.all()
            ],
        }
