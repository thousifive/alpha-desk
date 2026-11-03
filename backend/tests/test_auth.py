from httpx import AsyncClient

from app.auth import hash_password, verify_password
from tests.conftest import TEST_PASSWORD


def test_verify_password_roundtrip() -> None:
    h = hash_password("hunter2")
    assert verify_password("hunter2", h)
    assert not verify_password("hunter3", h)


def test_verify_password_rejects_empty_or_malformed_hash() -> None:
    assert not verify_password("anything", "")
    assert not verify_password("anything", "not-a-hash")


async def test_me_requires_login(client: AsyncClient) -> None:
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_wrong_password_rejected(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/login", json={"password": "nope"})
    assert resp.status_code == 401
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_login_then_logout(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert resp.status_code == 200
    assert "httponly" in resp.headers["set-cookie"].lower()
    assert (await client.get("/api/auth/me")).json() == {"authenticated": True}

    await client.post("/api/auth/logout")
    assert (await client.get("/api/auth/me")).status_code == 401
