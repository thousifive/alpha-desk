"""Grade an attempt and decide which events it produces, from the event log alone.

This is the offline twin of POST /api/exercises/{slug}/attempts: same rules, same order, same
idempotency keys, but it returns events to append instead of writing tables. The browser runs
it in Pyodide; nothing here touches a database or the network.

Any open TODO(me) it depends on raises NotImplementedError, exactly like the server route,
so a locked feature blocks the submit instead of silently paying 0 XP.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from app.content.schema import ContentBundle, PythonExercise, QuizExercise, SqlExercise
from app.events.schema import (
    AnyEvent,
    AttemptEvent,
    AttemptPayload,
    QuestCompletedEvent,
    QuestCompletedPayload,
    XpAwardedEvent,
    XpAwardedPayload,
    XpSource,
)
from app.game.projection import Derived
from app.game.streaks import streak_milestone
from app.game.unlocks import is_mastered, node_states
from app.game.xp import xp_for_attempt
from app.grading.python import ReportedTest, declared_test_names, grade_python_report
from app.grading.sql import ResultSet, compare_result_sets
from app.schemas import AttemptIn, AttemptOut
from app.views import level_out, locate, streak_out, streak_state


class SubmitRejected(Exception):
    """The attempt can't be graded (unknown exercise, locked node, missing answer)."""


@dataclass(frozen=True)
class Verdict:
    passed: bool
    feedback: str
    explanation: str | None = None


def grade(
    content: ContentBundle, slug: str, body: AttemptIn, expected: ResultSet | None
) -> Verdict:
    """Pass/fail for one attempt. For SQL, `expected` is the solution's result set, computed by
    the caller (in the browser: the same DuckDB-WASM engine that ran the player's query)."""
    loc = locate(content, slug)
    if loc is None:
        raise SubmitRejected("Unknown exercise")
    match loc.exercise:
        case SqlExercise() as ex:
            if body.result is None or expected is None:
                raise SubmitRejected("Missing result")
            actual = ResultSet(columns=body.result.columns, rows=body.result.rows)
            cmp = compare_result_sets(
                actual, expected, order_sensitive=ex.order_sensitive, float_tol=ex.float_tol
            )
            return Verdict(
                cmp.passed, "Every row matches. Nice work." if cmp.passed else cmp.reason
            )
        case QuizExercise() as ex:
            if body.choice is None:
                raise SubmitRejected("Missing choice")
            ok = body.choice == ex.answer
            return Verdict(ok, "Correct." if ok else "Not quite.", ex.explanation)
        case PythonExercise() as ex:
            if body.tests is None:
                raise SubmitRejected("Missing tests")
            g = grade_python_report(
                declared_test_names(ex.hidden_tests),
                [ReportedTest(name=t.name, passed=t.passed) for t in body.tests],
            )
            return Verdict(g.passed, "All hidden tests pass. Ship it." if g.passed else g.reason)
        case _:
            raise SubmitRejected("Exercise type not playable yet")


@dataclass(frozen=True)
class Context:
    """Where and when the attempt happens. Supplied by the device, never by the server."""

    device_id: str
    now: datetime  # timezone-aware
    today: date  # player-local calendar day at `now`
    milestone: str


@dataclass(frozen=True)
class Decision:
    events: list[AnyEvent]
    out: AttemptOut


def decide(
    content: ContentBundle,
    derived: Derived,
    slug: str,
    body: AttemptIn,
    verdict: Verdict,
    ctx: Context,
    quest_plan: Sequence[tuple[int, str]] | None = None,
) -> Decision:
    """The events one graded attempt produces, and the response the UI shows.

    quest_plan: today's (position, slug) items if the device has them cached, else None.
    """
    loc = locate(content, slug)
    if loc is None:
        raise SubmitRejected("Unknown exercise")
    states = node_states(content, derived.passed, ctx.milestone)
    if states[loc.node.slug].state in ("locked", "coming_soon"):
        raise SubmitRejected(f"Node is {states[loc.node.slug].state}")

    ex = loc.exercise
    first_try = derived.attempts.get(slug, (0, 0))[1] == 0
    already_passed = slug in derived.passed
    passed = verdict.passed

    xp = 0
    node_bonus = 0
    if passed and not already_passed:
        xp = xp_for_attempt(
            ex.difficulty, first_try=first_try, hints_used=body.hints_used, rules=content.levels.xp
        )
        if is_mastered(loc.node, derived.passed | {slug}) and not is_mastered(
            loc.node, derived.passed
        ):
            node_bonus = loc.node.xp_reward

    events: list[AnyEvent] = []
    paid = set(derived.paid_keys)  # a local copy: keys paid earlier in *this* submit count too

    def envelope() -> dict[str, object]:
        # uuid4 is random (122 bits), so ids from different devices never collide in practice.
        return {
            "id": uuid.uuid4(),
            "device_id": ctx.device_id,
            "created_at": ctx.now,
            "local_date": ctx.today,
        }

    def pay(source: XpSource, key: str, amount: int) -> int:
        # Same idempotency rule as the server ledger: a key is paid at most once, ever.
        if amount <= 0 or key in paid:
            return 0
        paid.add(key)
        events.append(
            XpAwardedEvent(
                type="xp_awarded",
                payload=XpAwardedPayload(ref_key=key, source=source, amount=amount),
                **envelope(),
            )
        )
        return amount

    events.append(
        AttemptEvent(
            type="attempt",
            payload=AttemptPayload(
                exercise_slug=slug,
                passed=passed,
                hints_used=body.hints_used,
                duration_ms=body.duration_ms,
                code=body.code,
            ),
            **envelope(),
        )
    )
    level_before = level_out(derived.xp_total, content)
    xp = pay("attempt", f"attempt:{slug}", xp)
    node_bonus = pay("node", f"node:{loc.node.slug}", node_bonus)

    quest_position: int | None = None
    quest_xp = 0
    all_done = False
    streak = None
    streak_xp = 0
    if passed:
        if quest_plan is not None:
            done = {pos for day, pos in derived.quests_done if day == ctx.today}
            item = next((p for p, s in sorted(quest_plan) if s == slug and p not in done), None)
            if item is not None:
                quest_position = item
                events.append(
                    QuestCompletedEvent(
                        type="quest_completed",
                        payload=QuestCompletedPayload(
                            day=ctx.today, position=item, exercise_slug=slug
                        ),
                        **envelope(),
                    )
                )
                rules = content.quests.quests
                day = ctx.today.isoformat()
                quest_xp += pay("quest", f"quest:{day}:{item}", rules.xp_per_quest)
                all_done = {p for p, _ in quest_plan} <= done | {item}
                if all_done:
                    quest_xp += pay("quest_bonus", f"quests_done:{day}", rules.all_done_bonus)

        # Today counts as active from this attempt on.
        state = streak_state(derived.active_days | {ctx.today}, ctx.today, content)
        if state is not None and state.run_start is not None:
            n = streak_milestone(state, content.quests.streaks)
            if n is not None:
                key = f"streak:{state.run_start.isoformat()}:{n}"
                streak_xp = pay("streak", key, content.quests.streaks.milestone_xp)
        streak = streak_out(state, content)

    total = derived.xp_total + xp + node_bonus + quest_xp + streak_xp
    return Decision(
        events=events,
        out=AttemptOut(
            passed=passed,
            feedback=verdict.feedback,
            explanation=verdict.explanation,
            xp_awarded=xp,
            node_bonus_xp=node_bonus,
            xp_total=total,
            already_passed=already_passed,
            level_before=level_before,
            level_after=level_out(total, content),
            quest_position=quest_position,
            quest_xp=quest_xp,
            quests_all_done=all_done,
            streak_xp=streak_xp,
            streak=streak,
        ),
    )
