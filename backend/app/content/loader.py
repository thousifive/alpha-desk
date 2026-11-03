"""Load /content YAML into validated models and upsert it into the database."""

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import get_settings
from app.content.schema import (
    BranchesFile,
    ContentBundle,
    LevelsFile,
    NodeDef,
    PlaceholderExercise,
    QuizExercise,
    SqlExercise,
)
from app.models import Exercise, SkillNode, User

log = logging.getLogger(__name__)


class ContentError(ValueError):
    pass


def _read_yaml(path: Path) -> object:
    # safe_load only builds plain dicts/lists/scalars. yaml.load can construct arbitrary
    # Python objects from tags, which is a code-execution risk with untrusted files.
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_content(content_dir: Path) -> ContentBundle:
    levels = LevelsFile.model_validate(_read_yaml(content_dir / "levels.yaml"))
    branches = BranchesFile.model_validate(_read_yaml(content_dir / "branches.yaml")).branches

    nodes: dict[str, list[NodeDef]] = {}
    for branch in branches:
        branch_dir = content_dir / "nodes" / branch.id
        files = sorted(branch_dir.glob("*.yaml")) if branch_dir.exists() else []
        try:
            parsed = [NodeDef.model_validate(_read_yaml(f)) for f in files]
        except ValueError as e:  # pydantic.ValidationError subclasses ValueError
            raise ContentError(f"invalid node file in {branch_dir}: {e}") from e
        nodes[branch.id] = sorted(parsed, key=lambda n: n.order)

    bundle = ContentBundle(levels=levels, branches=branches, nodes=nodes)
    _cross_validate(bundle)
    return bundle


def _cross_validate(bundle: ContentBundle) -> None:
    """Checks that span files and that Pydantic can't express per-model."""
    node_slugs: set[str] = set()
    ex_slugs: set[str] = set()
    for branch_nodes in bundle.nodes.values():
        for node in branch_nodes:
            if node.slug in node_slugs:
                raise ContentError(f"duplicate node slug: {node.slug}")
            node_slugs.add(node.slug)
            for ex in node.exercises:
                if ex.slug in ex_slugs:
                    raise ContentError(f"duplicate exercise slug: {ex.slug}")
                ex_slugs.add(ex.slug)
    for branch_nodes in bundle.nodes.values():
        for node in branch_nodes:
            missing = set(node.prerequisites) - node_slugs
            if missing:
                raise ContentError(f"{node.slug}: unknown prerequisites {sorted(missing)}")
    _check_acyclic(bundle)


def _check_acyclic(bundle: ContentBundle) -> None:
    graph = {n.slug: n.prerequisites for ns in bundle.nodes.values() for n in ns}
    done: set[str] = set()
    visiting: set[str] = set()

    def visit(slug: str, path: list[str]) -> None:
        if slug in done:
            return
        if slug in visiting:
            raise ContentError(f"prerequisite cycle: {' -> '.join([*path, slug])}")
        visiting.add(slug)
        for pre in graph[slug]:
            visit(pre, [*path, slug])
        visiting.discard(slug)
        done.add(slug)

    for slug in graph:
        visit(slug, [])


def _exercise_row(
    node_slug: str, order: int, ex: SqlExercise | QuizExercise | PlaceholderExercise
) -> Exercise:
    # `match` with class patterns narrows the union type per branch (like a TS switch on a tag).
    match ex:
        case SqlExercise():
            spec = {
                "solution_sql": ex.solution_sql,
                "order_sensitive": ex.order_sensitive,
                "float_tol": ex.float_tol,
            }
            starter, choices, playable = ex.starter_code, [], True
        case QuizExercise():
            spec = {"answer": ex.answer, "explanation": ex.explanation}
            starter, choices, playable = "", list(ex.choices), True
        case _:
            spec, starter, choices, playable = {}, "", [], False
    return Exercise(
        slug=ex.slug,
        node_slug=node_slug,
        order=order,
        type=ex.type,
        persona=ex.persona,
        title=ex.title,
        prompt_md=ex.prompt,
        starter_code=starter,
        difficulty=ex.difficulty,
        playable=playable,
        choices=choices,
        spec=spec,
    )


async def sync_content(session: AsyncSession, bundle: ContentBundle) -> dict[str, int]:
    """Upsert nodes and exercises by slug. Rows removed from YAML are left in place (attempts
    may reference them) and logged, so content edits never destroy progress history."""
    seen_nodes: set[str] = set()
    seen_ex: set[str] = set()
    for branch in bundle.branches:
        for node in bundle.nodes[branch.id]:
            seen_nodes.add(node.slug)
            # session.merge = "INSERT or UPDATE by primary key", the ORM-level upsert.
            await session.merge(
                SkillNode(
                    slug=node.slug,
                    branch=branch.id,
                    title=node.title,
                    description=node.description,
                    order=node.order,
                    prerequisites=list(node.prerequisites),
                    xp_reward=node.xp_reward,
                    is_boss=node.is_boss,
                )
            )
            for i, ex in enumerate(node.exercises):
                seen_ex.add(ex.slug)
                await session.merge(_exercise_row(node.slug, i, ex))

    stale = set((await session.exec(select(Exercise.slug))).all()) - seen_ex
    if stale:
        log.warning("exercises in DB but not in content (kept): %s", sorted(stale))

    if (await session.get(User, 1)) is None:
        session.add(User(id=1))  # single-user app: the one player row
    await session.commit()
    return {"nodes": len(seen_nodes), "exercises": len(seen_ex)}


# Cached so every request shares one parsed bundle. Restart (or cache_clear) to pick up
# YAML edits; uvicorn --reload restarts on .py changes only, so run `make sync-content`.
@lru_cache
def get_content() -> ContentBundle:
    return load_content(get_settings().content_dir)
