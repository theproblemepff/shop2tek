import logging
import discord
from services import config_service

log = logging.getLogger("bot.utils")

async def post_log(guild: discord.Guild, title: str, fields: list[tuple[str, str]], color: int = 0x7C5CFF) -> bool:
    """Publie un embed dans le salon de logs configuré. Retourne False si impossible."""
    cfg = await config_service.get_config()
    ch = guild.get_channel(cfg["channels"]["logs"]) if cfg["channels"]["logs"] else None
    if ch is None:
        return False
    e = discord.Embed(title=title, color=color)
    for name, value in fields:
        e.add_field(name=name, value=value[:1000], inline=False)
    try:
        await ch.send(embed=e)
        return True
    except discord.HTTPException:
        log.warning("Impossible d'écrire dans le salon de logs")
        return False
