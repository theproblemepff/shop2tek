import pytest
from database.session import init_db, close_db
from services import config_service

@pytest.fixture
async def db(tmp_path):
    await init_db(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    yield
    await close_db()

async def test_defaults_and_persistence(db):
    assert (await config_service.get_config())["welcome"]["enabled"] is True
    await config_service.update_section("channels", {"logs": 123})
    assert (await config_service.get_config())["channels"]["logs"] == 123
    assert (await config_service.get_config())["channels"]["welcome"] == 0

async def test_rejects_unknown_keys(db):
    with pytest.raises(ValueError):
        await config_service.update_section("channels", {"nope": 1})
    with pytest.raises(KeyError):
        await config_service.update_section("inconnue", {})

async def test_ids_exposed_as_strings_and_stored_as_ints(db):
    big = "1562981767311523953"  # > 2^53 : serait déformé par JavaScript
    await config_service.update_section("channels", {"logs": big})
    cfg = await config_service.get_config()
    assert cfg["channels"]["logs"] == int(big)
    assert config_service.to_public(cfg)["channels"]["logs"] == big

async def test_invalid_id_rejected(db):
    with pytest.raises(ValueError):
        await config_service.update_section("channels", {"logs": "abc"})

def test_db_url_normalization():
    from database.session import normalize_db_url
    assert normalize_db_url("postgres://u:p@h/db?sslmode=require&channel_binding=require") == "postgresql+asyncpg://u:p@h/db?ssl=require"
    assert normalize_db_url("postgresql://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert normalize_db_url("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"
