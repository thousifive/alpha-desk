from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.auth import AuthRequired
from app.content.schema import (
    BranchDef,
    ContentBundle,
    ExerciseDef,
    NodeDef,
    PythonExercise,
    QuizExercise,
    SqlExercise,
)
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.daily import (
    active_days,
    award_streak_milestone,
    complete_quest_item,
    streak_out,
    streak_state,
)
from app.game.service import award_xp, get_user, level_out, local_today, passed_slugs
from app.game.unlocks import is_mastered, node_states
from app.game.xp import xp_for_attempt
from app.grading.python import ReportedTest, declared_test_names, grade_python_report
from app.grading.sql import ResultSet, compare_result_sets, expected_result
from app.models import Attempt
from app.schemas import AttemptIn, AttemptOut, ExerciseOut, HiddenTestsOut

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
        starter_code=ex.starter_code if isinstance(ex, SqlExercise | PythonExercise) else "",
        choices=list(ex.choices) if isinstance(ex, QuizExercise) else [],
        branch_id=loc.branch.id,
        node_slug=loc.node.slug,
        node_title=loc.node.title,
        node_state=state,
        passed=ex.slug in passed,
        next_slug=siblings[loc.index + 1].slug if loc.index + 1 < len(siblings) else None,
        visible_tests=ex.visible_tests if isinstance(ex, PythonExercise) else "",
        packages=list(ex.packages) if isinstance(ex, PythonExercise) else [],
        timeout_s=ex.timeout_s if isinstance(ex, PythonExercise) else 10,
    )


async def _require_open(
    loc: _Located, session: SessionDep, content: ContentBundle, milestone: str
) -> set[str]:
    passed = await passed_slugs(session)
    state = node_states(content, passed, milestone)[loc.node.slug].state
    if state in ("locked", "coming_soon"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Node is {state}")
    return passed


# POST, not GET: it's fetched only when the player hits Submit, and a POST isn't prefetched,
# cached by the browser, or casually opened in a tab. It hides the tests from the exercise
# payload, not from a determined player; see app/grading/python.py for the trust model.
@router.post("/{slug}/test-bundle", response_model=HiddenTestsOut)
async def get_test_bundle(
    slug: str, _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> HiddenTestsOut:
    loc = _locate(content, slug)
    if not isinstance(loc.exercise, PythonExercise):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No tests for this exercise")
    await _require_open(loc, session, content, settings.current_milestone)
    return HiddenTestsOut(hidden_tests=loc.exercise.hidden_tests)


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
    passed_before = await _require_open(loc, session, content, settings.current_milestone)

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
        case PythonExercise():
            if body.tests is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Missing tests")
            try:
                grade = grade_python_report(
                    declared_test_names(ex.hidden_tests),
                    [ReportedTest(name=t.name, passed=t.passed) for t in body.tests],
                )
            except NotImplementedError as e:
                raise _todo_501(e) from e
            passed = grade.passed
            feedback = "All hidden tests pass. Ship it." if passed else grade.reason
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
    today = local_today(user)
    level_before = level_out(user.xp_total, content)
    # Ledger keys make each payout idempotent even if two submits race past already_passed.
    if not await award_xp(
        session, user, source="attempt", ref_key=f"attempt:{slug}", amount=xp, day=today
    ):
        xp = 0
    if not await award_xp(
        session, user, source="node", ref_key=f"node:{loc.node.slug}", amount=node_bonus, day=today
    ):
        node_bonus = 0
    session.add(
        Attempt(
            exercise_slug=slug,
            code=body.code,
            passed=passed,
            hints_used=body.hints_used,
            duration_ms=body.duration_ms,
            xp_awarded=xp + node_bonus,
            local_date=today,
        )
    )

    quest = None
    streak = None
    streak_xp = 0
    if passed:
        quest = await complete_quest_item(session, user, content, slug, today)
        # Today counts as active from this attempt on (it isn't flushed to the DB yet).
        state = streak_state(await active_days(session) | {today}, today, content)
        streak_xp = await award_streak_milestone(session, user, state, content, today)
        streak = streak_out(state, content)
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
        quest_position=quest.completed_position if quest else None,
        quest_xp=quest.xp if quest else 0,
        quests_all_done=quest.all_done if quest else False,
        streak_xp=streak_xp,
        streak=streak,
    )
