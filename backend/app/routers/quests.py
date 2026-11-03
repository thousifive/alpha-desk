from fastapi import APIRouter, HTTPException, status

from app.auth import AuthRequired
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.daily import get_or_create_quest, quest_out
from app.game.service import get_user, local_today, passed_slugs
from app.schemas import QuestOut

router = APIRouter(prefix="/api/quests", tags=["quests"])


@router.get("/today", response_model=QuestOut)
async def today_quests(
    _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> QuestOut:
    """Today's three quests. The first call of a (player-local) day generates them."""
    user = await get_user(session)
    day = local_today(user)
    try:
        quest, items = await get_or_create_quest(
            session, content, await passed_slugs(session), settings.current_milestone, day
        )
    except NotImplementedError as e:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, f"Quest board offline: {e}") from e
    return quest_out(quest, items, content)
