import pytest
from httpx import AsyncClient, ASGITransport
from database.models import Member
from database.session import init_db, close_db, session
from services import export_service, config_service
from services.honeypot_service import exempt_reason

BASE = dict(is_owner=False, is_admin=False, role_ids={1}, staff_role_ids={9}, top_position=3, bot_top_position=10)

def test_honeypot_exemptions():
    assert exempt_reason(**BASE) is None
    assert exempt_reason(**{**BASE, "is_owner": True})
    assert exempt_reason(**{**BASE, "is_admin": True})
    assert exempt_reason(**{**BASE, "role_ids": {9}})
    assert exempt_reason(**{**BASE, "top_position": 10})

@pytest.fixture
async def db(tmp_path):
    await init_db(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    async with session() as s:
        s.add_all([Member(discord_id=1562981767311523953, guild_id=1, verified=True),
                   Member(discord_id=1562981767311523953, guild_id=2, verified=True),  # doublon multi-serveurs
                   Member(discord_id=22, guild_id=1, verified=False)])
        await s.commit()
    yield tmp_path
    await close_db()

async def test_ids_file_deduplicated_and_verified_only(db):
    path, n = await export_service.sync_verified_ids(db / "ids.txt")
    assert n == 1 and path.read_text() == "1562981767311523953\n"
    assert await export_service.all_ids() == [1562981767311523953, 22] or set(await export_service.all_ids()) == {1562981767311523953, 22}

async def test_honeypot_config_saved_with_big_id(db):
    await config_service.update_section("honeypot", {"enabled": True, "channel": "1562981767311523953"})
    cfg = await config_service.get_config()
    assert cfg["honeypot"]["channel"] == 1562981767311523953 and cfg["honeypot"]["simulate"] is True

async def test_ids_export_endpoint(db, monkeypatch):
    monkeypatch.setenv("PANEL_ADMIN_PASSWORD", "secret"); monkeypatch.setenv("PANEL_SECRET", "x" * 32)
    from dashboard.app import create_app
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        assert (await c.get("/api/ids/export.txt")).status_code == 401
        await c.post("/api/login", json={"password": "secret"})
        r = await c.get("/api/ids/export.txt?scope=all")
        assert set(r.text.split()) == {"1562981767311523953", "22"} and "attachment" in r.headers["content-disposition"]
        assert (await c.get("/api/members", params={"verified": "1"})).json()["total"] == 2
