from datetime import datetime

from pydantic import BaseModel


class ClickEventResponse(BaseModel):
    id: int
    clicked_at: datetime
    ip_address: str | None
    user_agent: str | None
    referer: str | None
    country: str | None

    model_config = {"from_attributes": True}


class ClickStatsResponse(BaseModel):
    total_clicks: int
    granularity: str | None
    clicks_over_time: list[dict]
    clicks_by_day: list[dict]
    top_referers: list[dict]
    top_countries: list[dict]


class PaginatedClickResponse(BaseModel):
    items: list[ClickEventResponse]
    total: int
