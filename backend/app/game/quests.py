"""Daily quest selection: pure functions, so every rule is unit-testable without a database.

The day's RNG is seeded from the date, so "what are today's quests?" has one answer even if
the plan is computed twice (and tests can pin it).
"""

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.content.schema import QuestRules

REVIEW_FACTOR = 0.35  # an already-passed exercise is this much less likely than a fresh one
WEIGHT_FLOOR = 0.15  # so a node you ace still shows up now and then
MAX_PLANS = 25  # draws tried to land inside the minutes window


# `def f[T](...)` is Python 3.12 generic syntax (PEP 695), like `function f<T>(...)` in TS.
def weighted_sample[T](
    items: Sequence[T], weights: Sequence[float], k: int, rng: random.Random
) -> list[T]:
    """Pick up to k *distinct* items, each draw proportional to weight among those left.

    - len(items) != len(weights) → ValueError; any weight < 0 → ValueError; k < 0 → ValueError.
    - k >= the number of items → every item, still in a random (weighted) order.
    - Items with weight 0 are only picked once every positive-weight item is taken; then
      they fill the remaining slots uniformly at random.
    - Use only `rng` for randomness (never the `random` module's global functions), so the
      same seed always gives the same answer.

    Hint: one way is to draw a single item with rng.random() * total, remove it, repeat.
    Another is Efraimidis-Spirakis: key = rng.random() ** (1 / w), take the k largest keys.

    TODO(me): implement.
    Teaches: seeded `random.Random` for deterministic tests, sampling without replacement,
    TypeVar generics, and input validation.
    """
    raise NotImplementedError("TODO(me) M2-2: weighted_sample")


def day_rng(day: date) -> random.Random:
    # A private Random instance: seeding the global one would affect any other code using it.
    return random.Random(f"quests:{day.isoformat()}")


@dataclass(frozen=True)
class Candidate:
    slug: str
    branch_id: str
    node_slug: str
    difficulty: int
    passed: bool


def node_weakness(stats: Mapping[str, tuple[int, int]]) -> dict[str, float]:
    """node → weakness in (0, 1). stats: node → (passed_attempts, total_attempts).

    Raw accuracy is noisy at low counts (1 attempt, 1 pass = "100%"). Laplace smoothing
    adds one imaginary pass and one imaginary fail: (passes + 1) / (attempts + 2). An
    untouched node scores 0.5, and it takes real evidence to move far from that.
    """
    return {node: 1 - (p + 1) / (n + 2) for node, (p, n) in stats.items()}


def candidate_weight(c: Candidate, weakness: Mapping[str, float]) -> float:
    w = WEIGHT_FLOOR + weakness.get(c.node_slug, 0.5)
    return w * (REVIEW_FACTOR if c.passed else 1.0)


def plan_minutes(plan: Sequence[Candidate], rules: QuestRules) -> int:
    return sum(rules.minutes_by_difficulty[c.difficulty] for c in plan)


def _draw(
    candidates: Sequence[Candidate],
    weakness: Mapping[str, float],
    rules: QuestRules,
    rng: random.Random,
) -> list[Candidate]:
    k = min(rules.count, len(candidates))
    by_branch: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_branch.setdefault(c.branch_id, []).append(c)

    # 1. Spread: pick distinct branches first, weighted by their weakest candidate.
    branches = sorted(by_branch)
    branch_w = [max(candidate_weight(c, weakness) for c in by_branch[b]) for b in branches]
    spread = weighted_sample(branches, branch_w, min(rules.min_branches, len(branches), k), rng)
    plan: list[Candidate] = []
    for b in spread:
        pool = by_branch[b]
        plan += weighted_sample(pool, [candidate_weight(c, weakness) for c in pool], 1, rng)

    # 2. Fill the rest from everything not yet chosen.
    rest = [c for c in candidates if c not in plan]
    plan += weighted_sample(rest, [candidate_weight(c, weakness) for c in rest], k - len(plan), rng)
    return plan


def plan_quests(
    candidates: Sequence[Candidate],
    weakness: Mapping[str, float],
    rules: QuestRules,
    rng: random.Random,
) -> list[Candidate]:
    """Choose today's quests: weighted to weak nodes, spread over branches, and timed.

    Draws up to MAX_PLANS plans and returns the first whose estimated minutes fit
    [min_minutes, max_minutes]; if none fits (e.g. only hard exercises are open), returns
    the draw closest to the window.
    """
    if not candidates:
        return []
    # Sort for determinism: the DB may return rows in any order, the seed must see one order.
    ordered = sorted(candidates, key=lambda c: c.slug)
    best: list[Candidate] = []
    best_gap = float("inf")
    for _ in range(MAX_PLANS):
        plan = _draw(ordered, weakness, rules, rng)
        mins = plan_minutes(plan, rules)
        gap = max(rules.min_minutes - mins, mins - rules.max_minutes, 0)
        if gap == 0:
            return plan
        if gap < best_gap:
            best, best_gap = plan, gap
    return best
