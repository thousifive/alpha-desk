"""XP awarded for a passing attempt. Rules come from content/levels.yaml (`xp:`)."""

from app.content.schema import XpRules


def xp_for_attempt(difficulty: int, *, first_try: bool, hints_used: int, rules: XpRules) -> int:
    """XP for a *passing* attempt.

    1. base = rules.base_by_difficulty[difficulty]  (ValueError for an unknown difficulty)
    2. if first_try: add base * rules.first_try_bonus
    3. multiply by (1 - rules.hint_penalty[hints_used]); hints beyond the end of the
       list use the last penalty. Negative hints_used → ValueError.
    4. round *down* to an int (the player never gets a fractional XP rounded up)

    TODO(me): implement.
    Teaches: keyword-only args (`*`), validating inputs, and edge-case testing.
    """
    raise NotImplementedError("TODO(me) #2: xp_for_attempt")
