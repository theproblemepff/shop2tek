import pytest
from httpx import AsyncClient, ASGITransport
from database.models import Member
from database.session import init_db, close_db, session
from services import moderation_service as ms, log_service

@pytest.fixture
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PANEL_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("PANEL_SECRET", "x" * 32)
    await init_db(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    from dashboard.app import create_app
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://t") as c:
        assert (await c.post("/api/login", json={"password": "secret"})).status_code == 200
        yield c
    await close_db()

async def test_help_and_commands(client):
    h = (await client.get("/api/help")).json()
    assert "channels.logs" in h["fields"] and "verification" in h["sections"]
    cmds = (await client.get("/api/commands")).json()
    assert {"warn", "ban", "verification-publier"} <= {c["name"] for c in cmds}

async def test_guild_unavailable_without_bot(client):
    assert (await client.get("/api/guild")).json()["available"] is False

async def test_stats_logs_sanctions_members(client):
    await log_service.record("member_join", target_id=1562981767311523953)
    await log_service.record("welcome", result="error", details="salon introuvable")
    await ms.add_sanction(guild_id=1, target_id=1562981767311523953, actor_id=2, kind="warn", reason="spam")
    async with session() as s:
        s.add(Member(discord_id=1562981767311523953, guild_id=1, username="alex#0"))
        await s.commit()
    st = (await client.get("/api/stats")).json()
    assert st["members_present"] == 1 and st["sanctions"] == {"warn": 1} and st["errors_24h"] == 1
    assert sum(st["joins"]) == 1
    logs = (await client.get("/api/logs", params={"result": "error"})).json()
    assert logs["total"] == 1
    sanc = (await client.get("/api/sanctions", params={"target": "1562981767311523953"})).json()
    assert sanc["items"][0]["target_id"] == "1562981767311523953"
    mem = (await client.get("/api/members", params={"q": "alex"})).json()
    assert mem["items"][0]["warnings"] == 1
