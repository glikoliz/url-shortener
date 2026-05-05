from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, computed_field, field_validator

from app.config import settings


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
    user_id: int | None
    original_url: str
    short_code: str
    clicks: int
    created_at: datetime
    expires_at: datetime | None = None

    @computed_field
    @property
    def short_url(self) -> str:
        return f"{settings.base_url}/s/{self.short_code}"

    model_config = {"from_attributes": True}
