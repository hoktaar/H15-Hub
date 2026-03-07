from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from h15hub.database import Base


class UserRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_salt: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(64))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.MEMBER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )