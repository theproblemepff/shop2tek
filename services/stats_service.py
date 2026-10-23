"""Requêtes de lecture pour le panel (statistiques, historiques, recherche)."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from database.models import Member, LogEntry, Sanction
from database.session import session

def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() if dt.tzinfo else dt.isoformat() + "Z"

def _s(v) -> str | None:
    return None if v is None else str(v)

def log_dict(r: LogEntry) -> dict:
    return {"id": r.id, "created_at": iso(r.created_at), "kind": r.kind, "actor_id": _s(r.actor_id),
            "target_id": _s(r.target_id), "result": r.result, "details": r.details}

async def overview() -> dict:
    now_ = datetime.now(timezone.utc)
    since = now_ - timedelta(days=7)
    today = now_.date()
    days = [today - timedelta(days=6 - i) for i in range(7)]
    async with session() as s:
        present = (await s.execute(select(func.count()).select_from(Member).where(Member.left_at.is_(None)))).scalar_one()
        verified = (await s.execute(select(func.count()).select_from(Member)
                    .where(Member.left_at.is_(None), Member.verified.is_(True)))).scalar_one()
        rows = (await s.execute(select(LogEntry.kind, LogEntry.created_at)
                .where(LogEntry.kind.in_(["member_join", "member_leave"]), LogEntry.created_at >= since))).all()
        sanctions = {k: n for k, n in (await s.execute(select(Sanction.kind, func.count()).group_by(Sanction.kind))).all()}
        errors = (await s.execute(select(func.count()).select_from(LogEntry)
                  .where(LogEntry.result == "error", LogEntry.created_at >= now_ - timedelta(days=1)))).scalar_one()
        recent = (await s.execute(select(LogEntry).order_by(LogEntry.id.desc()).limit(8))).scalars().all()
    joins, leaves = [0] * 7, [0] * 7
    for kind, created in rows:
        if created.date() in days:
            (joins if kind == "member_join" else leaves)[days.index(created.date())] += 1
    return {"members_present": present, "members_verified": verified, "sanctions": sanctions,
            "sanctions_total": sum(sanctions.values()), "errors_24h": errors,
            "days": [d.strftime("%d/%m") for d in days], "joins": joins, "leaves": leaves,
            "recent": [log_dict(r) for r in recent]}

async def page_logs(kind: str, result: str, limit: int, offset: int) -> dict:
    cond = []
    if kind:
        cond.append(LogEntry.kind == kind)
    if result:
        cond.append(LogEntry.result == result)
    async with session() as s:
        total = (await s.execute(select(func.count()).select_from(LogEntry).where(*cond))).scalar_one()
        rows = (await s.execute(select(LogEntry).where(*cond).order_by(LogEntry.id.desc()).limit(limit).offset(offset))).scalars().all()
        kinds = [k for (k,) in (await s.execute(select(LogEntry.kind).distinct())).all()]
    return {"total": total, "items": [log_dict(r) for r in rows], "kinds": sorted(kinds)}

async def page_sanctions(kind: str, target: str, limit: int, offset: int) -> dict:
    cond = []
    if kind:
        cond.append(Sanction.kind == kind)
    if target.strip().isdigit():
        cond.append(Sanction.target_id == int(target.strip()))
    async with session() as s:
        total = (await s.execute(select(func.count()).select_from(Sanction).where(*cond))).scalar_one()
        rows = (await s.execute(select(Sanction).where(*cond).order_by(Sanction.id.desc()).limit(limit).offset(offset))).scalars().all()
    return {"total": total, "items": [{"id": r.id, "created_at": iso(r.created_at), "kind": r.kind,
            "target_id": str(r.target_id), "actor_id": str(r.actor_id), "reason": r.reason,
            "duration_s": r.duration_s} for r in rows]}

async def page_members(q: str, limit: int, offset: int, verified_only: bool = False) -> dict:
    q = q.strip()
    cond = [Member.verified.is_(True)] if verified_only else []
    if q.isdigit():
        cond.append(Member.discord_id == int(q))
    elif q:
        cond.append(Member.username.ilike(f"%{q}%"))
    async with session() as s:
        total = (await s.execute(select(func.count()).select_from(Member).where(*cond))).scalar_one()
        rows = (await s.execute(select(Member).where(*cond).order_by(Member.last_join.desc()).limit(limit).offset(offset))).scalars().all()
        ids = [m.discord_id for m in rows]
        warns = {}
        if ids:
            warns = {t: n for t, n in (await s.execute(select(Sanction.target_id, func.count())
                     .where(Sanction.kind == "warn", Sanction.target_id.in_(ids)).group_by(Sanction.target_id))).all()}
    return {"total": total, "items": [{"id": str(m.discord_id), "username": m.username, "first_join": iso(m.first_join),
            "last_join": iso(m.last_join), "left_at": iso(m.left_at), "verified": m.verified,
            "warnings": warns.get(m.discord_id, 0)} for m in rows]}
