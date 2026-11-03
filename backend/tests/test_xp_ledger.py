from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import false
from sqlmodel import func, select
from sqlmodel import select as real_select

from app.db import get_sessionmaker
from app.game.service import award_xp, get_user, local_today
from app.models import User, XpEvent

DAY = date(2026, 11, 3)


async def test_award_is_paid_once_per_ref_key() -> None:
    async with get_sessionmaker()() as s:
        user = await get_user(s)
        assert await award_xp(s, user, source="quest", ref_key="k1", amount=15, day=DAY)
        assert not await award_xp(s, user, source="quest", ref_key="k1", amount=15, day=DAY)
        assert await award_xp(s, user, source="quest", ref_key="k2", amount=5, day=DAY)
        await s.commit()
        assert user.xp_total == 20
        total = (await s.exec(select(func.sum(XpEvent.amount)))).one()
        assert total == 20  # cache matches ledger


async def test_zero_amount_writes_nothing() -> None:
    async with get_sessionmaker()() as s:
        user = await get_user(s)
        assert not await award_xp(s, user, source="x", ref_key="z", amount=0, day=DAY)
        assert (await s.exec(select(func.count()).select_from(XpEvent))).one() == 0


async def test_duplicate_insert_rolls_back_only_the_savepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulate a race: another request inserted the row after our SELECT ran."""
    import app.game.service as service

    # Make the fast-path SELECT find nothing, so the INSERT hits the unique constraint.
    monkeypatch.setattr(service, "select", lambda *_: real_select(XpEvent.id).where(false()))
    async with get_sessionmaker()() as s:
        user = await get_user(s)
        s.add(XpEvent(source="quest", ref_key="race", amount=10, local_date=DAY))
        s.add(XpEvent(source="quest", ref_key="other", amount=1, local_date=DAY))
        await s.flush()
        assert not await award_xp(s, user, source="quest", ref_key="race", amount=10, day=DAY)
        await s.commit()  # the outer transaction survived the IntegrityError
        assert user.xp_total == 0
        n = (await s.exec(real_select(func.count()).select_from(XpEvent))).one()
        assert n == 2  # earlier rows in the same transaction were not rolled back


def test_local_today_uses_player_timezone() -> None:
    # 02:00 UTC on Nov 4 is still Nov 3 in New York (UTC-5 in November).
    now = datetime(2026, 11, 4, 2, 0, tzinfo=UTC)
    assert local_today(User(timezone="America/New_York"), now) == date(2026, 11, 3)
    assert local_today(User(timezone="Asia/Tokyo"), now) == date(2026, 11, 4)
    assert local_today(User(timezone="Not/AZone"), now) == date(2026, 11, 4)  # falls back to UTC


async def test_timezone_endpoint(authed_client: AsyncClient) -> None:
    ok = await authed_client.put("/api/auth/timezone", json={"timezone": "Europe/London"})
    assert ok.status_code == 200
    bad = await authed_client.put("/api/auth/timezone", json={"timezone": "Mars/Olympus"})
    assert bad.status_code == 422
    async with get_sessionmaker()() as s:
        assert (await get_user(s)).timezone == "Europe/London"


async def test_login_records_timezone(client: AsyncClient) -> None:
    from tests.conftest import TEST_PASSWORD

    resp = await client.post(
        "/api/auth/login", json={"password": TEST_PASSWORD, "timezone": "Asia/Kolkata"}
    )
    assert resp.status_code == 200
    async with get_sessionmaker()() as s:
        assert (await get_user(s)).timezone == "Asia/Kolkata"
