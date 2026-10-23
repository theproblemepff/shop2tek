"""Logique de modération réutilisable (commandes Discord et panel appliquent les mêmes règles)."""
from sqlalchemy import select, func
from database.models import Sanction
from database.session import session

def check_action(*, actor_id: int, actor_top: int, target_id: int, target_top: int,
                 owner_id: int, bot_id: int, bot_top: int) -> str | None:
    """Retourne un message d'erreur si l'action est interdite, sinon None."""
    if target_id == actor_id:
        return "Tu ne peux pas te sanctionner toi-même."
    if target_id == bot_id:
        return "Je ne peux pas me sanctionner moi-même."
    if target_id == owner_id:
        return "Le propriétaire du serveur ne peut pas être sanctionné."
    if actor_id != owner_id and actor_top <= target_top:
        return "Ton rôle le plus haut n'est pas supérieur à celui de la cible."
    if bot_top <= target_top:
        return "Mon rôle le plus haut n'est pas supérieur à celui de la cible : monte mon rôle dans la liste."
    return None

async def add_sanction(*, guild_id: int, target_id: int, actor_id: int, kind: str,
                       reason: str = "", duration_s: int | None = None, source: str = "commande") -> Sanction:
    async with session() as s:
        row = Sanction(guild_id=guild_id, target_id=target_id, actor_id=actor_id, kind=kind,
                       reason=reason or "Aucun motif", duration_s=duration_s, source=source)
        s.add(row)
        await s.commit()
        return row

async def list_sanctions(guild_id: int, target_id: int | None = None, kind: str | None = None,
                         limit: int = 20, offset: int = 0) -> list[Sanction]:
    q = select(Sanction).where(Sanction.guild_id == guild_id)
    if target_id is not None:
        q = q.where(Sanction.target_id == target_id)
    if kind:
        q = q.where(Sanction.kind == kind)
    q = q.order_by(Sanction.id.desc()).limit(limit).offset(offset)
    async with session() as s:
        return list((await s.execute(q)).scalars())

async def count_sanctions(guild_id: int, kind: str) -> int:
    async with session() as s:
        return (await s.execute(select(func.count()).select_from(Sanction)
                .where(Sanction.guild_id == guild_id, Sanction.kind == kind))).scalar_one()
