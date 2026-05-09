from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click_event import ClickEvent
from app.schemas.click import ClickStatsResponse


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
            query = query.where(ClickEvent.ip_address.contains(ip))
            count_query = count_query.where(ClickEvent.ip_address.contains(ip))

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
        self, link_id: int, granularity: str | None = None, is_demo: bool = False
    ) -> ClickStatsResponse:
        now = datetime.now(timezone.utc)
        if is_demo:
            max_date_query = select(func.max(ClickEvent.clicked_at)).where(
                ClickEvent.link_id == link_id
            )
            max_date = (await self.db.execute(max_date_query)).scalar()
            if max_date:
                if max_date.tzinfo is None:
                    max_date = max_date.replace(tzinfo=timezone.utc)
                now = max_date

        # Configuration mapping for different granularities
        # Format: (since_delta, trunc_part, point_delta, num_points, format_str)
        config = {
            "minute": (
                timedelta(hours=1),
                "minute",
                timedelta(minutes=1),
                60,
                "%Y-%m-%dT%H:%M:00Z",
            ),
            "hour": (
                timedelta(hours=23),
                "hour",
                timedelta(hours=1),
                24,
                "%Y-%m-%dT%H:00:00Z",
            ),
            "day": (timedelta(days=29), "day", timedelta(days=1), 30, "%Y-%m-%d"),
        }

        delta, trunc, time_delta, num_points, format_str = config.get(
            granularity, config["hour"]
        )

        since = now - delta
        if trunc in ("hour", "day"):
            since = since.replace(minute=0, second=0, microsecond=0)
        if trunc == "day":
            since = since.replace(hour=0)

        group_func = func.date_trunc(trunc, ClickEvent.clicked_at)

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

        return ClickStatsResponse(
            total_clicks=summary.total,
            unique_ips=summary.unique_ips,
            clicks_over_time=clicks_over_time,
            clicks_by_day=clicks_over_time
            if granularity != "day"
            else clicks_over_time,
            granularity=granularity,
            top_referers=[
                {"referer": r.referer or "Direct", "clicks": r.clicks}
                for r in referers_result.all()
            ],
            top_countries=[
                {"country": r.country, "clicks": r.clicks}
                for r in countries_result.all()
            ],
        )
