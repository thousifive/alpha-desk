from fastapi import APIRouter

from app.auth import AuthRequired
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.daily import active_days
from app.game.service import get_user, local_today, passed_slugs
from app.schemas import ProgressOut
from app.views import progress_view

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("", response_model=ProgressOut)
async def get_progress(
    _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> ProgressOut:
    user = await get_user(session)
    return progress_view(
        content,
        passed=await passed_slugs(session),
        xp_total=user.xp_total,
        active_days=await active_days(session),
        today=local_today(user),
        milestone=settings.current_milestone,
    )
