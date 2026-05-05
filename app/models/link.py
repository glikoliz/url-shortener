from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.click_event import ClickEvent
    from app.models.user import User


class Link(Base):
    __tablename__ = "links"
    __table_args__ = (
        Index("ix_link_user_created", "user_id", text("created_at DESC")),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    original_url: Mapped[str] = mapped_column(String(2048))
    short_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    clicks: Mapped[int] = mapped_column(default=text("0"), server_default=text("0"))
    is_public_stats: Mapped[bool] = mapped_column(
        default=False, server_default=text("false")
    )

    user: Mapped["User"] = relationship(back_populates="links")
    click_events: Mapped[list["ClickEvent"]] = relationship(
        back_populates="link", cascade="all, delete-orphan"
    )
