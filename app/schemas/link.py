from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_code: str | None = Field(
        default=None, examples=[None], min_length=3, max_length=32
    )
    ttl_minutes: int | None = Field(default=None, le=31536000)

    @field_validator("custom_code")
    @classmethod
    def validate_custom_code(cls, v: str | None) -> str | None:
        if v is not None and not v.isalnum():
            raise ValueError("Custom code must contain only alphanumeric characters")
        return v


class LinkResponse(BaseModel):
    id: int
    original_url: str
    short_code: str
    short_url: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}
