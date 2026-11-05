"""A small in-memory rate limiter for login (and, from M3, the AI endpoints).

In-memory is enough here: one uvicorn worker, one player. A restart forgets the counters,
which only matters to an attacker who can also restart your server.
"""

import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


class SlidingWindow:
    """At most `limit` hits per `window_s` seconds per key. A deque of timestamps per key:
    old ones fall off the left, so the check is O(expired) and memory is O(limit) per key."""

    def __init__(self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def hit(self, key: str) -> float | None:
        """Record a hit. Returns None if allowed, else seconds until the next one is."""
        now = self._clock()
        q = self._hits.setdefault(key, deque())
        while q and q[0] <= now - self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return q[0] + self.window_s - now
        q.append(now)
        return None

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


def client_key(request: Request) -> str:
    # The direct peer. Behind `tailscale serve` this is the proxy (in Docker: the Docker
    # gateway) unless uvicorn's --proxy-headers trusts it (FORWARDED_ALLOW_IPS) and rewrites
    # request.client from X-Forwarded-For.
    return request.client.host if request.client else "unknown"


def enforce(limiter: SlidingWindow, request: Request) -> None:
    wait = limiter.hit(client_key(request))
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {max(1, round(wait / 60))} min.",
            headers={"Retry-After": str(int(wait) + 1)},
        )
