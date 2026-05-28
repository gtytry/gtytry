from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from config.settings import Settings
from database.base import Base


def create_engine(settings: Settings) -> AsyncEngine:
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_async_engine(settings.database_url, echo=False, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
