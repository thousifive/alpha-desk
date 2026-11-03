"""Shared pytest fixtures.

Each test session gets a fresh SQLite file in a temp dir. Settings come from env vars,
so we set them *before* anything calls get_settings() (which caches its result).
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel

from app.auth import hash_password
from app.config import get_settings
from app.db import dispose_engine, get_engine

TEST_PASSWORD = "correct horse battery staple"


@pytest.fixture(scope="session", autouse=True)
def _test_env(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    db_path: Path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    os.environ["SESSION_SECRET"] = "test-secret"
    os.environ["SYNC_CONTENT_ON_STARTUP"] = "false"
    os.environ["APP_PASSWORD_HASH"] = hash_password(TEST_PASSWORD)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def _schema(_test_env: None) -> AsyncIterator[None]:
    # Rebuild tables per test: slower than transactions-with-rollback, but dead simple and
    # SQLite in a temp file is fast enough for this test suite's size.
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    await dispose_engine()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.main import create_app

    # ASGITransport calls the app in-process: no real server or port, but full HTTP semantics.
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    resp = await client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert resp.status_code == 200
    return client  # httpx keeps the session cookie on the client for later requests
