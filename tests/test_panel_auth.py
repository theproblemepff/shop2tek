import pytest
from httpx import AsyncClient, ASGITransport
from database.session import init_db, close_db

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PANEL_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("PANEL_SECRET", "x" * 32)
    await init_db(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    from dashboard.app import create_app
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        yield c
    await close_db()

async def test_requires_login(client):
    assert (await client.get("/api/config")).status_code == 401

async def test_login_then_access(client):
    assert (await client.post("/api/login", json={"password": "bad"})).status_code == 401
    assert (await client.post("/api/login", json={"password": "secret"})).status_code == 200
    assert (await client.get("/api/config")).status_code == 200

async def test_cookie_secure_and_fly_ip(tmp_path, monkeypatch):
    monkeypatch.setenv("PANEL_ADMIN_PASSWORD", "secret"); monkeypatch.setenv("PANEL_SECRET", "x" * 32)
    monkeypatch.setenv("PANEL_COOKIE_SECURE", "1"); monkeypatch.setenv("PANEL_IP_HEADER", "fly-client-ip")
    await init_db(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    from dashboard.app import create_app
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        # 5 échecs depuis une adresse : bloquées ; une autre adresse reste libre
        for _ in range(5):
            await c.post("/api/login", json={"password": "bad"}, headers={"fly-client-ip": "1.1.1.1"})
        assert (await c.post("/api/login", json={"password": "secret"}, headers={"fly-client-ip": "1.1.1.1"})).status_code == 429
        r = await c.post("/api/login", json={"password": "secret"}, headers={"fly-client-ip": "2.2.2.2"})
        assert r.status_code == 200 and "secure" in r.headers["set-cookie"].lower()
    await close_db()
