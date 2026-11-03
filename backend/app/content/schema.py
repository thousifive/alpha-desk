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


class PlaceholderExercise(_ExerciseBase):
    """Exercises for branches that become playable in later milestones (Pyodide in M2, …)."""

    type: Literal["python", "polars", "review"]


# A discriminated union: Pydantic reads `type` first and validates against exactly one
# model, giving precise error messages instead of "didn't match any of 3 variants".
ExerciseDef = Annotated[
    SqlExercise | QuizExercise | PlaceholderExercise, Field(discriminator="type")
]


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
    boss: BossDef | None = None


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
    branches: list[BranchDef]
    nodes: dict[str, list[NodeDef]]  # branch id → nodes ordered by `order`
