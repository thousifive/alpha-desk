"""Pydantic models describing the YAML files in /content.

Validation happens once at load time, so a typo in YAML fails loudly at startup (or in
the content tests) rather than as a confusing 500 in the middle of a session.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Persona = Literal["priya", "marcus", "lena"]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]


class _Strict(BaseModel):
    # extra="forbid": unknown keys in YAML are errors, which catches typos like `dificulty:`.
    model_config = ConfigDict(extra="forbid", frozen=True)


class _ExerciseBase(_Strict):
    slug: Slug
    persona: Persona
    title: str
    prompt: str  # markdown, written as a ticket from the persona
    difficulty: Literal[1, 2, 3] = 1


class SqlExercise(_ExerciseBase):
    type: Literal["sql"]
    starter_code: str = ""
    solution_sql: str
    order_sensitive: bool = False  # True when the ticket asks for a specific ORDER BY
    float_tol: float = 1e-6


class QuizExercise(_ExerciseBase):
    type: Literal["quiz"]
    choices: list[str] = Field(min_length=2, max_length=6)
    answer: int  # index into choices
    explanation: str

    @model_validator(mode="after")
    def _answer_in_range(self) -> "QuizExercise":
        if not 0 <= self.answer < len(self.choices):
            raise ValueError(f"answer index {self.answer} out of range for {self.slug}")
        return self


# Packages the browser preloads from the Pyodide distribution. Kept to a closed set so a
# typo fails at load time, and so the backend content check has every one installed too.
PyPackage = Literal["polars", "pydantic", "fastapi", "httpx", "numpy"]


class PythonExercise(_ExerciseBase):
    """Runs in Pyodide. The player's code becomes the `solution` module; tests import from it.

    visible_tests: shown in the UI and run by Run (Cmd+Enter).
    hidden_tests: only fetched at Submit time; the grade is decided by these.
    solution: reference answer, never sent to the browser; content tests prove it passes.
    """

    type: Literal["python"]
    starter_code: str
    visible_tests: str = ""
    hidden_tests: str
    solution: str
    packages: list[PyPackage] = []
    timeout_s: float = Field(default=10, gt=0, le=60)


class PlaceholderExercise(_ExerciseBase):
    """Exercises for branches that become playable in later milestones."""

    type: Literal["review"]


# A discriminated union: Pydantic reads `type` first and validates against exactly one
# model, giving precise error messages instead of "didn't match any of 4 variants".
ExerciseDef = Annotated[
    SqlExercise | QuizExercise | PythonExercise | PlaceholderExercise,
    Field(discriminator="type"),
]


class QuestRules(_Strict):
    count: int = Field(default=3, ge=1, le=6)
    min_minutes: int = Field(ge=1)
    max_minutes: int = Field(ge=1)
    minutes_by_difficulty: dict[int, int]
    min_branches: int = Field(default=2, ge=1)
    xp_per_quest: int = Field(ge=0)
    all_done_bonus: int = Field(ge=0)


class StreakRules(_Strict):
    freeze_every: int = Field(ge=1)  # earn one freeze per this many consecutive days
    max_freezes: int = Field(ge=0)
    milestone_every: int = Field(ge=1)  # pay streak XP at every N days (7, 14, …)
    milestone_xp: int = Field(ge=0)


class QuestsFile(_Strict):
    quests: QuestRules
    streaks: StreakRules

    @model_validator(mode="after")
    def _minutes(self) -> "QuestsFile":
        if self.quests.min_minutes > self.quests.max_minutes:
            raise ValueError("quests.min_minutes must be <= max_minutes")
        if set(self.quests.minutes_by_difficulty) != {1, 2, 3}:
            raise ValueError("quests.minutes_by_difficulty needs keys 1, 2, 3")
        return self


class NodeDef(_Strict):
    slug: Slug
    title: str
    description: str = ""
    order: int
    prerequisites: list[Slug] = []
    xp_reward: int = 0  # bonus awarded once when the node is mastered
    is_boss: bool = False
    exercises: list[ExerciseDef] = []


class BossDef(_Strict):
    title: str
    description: str


class BranchDef(_Strict):
    id: Slug
    title: str
    description: str
    order: int
    playable_from: str  # milestone label, e.g. "M1"
    # Fought in list order once the branch is mastered. A list (not one boss) because
    # Agents & LLMs ends in two: the MCP server, then the LangGraph agent built on it.
    bosses: list[BossDef] = []


class LevelDef(_Strict):
    title: str
    min_xp: int = Field(ge=0)


class XpRules(_Strict):
    base_by_difficulty: dict[int, int]
    first_try_bonus: float = Field(ge=0)
    hint_penalty: list[float]  # fraction of XP removed for 0, 1, 2, 3 hints used


class LevelsFile(_Strict):
    levels: list[LevelDef]
    xp: XpRules

    @model_validator(mode="after")
    def _ascending(self) -> "LevelsFile":
        mins = [lv.min_xp for lv in self.levels]
        if mins[0] != 0 or mins != sorted(mins) or len(set(mins)) != len(mins):
            raise ValueError("levels must start at 0 XP and strictly increase")
        return self


class BranchesFile(_Strict):
    branches: list[BranchDef]


class ContentBundle(_Strict):
    """Everything under /content, validated and cross-checked."""

    levels: LevelsFile
    quests: QuestsFile
    branches: list[BranchDef]
    nodes: dict[str, list[NodeDef]]  # branch id → nodes ordered by `order`
