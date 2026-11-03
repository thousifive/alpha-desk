from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import SESSION_KEY, AuthRequired, verify_password
from app.config import Settings, get_settings
from app.schemas import LoginRequest, MeResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=MeResponse)
async def login(
    body: LoginRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MeResponse:
    if not verify_password(body.password, settings.app_password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong password")
    # Clear before setting: a fresh session on login avoids session fixation.
    request.session.clear()
    request.session[SESSION_KEY] = True
    return MeResponse(authenticated=True)


@router.post("/logout", response_model=MeResponse)
async def logout(request: Request) -> MeResponse:
    request.session.clear()
    return MeResponse(authenticated=False)


@router.get("/me", response_model=MeResponse)
async def me(_: AuthRequired) -> MeResponse:
    return MeResponse(authenticated=True)
