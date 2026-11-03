"""Glue between game rules (pure functions) and the database."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.content.schema import ContentBundle
from app.game.levels import level_info
from app.game.unlocks import NodeStatus, branch_playable
from app.models import Attempt, User
from app.schemas import BossOut, LevelOut


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
