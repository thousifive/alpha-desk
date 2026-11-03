"""Derive node states from content + which exercises have been passed.

Nothing here is stored: state is recomputed from Attempt rows, so there's no cached
"unlocked" flag that can drift out of sync with reality.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.content.schema import BranchDef, ContentBundle, NodeDef

NodeState = Literal["locked", "available", "mastered", "coming_soon"]
MILESTONE_ORDER = ("M1", "M2", "M3", "M4", "M5", "M6")


def branch_playable(branch: BranchDef, current_milestone: str) -> bool:
    return MILESTONE_ORDER.index(branch.playable_from) <= MILESTONE_ORDER.index(current_milestone)


def playable_exercise_slugs(node: NodeDef) -> list[str]:
    return [ex.slug for ex in node.exercises if ex.type in ("sql", "quiz")]


def is_mastered(node: NodeDef, passed: set[str]) -> bool:
    slugs = playable_exercise_slugs(node)
    # A node with nothing playable can't be mastered; otherwise empty nodes would
    # unlock their dependents for free.
    return bool(slugs) and all(s in passed for s in slugs)


@dataclass(frozen=True)
class NodeStatus:
    node: NodeDef
    branch_id: str
    state: NodeState


def node_states(
    bundle: ContentBundle, passed: Iterable[str], current_milestone: str
) -> dict[str, NodeStatus]:
    passed_set = set(passed)
    mastered = {n.slug for ns in bundle.nodes.values() for n in ns if is_mastered(n, passed_set)}
    out: dict[str, NodeStatus] = {}
    for branch in bundle.branches:
        playable = branch_playable(branch, current_milestone)
        for node in bundle.nodes[branch.id]:
            state: NodeState
            if not playable or not playable_exercise_slugs(node):
                state = "coming_soon"
            elif node.slug in mastered:
                state = "mastered"
            elif all(p in mastered for p in node.prerequisites):
                state = "available"
            else:
                state = "locked"
            out[node.slug] = NodeStatus(node=node, branch_id=branch.id, state=state)
    return out
