from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_code: str | None = Field(default=None, examples=[None])
    ttl_minutes: int | None = None


class LinkResponse(BaseModel):
    id: int
    original_url: str
    short_code: str
    short_url: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
