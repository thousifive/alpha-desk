"""Database tables (SQLModel). API shapes live in schemas.py, kept separate on purpose:
table columns and public JSON evolve independently, and some columns (Exercise.spec)
must never be serialized to the browser."""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    xp_total: int = 0  # cached sum of XpEvent.amount; cheap to read on every page
    # IANA zone name ("Europe/London"), sent by the browser at login. "Today" for quests and
    # streaks is the player's local date, not the server's UTC date.
    timezone: str = "UTC"
    created_at: datetime = Field(default_factory=utcnow)


class SkillNode(SQLModel, table=True):
    # Natural keys (slugs) instead of autoincrement ids: YAML content refers to nodes by
    # slug, and re-syncing content must update the same row, not create a new one.
    slug: str = Field(primary_key=True)
    branch: str = Field(index=True)
    title: str
    description: str = ""
    order: int = 0
    # A JSON column holds a plain list; SQLite has no array type and we never join on it.
    prerequisites: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    xp_reward: int = 0
    is_boss: bool = False


class Exercise(SQLModel, table=True):
    slug: str = Field(primary_key=True)
    node_slug: str = Field(foreign_key="skillnode.slug", index=True)
    order: int = 0
    type: str  # "sql" | "quiz" | later "python", "polars", "review"
    persona: str  # "priya" | "marcus" | "lena"
    title: str
    prompt_md: str
    starter_code: str = ""
    difficulty: int = 1
    playable: bool = True  # False for placeholder exercises in branches built later
    choices: list[str] = Field(default_factory=list, sa_column=Column(JSON))  # quiz only; public
    # Hidden grading data: solution_sql, quiz answers, etc. Never sent to the client.
    spec: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    exercise_slug: str = Field(foreign_key="exercise.slug", index=True)
    code: str = ""
    passed: bool = False
    hints_used: int = 0
    duration_ms: int = 0
    xp_awarded: int = 0  # exercise + node-mastery XP paid by this attempt (quest XP is separate)
    created_at: datetime = Field(default_factory=utcnow)
    # Player-local calendar day, frozen at insert time. Streaks group by this; recomputing it
    # from created_at later would shift days if the player changes timezone.
    local_date: date = Field(index=True)


class XpEvent(SQLModel, table=True):
    """Append-only XP ledger. User.xp_total is a cache of SUM(amount).

    `ref_key` is unique and names *what* was paid for ("quest:2026-11-03:1"), so paying the
    same thing twice (double-click, retry, race) hits the constraint instead of the wallet.
    That's the same idempotency-key idea as an upsert in an ETL load.
    """

    id: int | None = Field(default=None, primary_key=True)
    source: str  # "attempt" | "quest" | "quest_bonus" | "streak" | "legacy"
    ref_key: str = Field(unique=True)
    amount: int
    local_date: date = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Quest(SQLModel, table=True):
    """One row per player-local day. The unique day makes lazy generation race-safe."""

    id: int | None = Field(default=None, primary_key=True)
    # Named `day`, not `date`: a field called `date` would shadow the `date` type in the
    # class body, and Pydantic can no longer resolve the annotation.
    day: date = Field(unique=True)
    created_at: datetime = Field(default_factory=utcnow)


class QuestItem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("quest_id", "position"),)

    id: int | None = Field(default=None, primary_key=True)
    quest_id: int = Field(foreign_key="quest.id", index=True)
    position: int
    exercise_slug: str = Field(foreign_key="exercise.slug")
    completed_at: datetime | None = None
    xp_awarded: int = 0


class SyncEvent(SQLModel, table=True):
    """The server's copy of every device's event log (see app.events.schema).

    `seq` is the sync cursor: devices ask for "everything after seq N". It's the autoincrement
    primary key, so it only grows. That's safe as a cursor here because SQLite has a single
    writer: a row with a higher seq can't commit *before* a lower one and get skipped. (On
    Postgres, concurrent transactions can commit out of seq order; you'd need a different
    cursor there.)
    """

    seq: int | None = Field(default=None, primary_key=True)
    # The device-generated uuid. Unique, so re-sending an event (retry after a dropped
    # response) can't store it twice: that's what makes ingestion idempotent.
    id: str = Field(unique=True, max_length=36)
    device_id: str = Field(index=True, max_length=64)
    type: str = Field(max_length=40)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime
    local_date: date
    v: int = 1
    received_at: datetime = Field(default_factory=utcnow)


class SyncState(SQLModel, table=True):
    """Single row (id=1): how far the derived tables (Attempt, XpEvent, quests) have read
    the event log. Like a consumer offset in Kafka: reprocessing restarts from here."""

    id: int | None = Field(default=1, primary_key=True)
    derived_seq: int = 0
