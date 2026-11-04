"""Single-password auth: a signed session cookie (same-origin dev) or a signed bearer token.

The PWA on Netlify talks to the API on another domain, and iOS Safari blocks third-party
cookies (ITP), so the phone uses a bearer token kept in IndexedDB instead.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.config import Settings, get_settings

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


# The salt namespaces signatures: a value signed for the session cookie can't be replayed
# as a bearer token, even though both use SESSION_SECRET.
_TOKEN_SALT = "alpha-desk.bearer.v1"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_TOKEN_SALT)


def issue_token(settings: Settings) -> tuple[str, datetime]:
    """A stateless token: the signature *is* the proof, so there's no token table. The
    trade-off is no per-token revoke; rotating SESSION_SECRET logs every device out."""
    token = _serializer(settings).dumps({"sub": "player"})
    return token, datetime.now(UTC) + timedelta(seconds=settings.token_max_age_s)


def token_valid(token: str, settings: Settings) -> bool:
    try:
        # max_age checks the timestamp embedded (and signed) at dumps() time.
        _serializer(settings).loads(token, max_age=settings.token_max_age_s)
    except BadSignature:  # SignatureExpired is a subclass
        return False
    return True


async def require_auth(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> None:
    # request.session is populated by Starlette's SessionMiddleware: a dict serialized into
    # a cookie and signed with itsdangerous, so the client can read it but not forge it.
    if request.session.get(SESSION_KEY):
        return
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token and token_valid(token, settings):
        return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in")


# `Annotated[None, Depends(...)]` lets routes declare the dependency once as a type alias.
AuthRequired = Annotated[None, Depends(require_auth)]
