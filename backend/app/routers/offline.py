"""What a device downloads to work with the server off."""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from sqlmodel import col, select

from app.auth import AuthRequired
from app.content.bundle import build_bundle
from app.deps import ContentDep, SessionDep, SettingsDep
from app.events.legacy import legacy_events
from app.events.schema import EVENT_LIST
from app.models import Attempt, Quest, QuestItem, XpEvent

router = APIRouter(prefix="/api/offline", tags=["offline"])


@router.get("/bundle")
async def bundle(_: AuthRequired, content: ContentDep, settings: SettingsDep) -> dict[str, Any]:
    # Behind auth, so the grading data in it isn't public on the internet.
    return build_bundle(content, settings.current_milestone)


@router.get("/legacy-events")
async def legacy(_: AuthRequired, session: SessionDep) -> Response:
    """Progress recorded before the event log existed, as events. Imported once per device."""
    attempts = list((await session.exec(select(Attempt).order_by(col(Attempt.id)))).all())
    xp = list((await session.exec(select(XpEvent).order_by(col(XpEvent.id)))).all())
    rows = await session.exec(
        select(Quest, QuestItem).where(col(QuestItem.quest_id) == col(Quest.id))
    )
    events = legacy_events(attempts, xp, [(q, it) for q, it in rows.all()])
    # dump_json serializes UUIDs/dates the same way the browser's events are written.
    return Response(EVENT_LIST.dump_json(events), media_type="application/json")
