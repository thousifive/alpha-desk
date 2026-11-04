"""Liveness + "which machine is this?" for the PWA's server detection and for you."""

import asyncio
import os
import socket
from importlib.metadata import PackageNotFoundError, version
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlmodel import select

from app.db import get_sessionmaker
from app.deps import SettingsDep

router = APIRouter(tags=["health"])


def _version() -> str:
    try:
        v = version("alpha-desk")  # from pyproject.toml, via the installed package metadata
    except PackageNotFoundError:
        v = "dev"
    sha = os.environ.get("GIT_SHA", "")
    return f"{v}+{sha[:7]}" if sha else v


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    db: Literal["ok", "error"]
    host: str


async def _db_ok() -> bool:
    try:
        # wait_for: a locked or wedged DB should make /health fail fast, not hang the poll.
        async with asyncio.timeout(2):
            async with get_sessionmaker()() as session:
                await session.exec(select(1))
    except Exception:
        return False
    return True


# Two paths, one handler: /api/health is what the PWA polls (it's under the API prefix the
# dev proxy forwards), /health is the conventional path for curl and Docker's healthcheck.
@router.get("/health", response_model=HealthOut)
@router.get("/api/health", response_model=HealthOut)
async def health(response: Response, settings: SettingsDep) -> HealthOut:
    db_ok = await _db_ok()
    if not db_ok:
        # 503 so the PWA treats the server as unavailable rather than syncing into an error.
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthOut(
        status="ok" if db_ok else "degraded",
        version=_version(),
        db="ok" if db_ok else "error",
        host=settings.server_name or socket.gethostname(),
    )
