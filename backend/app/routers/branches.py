from fastapi import APIRouter, HTTPException, status

from app.auth import AuthRequired
from app.content.schema import BranchDef, ContentBundle
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.service import bosses_out, branch_counts, passed_slugs
from app.game.unlocks import (
    PLAYABLE_TYPES,
    NodeStatus,
    branch_playable,
    node_states,
    playable_exercise_slugs,
)
from app.schemas import BranchDetail, BranchSummary, ExerciseSummary, NodeOut

router = APIRouter(prefix="/api/branches", tags=["branches"])


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


@router.get("", response_model=list[BranchSummary])
async def list_branches(
    _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> list[BranchSummary]:
    passed = await passed_slugs(session)
    states = node_states(content, passed, settings.current_milestone)
    return [
        _summary(content, b, states, passed, settings.current_milestone)
        for b in sorted(content.branches, key=lambda b: b.order)
    ]


@router.get("/{branch_id}", response_model=BranchDetail)
async def get_branch(
    branch_id: str,
    _: AuthRequired,
    session: SessionDep,
    content: ContentDep,
    settings: SettingsDep,
) -> BranchDetail:
    branch = next((b for b in content.branches if b.id == branch_id), None)
    if branch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown branch")
    passed = await passed_slugs(session)
    states = node_states(content, passed, settings.current_milestone)
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
    summary = _summary(content, branch, states, passed, settings.current_milestone)
    # model_dump() → dict, then ** unpacks it as keyword args: "copy every summary field".
    return BranchDetail(**summary.model_dump(), nodes=nodes)
