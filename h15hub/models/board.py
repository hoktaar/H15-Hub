from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from h15hub.database import Base


class BoardCardColumn(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class BoardGroup(Base):
    __tablename__ = "board_groups"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BoardCard(Base):
    __tablename__ = "board_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("board_groups.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(128), nullable=True)
    column: Mapped[BoardCardColumn] = mapped_column(
        SAEnum(BoardCardColumn),
        default=BoardCardColumn.BACKLOG,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )