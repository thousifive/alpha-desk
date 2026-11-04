"""Keep the server's derived tables (Attempt, XpEvent, QuestItem) in step with the event log.

Devices are the source of truth now; these tables exist so server-side features (the AI
grader's history, the weekly report, quest planning by weakness) can keep using plain SQL.
They're a *projection*: rebuildable from SyncEvent at any time by resetting derived_seq.
"""

import asyncio
from datetime import UTC

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.content.schema import ContentBundle
from app.events.legacy import LEGACY_DEVICE
from app.events.schema import EVENT, AttemptEvent, QuestCompletedEvent, XpAwardedEvent
from app.game.service import award_xp, get_user
from app.models import Attempt, Quest, QuestItem, SyncEvent, SyncState, User
from app.sync.query import row_to_event

# One uvicorn worker, so an asyncio.Lock is enough to stop two concurrent syncs from both
# reading derived_seq = N and applying the same events twice.
_lock = asyncio.Lock()
_CHUNK = 500


async def refresh_derived(session: AsyncSession, content: ContentBundle) -> int:
    """Apply every event after the stored cursor. Returns how many were applied."""
    async with _lock:
        state = await session.get(SyncState, 1)
        if state is None:
            state = SyncState(id=1)
            session.add(state)
        exercises = {
            ex.slug for nodes in content.nodes.values() for n in nodes for ex in n.exercises
        }
        user = await get_user(session)
        applied = 0
        while True:
            rows = (
                await session.exec(
                    select(SyncEvent)
                    .where(col(SyncEvent.seq) > state.derived_seq)
                    .order_by(col(SyncEvent.seq))
                    .limit(_CHUNK)
                )
            ).all()
            if not rows:
                break
            for row in rows:
                # Legacy events were *made from* these tables; applying them would double up.
                if row.device_id != LEGACY_DEVICE:
                    await _apply(session, row, user, exercises)
                    applied += 1
                assert row.seq is not None
                state.derived_seq = row.seq
            session.add(state)
            await session.commit()  # cursor and effects commit together, so a crash replays
        return applied


async def _apply(session: AsyncSession, row: SyncEvent, user: User, exercises: set[str]) -> None:
    # Rows were validated on ingest; re-validating gives typed access to the payload.
    ev = EVENT.validate_python(row_to_event(row))
    match ev:
        case AttemptEvent(payload=p):
            if p.exercise_slug not in exercises:
                return  # exercise since removed from content
            session.add(
                Attempt(
                    exercise_slug=p.exercise_slug,
                    code=p.code,
                    passed=p.passed,
                    hints_used=p.hints_used,
                    duration_ms=p.duration_ms,
                    created_at=ev.created_at,
                    local_date=ev.local_date,
                    event_id=row.id,
                )
            )
        case XpAwardedEvent(payload=p):
            # The ledger's unique ref_key does the cross-device dedupe: if both devices paid
            # "attempt:x" offline, the second insert is a no-op. Same rule as the projection.
            await award_xp(
                session,
                user,
                source=p.source,
                ref_key=p.ref_key,
                amount=p.amount,
                day=ev.local_date,
            )
        case QuestCompletedEvent(payload=p):
            item = (
                await session.exec(
                    select(QuestItem)
                    .join(Quest, col(Quest.id) == col(QuestItem.quest_id))
                    .where(Quest.day == p.day, QuestItem.position == p.position)
                )
            ).first()
            if item is not None and item.completed_at is None:
                item.completed_at = ev.created_at.astimezone(UTC)
                session.add(item)
        case _:
            pass  # flashcards/hints/achievements: no server tables until M3/M4
