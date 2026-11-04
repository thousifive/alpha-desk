from datetime import UTC, date, datetime

from httpx import AsyncClient

from app.config import get_settings
from app.content.loader import load_content, sync_content
from app.db import get_sessionmaker
from app.events.legacy import LEGACY_DEVICE, legacy_events
from app.events.schema import EVENT_LIST
from app.models import Attempt, Quest, QuestItem, XpEvent

BUNDLE = load_content(get_settings().content_dir)


async def test_offline_routes_require_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/offline/bundle")).status_code == 401
    assert (await client.get("/api/offline/legacy-events")).status_code == 401


async def test_bundle_has_grading_data_and_stable_version(authed_client: AsyncClient) -> None:
    a = (await authed_client.get("/api/offline/bundle")).json()
    b = (await authed_client.get("/api/offline/bundle")).json()
    assert a["version"] == b["version"]
    assert a["milestone"] == get_settings().current_milestone
    text = str(a["content"])
    # Offline grading needs these on the device (single-player trust model).
    assert "solution_sql" in text and "hidden_tests" in text


def _rows() -> tuple[list[Attempt], list[XpEvent], list[tuple[Quest, QuestItem]]]:
    t = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)
    d = date(2026, 11, 1)
    attempts = [
        Attempt(id=1, exercise_slug="sql-first-look", passed=True, local_date=d, created_at=t)
    ]
    xp = [
        XpEvent(id=1, source="attempt", ref_key="attempt:sql-first-look", amount=20, local_date=d),
        XpEvent(id=2, source="attempt", ref_key="attempt:zero", amount=0, local_date=d),
    ]
    q = Quest(id=1, day=d)
    items = [
        (
            q,
            QuestItem(id=1, quest_id=1, position=0, exercise_slug="sql-first-look", completed_at=t),
        ),
        (q, QuestItem(id=2, quest_id=1, position=1, exercise_slug="quiz-py-generics")),
    ]
    return attempts, xp, items


def test_legacy_conversion_is_deterministic() -> None:
    a = legacy_events(*_rows())
    b = legacy_events(*_rows())
    assert [e.id for e in a] == [e.id for e in b]  # uuid5: same rows → same ids
    assert [e.type for e in a] == ["attempt", "xp_awarded", "quest_completed"]  # 0 XP dropped
    assert all(e.device_id == LEGACY_DEVICE and e.created_at.tzinfo is UTC for e in a)


async def test_legacy_endpoint(authed_client: AsyncClient) -> None:
    async with get_sessionmaker()() as s:
        await sync_content(s, BUNDLE)
        attempts, xp, items = _rows()
        s.add_all([*attempts, *xp, items[0][0], *(it for _, it in items)])
        await s.commit()
    body = (await authed_client.get("/api/offline/legacy-events")).json()
    events = EVENT_LIST.validate_python(body)
    assert [e.type for e in events] == ["attempt", "xp_awarded", "quest_completed"]
