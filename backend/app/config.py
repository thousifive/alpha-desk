"""App settings, loaded from environment variables and backend/.env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Paths are resolved from this file, not the CWD, so `uvicorn`, `pytest`, and the CLI
# all find the same files no matter which directory they're launched from.
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    # pydantic-settings maps each field to an env var of the same name (case-insensitive)
    # and validates/coerces types, so a typo'd or malformed value fails fast at startup.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'alpha_desk.db'}"
    session_secret: str = "dev-insecure-change-me"
    # argon2 hash of the single login password. Generate with: uv run alpha-desk hash-password
    app_password_hash: str = ""
    session_max_age_s: int = 60 * 60 * 24 * 30
    secure_cookies: bool = False  # set True behind HTTPS in prod

    content_dir: Path = REPO_ROOT / "content"
    dataset_dir: Path = REPO_ROOT / "data" / "meridian"
    sync_content_on_startup: bool = True
    # Branches whose playable_from is at or before this milestone are playable.
    current_milestone: str = "M1"


# lru_cache turns this into a lazy singleton; FastAPI dependencies can call it cheaply,
# and tests can override it via app.dependency_overrides or get_settings.cache_clear().
@lru_cache
def get_settings() -> Settings:
    return Settings()
