from fastapi import APIRouter, HTTPException, status

from app.auth import AuthRequired
from app.deps import ContentDep, SessionDep, SettingsDep
from app.game.service import passed_slugs
from app.schemas import BranchDetail, BranchSummary
from app.views import branch_detail, branch_summaries

router = APIRouter(prefix="/api/branches", tags=["branches"])


@router.get("", response_model=list[BranchSummary])
async def list_branches(
    _: AuthRequired, session: SessionDep, content: ContentDep, settings: SettingsDep
) -> list[BranchSummary]:
    return branch_summaries(content, await passed_slugs(session), settings.current_milestone)


@router.get("/{branch_id}", response_model=BranchDetail)
async def get_branch(
    branch_id: str,
    _: AuthRequired,
    session: SessionDep,
    content: ContentDep,
    settings: SettingsDep,
) -> BranchDetail:
    detail = branch_detail(
        content, branch_id, await passed_slugs(session), settings.current_milestone
    )
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown branch")
    return detail
