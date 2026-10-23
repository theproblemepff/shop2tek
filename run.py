"""Point d'entrée unique : base de données + bot + panel dans une seule boucle asyncio."""
import asyncio
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import discord
import uvicorn
from config.settings import get_env
from database.session import init_db, close_db
from bot.main import AllInOneBot
from dashboard.app import create_app

def setup_logging() -> None:
    log_dir = Path(get_env().data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(log_dir / "bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    sh = logging.StreamHandler()
    for h in (fh, sh):
        h.setFormatter(fmt)
    logging.basicConfig(level=logging.INFO, handlers=[fh, sh])

async def main() -> None:
    env = get_env()
    setup_logging()
    log = logging.getLogger("run")
    if not env.token:
        log.error("DISCORD_TOKEN manquant dans .env")
        sys.exit(1)
    await init_db()
    log.info("Base de données initialisée")
    bot = AllInOneBot()
    server = uvicorn.Server(uvicorn.Config(create_app(bot), host=env.panel_host, port=env.panel_port, log_level="warning"))
    log.info("Panel : http://%s:%d", env.panel_host, env.panel_port)
    tasks = [asyncio.create_task(bot.start(env.token), name="bot"), asyncio.create_task(server.serve(), name="panel")]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            exc = None if t.cancelled() else t.exception()
            if exc:
                log.error("'%s' s'est arrêté sur une erreur : %r", t.get_name(), exc)
                if isinstance(exc, discord.LoginFailure):
                    log.error("Token invalide : vérifie DISCORD_TOKEN dans .env")
                elif isinstance(exc, discord.PrivilegedIntentsRequired):
                    log.error("Active Server Members Intent et Message Content Intent dans le portail développeur")
    finally:
        server.should_exit = True
        await bot.close()
        await asyncio.gather(*tasks, return_exceptions=True)
        await close_db()
        log.info("Arrêt propre terminé")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
