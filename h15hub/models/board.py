from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, inspect, text
from sqlalchemy.ext.asyncio import AsyncConnection
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


class BoardProject(Base):
    __tablename__ = "board_projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("board_groups.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BoardCard(Base):
    __tablename__ = "board_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("board_projects.id", ondelete="CASCADE"))
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


async def migrate_board_schema(conn: AsyncConnection) -> None:
    def _schema_info(sync_conn):
        inspector = inspect(sync_conn)
        table_names = set(inspector.get_table_names())
        card_columns = set()
        if "board_cards" in table_names:
            card_columns = {column["name"] for column in inspector.get_columns("board_cards")}
        return table_names, card_columns

    table_names, card_columns = await conn.run_sync(_schema_info)
    if "board_cards" not in table_names or "project_id" in card_columns or "group_id" not in card_columns:
        return

    await conn.execute(
        text(
            """
            INSERT INTO board_projects (id, group_id, name, created_at)
            SELECT g.id, g.id, g.name, g.created_at
            FROM board_groups g
            WHERE NOT EXISTS (
                SELECT 1 FROM board_projects p WHERE p.id = g.id
            )
            """
        )
    )
    await conn.execute(
        text(
            """
            CREATE TABLE board_cards_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES board_projects(id) ON DELETE CASCADE,
                title VARCHAR(140) NOT NULL,
                description TEXT,
                assignee VARCHAR(128),
                column VARCHAR(11) NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    )
    await conn.execute(
        text(
            """
            INSERT INTO board_cards_new (
                id, project_id, title, description, assignee, column, position, created_at, updated_at
            )
            SELECT id, group_id, title, description, assignee, column, position, created_at, updated_at
            FROM board_cards
            """
        )
    )
    await conn.execute(text("DROP TABLE board_cards"))
    await conn.execute(text("ALTER TABLE board_cards_new RENAME TO board_cards"))