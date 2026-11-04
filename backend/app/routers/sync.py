"""Device sync: upload events, download events, and fetch quest plans for offline days."""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query, status
from pydantic import BaseModel

from app.auth import AuthRequired
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.daily import get_or_create_quest
from app.game.service import passed_slugs
from app.sync.derive import refresh_derived
from app.sync.ingest import MAX_BATCH, ingest_events
from app.sync.query import MAX_PAGE, events_since, row_to_event

router = APIRouter(prefix="/api/sync", tags=["sync"])


def _locked(e: NotImplementedError) -> HTTPException:
    # Same 501 contract as the other TODO(me) routes, so the UI shows which task unlocks it.
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"Sync offline: {e}")


class IngestOut(BaseModel):
    accepted: int
    duplicates: int
    rejected: int


class EventPage(BaseModel):
    events: list[dict[str, Any]]
    cursor: int  # pass back as ?since= for the next page
    more: bool


class QuestPlanOut(BaseModel):
    day: date
    items: list[tuple[int, str]]  # (position, exercise slug)


class QuestPlansOut(BaseModel):
    plans: list[QuestPlanOut]


@router.post("/events", response_model=IngestOut)
async def post_events(
    _: AuthRequired,
    session: SessionDep,
    content: ContentDep,
    # Raw dicts, not list[AnyEvent]: one bad event must count as "rejected", not 422 the
    # whole batch, so validation happens per event inside ingest_events.
    batch: Annotated[list[dict[str, Any]], Body(max_length=MAX_BATCH)],
) -> IngestOut:
    try:
        result = await ingest_events(session, batch)
    except NotImplementedError as e:
        raise _locked(e) from e
    await refresh_derived(session, content)
    return IngestOut(
        accepted=result.accepted, duplicates=result.duplicates, rejected=result.rejected
    )


@router.get("/events", response_model=EventPage)
async def get_events(
    _: AuthRequired,
    session: SessionDep,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = MAX_PAGE,
) -> EventPage:
    try:
        rows, more = await events_since(session, since, limit)
    except NotImplementedError as e:
        raise _locked(e) from e
    cursor = rows[-1].seq if rows and rows[-1].seq is not None else since
    return EventPage(events=[row_to_event(r) for r in rows], cursor=cursor, more=more)


@router.get("/quests", response_model=QuestPlansOut)
async def quest_plans(
    _: AuthRequired,
    session: SessionDep,
    content: ContentDep,
    settings: SettingsDep,
    # The device's local date: it knows its own timezone better than the server does.
    start: Annotated[date, Query(alias="from")],
    days: Annotated[int, Query(ge=1, le=7)] = 3,
) -> QuestPlansOut:
    """Quest plans for `days` days from `from`, generated now so they work offline later.

    Each day's plan is created once and then fixed (Quest.day is unique), so every device
    gets the same tickets for the same day.
    """
    passed = await passed_slugs(session)
    plans: list[QuestPlanOut] = []
    for i in range(days):
        day = start + timedelta(days=i)
        try:
            _q, items = await get_or_create_quest(
                session, content, passed, settings.current_milestone, day
            )
        except NotImplementedError as e:
            # Same prefix as /quests/today, so the UI maps it to TODO(me) M2-2.
            raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"Quest board offline: {e}") from e
        plans.append(QuestPlanOut(day=day, items=[(it.position, it.exercise_slug) for it in items]))
    return QuestPlansOut(plans=plans)
