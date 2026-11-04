from collections.abc import Iterator

import pytest
from httpx import AsyncClient

import app.routers.auth as auth_router
from app.config import get_settings
from app.ratelimit import SlidingWindow
from tests.conftest import TEST_PASSWORD


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_sliding_window_allows_limit_then_blocks_until_oldest_expires() -> None:
    clock = Clock()
    w = SlidingWindow(limit=3, window_s=60, clock=clock)
    assert [w.hit("ip") for _ in range(3)] == [None, None, None]
    assert w.hit("ip") == pytest.approx(60)
    clock.t += 30
    assert w.hit("ip") == pytest.approx(30)  # blocked hits don't extend the window
    clock.t += 30.001
    assert w.hit("ip") is None


def test_sliding_window_keys_are_independent_and_reset_clears() -> None:
    w = SlidingWindow(limit=1, window_s=60, clock=Clock())
    assert w.hit("a") is None and w.hit("b") is None
    assert w.hit("a") is not None
    w.reset("a")
    assert w.hit("a") is None


@pytest.fixture
def tight_login_limit(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "login_rate_limit", 3)
    monkeypatch.setattr(auth_router, "_login_limiter", None)  # rebuild from the new settings
    yield
    auth_router._login_limiter = None


async def test_login_is_rate_limited(client: AsyncClient, tight_login_limit: None) -> None:
    for _ in range(3):
        assert (await client.post("/api/auth/login", json={"password": "x"})).status_code == 401
    blocked = await client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert blocked.status_code == 429  # even the right password, until the window passes
    assert int(blocked.headers["retry-after"]) > 0
    assert "Too many attempts" in blocked.json()["detail"]


async def test_successful_login_resets_the_count(
    client: AsyncClient, tight_login_limit: None
) -> None:
    for _ in range(2):
        await client.post("/api/auth/login", json={"password": "x"})
    assert (await client.post("/api/auth/login", json={"password": TEST_PASSWORD})).is_success
    for _ in range(2):  # a fresh budget after logging in
        assert (await client.post("/api/auth/login", json={"password": "x"})).status_code == 401
