import shutil
from pathlib import Path

import pytest
import yaml
from sqlmodel import func, select

from app.config import REPO_ROOT
from app.content.loader import ContentError, load_content, sync_content
from app.db import get_sessionmaker
from app.models import Exercise, SkillNode, User

CONTENT = REPO_ROOT / "content"


def test_real_content_loads() -> None:
    bundle = load_content(CONTENT)
    assert bundle.branches[0].id == "sql-olap"
    assert set(bundle.nodes) == {b.id for b in bundle.branches}


@pytest.fixture
def content_copy(tmp_path: Path) -> Path:
    dst = tmp_path / "content"
    shutil.copytree(CONTENT, dst)
    return dst


def _first_node_file(content: Path) -> Path:
    return sorted((content / "nodes" / "buy-side-finance").glob("*.yaml"))[0]


def _edit(path: Path, **changes: object) -> None:
    data = yaml.safe_load(path.read_text())
    data.update(changes)
    path.write_text(yaml.safe_dump(data))


def test_unknown_yaml_key_rejected(content_copy: Path) -> None:
    _edit(_first_node_file(content_copy), dificulty=2)
    with pytest.raises(ContentError, match="dificulty"):
        load_content(content_copy)


def test_unknown_prerequisite_rejected(content_copy: Path) -> None:
    _edit(_first_node_file(content_copy), prerequisites=["does-not-exist"])
    with pytest.raises(ContentError, match="unknown prerequisites"):
        load_content(content_copy)


def test_prerequisite_cycle_rejected(content_copy: Path) -> None:
    files = sorted((content_copy / "nodes" / "buy-side-finance").glob("*.yaml"))
    _edit(files[0], prerequisites=[yaml.safe_load(files[1].read_text())["slug"]])
    with pytest.raises(ContentError, match="cycle"):
        load_content(content_copy)


def test_duplicate_exercise_slug_rejected(content_copy: Path) -> None:
    files = sorted((content_copy / "nodes" / "buy-side-finance").glob("*.yaml"))
    donor = yaml.safe_load(files[1].read_text())["exercises"][0]
    _edit(files[0], exercises=[donor])
    with pytest.raises(ContentError, match="duplicate exercise slug"):
        load_content(content_copy)


def test_quiz_answer_out_of_range_rejected(content_copy: Path) -> None:
    f = sorted((content_copy / "nodes" / "buy-side-finance").glob("*.yaml"))[1]
    data = yaml.safe_load(f.read_text())
    data["exercises"][0]["answer"] = 9
    f.write_text(yaml.safe_dump(data))
    with pytest.raises(ContentError, match="out of range"):
        load_content(content_copy)


async def test_sync_is_idempotent_and_hides_nothing_public() -> None:
    bundle = load_content(CONTENT)
    async with get_sessionmaker()() as s:
        first = await sync_content(s, bundle)
        second = await sync_content(s, bundle)
        assert first == second
        n_nodes = (await s.exec(select(func.count()).select_from(SkillNode))).one()
        n_ex = (await s.exec(select(func.count()).select_from(Exercise))).one()
        assert (n_nodes, n_ex) == (first["nodes"], first["exercises"])
        assert await s.get(User, 1) is not None
        quiz = await s.get(Exercise, "quiz-gross-vs-net")
        assert quiz is not None and quiz.choices and "answer" in quiz.spec
