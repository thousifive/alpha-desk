"""Database tables (SQLModel). API shapes live in schemas.py, kept separate on purpose:
table columns and public JSON evolve independently, and some columns (Exercise.spec)
must never be serialized to the browser."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    xp_total: int = 0  # cached sum of Attempt.xp_awarded; cheap to read on every page
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
    # Hidden grading data: solution_sql, quiz answers, etc. Never sent to the client.
    spec: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    exercise_slug: str = Field(foreign_key="exercise.slug", index=True)
    code: str = ""
    passed: bool = False
    hints_used: int = 0
    duration_ms: int = 0
    xp_awarded: int = 0
    created_at: datetime = Field(default_factory=utcnow)
