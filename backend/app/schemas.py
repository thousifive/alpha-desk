"""Public API shapes (Pydantic v2). Kept apart from tables in models.py so hidden columns
(Exercise.spec) can't leak by accident: a response model only serializes its own fields."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.grading.dataset import MAX_RESULT_ROWS

Cell = str | int | float | bool | None
NodeStateT = Literal["locked", "available", "mastered", "coming_soon"]


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    timezone: str | None = Field(default=None, max_length=64)  # IANA name from the browser


class TimezoneIn(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)


class MeResponse(BaseModel):
    authenticated: bool


class LevelOut(BaseModel):
    index: int
    title: str
    min_xp: int
    next_title: str | None
    next_min_xp: int | None


class BossOut(BaseModel):
    branch_id: str
    branch_title: str
    title: str
    description: str


class StreakOut(BaseModel):
    current: int
    best: int
    freezes: int
    max_freezes: int
    active_today: bool
    next_milestone: int


class QuestItemOut(BaseModel):
    position: int
    slug: str
    title: str
    type: str
    persona: str
    difficulty: int
    branch_id: str
    branch_title: str
    node_title: str
    minutes: int
    completed: bool


class QuestOut(BaseModel):
    day: date
    items: list[QuestItemOut]
    xp_per_quest: int
    all_done_bonus: int
    done: bool
    est_minutes: int


class ProgressOut(BaseModel):
    xp_total: int
    # None until TODO(me) #1 (level_for_xp) is implemented; the UI shows a notice.
    level: LevelOut | None
    # None until TODO(me) M2-1 (compute_streak) is implemented.
    streak: StreakOut | None
    passed_exercises: int
    playable_exercises: int
    mastered_nodes: int
    next_boss: BossOut | None


class BranchSummary(BaseModel):
    id: str
    title: str
    description: str
    order: int
    playable: bool
    playable_from: str
    boss: BossOut | None
    n_nodes: int
    n_mastered: int
    n_exercises: int
    n_passed: int


class ExerciseSummary(BaseModel):
    slug: str
    title: str
    type: str
    persona: str
    difficulty: int
    passed: bool


class NodeOut(BaseModel):
    slug: str
    title: str
    description: str
    order: int
    prerequisites: list[str]
    xp_reward: int
    state: NodeStateT
    exercises: list[ExerciseSummary]


class BranchDetail(BranchSummary):
    nodes: list[NodeOut]


class ExerciseOut(BaseModel):
    slug: str
    title: str
    type: str
    persona: str
    difficulty: int
    prompt_md: str
    starter_code: str
    choices: list[str]
    branch_id: str
    node_slug: str
    node_title: str
    node_state: NodeStateT
    passed: bool
    next_slug: str | None  # next exercise in the same node, for "Next ticket" flow
    # python only. Hidden tests are deliberately absent: see POST /test-bundle.
    visible_tests: str = ""
    packages: list[str] = []
    timeout_s: float = 10


class HiddenTestsOut(BaseModel):
    hidden_tests: str


class SqlResult(BaseModel):
    columns: list[str] = Field(max_length=100)
    rows: list[list[Cell]] = Field(max_length=MAX_RESULT_ROWS)


class ReportedTestIn(BaseModel):
    name: str = Field(max_length=200)
    passed: bool


class AttemptIn(BaseModel):
    code: str = Field(default="", max_length=20_000)
    result: SqlResult | None = None  # sql exercises
    choice: int | None = None  # quiz exercises
    tests: list[ReportedTestIn] | None = Field(default=None, max_length=200)  # python exercises
    duration_ms: int = Field(default=0, ge=0)
    hints_used: int = Field(default=0, ge=0, le=3)


class AttemptOut(BaseModel):
    passed: bool
    feedback: str
    explanation: str | None  # quizzes: shown after answering
    xp_awarded: int
    node_bonus_xp: int
    xp_total: int
    already_passed: bool
    level_before: LevelOut | None
    level_after: LevelOut | None
    quest_position: int | None = None  # which of today's quests this closed, if any
    quest_xp: int = 0  # quest XP + all-done bonus paid by this attempt
    quests_all_done: bool = False
    streak_xp: int = 0
    streak: StreakOut | None = None
