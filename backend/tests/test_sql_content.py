"""Every SQL exercise's solution must run against the real dataset and give a usable answer."""

import pytest

from app.config import get_settings
from app.content.loader import load_content
from app.content.schema import SqlExercise
from app.grading.dataset import MAX_RESULT_ROWS, open_dataset

BUNDLE = load_content(get_settings().content_dir)
SQL_EXERCISES = [
    ex
    for nodes in BUNDLE.nodes.values()
    for n in nodes
    for ex in n.exercises
    if isinstance(ex, SqlExercise)
]


def test_sql_branch_meets_m1_scope() -> None:
    sql_nodes = BUNDLE.nodes["sql-olap"]
    assert len(sql_nodes) >= 8
    assert len(SQL_EXERCISES) >= 15  # M1 definition of done


@pytest.fixture(scope="module")
def con():  # type: ignore[no-untyped-def]
    c = open_dataset(get_settings().dataset_dir)
    yield c
    c.close()


@pytest.mark.parametrize("ex", SQL_EXERCISES, ids=lambda e: e.slug)
def test_solution_runs_and_returns_rows(ex: SqlExercise, con) -> None:  # type: ignore[no-untyped-def]
    rel = con.sql(ex.solution_sql)
    rows = rel.fetchall()
    assert 0 < len(rows) <= MAX_RESULT_ROWS
    assert len(set(rel.columns)) == len(rel.columns), "duplicate output column names"


@pytest.mark.parametrize(
    "ex", [e for e in SQL_EXERCISES if e.order_sensitive], ids=lambda e: e.slug
)
def test_order_sensitive_solutions_have_order_by(ex: SqlExercise) -> None:
    assert "order by" in ex.solution_sql.lower()


def test_dataset_connection_blocks_file_access(con) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(Exception, match=r"(?i)external|disabled|permission"):
        con.sql("SELECT * FROM read_csv('/etc/hosts')").fetchall()
