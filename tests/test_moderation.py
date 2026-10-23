import pytest
from database.session import init_db, close_db
from services import moderation_service as ms
from services.verification_service import check_answer

BASE = dict(actor_id=1, actor_top=10, target_id=2, target_top=5, owner_id=99, bot_id=50, bot_top=20)

def test_hierarchy_ok():
    assert ms.check_action(**BASE) is None

@pytest.mark.parametrize("override", [
    dict(target_id=1),                 # soi-même
    dict(target_id=50),                # le bot
    dict(target_id=99),                # propriétaire
    dict(target_top=10),               # rôle égal à l'auteur
    dict(target_top=25),               # plus haut que l'auteur et le bot
    dict(bot_top=5),                   # bot trop bas
])
def test_hierarchy_refused(override):
    assert ms.check_action(**{**BASE, **override}) is not None

def test_owner_can_sanction_higher_role():
    assert ms.check_action(**{**BASE, "actor_id": 99, "actor_top": 0, "target_top": 15}) is None

@pytest.fixture
async def db(tmp_path):
    await init_db(f"sqlite+aiosqlite:///{tmp_path/'t.db'}")
    yield
    await close_db()

async def test_sanction_history(db):
    await ms.add_sanction(guild_id=1, target_id=2, actor_id=3, kind="warn", reason="spam")
    await ms.add_sanction(guild_id=1, target_id=2, actor_id=3, kind="timeout", duration_s=600)
    await ms.add_sanction(guild_id=1, target_id=7, actor_id=3, kind="warn")
    assert len(await ms.list_sanctions(1, 2)) == 2
    assert [r.kind for r in await ms.list_sanctions(1, 2, "warn")] == ["warn"]
    assert await ms.count_sanctions(1, "warn") == 2
    assert await ms.list_sanctions(2, 2) == []

def test_verification_answer():
    assert check_answer("  Éléphant ", ["elephant"])
    assert not check_answer("chat", ["elephant"])
    assert not check_answer("x", [])
