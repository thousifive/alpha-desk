from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import SESSION_KEY, AuthRequired, issue_token, verify_password
from app.config import Settings, get_settings
from app.deps import SessionDep
from app.game.service import get_user, valid_timezone
from app.schemas import LoginRequest, MeResponse, TimezoneIn, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: SessionDep,
) -> TokenOut:
    if not verify_password(body.password, settings.app_password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong password")
    # Clear before setting: a fresh session on login avoids session fixation.
    request.session.clear()
    request.session[SESSION_KEY] = True
    if body.timezone and valid_timezone(body.timezone):  # bad zone: ignore, don't block login
        await _set_timezone(session, body.timezone)
    token, expires_at = issue_token(settings)
    return TokenOut(authenticated=True, token=token, expires_at=expires_at)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    _: AuthRequired, settings: Annotated[Settings, Depends(get_settings)]
) -> TokenOut:
    """Swap a still-valid token for a fresh 30-day one (the app calls this while syncing)."""
    token, expires_at = issue_token(settings)
    return TokenOut(authenticated=True, token=token, expires_at=expires_at)


async def _set_timezone(session: SessionDep, tz: str) -> None:
    user = await get_user(session)
    if user.timezone != tz:
        user.timezone = tz
        session.add(user)
        await session.commit()


@router.put("/timezone", response_model=MeResponse)
async def set_timezone(body: TimezoneIn, _: AuthRequired, session: SessionDep) -> MeResponse:
    """Called on app load, so travelling (or a DST-less zone change) updates "today"."""
    if not valid_timezone(body.timezone):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown timezone")
    await _set_timezone(session, body.timezone)
    return MeResponse(authenticated=True)


@router.post("/logout", response_model=MeResponse)
async def logout(request: Request) -> MeResponse:
    request.session.clear()
    return MeResponse(authenticated=False)


@router.get("/me", response_model=MeResponse)
async def me(_: AuthRequired) -> MeResponse:
    return MeResponse(authenticated=True)
