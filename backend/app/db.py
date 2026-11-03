"""Async database engine and per-request session dependency."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import get_settings

# SQLModel's own async story is thin, so we build the engine with SQLAlchemy directly and
# only borrow SQLModel's AsyncSession (it adds the typed `session.exec(select(...))` API).
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url)
        # expire_on_commit=False: after commit, keep loaded attribute values instead of
        # lazily re-fetching them. Lazy loads are implicit I/O, which async SQLAlchemy forbids.
        _sessionmaker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


# A generator dependency: FastAPI runs code before `yield` per request, injects the
# yielded value, then resumes after the response, so the session is always closed.
async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
