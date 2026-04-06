from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from app.database import Base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship


class Link(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    original_url = Column(String(2048), nullable=False)
    short_code = Column(String(32), unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    clicks = Column(Integer, server_default=text("0"))

    user = relationship("User", back_populates="links")
