from fastapi import APIRouter

from app.auth import AuthRequired
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.daily import active_days, streak_out, streak_state
from app.game.service import get_user, level_out, local_today, next_boss, passed_slugs
from app.game.unlocks import node_states, playable_exercise_slugs
from app.schemas import ProgressOut

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
async def get_progress(
    _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> ProgressOut:
    user = await get_user(session)
    passed = await passed_slugs(session)
    states = node_states(content, passed, settings.current_milestone)
    playable = {
        s
        for st in states.values()
        if st.state != "coming_soon"
        for s in playable_exercise_slugs(st.node)
    }
    return ProgressOut(
        xp_total=user.xp_total,
        level=level_out(user.xp_total, content),
        streak=streak_out(
            streak_state(await active_days(session), local_today(user), content), content
        ),
        passed_exercises=len(passed & playable),
        playable_exercises=len(playable),
        mastered_nodes=sum(st.state == "mastered" for st in states.values()),
        next_boss=next_boss(content, states, passed, settings.current_milestone),
    )
