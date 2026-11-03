"""FastAPI app factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.content.loader import get_content, sync_content
from app.db import dispose_engine, get_sessionmaker
from app.routers import auth, branches, datasets, exercises, progress, quests


# lifespan replaces the old @app.on_event("startup"/"shutdown") hooks: code before
# `yield` runs once at startup, code after runs at shutdown.
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    content = get_content()  # parse + validate at boot so bad YAML fails fast
    if get_settings().sync_content_on_startup:
        async with get_sessionmaker()() as session:
            await sync_content(session, content)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Alpha Desk", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="alpha_desk_session",
        max_age=settings.session_max_age_s,
        same_site="lax",  # sent on top-level navigations, not cross-site subrequests (CSRF guard)
        https_only=settings.secure_cookies,
    )
    for r in (
        auth.router,
        progress.router,
        branches.router,
        exercises.router,
        datasets.router,
        quests.router,
    ):
        app.include_router(r)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
