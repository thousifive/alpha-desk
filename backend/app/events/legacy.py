"""Convert pre-event-log tables (Attempt, XpEvent, QuestItem) into events, once.

Ids are uuid5 (a hash of a fixed namespace plus the row's identity), not random: converting
the same row twice always gives the same id, so the browser import now and the server
migration in Part 2 produce identical events, and merge-by-id removes the overlap.
"""

import uuid
from datetime import UTC, date, datetime

from app.events.schema import (
    AnyEvent,
    AttemptEvent,
    AttemptPayload,
    QuestCompletedEvent,
    QuestCompletedPayload,
    XpAwardedEvent,
    XpAwardedPayload,
)
from app.models import Attempt, Quest, QuestItem, XpEvent

# Any fixed UUID works as a namespace; this one is just uuid5(NAMESPACE_URL, "alpha-desk").
LEGACY_NS = uuid.uuid5(uuid.NAMESPACE_URL, "alpha-desk:legacy")
LEGACY_DEVICE = "server-legacy"


def _aware(dt: datetime) -> datetime:
    # SQLite has no timezone type, so rows come back naive even though we wrote UTC.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def legacy_events(
    attempts: list[Attempt],
    xp_events: list[XpEvent],
    quest_items: list[tuple[Quest, QuestItem]],
) -> list[AnyEvent]:
    out: list[AnyEvent] = []
    for a in attempts:
        out.append(
            AttemptEvent(
                type="attempt",
                id=uuid.uuid5(LEGACY_NS, f"attempt:{a.id}"),
                device_id=LEGACY_DEVICE,
                created_at=_aware(a.created_at),
                local_date=a.local_date,
                payload=AttemptPayload(
                    exercise_slug=a.exercise_slug,
                    passed=a.passed,
                    hints_used=min(a.hints_used, 3),
                    duration_ms=a.duration_ms,
                    code=a.code[:20_000],
                ),
            )
        )
    for x in xp_events:
        if x.amount <= 0:
            continue
        out.append(
            XpAwardedEvent(
                type="xp_awarded",
                id=uuid.uuid5(LEGACY_NS, f"xp:{x.ref_key}"),
                device_id=LEGACY_DEVICE,
                created_at=_aware(x.created_at),
                local_date=x.local_date,
                payload=XpAwardedPayload(
                    ref_key=x.ref_key,
                    source=x.source if x.source in _SOURCES else "legacy",
                    amount=x.amount,
                ),
            )
        )
    for q, it in quest_items:
        if it.completed_at is None:
            continue
        day: date = q.day
        out.append(
            QuestCompletedEvent(
                type="quest_completed",
                id=uuid.uuid5(LEGACY_NS, f"quest:{day.isoformat()}:{it.position}"),
                device_id=LEGACY_DEVICE,
                created_at=_aware(it.completed_at),
                local_date=day,
                payload=QuestCompletedPayload(
                    day=day, position=it.position, exercise_slug=it.exercise_slug
                ),
            )
        )
    return out


_SOURCES = {"attempt", "node", "quest", "quest_bonus", "streak", "legacy"}
