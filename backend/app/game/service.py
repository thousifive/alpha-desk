"""Glue between game rules (pure functions) and the database."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Attempt, User, XpEvent


def valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)  # zoneinfo reads the IANA database (the tzdata package as fallback)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def local_today(user: User, now: datetime | None = None) -> date:
    """The player's calendar date right now. Quests and streaks roll over at *local*
    midnight; using the server's UTC date would flip "today" at 7pm in New York."""
    now = now or datetime.now(UTC)
    tz = ZoneInfo(user.timezone) if valid_timezone(user.timezone) else UTC
    return now.astimezone(tz).date()


async def award_xp(
    session: AsyncSession, user: User, *, source: str, ref_key: str, amount: int, day: date
) -> bool:
    """Pay `amount` XP for `ref_key` at most once. Returns True if it was paid now.

    The SELECT is the fast path; the unique constraint on ref_key is the real guarantee
    (two concurrent requests can both pass the SELECT). begin_nested() opens a SAVEPOINT, so
    a duplicate rolls back just this INSERT, not the caller's whole transaction.
    """
    if amount <= 0:
        return False
    seen = await session.exec(select(XpEvent.id).where(XpEvent.ref_key == ref_key))
    if seen.first() is not None:
        return False
    try:
        async with session.begin_nested():
            session.add(XpEvent(source=source, ref_key=ref_key, amount=amount, local_date=day))
    except IntegrityError:
        return False
    user.xp_total += amount
    session.add(user)
    return True


async def passed_slugs(session: AsyncSession) -> set[str]:
    rows = await session.exec(select(Attempt.exercise_slug).where(Attempt.passed).distinct())
    return set(rows.all())


async def get_user(session: AsyncSession) -> User:
    user = await session.get(User, 1)
    if user is None:  # content sync normally creates it; tests may not have synced
        user = User(id=1)
        session.add(user)
        await session.flush()  # flush = send the INSERT now, but stay in the transaction
    return user
