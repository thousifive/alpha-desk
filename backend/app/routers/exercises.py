from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.auth import AuthRequired
from app.content.schema import (
    BranchDef,
    ContentBundle,
    ExerciseDef,
    NodeDef,
    QuizExercise,
    SqlExercise,
)
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.service import get_user, level_out, passed_slugs
from app.game.unlocks import is_mastered, node_states
from app.game.xp import xp_for_attempt
from app.grading.sql import ResultSet, compare_result_sets, expected_result
from app.models import Attempt
from app.schemas import AttemptIn, AttemptOut, ExerciseOut

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


@dataclass(frozen=True)
class _Located:
    branch: BranchDef
    node: NodeDef
    exercise: ExerciseDef
    index: int


def _locate(content: ContentBundle, slug: str) -> _Located:
    for branch in content.branches:
        for node in content.nodes[branch.id]:
            for i, ex in enumerate(node.exercises):
                if ex.slug == slug:
                    return _Located(branch, node, ex, i)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown exercise")


def _todo_501(err: NotImplementedError) -> HTTPException:
    # Surfaced in the UI so it's obvious *which* TODO(me) blocks submitting.
    return HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"Grader offline: {err}")


@router.get("/{slug}", response_model=ExerciseOut)
async def get_exercise(
    slug: str, _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> ExerciseOut:
    loc = _locate(content, slug)
    passed = await passed_slugs(session)
    state = node_states(content, passed, settings.current_milestone)[loc.node.slug].state
    ex = loc.exercise
    siblings = loc.node.exercises
    return ExerciseOut(
        slug=ex.slug,
        title=ex.title,
        type=ex.type,
        persona=ex.persona,
        difficulty=ex.difficulty,
        prompt_md=ex.prompt,
        starter_code=ex.starter_code if isinstance(ex, SqlExercise) else "",
        choices=list(ex.choices) if isinstance(ex, QuizExercise) else [],
        branch_id=loc.branch.id,
        node_slug=loc.node.slug,
        node_title=loc.node.title,
        node_state=state,
        passed=ex.slug in passed,
        next_slug=siblings[loc.index + 1].slug if loc.index + 1 < len(siblings) else None,
    )


@router.post("/{slug}/attempts", response_model=AttemptOut)
async def submit_attempt(
    slug: str,
    body: AttemptIn,
    _: AuthRequired,
    session: SessionDep,
    content: ContentDep,
    settings: SettingsDep,
) -> AttemptOut:
    loc = _locate(content, slug)
    ex = loc.exercise
    passed_before = await passed_slugs(session)
    state = node_states(content, passed_before, settings.current_milestone)[loc.node.slug].state
    if state in ("locked", "coming_soon"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Node is {state}")

    prior = (await session.exec(select(Attempt).where(Attempt.exercise_slug == slug))).all()
    first_try = len(prior) == 0
    already_passed = slug in passed_before

    explanation: str | None = None
    match ex:
        case SqlExercise():
            if body.result is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Missing result")
            expected = await expected_result(settings.dataset_dir, ex.solution_sql)
            actual = ResultSet(columns=body.result.columns, rows=body.result.rows)
            try:
                cmp = compare_result_sets(
                    actual, expected, order_sensitive=ex.order_sensitive, float_tol=ex.float_tol
                )
            except NotImplementedError as e:
                raise _todo_501(e) from e
            passed = cmp.passed
            feedback = "Every row matches. Nice work." if passed else cmp.reason
        case QuizExercise():
            if body.choice is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Missing choice")
            passed = body.choice == ex.answer
            feedback = "Correct." if passed else "Not quite."
            explanation = ex.explanation
        case _:
            raise HTTPException(status.HTTP_409_CONFLICT, "Exercise type not playable yet")

    xp = 0
    node_bonus = 0
    if passed and not already_passed:
        try:
            xp = xp_for_attempt(
                ex.difficulty,
                first_try=first_try,
                hints_used=body.hints_used,
                rules=content.levels.xp,
            )
        except NotImplementedError as e:
            raise _todo_501(e) from e
        if is_mastered(loc.node, passed_before | {slug}) and not is_mastered(
            loc.node, passed_before
        ):
            node_bonus = loc.node.xp_reward

    user = await get_user(session)
    level_before = level_out(user.xp_total, content)
    user.xp_total += xp + node_bonus
    session.add(user)
    session.add(
        Attempt(
            exercise_slug=slug,
            code=body.code,
            passed=passed,
            hints_used=body.hints_used,
            duration_ms=body.duration_ms,
            xp_awarded=xp + node_bonus,
        )
    )
    await session.commit()

    return AttemptOut(
        passed=passed,
        feedback=feedback,
        explanation=explanation,
        xp_awarded=xp,
        node_bonus_xp=node_bonus,
        xp_total=user.xp_total,
        already_passed=already_passed,
        level_before=level_before,
        level_after=level_out(user.xp_total, content),
    )
