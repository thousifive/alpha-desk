import socket

import pytest
from httpx import AsyncClient

import app.routers.health as health
from app.config import get_settings


@pytest.mark.parametrize("path", ["/health", "/api/health"])
async def test_health_reports_db_version_and_host(client: AsyncClient, path: str) -> None:
    resp = await client.get(path)  # no auth: the PWA polls it before/without logging in
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok" and body["db"] == "ok"
    assert body["version"]
    assert body["host"] == (get_settings().server_name or socket.gethostname())


async def test_health_uses_configured_server_name(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "server_name", "linux-laptop")
    assert (await client.get("/health")).json()["host"] == "linux-laptop"


async def test_health_is_503_when_db_is_unreachable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down() -> bool:
        return False

    monkeypatch.setattr(health, "_db_ok", down)
    resp = await client.get("/api/health")
    assert resp.status_code == 503  # the PWA's monitor treats non-2xx as "server off"
    assert resp.json()["status"] == "degraded" and resp.json()["db"] == "error"


async def test_health_version_includes_git_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_SHA", "0123456789abcdef")
    assert health._version().endswith("+0123456")
