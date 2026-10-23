import logging
import discord
from discord.ext import commands
from database.models import Member, now
from database.session import session
from services import config_service, log_service

log = logging.getLogger("bot.welcome")

def render(template: str, member: discord.Member) -> str:
    return (template.replace("{user}", member.mention).replace("{username}", member.display_name)
            .replace("{server}", member.guild.name).replace("{count}", str(member.guild.member_count)))

class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await config_service.get_config()
        async with session() as s:
            row = await s.get(Member, (member.id, member.guild.id))
            if row:
                row.last_join, row.left_at, row.username = now(), None, str(member)
            else:
                s.add(Member(discord_id=member.id, guild_id=member.guild.id, username=str(member)))
            await s.commit()
        await log_service.record("member_join", target_id=member.id)
        w, ch_id = cfg["welcome"], cfg["channels"]["welcome"]
        if not w["enabled"] or not ch_id:
            return
        channel = member.guild.get_channel(ch_id)
        if channel is None:
            return await log_service.record("welcome", target_id=member.id, result="error", details="salon introuvable")
        embed = discord.Embed(title=render(w["title"], member), description=render(w["description"], member),
                              color=discord.Color.from_str(w["color"]))
        if w["show_avatar"]:
            embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(content=member.mention, embed=embed)
        except discord.Forbidden:
            await log_service.record("welcome", target_id=member.id, result="error", details="permission manquante")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = await config_service.get_config()
        async with session() as s:
            row = await s.get(Member, (member.id, member.guild.id))
            if row:
                row.left_at = now()
                await s.commit()
        await log_service.record("member_leave", target_id=member.id)
        g, ch_id = cfg["goodbye"], cfg["channels"]["goodbye"]
        channel = member.guild.get_channel(ch_id) if ch_id else None
        if g["enabled"] and channel:
            try:
                await channel.send(render(g["message"], member))
            except discord.Forbidden:
                await log_service.record("goodbye", target_id=member.id, result="error", details="permission manquante")

async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
