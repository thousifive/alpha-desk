"""Glue between game rules (pure functions) and the database."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.content.schema import ContentBundle
from app.game.levels import level_info
from app.game.unlocks import NodeStatus, branch_playable, playable_exercise_slugs
from app.models import Attempt, User, XpEvent
from app.schemas import BossOut, BranchCounts, LevelOut, NextBossOut


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


def bosses_out(bundle: ContentBundle, branch_id: str) -> list[BossOut]:
    branch = next(b for b in bundle.branches if b.id == branch_id)
    # enumerate(xs, start=1) yields (1, x0), (2, x1), …: 1-based stage numbers for the UI.
    return [
        BossOut(
            branch_id=branch.id,
            branch_title=branch.title,
            title=boss.title,
            description=boss.description,
            stage=i,
            stages=len(branch.bosses),
        )
        for i, boss in enumerate(branch.bosses, start=1)
    ]


def branch_counts(
    bundle: ContentBundle, branch_id: str, states: dict[str, NodeStatus], passed: set[str]
) -> BranchCounts:
    nodes = bundle.nodes[branch_id]
    ex_slugs = [s for n in nodes for s in playable_exercise_slugs(n)]
    return BranchCounts(
        n_nodes=len(nodes),
        n_mastered=sum(states[n.slug].state == "mastered" for n in nodes),
        n_exercises=len(ex_slugs),
        n_passed=sum(s in passed for s in ex_slugs),
    )


def next_boss(
    bundle: ContentBundle, states: dict[str, NodeStatus], passed: set[str], milestone: str
) -> NextBossOut | None:
    """The first boss of the first playable branch that isn't fully mastered yet, with that
    branch's own counts (not totals across branches). Boss fights land in M5, so until then
    "next" is always a branch's first boss."""
    for branch in sorted(bundle.branches, key=lambda b: b.order):
        if not branch_playable(branch, milestone) or not branch.bosses:
            continue
        if any(states[n.slug].state != "mastered" for n in bundle.nodes[branch.id]):
            first = bosses_out(bundle, branch.id)[0]
            counts = branch_counts(bundle, branch.id, states, passed)
            return NextBossOut(**first.model_dump(), **counts.model_dump())
    return None
