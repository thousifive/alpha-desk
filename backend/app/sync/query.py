"""Reading the event log back out, page by page."""

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import SyncEvent

MAX_PAGE = 500


def row_to_event(row: SyncEvent) -> dict[str, Any]:
    """The JSON envelope devices store (the same shape they uploaded)."""
    return {
        "id": row.id,
        "device_id": row.device_id,
        "type": row.type,
        "payload": row.payload,
        # SQLite drops the timezone; every stored timestamp is UTC (validated as aware on input).
        "created_at": row.created_at.isoformat()
        if row.created_at.tzinfo
        else row.created_at.isoformat() + "+00:00",
        "local_date": row.local_date.isoformat(),
        "v": row.v,
    }


async def events_since(
    session: AsyncSession, since: int, limit: int
) -> tuple[list[SyncEvent], bool]:
    """One page of the log after cursor `since`: (rows ordered by seq, more_rows_exist).

    TODO(me) M2.5-2. Teaches: keyset pagination. `WHERE seq > :since ORDER BY seq LIMIT n`
    uses the primary-key index and stays fast at any depth, unlike OFFSET, which re-reads and
    throws away every earlier row (and skips or repeats rows if new ones arrive between pages).

    Fetch `limit + 1` rows: if you get the extra one, there's another page; drop it before
    returning. The caller sends the last row's seq back as the next cursor.
    """
    raise NotImplementedError("TODO(me) M2.5-2: implement events_since")
