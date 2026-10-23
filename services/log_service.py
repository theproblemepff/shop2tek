import logging
from database.models import LogEntry
from database.session import session

log = logging.getLogger("bot")

async def record(kind: str, actor_id=None, target_id=None, result="ok", details="") -> None:
    async with session() as s:
        s.add(LogEntry(kind=kind, actor_id=actor_id, target_id=target_id, result=result, details=details))
        await s.commit()
    log.info("[%s] actor=%s target=%s result=%s %s", kind, actor_id, target_id, result, details)
