"""Public API shapes (Pydantic v2). Kept apart from tables in models.py."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class MeResponse(BaseModel):
    authenticated: bool
