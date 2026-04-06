from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "users"
    links = relationship("Link", back_populates="user")

    id = Column(Integer, primary_key=True, index=True)
    is_active = Column(Boolean, default=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
