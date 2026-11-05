"""Device sync (Part 2 of docs/tasks/deploy-mobile-sync.md).

`ingest_events` is TODO(me) M2.5-1 and `events_since` is TODO(me) M2.5-2: their tests are
strict xfail. Remove a `todo_*` marker once that function is done; also delete the matching
`*_locked_until_*` test, which checks the 501 shown while it isn't.
"""

import random
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import col, select

import app.game.quests as quests
from app.auth import issue_token, token_valid
from app.config import get_settings
from app.content.loader import load_content, sync_content
from app.db import get_sessionmaker
from app.events.legacy import LEGACY_DEVICE
from app.events.schema import EVENT
from app.models import Attempt, Quest, QuestItem, SyncEvent, User, XpEvent
from app.sync.derive import refresh_derived
from app.sync.ingest import IngestResult, ingest_events, to_row
from app.sync.query import events_since, row_to_event
from tests.conftest import TEST_PASSWORD

BUNDLE = load_content(get_settings().content_dir)

todo_ingest = pytest.mark.xfail(reason="TODO(me) M2.5-1: implement ingest_events", strict=True)
todo_since = pytest.mark.xfail(reason="TODO(me) M2.5-2: implement events_since", strict=True)
todo_both = pytest.mark.xfail(
    reason="TODO(me) M2.5-1 + M2.5-2: ingest_events and events_since", strict=True
)

T0 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def _synced() -> None:
    async with get_sessionmaker()() as s:
        await sync_content(s, BUNDLE)


def ev(n: int, *, device: str = "dev-a", type_: str = "attempt", **payload: Any) -> dict[str, Any]:
    """A raw event as a device would POST it. Ids are deterministic per (device, n)."""
    if not payload:
        payload = {"exercise_slug": "sql-first-look", "passed": False}
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{device}:{n}")),
        "device_id": device,
        "type": type_,
        "payload": payload,
        "created_at": (T0 + timedelta(minutes=n)).isoformat(),
        "local_date": "2026-11-04",
        "v": 1,
    }


async def _store(*events: dict[str, Any]) -> None:
    """Put events in the log directly (bypassing the TODO) to test what reads it."""
    async with get_sessionmaker()() as s:
        s.add_all([to_row(EVENT.validate_python(e)) for e in events])
        await s.commit()


# ---- auth: bearer tokens ----------------------------------------------------------------


async def test_login_returns_a_30_day_token(client: AsyncClient) -> None:
    body = (await client.post("/api/auth/login", json={"password": TEST_PASSWORD})).json()
    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(days=29) < expires - datetime.now(UTC) <= timedelta(days=30)
    assert token_valid(body["token"], get_settings())


async def test_bearer_token_works_without_cookie(client: AsyncClient) -> None:
    from app.main import create_app

    token = (await client.post("/api/auth/login", json={"password": TEST_PASSWORD})).json()["token"]
    # A fresh client has no cookie jar: like the PWA on another origin.
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        assert (await c.get("/api/auth/me")).status_code == 401
        h = {"Authorization": f"Bearer {token}"}
        assert (await c.get("/api/auth/me", headers=h)).status_code == 200
        fresh = await c.post("/api/auth/refresh", headers=h)
        assert fresh.status_code == 200 and token_valid(fresh.json()["token"], get_settings())


async def test_bad_or_expired_token_rejected(client: AsyncClient) -> None:
    settings = get_settings()
    token, _ = issue_token(settings)
    expired = settings.model_copy(update={"token_max_age_s": -1})
    assert not token_valid(token, expired)
    assert not token_valid(token + "x", settings)
    assert not token_valid(token, settings.model_copy(update={"session_secret": "other"}))
    bad = {"Authorization": f"Bearer {token}x"}
    assert (await client.get("/api/auth/me", headers=bad)).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_cors_allows_configured_origin_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "cors_origins", "https://alpha.netlify.app")
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:

        async def preflight(origin: str) -> str | None:
            r = await c.options(
                "/api/sync/events",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            return r.headers.get("access-control-allow-origin")

        assert await preflight("https://alpha.netlify.app") == "https://alpha.netlify.app"
        assert await preflight("https://evil.example") is None


NETLIFY = "https://alpha.netlify.app"


async def _cross_origin_client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """The API as the Netlify PWA sees it: another origin, no cookie jar shared with login."""
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "cors_origins", f"{NETLIFY},http://localhost:5173")
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="https://api.ts.net")


def _pna_preflight(origin: str) -> dict[str, str]:
    # What Chrome sends before a public page calls a private (tailnet 100.x) address.
    return {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
        "Access-Control-Request-Private-Network": "true",
    }


async def test_private_network_preflight_allowed_for_configured_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with await _cross_origin_client(monkeypatch) as c:
        r = await c.options("/api/auth/login", headers=_pna_preflight(NETLIFY))
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == NETLIFY
        assert r.headers["access-control-allow-private-network"] == "true"
        # No cookies cross origins: auth is the bearer header.
        assert "access-control-allow-credentials" not in r.headers
        # Dev origin from the same env var.
        r = await c.options("/api/sync/events", headers=_pna_preflight("http://localhost:5173"))
        assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_private_network_preflight_from_other_origin_stays_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with await _cross_origin_client(monkeypatch) as c:
        r = await c.options("/api/auth/login", headers=_pna_preflight("https://evil.example"))
        # Without Allow-Origin the browser blocks the request, whatever else is in the reply.
        assert r.status_code == 400
        assert "access-control-allow-origin" not in r.headers


async def test_plain_request_without_pna_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    # Safari and Firefox don't send the private-network header at all.
    async with await _cross_origin_client(monkeypatch) as c:
        h = _pna_preflight(NETLIFY)
        del h["Access-Control-Request-Private-Network"]
        r = await c.options("/api/sync/events", headers=h)
        assert r.status_code == 200
        assert "access-control-allow-private-network" not in r.headers


async def test_cross_origin_login_then_bearer_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole Netlify -> ts.net flow: login returns a token, later calls carry only that."""
    async with await _cross_origin_client(monkeypatch) as c:
        origin = {"Origin": NETLIFY}
        login = await c.post("/api/auth/login", json={"password": TEST_PASSWORD}, headers=origin)
        assert login.status_code == 200
        assert login.headers["access-control-allow-origin"] == NETLIFY
        token = login.json()["token"]
        # Like Safari blocking third-party cookies: drop whatever cookie login set.
        c.cookies.clear()
        auth = {**origin, "Authorization": f"Bearer {token}"}
        me = await c.get("/api/auth/me", headers=auth)
        assert me.status_code == 200
        assert me.headers["access-control-allow-origin"] == NETLIFY
        assert (await c.get("/api/auth/me", headers=origin)).status_code == 401


# ---- routes -------------------------------------------------------------------------------


async def test_sync_routes_require_auth(client: AsyncClient) -> None:
    assert (await client.post("/api/sync/events", json=[])).status_code == 401
    assert (await client.get("/api/sync/events")).status_code == 401
    assert (await client.get("/api/sync/quests?from=2026-11-04")).status_code == 401


async def test_batch_size_is_capped(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/sync/events", json=[ev(i) for i in range(201)])
    assert resp.status_code == 422


async def test_upload_locked_until_ingest_events(authed_client: AsyncClient) -> None:
    resp = await authed_client.post("/api/sync/events", json=[ev(1)])
    assert resp.status_code == 501
    assert "TODO(me) M2.5-1" in resp.json()["detail"]


async def test_download_locked_until_events_since(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/sync/events?since=0")
    assert resp.status_code == 501
    assert "TODO(me) M2.5-2" in resp.json()["detail"]


# ---- TODO(me) M2.5-1: ingest_events ---------------------------------------------------------


@todo_ingest
async def test_ingest_accepts_new_events() -> None:
    async with get_sessionmaker()() as s:
        assert await ingest_events(s, [ev(1), ev(2)]) == IngestResult(2, 0, 0)
        assert len((await s.exec(select(SyncEvent))).all()) == 2


@todo_ingest
async def test_ingest_is_idempotent() -> None:
    # The client never saw the first response (phone went to sleep) and sends it again.
    batch = [ev(1), ev(2), ev(3)]
    async with get_sessionmaker()() as s:
        await ingest_events(s, batch)
        assert await ingest_events(s, batch) == IngestResult(0, 3, 0)
        assert len((await s.exec(select(SyncEvent))).all()) == 3


@todo_ingest
async def test_ingest_dedupes_within_a_batch() -> None:
    async with get_sessionmaker()() as s:
        assert await ingest_events(s, [ev(1), ev(1), ev(2)]) == IngestResult(2, 1, 0)


@todo_ingest
async def test_ingest_rejects_invalid_events_but_keeps_the_rest() -> None:
    naive_time = {**ev(2), "created_at": "2026-11-04T09:00:00"}  # no timezone
    bad_payload = ev(3, passed="maybe")
    unknown_type = {**ev(4), "type": "teleport"}
    not_an_event: dict[str, Any] = {"hello": "world"}
    async with get_sessionmaker()() as s:
        result = await ingest_events(
            s, [ev(1), naive_time, bad_payload, unknown_type, not_an_event, ev(5)]
        )
        assert result == IngestResult(accepted=2, duplicates=0, rejected=4)
        ids = set((await s.exec(select(SyncEvent.id))).all())
        assert ids == {ev(1)["id"], ev(5)["id"]}


@todo_ingest
async def test_ingest_preserves_the_event_exactly() -> None:
    e = ev(1, exercise_slug="sql-first-look", passed=True, hints_used=1, code="SELECT 1")
    async with get_sessionmaker()() as s:
        await ingest_events(s, [e])
        row = (await s.exec(select(SyncEvent))).one()
        assert EVENT.validate_python(row_to_event(row)) == EVENT.validate_python(e)


# ---- TODO(me) M2.5-2: events_since ----------------------------------------------------------


@todo_since
async def test_events_since_pages_by_seq() -> None:
    await _store(*[ev(i) for i in range(5)])
    async with get_sessionmaker()() as s:
        page1, more1 = await events_since(s, 0, 2)
        assert [r.id for r in page1] == [ev(0)["id"], ev(1)["id"]] and more1
        assert page1[-1].seq is not None
        page2, more2 = await events_since(s, page1[-1].seq, 2)
        assert [r.id for r in page2] == [ev(2)["id"], ev(3)["id"]] and more2
        assert page2[-1].seq is not None
        page3, more3 = await events_since(s, page2[-1].seq, 2)
        assert [r.id for r in page3] == [ev(4)["id"]] and not more3


@todo_since
async def test_events_since_exact_page_has_no_more() -> None:
    await _store(ev(0), ev(1))
    async with get_sessionmaker()() as s:
        rows, more = await events_since(s, 0, 2)
        assert len(rows) == 2 and not more
        assert rows[-1].seq is not None
        assert await events_since(s, rows[-1].seq, 2) == ([], False)


@todo_since
async def test_events_since_sees_rows_added_between_pages() -> None:
    # The keyset cursor is "after seq N", so rows that arrive mid-download aren't skipped.
    await _store(ev(0), ev(1))
    async with get_sessionmaker()() as s:
        first, _ = await events_since(s, 0, 1)
    await _store(ev(2, device="dev-b"))
    async with get_sessionmaker()() as s:
        assert first[-1].seq is not None
        rest, more = await events_since(s, first[-1].seq, 10)
        assert [r.id for r in rest] == [ev(1)["id"], ev(2, device="dev-b")["id"]] and not more


# ---- both: the full round trip --------------------------------------------------------------


@todo_both
async def test_two_devices_merge_through_the_server(authed_client: AsyncClient) -> None:
    a = [ev(i, device="phone") for i in range(3)]
    b = [ev(i, device="ipad") for i in range(2)]
    assert (await authed_client.post("/api/sync/events", json=a)).json()["accepted"] == 3
    assert (await authed_client.post("/api/sync/events", json=b)).json()["accepted"] == 2
    page = (await authed_client.get("/api/sync/events?since=0")).json()
    assert {e["id"] for e in page["events"]} == {e["id"] for e in a + b}
    assert not page["more"]
    # The phone's next sync: only what's new since its cursor.
    newer = [ev(9, device="ipad")]
    await authed_client.post("/api/sync/events", json=newer)
    after = (await authed_client.get(f"/api/sync/events?since={page['cursor']}")).json()
    assert [e["id"] for e in after["events"]] == [newer[0]["id"]]


@todo_both
async def test_resent_batch_after_interruption(authed_client: AsyncClient) -> None:
    batch = [ev(i) for i in range(4)]
    await authed_client.post("/api/sync/events", json=batch[:2])  # response "lost"
    again = (await authed_client.post("/api/sync/events", json=batch)).json()
    assert again == {"accepted": 2, "duplicates": 2, "rejected": 0}
    page = (await authed_client.get("/api/sync/events?since=0&limit=3")).json()
    assert len(page["events"]) == 3 and page["more"]


# ---- derived tables (fed from the log, no TODO needed) --------------------------------------


async def test_refresh_derived_applies_each_event_once() -> None:
    await _store(
        ev(1, exercise_slug="sql-first-look", passed=True),
        ev(2, type_="xp_awarded", ref_key="attempt:sql-first-look", source="attempt", amount=20),
        # The iPad passed the same exercise offline and paid the same key: no double pay.
        ev(1, device="ipad", exercise_slug="sql-first-look", passed=True),
        ev(
            2,
            device="ipad",
            type_="xp_awarded",
            ref_key="attempt:sql-first-look",
            source="attempt",
            amount=20,
        ),
        # Made *from* the derived tables, so applying it would double count.
        ev(1, device=LEGACY_DEVICE, exercise_slug="sql-first-look", passed=True),
    )
    async with get_sessionmaker()() as s:
        assert await refresh_derived(s, BUNDLE) == 4
        assert await refresh_derived(s, BUNDLE) == 0
        attempts = (await s.exec(select(Attempt))).all()
        assert len(attempts) == 2 and all(a.local_date == date(2026, 11, 4) for a in attempts)
        assert [x.amount for x in (await s.exec(select(XpEvent))).all()] == [20]
        user = await s.get(User, 1)
        assert user is not None and user.xp_total == 20


async def test_refresh_derived_marks_quest_items_done() -> None:
    day = date(2026, 11, 4)
    async with get_sessionmaker()() as s:
        q = Quest(day=day)
        s.add(q)
        await s.flush()
        assert q.id is not None
        s.add(QuestItem(quest_id=q.id, position=1, exercise_slug="sql-first-look"))
        await s.commit()
    await _store(
        ev(1, type_="quest_completed", day="2026-11-04", position=1, exercise_slug="sql-first-look")
    )
    async with get_sessionmaker()() as s:
        await refresh_derived(s, BUNDLE)
        item = (await s.exec(select(QuestItem))).one()
        assert item.completed_at is not None


async def test_refresh_derived_skips_removed_exercises() -> None:
    await _store(ev(1, exercise_slug="gone-from-content", passed=True))
    async with get_sessionmaker()() as s:
        await refresh_derived(s, BUNDLE)
        assert (await s.exec(select(Attempt))).all() == []


# ---- quest plans for offline days -----------------------------------------------------------


def _top_k[T](items: Sequence[T], weights: Sequence[float], k: int, rng: random.Random) -> list[T]:
    ranked = sorted(range(len(items)), key=lambda i: -weights[i])
    return [items[i] for i in ranked[: max(k, 0)]]


async def test_quest_plans_locked_until_weighted_sample(authed_client: AsyncClient) -> None:
    resp = await authed_client.get("/api/sync/quests?from=2026-11-04")
    assert resp.status_code == 501
    assert "M2-2" in resp.json()["detail"]


async def test_quest_plans_cover_the_next_three_days(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(quests, "weighted_sample", _top_k)  # stand-in for TODO(me) M2-2
    first = (await authed_client.get("/api/sync/quests?from=2026-11-04")).json()["plans"]
    assert [p["day"] for p in first] == ["2026-11-04", "2026-11-05", "2026-11-06"]
    assert all(len(p["items"]) == 3 for p in first)
    # Fixed once generated: another device (or tomorrow's call) gets the same tickets.
    again = (await authed_client.get("/api/sync/quests?from=2026-11-05&days=2")).json()["plans"]
    assert again == first[1:]
    async with get_sessionmaker()() as s:
        days = (await s.exec(select(Quest.day).order_by(col(Quest.day)))).all()
        assert days == [date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 6)]


async def test_quest_plan_days_are_bounded(authed_client: AsyncClient) -> None:
    assert (await authed_client.get("/api/sync/quests?from=2026-11-04&days=8")).status_code == 422
    assert (await authed_client.get("/api/sync/quests")).status_code == 422


async def test_legacy_export_skips_rows_derived_from_synced_events(
    authed_client: AsyncClient,
) -> None:
    # A fresh iPad imports legacy events *and* pulls the log; a derived row in both would
    # count the phone's attempt twice.
    await _store(ev(1, device="phone", exercise_slug="sql-first-look", passed=True))
    async with get_sessionmaker()() as s:
        await refresh_derived(s, BUNDLE)
        s.add(Attempt(exercise_slug="sql-first-look", passed=False, local_date=date(2026, 1, 1)))
        await s.commit()
    legacy = (await authed_client.get("/api/offline/legacy-events")).json()
    attempts = [e for e in legacy if e["type"] == "attempt"]
    assert [e["local_date"] for e in attempts] == ["2026-01-01"]
