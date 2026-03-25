import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DB_URL = os.getenv("H15HUB_DB_URL", "sqlite+aiosqlite:///./data/h15hub.db")

engine = create_async_engine(DB_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    import h15hub.models.settings  # noqa: F401 — register DeviceSettings table
    os.makedirs("data", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from h15hub.models.board import migrate_board_schema, migrate_board_cards_v2

        await migrate_board_schema(conn)
        await migrate_board_cards_v2(conn)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
