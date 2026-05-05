from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click_event import ClickEvent


class ClickRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, click_event: ClickEvent) -> ClickEvent:
        self.db.add(click_event)
        return click_event

    async def get_by_link_id(
        self,
        link_id: int,
        skip: int = 0,
        limit: int = 50,
        ip: str | None = None,
        country: str | None = None,
        sort_by: str = "clicked_at",
        sort_dir: str = "desc",
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

        allowed_sort_columns = {
            "clicked_at": ClickEvent.clicked_at,
            "ip_address": ClickEvent.ip_address,
            "user_agent": ClickEvent.user_agent,
            "referer": ClickEvent.referer,
            "country": ClickEvent.country,
        }

        sort_col = allowed_sort_columns.get(sort_by, ClickEvent.clicked_at)
        if sort_dir.lower() == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        result = await self.db.execute(query.offset(skip).limit(limit))
        items = list(result.scalars().all())

        return items, total

    async def get_aggregated_stats(
        self, link_id: int, granularity: str | None = None
    ) -> dict:
        now = datetime.now(timezone.utc)

        # Define time window and granularity
        if granularity == "minute":
            since = now - timedelta(hours=1)
            group_func = func.date_trunc("minute", ClickEvent.clicked_at)
            time_delta = timedelta(minutes=1)
            num_points = 60
            format_str = "%Y-%m-%dT%H:%M:00Z"
        elif granularity == "hour":
            since = now - timedelta(hours=23)  # last 24 hours
            since = since.replace(minute=0, second=0, microsecond=0)
            group_func = func.date_trunc("hour", ClickEvent.clicked_at)
            time_delta = timedelta(hours=1)
            num_points = 24
            format_str = "%Y-%m-%dT%H:00:00Z"
        else:
            granularity = "day"
            since = now - timedelta(days=29)  # last 30 days
            since = since.replace(hour=0, minute=0, second=0, microsecond=0)
            group_func = func.date(ClickEvent.clicked_at)
            time_delta = timedelta(days=1)
            num_points = 30
            format_str = "%Y-%m-%d"

        clicks_query = (
            select(
                group_func.label("period"),
                func.count().label("clicks"),
            )
            .where(ClickEvent.link_id == link_id, ClickEvent.clicked_at >= since)
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

        # Total clicks and Distinct IPs (always global)
        summary_query = select(
            func.count().label("total"),
            func.count(func.distinct(ClickEvent.ip_address)).label("unique_ips"),
        ).where(ClickEvent.link_id == link_id)

        summary_result = await self.db.execute(summary_query)
        summary = summary_result.one()

        clicks_result = await self.db.execute(clicks_query)
        referers_result = await self.db.execute(referers_query)
        countries_result = await self.db.execute(countries_query)

        # Process clicks with gap filling
        def get_key(dt, gran):
            if gran == "day":
                return (dt.year, dt.month, dt.day)
            if gran == "hour":
                return (dt.year, dt.month, dt.day, dt.hour)
            if gran == "minute":
                return (dt.year, dt.month, dt.day, dt.hour, dt.minute)
            return dt

        raw_clicks = {
            get_key(r.period, granularity): r.clicks for r in clicks_result.all()
        }
        clicks_over_time = []

        current = since
        for _ in range(num_points):
            key = get_key(current, granularity)
            clicks_over_time.append(
                {"date": current.strftime(format_str), "clicks": raw_clicks.get(key, 0)}
            )
            current += time_delta

        return {
            "total_clicks": summary.total,
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
