"""The progress event log: one append-only record per thing that happened.

Events are facts ("this attempt passed", "this XP was paid"), never updated or deleted. Every
device keeps its own copy of the log; state (XP, level, streak, node progress) is derived from
it by app.game.projection. The browser runs this exact module in Pyodide, so it must only
import pydantic and the standard library.
"""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter

SCHEMA_VERSION = 1


class _Payload(BaseModel):
    # extra="forbid" so a typo'd field from a buggy client is rejected, not silently stored.
    model_config = ConfigDict(extra="forbid", frozen=True)


class AttemptPayload(_Payload):
    exercise_slug: str = Field(max_length=120)
    passed: bool
    hints_used: int = Field(default=0, ge=0, le=3)
    duration_ms: int = Field(default=0, ge=0)
    # Optional so the browser can strip it before handing events to the rules worker.
    code: str = Field(default="", max_length=20_000)


XpSource = Literal["attempt", "node", "quest", "quest_bonus", "streak", "legacy"]


class XpAwardedPayload(_Payload):
    # Names *what* was paid for ("attempt:sql-first-look"). Two devices paying the same key
    # offline both log an event; the projection counts only the first one.
    ref_key: str = Field(max_length=200)
    source: XpSource
    amount: int = Field(ge=1)


class QuestCompletedPayload(_Payload):
    day: date
    position: int = Field(ge=0, le=5)
    exercise_slug: str = Field(max_length=120)


# Reserved for M3/M4 so the log format doesn't change when those features land.
class FlashcardReviewedPayload(_Payload):
    card_id: str = Field(max_length=120)
    grade: int = Field(ge=0, le=5)  # SM-2 quality


class HintUsedPayload(_Payload):
    exercise_slug: str = Field(max_length=120)
    level: int = Field(ge=1, le=3)


class AchievementUnlockedPayload(_Payload):
    achievement_id: str = Field(max_length=120)


class _EventBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    device_id: str = Field(min_length=1, max_length=64)
    # AwareDatetime rejects naive timestamps: "12:00" is meaningless without a zone.
    created_at: AwareDatetime
    # The player's calendar day when it happened, frozen on the device that created it.
    # Streaks group by this; recomputing it later (or from sync time) would shift days.
    local_date: date
    v: int = SCHEMA_VERSION


class AttemptEvent(_EventBase):
    type: Literal["attempt"]
    payload: AttemptPayload


class XpAwardedEvent(_EventBase):
    type: Literal["xp_awarded"]
    payload: XpAwardedPayload


class QuestCompletedEvent(_EventBase):
    type: Literal["quest_completed"]
    payload: QuestCompletedPayload


class FlashcardReviewedEvent(_EventBase):
    type: Literal["flashcard_reviewed"]
    payload: FlashcardReviewedPayload


class HintUsedEvent(_EventBase):
    type: Literal["hint_used"]
    payload: HintUsedPayload


class AchievementUnlockedEvent(_EventBase):
    type: Literal["achievement_unlocked"]
    payload: AchievementUnlockedPayload


# Discriminated on `type`: Pydantic picks the one matching model and validates its payload.
AnyEvent = Annotated[
    AttemptEvent
    | XpAwardedEvent
    | QuestCompletedEvent
    | FlashcardReviewedEvent
    | HintUsedEvent
    | AchievementUnlockedEvent,
    Field(discriminator="type"),
]

# A TypeAdapter validates types that aren't BaseModel subclasses (here: a list of a union).
# Build it once at import: constructing one compiles a validator, which isn't free.
EVENT_LIST = TypeAdapter(list[AnyEvent])
EVENT = TypeAdapter(AnyEvent)
