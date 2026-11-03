from app.config import get_settings
from app.content.loader import load_content
from app.game.unlocks import node_states, playable_exercise_slugs

BUNDLE = load_content(get_settings().content_dir)
SQL = BUNDLE.nodes["sql-olap"]


def _all_slugs(node_slug: str) -> set[str]:
    node = next(n for n in SQL if n.slug == node_slug)
    return set(playable_exercise_slugs(node))


def test_fresh_player_has_only_root_available() -> None:
    states = node_states(BUNDLE, set(), "M1")
    sql_states = {n.slug: states[n.slug].state for n in SQL}
    assert sql_states["select-filter"] == "available"
    assert {s for s, st in sql_states.items() if st == "available"} == {"select-filter"}


def test_later_branches_are_coming_soon_in_m1() -> None:
    states = node_states(BUNDLE, set(), "M1")
    for branch in BUNDLE.branches:
        if branch.id != "sql-olap":
            assert all(states[n.slug].state == "coming_soon" for n in BUNDLE.nodes[branch.id])


def test_mastering_a_node_unlocks_dependents() -> None:
    passed = _all_slugs("select-filter")
    states = node_states(BUNDLE, passed, "M1")
    assert states["select-filter"].state == "mastered"
    assert states["joins"].state == "available"
    assert states["aggregation"].state == "locked"


def test_partial_progress_is_not_mastery() -> None:
    passed = set(list(_all_slugs("select-filter"))[:1])
    assert node_states(BUNDLE, passed, "M1")["select-filter"].state == "available"


def test_node_with_multiple_prerequisites_needs_all() -> None:
    # duckdb-specifics requires time-bucketing AND row-vs-columnar
    chain = ["select-filter", "joins", "aggregation", "ctes", "window-lag", "time-bucketing"]
    passed = set().union(*(_all_slugs(s) for s in chain))
    states = node_states(BUNDLE, passed, "M1")
    assert states["duckdb-specifics"].state == "locked"
    passed |= _all_slugs("row-vs-columnar")
    assert node_states(BUNDLE, passed, "M1")["duckdb-specifics"].state == "available"


def test_branch_becomes_playable_at_its_milestone() -> None:
    states = node_states(BUNDLE, set(), "M3")
    assert states["gross-net-exposure"].state == "locked"  # finance branch, prereq not met
    assert states["long-short"].state == "coming_soon"  # no playable exercises
