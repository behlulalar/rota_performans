from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings

# Testlerde her test kendi olay döngüsünü açtığı için havuz kullanılmaz.
_pool_args = {"poolclass": NullPool} if settings.env == "test" else {"pool_size": 10, "max_overflow": 10}

engine = create_async_engine(settings.database_url, pool_pre_ping=True, **_pool_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
