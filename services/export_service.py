"""Export des identifiants Discord (fichier TXT sur disque + téléchargement depuis le panel)."""
import asyncio
import os
from pathlib import Path
from sqlalchemy import select
from database.models import Member
from database.session import session

from config.settings import get_env

def default_file() -> Path:
    base = Path(get_env().data_dir)
    return (base if base.is_absolute() else Path(__file__).resolve().parent.parent / base) / "exports" / "ids_verifies.txt"

async def _ids(verified_only: bool) -> list[int]:
    q = select(Member.discord_id).order_by(Member.first_join)
    if verified_only:
        q = q.where(Member.verified.is_(True))
    async with session() as s:
        rows = (await s.execute(q)).scalars().all()
    return list(dict.fromkeys(rows))  # sans doublons, ordre conservé

async def verified_ids() -> list[int]:
    return await _ids(True)

async def all_ids() -> list[int]:
    return await _ids(False)

def _write(path: Path, ids: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")
    os.replace(tmp, path)  # écriture atomique : jamais de fichier à moitié écrit

async def sync_verified_ids(path: Path | None = None) -> tuple[Path, int]:
    """Réécrit le fichier TXT à partir de la base (source de référence)."""
    path = path or default_file()
    ids = await verified_ids()
    await asyncio.to_thread(_write, path, ids)
    return path, len(ids)
