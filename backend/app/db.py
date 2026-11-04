"""Async database engine and per-request session dependency."""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
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
        url = get_settings().database_url
        _engine = create_async_engine(url)
        if url.startswith("sqlite"):
            # Pragmas are per connection, so set them on every new pooled connection.
            event.listen(_engine.sync_engine, "connect", _sqlite_pragmas)
        # expire_on_commit=False: after commit, keep loaded attribute values instead of
        # lazily re-fetching them. Lazy loads are implicit I/O, which async SQLAlchemy forbids.
        _sessionmaker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _engine


def _sqlite_pragmas(dbapi_conn: Any, _record: Any) -> None:
    cur = dbapi_conn.cursor()
    # WAL: writers append to a side log instead of rewriting pages in place, so readers never
    # block on a writer (a sync upload while the dashboard reads) and a crash mid-write
    # can't corrupt the main file. The mode is stored in the DB file, so this sticks.
    cur.execute("PRAGMA journal_mode=WAL")
    # In WAL mode NORMAL is still crash-safe for the database; a power cut can only lose the
    # last few commits, which the devices simply re-upload (ingestion is idempotent).
    cur.execute("PRAGMA synchronous=NORMAL")
    # Wait up to 5 s for a lock instead of failing immediately with "database is locked"
    # (e.g. while `alpha-desk backup` is reading).
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


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
