import logging
import discord
from discord import app_commands
from discord.ext import commands
from bot.utils import post_log
from services import config_service, log_service, moderation_service as ms
from services.honeypot_service import exempt_reason

log = logging.getLogger("bot.honeypot")

class Honeypot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.id == self.bot.user.id or message.webhook_id:
            return
        cfg = await config_service.get_config()
        h = cfg["honeypot"]
        if not h["enabled"] or not h["channel"] or message.channel.id != h["channel"]:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return
        guild = message.guild
        why = exempt_reason(
            is_owner=member.id == guild.owner_id, is_admin=member.guild_permissions.administrator,
            role_ids={r.id for r in member.roles}, staff_role_ids=set(cfg["roles"]["staff"]),
            top_position=member.top_role.position, bot_top_position=guild.me.top_role.position)
        who = f"{member.mention} (`{member.id}`)"
        if why:
            return await log_service.record("honeypot", target_id=member.id, result="ignored", details=why)
        if h["simulate"]:
            await log_service.record("honeypot", target_id=member.id, result="simulation", details="aurait supprimé le message et expulsé")
            return await post_log(guild, "Salon piège : SIMULATION", [("Membre", who), ("Action", "Aurait été expulsé (mode simulation actif)")], 0xF1C40F)
        try:
            await message.delete()
        except discord.HTTPException as e:
            await log_service.record("honeypot", target_id=member.id, result="error", details=f"suppression impossible : {e}")
        try:
            await member.kick(reason=f"Salon piège : message dans #{message.channel}")
        except discord.HTTPException as e:
            await log_service.record("honeypot", target_id=member.id, result="error", details=f"expulsion impossible : {e}")
            return await post_log(guild, "Salon piège : ÉCHEC de l'expulsion", [("Membre", who), ("Erreur", str(e))], 0xE74C3C)
        await ms.add_sanction(guild_id=guild.id, target_id=member.id, actor_id=self.bot.user.id, kind="kick",
                              reason="Salon piège", source="salon-piege")
        await log_service.record("honeypot", target_id=member.id, details="message supprimé, membre expulsé")
        await post_log(guild, "Salon piège : membre expulsé", [("Membre", who)], 0xE74C3C)

    @app_commands.command(name="piege-publier", description="Publie l'avertissement dans le salon piège")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def publish(self, interaction: discord.Interaction):
        h = (await config_service.get_config())["honeypot"]
        ch = interaction.guild.get_channel(h["channel"]) if h["channel"] else None
        if ch is None:
            return await interaction.response.send_message("Salon piège non configuré dans le panel.", ephemeral=True)
        try:
            await ch.send(embed=discord.Embed(title="Salon piège", description=h["warning_text"], color=0xE74C3C))
        except discord.Forbidden:
            return await interaction.response.send_message("Je ne peux pas écrire dans ce salon.", ephemeral=True)
        await interaction.response.send_message(f"Avertissement publié dans {ch.mention}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Honeypot(bot))
