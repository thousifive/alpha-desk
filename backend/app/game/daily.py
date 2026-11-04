"""Daily loop glue: today's quests and the streak, on top of the pure engines."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.content.schema import ContentBundle
from app.game.quests import Candidate, day_rng, node_weakness, plan_quests
from app.game.service import award_xp
from app.game.streaks import StreakState, streak_milestone
from app.game.unlocks import PLAYABLE_TYPES, node_states
from app.models import Attempt, Quest, QuestItem, User
from app.schemas import QuestOut
from app.views import quest_view

# ---- streak ---------------------------------------------------------------------------


async def active_days(session: AsyncSession) -> set[date]:
    rows = await session.exec(select(Attempt.local_date).where(Attempt.passed).distinct())
    return set(rows.all())


async def award_streak_milestone(
    session: AsyncSession, user: User, state: StreakState | None, content: ContentBundle, day: date
) -> int:
    if state is None or state.run_start is None:
        return 0
    n = streak_milestone(state, content.quests.streaks)
    if n is None:
        return 0
    # Keyed by run start: after a break, reaching 7 again in a new run pays again.
    amount = content.quests.streaks.milestone_xp
    key = f"streak:{state.run_start.isoformat()}:{n}"
    paid = await award_xp(session, user, source="streak", ref_key=key, amount=amount, day=day)
    return amount if paid else 0


# ---- quests ---------------------------------------------------------------------------


async def _node_stats(session: AsyncSession, content: ContentBundle) -> dict[str, tuple[int, int]]:
    """node → (passed attempts, total attempts), aggregated in SQL rather than in Python."""
    ex_to_node = {
        ex.slug: n.slug for ns in content.nodes.values() for n in ns for ex in n.exercises
    }
    # SUM(CASE WHEN passed THEN 1 ELSE 0 END): portable, since Postgres can't SUM a boolean.
    passes = func.sum(case((col(Attempt.passed), 1), else_=0))
    rows = await session.exec(
        select(Attempt.exercise_slug, passes, func.count()).group_by(Attempt.exercise_slug)
    )
    stats: dict[str, tuple[int, int]] = {}
    for slug, p, n in rows.all():
        node = ex_to_node.get(slug)
        if node is None:
            continue  # exercise removed from content
        old_p, old_n = stats.get(node, (0, 0))
        stats[node] = (old_p + int(p or 0), old_n + n)
    return stats


def _candidates(content: ContentBundle, passed: set[str], milestone: str) -> list[Candidate]:
    states = node_states(content, passed, milestone)
    return [
        Candidate(
            slug=ex.slug,
            branch_id=st.branch_id,
            node_slug=st.node.slug,
            difficulty=ex.difficulty,
            passed=ex.slug in passed,
        )
        for st in states.values()
        if st.state in ("available", "mastered")
        for ex in st.node.exercises
        if ex.type in PLAYABLE_TYPES
    ]


async def _items(session: AsyncSession, quest: Quest) -> list[QuestItem]:
    rows = await session.exec(
        select(QuestItem).where(QuestItem.quest_id == quest.id).order_by(col(QuestItem.position))
    )
    return list(rows.all())


async def get_or_create_quest(
    session: AsyncSession, content: ContentBundle, passed: set[str], milestone: str, day: date
) -> tuple[Quest, list[QuestItem]]:
    """Today's quest, generated on first request. Raises NotImplementedError until
    TODO(me) M2-2 (weighted_sample) is done."""
    existing = (await session.exec(select(Quest).where(Quest.day == day))).first()
    if existing is not None:
        return existing, await _items(session, existing)

    weakness = node_weakness(await _node_stats(session, content))
    plan = plan_quests(
        _candidates(content, passed, milestone), weakness, content.quests.quests, day_rng(day)
    )
    try:
        async with session.begin_nested():
            quest = Quest(day=day)
            session.add(quest)
            await session.flush()  # assigns quest.id
            assert quest.id is not None
            for i, cand in enumerate(plan):
                session.add(QuestItem(quest_id=quest.id, position=i, exercise_slug=cand.slug))
        await session.commit()
    except IntegrityError:
        # Two tabs opened the dashboard at once and the other one won: use its quest.
        quest = (await session.exec(select(Quest).where(Quest.day == day))).one()
    return quest, await _items(session, quest)


def quest_out(quest: Quest, items: list[QuestItem], content: ContentBundle) -> QuestOut:
    return quest_view(
        content,
        quest.day,
        [(it.position, it.exercise_slug) for it in items],
        {it.position for it in items if it.completed_at is not None},
    )


@dataclass(frozen=True)
class QuestDelta:
    completed_position: int | None = None
    xp: int = 0
    all_done: bool = False


async def complete_quest_item(
    session: AsyncSession, user: User, content: ContentBundle, slug: str, day: date
) -> QuestDelta:
    """Mark `slug` done in today's quest (if it's on it) and pay quest XP via the ledger."""
    quest = (await session.exec(select(Quest).where(Quest.day == day))).first()
    if quest is None:
        return QuestDelta()
    items = await _items(session, quest)
    item = next((i for i in items if i.exercise_slug == slug and i.completed_at is None), None)
    if item is None:
        return QuestDelta()
    rules = content.quests.quests
    xp = 0
    key = f"quest:{day.isoformat()}:{item.position}"
    if await award_xp(
        session, user, source="quest", ref_key=key, amount=rules.xp_per_quest, day=day
    ):
        xp += rules.xp_per_quest
    item.completed_at = datetime.now(UTC)
    item.xp_awarded = xp
    session.add(item)
    all_done = all(i.completed_at is not None for i in items)
    if all_done and await award_xp(
        session,
        user,
        source="quest_bonus",
        ref_key=f"quests_done:{day.isoformat()}",
        amount=rules.all_done_bonus,
        day=day,
    ):
        xp += rules.all_done_bonus
    return QuestDelta(completed_position=item.position, xp=xp, all_done=all_done)
