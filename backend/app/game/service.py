"""Glue between game rules (pure functions) and the database."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.content.schema import ContentBundle
from app.game.levels import level_info
from app.game.unlocks import NodeStatus, branch_playable
from app.models import Attempt, User, XpEvent
from app.schemas import BossOut, LevelOut


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


def level_out(xp: int, bundle: ContentBundle) -> LevelOut | None:
    try:
        info = level_info(xp, bundle.levels.levels)
    except NotImplementedError:
        return None  # TODO(me) #1 not done yet: the UI shows "level system offline"
    return LevelOut(
        index=info.index,
        title=info.title,
        min_xp=info.min_xp,
        next_title=info.next_title,
        next_min_xp=info.next_min_xp,
    )


def boss_out(bundle: ContentBundle, branch_id: str) -> BossOut | None:
    branch = next(b for b in bundle.branches if b.id == branch_id)
    if branch.boss is None:
        return None
    return BossOut(
        branch_id=branch.id,
        branch_title=branch.title,
        title=branch.boss.title,
        description=branch.boss.description,
    )


def next_boss(
    bundle: ContentBundle, states: dict[str, NodeStatus], milestone: str
) -> BossOut | None:
    """The boss at the end of the first playable branch that isn't fully mastered yet."""
    for branch in sorted(bundle.branches, key=lambda b: b.order):
        if not branch_playable(branch, milestone) or branch.boss is None:
            continue
        nodes = bundle.nodes[branch.id]
        if any(states[n.slug].state != "mastered" for n in nodes):
            return boss_out(bundle, branch.id)
    return None
