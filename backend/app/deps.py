"""Reusable dependency aliases. `Annotated[T, Depends(f)]` lets a route just declare
`session: SessionDep` and FastAPI resolves (and caches per request) the value."""

from typing import Annotated

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.config import Settings, get_settings
from app.content.loader import get_content
from app.content.schema import ContentBundle
from app.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ContentDep = Annotated[ContentBundle, Depends(get_content)]
