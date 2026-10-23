from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config.settings import get_env
from database.models import Base

_engine = None

def normalize_db_url(url: str) -> str:
    """Accepte les URL fournies par les hébergeurs (postgres://, ?sslmode=require…) et les adapte à asyncpg."""
    parts = urlsplit(url)
    if parts.scheme in ("postgres", "postgresql"):
        query = []
        for k, v in parse_qsl(parts.query):
            if k == "sslmode":
                query.append(("ssl", v))
            elif k not in ("channel_binding",):
                query.append((k, v))
        parts = parts._replace(scheme="postgresql+asyncpg", query=urlencode(query))
        return urlunsplit(parts)
    return url
_maker: async_sessionmaker[AsyncSession] | None = None

async def init_db(url: str | None = None) -> None:
    global _engine, _maker
    _engine = create_async_engine(normalize_db_url(url or get_env().database_url), pool_pre_ping=True)
    _maker = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def session() -> AsyncSession:
    assert _maker is not None, "init_db() n'a pas été appelé"
    return _maker()

async def close_db() -> None:
    if _engine:
        await _engine.dispose()
