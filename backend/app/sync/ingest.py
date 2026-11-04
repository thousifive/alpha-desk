"""Accepting a batch of events from a device."""

from dataclasses import dataclass
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.events.schema import AnyEvent
from app.models import SyncEvent

MAX_BATCH = 200


@dataclass(frozen=True)
class IngestResult:
    accepted: int  # newly stored
    duplicates: int  # id already stored (or repeated within this batch)
    rejected: int  # failed validation; not stored


def to_row(event: AnyEvent) -> SyncEvent:
    """A validated event as a table row. mode="json" turns UUID/date values into plain JSON."""
    return SyncEvent(
        id=str(event.id),
        device_id=event.device_id,
        type=event.type,
        payload=event.payload.model_dump(mode="json"),
        created_at=event.created_at,
        local_date=event.local_date,
        v=event.v,
    )


async def ingest_events(session: AsyncSession, batch: list[dict[str, Any]]) -> IngestResult:
    """Store a device's batch of events, idempotently.

    TODO(me) M2.5-1. Teaches: idempotent ingestion, the same pattern as an ETL load that can
    be safely re-run after a crash halfway through.

    1. Validate each raw dict with `EVENT` (a TypeAdapter in app.events.schema). An invalid
       one counts as rejected, but the rest of the batch still goes in.
    2. Skip events whose id is already in `SyncEvent` (one SELECT ... WHERE id IN (...), not a
       query per event) and ids repeated inside the batch itself. Both count as duplicates.
    3. Insert the rest with `to_row` in **one** transaction (session.add_all + one commit),
       so a crash leaves either the whole batch or none of it.
    4. Return the three counts.

    The client re-sends a batch if it never saw the response, so calling this twice with the
    same batch must store each event once: the second call returns accepted=0.
    """
    raise NotImplementedError("TODO(me) M2.5-1: implement ingest_events")
