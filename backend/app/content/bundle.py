"""The offline content bundle a device downloads (GET /api/offline/bundle)."""

import hashlib
import json
from typing import Any

from app.content.schema import ContentBundle


def build_bundle(content: ContentBundle, milestone: str) -> dict[str, Any]:
    """All content *including* grading data (solutions, quiz answers, hidden tests), so the
    device can grade offline: acceptable for a single-player app (see docs/SPEC.md)."""
    body = content.model_dump(mode="json")
    # sort_keys makes the hash stable across runs (dict order alone isn't a content change).
    raw = json.dumps({"c": body, "m": milestone}, sort_keys=True)
    version = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return {"version": version, "milestone": milestone, "content": body}
