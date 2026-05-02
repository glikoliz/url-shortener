from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.link import Link


class ClickEvent(Base):
    __tablename__ = "click_events"

    __table_args__ = (
        Index("ix_click_events_link_country", "link_id", "country"),
        Index("ix_click_events_link_referer", "link_id", "referer"),
        Index("ix_click_events_link_clicked_at", "link_id", "clicked_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    link_id: Mapped[int] = mapped_column(
        ForeignKey("links.id", ondelete="CASCADE"), index=True
    )
    clicked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now()
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), index=True)
    user_agent: Mapped[str | None] = mapped_column(String(512))
    referer: Mapped[str | None] = mapped_column(String(2048))
    country: Mapped[str | None] = mapped_column(String(2), index=True)

    link: Mapped["Link"] = relationship(back_populates="click_events")
