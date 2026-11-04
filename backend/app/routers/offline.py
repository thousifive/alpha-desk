"""What a device downloads to work with the server off."""

import hashlib
import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from sqlmodel import col, select

from app.auth import AuthRequired
from app.deps import ContentDep, SessionDep, SettingsDep
from app.events.legacy import legacy_events
from app.events.schema import EVENT_LIST
from app.models import Attempt, Quest, QuestItem, XpEvent

router = APIRouter(prefix="/api/offline", tags=["offline"])


@router.get("/bundle")
async def bundle(_: AuthRequired, content: ContentDep, settings: SettingsDep) -> dict[str, Any]:
    """All content, *including* grading data (solutions, quiz answers, hidden tests), so the
    device can grade offline. Acceptable for a single-player app: see docs/SPEC.md. Behind
    auth, so it isn't public on the internet."""
    body = content.model_dump(mode="json")
    # sort_keys makes the hash stable across runs (dict order alone isn't a content change).
    raw = json.dumps({"c": body, "m": settings.current_milestone}, sort_keys=True)
    version = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return {"version": version, "milestone": settings.current_milestone, "content": body}


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
