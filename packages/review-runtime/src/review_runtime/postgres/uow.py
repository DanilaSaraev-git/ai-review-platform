from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def normalize_async_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class AsyncUnitOfWork:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncUnitOfWork:
        self.session = self.factory()
        await self.session.begin()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        if self.session is None:
            return
        if exc_type is None:
            await self.session.commit()
        else:
            await self.session.rollback()
        await self.session.close()

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("unit of work is not active")
        await self.session.commit()


def create_uow_factory(url: str) -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(normalize_async_url(url), pool_pre_ping=True)
    return engine, async_sessionmaker(engine, expire_on_commit=False)
