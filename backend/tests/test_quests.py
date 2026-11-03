"""Quest selection. weighted_sample is TODO(me) M2-2 (strict xfail below); the plan logic on
top of it is tested now with a deterministic stand-in sampler."""

import random
from collections import Counter
from collections.abc import Sequence
from datetime import date

import pytest

import app.game.quests as quests
from app.content.schema import QuestRules
from app.game.quests import (
    Candidate,
    candidate_weight,
    day_rng,
    node_weakness,
    plan_minutes,
    plan_quests,
    weighted_sample,
)

RULES = QuestRules(
    count=3,
    min_minutes=15,
    max_minutes=30,
    minutes_by_difficulty={1: 5, 2: 9, 3: 14},
    min_branches=2,
    xp_per_quest=15,
    all_done_bonus=30,
)

todo = pytest.mark.xfail(reason="TODO(me) M2-2: implement weighted_sample", strict=True)

# ---- TODO(me) M2-2: weighted_sample ---------------------------------------------------


@todo
def test_sample_is_distinct_and_sized() -> None:
    got = weighted_sample(list("abcdef"), [1, 2, 3, 4, 5, 6], 3, random.Random(1))
    assert len(got) == 3 and len(set(got)) == 3 and set(got) <= set("abcdef")


@todo
def test_same_seed_same_answer() -> None:
    items, w = list(range(20)), [i + 1 for i in range(20)]
    a = weighted_sample(items, w, 5, random.Random("x"))
    b = weighted_sample(items, w, 5, random.Random("x"))
    assert a == b


@todo
def test_k_larger_than_items_returns_all() -> None:
    got = weighted_sample(["a", "b"], [1, 1], 5, random.Random(0))
    assert sorted(got) == ["a", "b"]


@todo
def test_k_zero() -> None:
    assert weighted_sample(["a"], [1], 0, random.Random(0)) == []


@todo
def test_zero_weights_only_fill_leftover_slots() -> None:
    for seed in range(50):
        got = weighted_sample(["z1", "a", "z2", "b"], [0, 1, 0, 3], 3, random.Random(seed))
        assert set(got[:2]) == {"a", "b"}
        assert got[2] in {"z1", "z2"}


@todo
def test_heavier_items_are_picked_more_often() -> None:
    rng = random.Random(42)
    firsts = Counter(weighted_sample(["light", "heavy"], [1, 9], 1, rng)[0] for _ in range(4000))
    share = firsts["heavy"] / 4000
    assert 0.86 < share < 0.94  # expected 0.9


@todo
@pytest.mark.parametrize(
    ("items", "weights", "k"),
    [(["a", "b"], [1], 1), (["a"], [-1], 1), (["a"], [1], -1)],
)
def test_bad_input_rejected(items: list[str], weights: list[float], k: int) -> None:
    with pytest.raises(ValueError):
        weighted_sample(items, weights, k, random.Random(0))


@todo
def test_does_not_touch_global_random() -> None:
    random.seed(123)
    expected = random.random()
    random.seed(123)
    weighted_sample(list("abc"), [1, 1, 1], 2, random.Random(0))
    assert random.random() == expected


# ---- plan logic (always on) -----------------------------------------------------------


def _top_k[T](items: Sequence[T], weights: Sequence[float], k: int, rng: random.Random) -> list[T]:
    """Stand-in sampler: highest weights first, ties by input order. Deterministic and
    deliberately *not* random, so these tests only check the plan logic around sampling."""
    ranked = sorted(range(len(items)), key=lambda i: -weights[i])
    return [items[i] for i in ranked[: max(k, 0)]]


@pytest.fixture
def stub_sampler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quests, "weighted_sample", _top_k)


def c(slug: str, branch: str, node: str, diff: int = 1, passed: bool = False) -> Candidate:
    return Candidate(slug=slug, branch_id=branch, node_slug=node, difficulty=diff, passed=passed)


def test_node_weakness_is_smoothed() -> None:
    w = node_weakness({"new": (0, 0), "aced": (1, 1), "struggling": (1, 5)})
    assert w["new"] == 0.5
    assert w["aced"] == pytest.approx(1 / 3)  # one pass is weak evidence, not 0% weakness
    assert w["struggling"] == pytest.approx(1 - 2 / 7)


def test_passed_exercises_weigh_less() -> None:
    fresh, review = c("a", "x", "n"), c("b", "x", "n", passed=True)
    assert candidate_weight(review, {"n": 0.5}) < candidate_weight(fresh, {"n": 0.5})


def test_plan_prefers_weak_nodes(stub_sampler: None) -> None:
    cands = [c("s1", "sql", "strong"), c("s2", "sql", "weak"), c("p1", "py", "weak-py")]
    cands += [c("s3", "sql", "strong"), c("p2", "py", "strong-py")]
    weak = {"strong": 0.1, "weak": 0.9, "weak-py": 0.8, "strong-py": 0.1}
    plan = plan_quests(cands, weak, RULES, random.Random(0))
    assert {p.slug for p in plan} >= {"s2", "p1"}


def test_plan_spreads_over_branches(stub_sampler: None) -> None:
    # SQL is much weaker, but min_branches=2 still forces one Python quest in.
    cands = [c(f"s{i}", "sql", f"n{i}", 2) for i in range(5)] + [c("p", "py", "pn", 2)]
    weak = {f"n{i}": 0.9 for i in range(5)} | {"pn": 0.1}
    plan = plan_quests(cands, weak, RULES, random.Random(0))
    assert len(plan) == 3
    assert {p.branch_id for p in plan} == {"sql", "py"}


def test_plan_has_no_duplicates_and_respects_count(stub_sampler: None) -> None:
    cands = [c(f"e{i}", "sql" if i % 2 else "py", f"n{i}") for i in range(10)]
    plan = plan_quests(cands, {}, RULES, random.Random(0))
    assert len(plan) == len({p.slug for p in plan}) == 3


def test_plan_with_few_candidates(stub_sampler: None) -> None:
    assert plan_quests([], {}, RULES, random.Random(0)) == []
    plan = plan_quests([c("only", "sql", "n")], {}, RULES, random.Random(0))
    assert [p.slug for p in plan] == ["only"]


def test_plan_input_order_does_not_matter(stub_sampler: None) -> None:
    cands = [c(f"e{i}", "sql" if i % 3 else "py", f"n{i}", 1 + i % 3) for i in range(9)]
    a = plan_quests(cands, {}, RULES, day_rng(date(2026, 11, 3)))
    b = plan_quests(list(reversed(cands)), {}, RULES, day_rng(date(2026, 11, 3)))
    assert a == b


def test_plan_minutes() -> None:
    assert plan_minutes([c("a", "x", "n", 1), c("b", "x", "n", 3)], RULES) == 19


def test_day_rng_is_stable_per_day() -> None:
    assert day_rng(date(2026, 11, 3)).random() == day_rng(date(2026, 11, 3)).random()
    assert day_rng(date(2026, 11, 3)).random() != day_rng(date(2026, 11, 4)).random()
