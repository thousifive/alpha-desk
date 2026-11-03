"""XP → level mapping. Thresholds come from content/levels.yaml."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.content.schema import LevelDef


def level_for_xp(xp: int, thresholds: Sequence[int]) -> int:
    """Return the index of the level a player with `xp` total XP has reached.

    `thresholds` are the min_xp values in ascending order, starting at 0
    (e.g. [0, 500, 1500, ...]). The level is the highest index whose threshold <= xp.
    Raise ValueError for negative xp.

    TODO(me): implement with the stdlib `bisect` module (no loop needed).
    Teaches: pure functions, binary search via bisect, and pytest.mark.parametrize.
    """
    raise NotImplementedError("TODO(me) #1: level_for_xp")


# frozen=True makes instances immutable and hashable, like a TS `Readonly<...>` you can
# also use as a dict key. Good default for small value objects.
@dataclass(frozen=True)
class LevelInfo:
    index: int
    title: str
    min_xp: int
    next_title: str | None
    next_min_xp: int | None  # None at max level


def level_info(xp: int, levels: Sequence[LevelDef]) -> LevelInfo:
    idx = level_for_xp(xp, [lv.min_xp for lv in levels])
    cur = levels[idx]
    nxt = levels[idx + 1] if idx + 1 < len(levels) else None
    return LevelInfo(
        index=idx,
        title=cur.title,
        min_xp=cur.min_xp,
        next_title=nxt.title if nxt else None,
        next_min_xp=nxt.min_xp if nxt else None,
    )
