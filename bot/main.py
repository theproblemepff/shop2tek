import logging
import discord
from discord.ext import commands

log = logging.getLogger("bot")
COGS = ["bot.cogs.welcome", "bot.cogs.verification", "bot.cogs.moderation", "bot.cogs.honeypot"]

class AllInOneBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True          # à activer dans le portail développeur
        intents.message_content = True  # nécessaire pour anti-spam / anti-liens
        super().__init__(command_prefix="!", intents=intents)
        self.module_status: dict[str, str] = {}

    async def setup_hook(self):
        for ext in COGS:
            try:
                await self.load_extension(ext)
                self.module_status[ext] = "ok"
            except Exception:
                log.exception("Module %s non chargé", ext)
                self.module_status[ext] = "erreur"
        await self.tree.sync()

    async def on_ready(self):
        log.info("Connecté en tant que %s (%d serveur(s))", self.user, len(self.guilds))
