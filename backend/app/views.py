"""Build every progress-shaped API response from plain facts (passed exercises, XP, active days).

Both sides call these: the FastAPI routers (facts from the database) and the browser's rules
worker (facts from the local event log via app.game.projection). One builder per screen keeps
the boss card, skill tree, and node grid identical online and offline.

Pyodide-safe: imports only pydantic-based modules and pure game rules, never the database.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

from app.content.schema import (
    BranchDef,
    ContentBundle,
    ExerciseDef,
    NodeDef,
    PythonExercise,
    QuizExercise,
    SqlExercise,
)
from app.game.levels import level_info
from app.game.streaks import StreakState, compute_streak
from app.game.unlocks import (
    PLAYABLE_TYPES,
    NodeStatus,
    branch_playable,
    node_states,
    playable_exercise_slugs,
)
from app.schemas import (
    BossOut,
    BranchCounts,
    BranchDetail,
    BranchSummary,
    ExerciseOut,
    ExerciseSummary,
    LevelOut,
    NextBossOut,
    NodeOut,
    ProgressOut,
    QuestItemOut,
    QuestOut,
    StreakOut,
)

# ---- lookup ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Located:
    branch: BranchDef
    node: NodeDef
    exercise: ExerciseDef
    index: int  # position within the node


def locate(content: ContentBundle, slug: str) -> Located | None:
    for branch in content.branches:
        for node in content.nodes[branch.id]:
            for i, ex in enumerate(node.exercises):
                if ex.slug == slug:
                    return Located(branch, node, ex, i)
    return None


# ---- level and streak (None while their TODO(me) is open) -----------------------------


def level_out(xp: int, content: ContentBundle) -> LevelOut | None:
    try:
        info = level_info(xp, content.levels.levels)
    except NotImplementedError:
        return None  # TODO(me) #1 not done yet: the UI shows a locked panel
    return LevelOut(
        index=info.index,
        title=info.title,
        min_xp=info.min_xp,
        next_title=info.next_title,
        next_min_xp=info.next_min_xp,
    )


def streak_state(days: Iterable[date], today: date, content: ContentBundle) -> StreakState | None:
    try:
        return compute_streak(days, today, content.quests.streaks)
    except NotImplementedError:
        return None  # TODO(me) M2-1 not done yet: the UI shows a locked panel


def streak_out(state: StreakState | None, content: ContentBundle) -> StreakOut | None:
    if state is None:
        return None
    every = content.quests.streaks.milestone_every
    return StreakOut(
        current=state.current,
        best=state.best,
        freezes=state.freezes,
        max_freezes=content.quests.streaks.max_freezes,
        active_today=state.active_today,
        # Next multiple of `every` strictly above current (7 → 14, 0 → 7).
        next_milestone=(state.current // every + 1) * every,
    )


# ---- bosses and counts ----------------------------------------------------------------


def bosses_out(content: ContentBundle, branch_id: str) -> list[BossOut]:
    branch = next(b for b in content.branches if b.id == branch_id)
    # enumerate(xs, start=1) yields (1, x0), (2, x1), …: 1-based stage numbers for the UI.
    return [
        BossOut(
            branch_id=branch.id,
            branch_title=branch.title,
            title=boss.title,
            description=boss.description,
            stage=i,
            stages=len(branch.bosses),
        )
        for i, boss in enumerate(branch.bosses, start=1)
    ]


def branch_counts(
    content: ContentBundle, branch_id: str, states: dict[str, NodeStatus], passed: set[str]
) -> BranchCounts:
    nodes = content.nodes[branch_id]
    ex_slugs = [s for n in nodes for s in playable_exercise_slugs(n)]
    return BranchCounts(
        n_nodes=len(nodes),
        n_mastered=sum(states[n.slug].state == "mastered" for n in nodes),
        n_exercises=len(ex_slugs),
        n_passed=sum(s in passed for s in ex_slugs),
    )


def next_boss(
    content: ContentBundle, states: dict[str, NodeStatus], passed: set[str], milestone: str
) -> NextBossOut | None:
    """The first boss of the first playable branch that isn't fully mastered yet, with that
    branch's own counts (not totals across branches). Boss fights land in M5, so until then
    "next" is always a branch's first boss."""
    for branch in sorted(content.branches, key=lambda b: b.order):
        if not branch_playable(branch, milestone) or not branch.bosses:
            continue
        if any(states[n.slug].state != "mastered" for n in content.nodes[branch.id]):
            first = bosses_out(content, branch.id)[0]
            counts = branch_counts(content, branch.id, states, passed)
            return NextBossOut(**first.model_dump(), **counts.model_dump())
    return None


# ---- screens --------------------------------------------------------------------------


def progress_view(
    content: ContentBundle,
    *,
    passed: set[str],
    xp_total: int,
    active_days: Iterable[date],
    today: date,
    milestone: str,
) -> ProgressOut:
    states = node_states(content, passed, milestone)
    playable = {
        s
        for st in states.values()
        if st.state != "coming_soon"
        for s in playable_exercise_slugs(st.node)
    }
    return ProgressOut(
        xp_total=xp_total,
        level=level_out(xp_total, content),
        streak=streak_out(streak_state(active_days, today, content), content),
        passed_exercises=len(passed & playable),
        playable_exercises=len(playable),
        mastered_nodes=sum(st.state == "mastered" for st in states.values()),
        next_boss=next_boss(content, states, passed, milestone),
    )


def _summary(
    content: ContentBundle,
    branch: BranchDef,
    states: dict[str, NodeStatus],
    passed: set[str],
    milestone: str,
) -> BranchSummary:
    return BranchSummary(
        id=branch.id,
        title=branch.title,
        description=branch.description,
        order=branch.order,
        playable=branch_playable(branch, milestone),
        playable_from=branch.playable_from,
        bosses=bosses_out(content, branch.id),
        **branch_counts(content, branch.id, states, passed).model_dump(),
    )


def branch_summaries(
    content: ContentBundle, passed: set[str], milestone: str
) -> list[BranchSummary]:
    states = node_states(content, passed, milestone)
    return [
        _summary(content, b, states, passed, milestone)
        for b in sorted(content.branches, key=lambda b: b.order)
    ]


def branch_detail(
    content: ContentBundle, branch_id: str, passed: set[str], milestone: str
) -> BranchDetail | None:
    branch = next((b for b in content.branches if b.id == branch_id), None)
    if branch is None:
        return None
    states = node_states(content, passed, milestone)
    nodes = [
        NodeOut(
            slug=n.slug,
            title=n.title,
            description=n.description,
            order=n.order,
            prerequisites=list(n.prerequisites),
            xp_reward=n.xp_reward,
            state=states[n.slug].state,
            n_exercises=len(playable_exercise_slugs(n)),
            n_passed=sum(s in passed for s in playable_exercise_slugs(n)),
            exercises=[
                ExerciseSummary(
                    slug=ex.slug,
                    title=ex.title,
                    type=ex.type,
                    persona=ex.persona,
                    difficulty=ex.difficulty,
                    passed=ex.slug in passed,
                    playable=ex.type in PLAYABLE_TYPES,
                )
                for ex in n.exercises
            ],
        )
        for n in content.nodes[branch.id]
    ]
    summary = _summary(content, branch, states, passed, milestone)
    # model_dump() → dict, then ** unpacks it as keyword args: "copy every summary field".
    return BranchDetail(**summary.model_dump(), nodes=nodes)


def exercise_view(
    content: ContentBundle, slug: str, passed: set[str], milestone: str
) -> ExerciseOut | None:
    loc = locate(content, slug)
    if loc is None:
        return None
    state = node_states(content, passed, milestone)[loc.node.slug].state
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


def quest_view(
    content: ContentBundle,
    day: date,
    items: Sequence[tuple[int, str]],
    completed: set[int],
) -> QuestOut:
    """items: (position, exercise slug) for the day's plan; completed: positions done."""
    rules = content.quests.quests
    out: list[QuestItemOut] = []
    for position, slug in sorted(items):
        loc = locate(content, slug)
        if loc is None:
            continue  # exercise removed from content since the plan was made
        ex = loc.exercise
        out.append(
            QuestItemOut(
                position=position,
                slug=ex.slug,
                title=ex.title,
                type=ex.type,
                persona=ex.persona,
                difficulty=ex.difficulty,
                branch_id=loc.branch.id,
                branch_title=loc.branch.title,
                node_title=loc.node.title,
                minutes=rules.minutes_by_difficulty[ex.difficulty],
                completed=position in completed,
            )
        )
    return QuestOut(
        day=day,
        items=out,
        xp_per_quest=rules.xp_per_quest,
        all_done_bonus=rules.all_done_bonus,
        done=bool(out) and all(i.completed for i in out),
        est_minutes=sum(i.minutes for i in out),
    )
