"""Single-password auth backed by a signed session cookie."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

# argon2 is deliberately slow and memory-hard, which is what makes offline brute force
# of a leaked hash expensive. pwdlib wraps it and handles salt + parameter encoding.
_hasher = PasswordHash((Argon2Hasher(),))

SESSION_KEY = "authed"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False  # no password configured → nobody gets in
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        # A malformed hash in .env should read as "wrong password", not a 500.
        return False


async def require_auth(request: Request) -> None:
    # request.session is populated by Starlette's SessionMiddleware: a dict serialized into
    # a cookie and signed with itsdangerous, so the client can read it but not forge it.
    if not request.session.get(SESSION_KEY):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")


# `Annotated[None, Depends(...)]` lets routes declare the dependency once as a type alias.
AuthRequired = Annotated[None, Depends(require_auth)]
