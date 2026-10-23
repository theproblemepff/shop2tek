import asyncio
import logging
from datetime import datetime, timezone, timedelta
import discord
from discord import app_commands
from discord.ext import commands, tasks
from database.models import Member
from database.session import session
from bot.utils import post_log
from services import config_service, log_service, export_service
from services.verification_service import check_answer

log = logging.getLogger("bot.verification")
_locks: dict[int, asyncio.Lock] = {}      # anti double-clic par membre
_attempts: dict[int, int] = {}            # essais du mode question (mémoire, remis à zéro au redémarrage)

async def complete_verification(member: discord.Member) -> str | None:
    """Attribue le rôle membre. Retourne un message d'erreur, ou None si tout a réussi."""
    cfg = await config_service.get_config()
    member_role = member.guild.get_role(cfg["roles"]["member"])
    if member_role is None:
        return "Le rôle membre n'est pas configuré (ou a été supprimé). Préviens le staff."
    try:
        await member.add_roles(member_role, reason="Vérification réussie")
        unv = member.guild.get_role(cfg["roles"]["unverified"])
        if unv and unv in member.roles:
            await member.remove_roles(unv, reason="Vérification réussie")
    except discord.Forbidden:
        await log_service.record("verification", target_id=member.id, result="error", details="permission/hiérarchie")
        return "Je n'ai pas la permission de te donner ce rôle (mon rôle doit être au-dessus). Préviens le staff."
    except discord.HTTPException as e:
        await log_service.record("verification", target_id=member.id, result="error", details=str(e))
        return "Erreur Discord, réessaie dans un instant."
    async with session() as s:
        row = await s.get(Member, (member.id, member.guild.id))
        if row:
            row.verified = True
            await s.commit()
    await log_service.record("verification", target_id=member.id, details=cfg["verification"]["mode"])
    await post_log(member.guild, "Vérification réussie", [("Membre", f"{member.mention} (`{member.id}`)"), ("Mode", cfg["verification"]["mode"])], 0x2ECC71)
    try:
        await export_service.sync_verified_ids()
    except OSError:
        log.exception("Écriture du fichier TXT des identifiants impossible")
    return None

class QuestionModal(discord.ui.Modal):
    def __init__(self, question: str, answers: list[str], max_attempts: int):
        super().__init__(title="Vérification")
        self.answers, self.max_attempts = answers, max_attempts
        self.field = discord.ui.TextInput(label=question[:45] or "Réponse", max_length=100)
        self.add_item(self.field)

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if _attempts.get(uid, 0) >= self.max_attempts:
            return await interaction.response.send_message("Trop d'essais. Contacte le staff.", ephemeral=True)
        if not check_answer(self.field.value, self.answers):
            _attempts[uid] = _attempts.get(uid, 0) + 1
            left = self.max_attempts - _attempts[uid]
            return await interaction.response.send_message(f"Mauvaise réponse. Essais restants : {left}.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        err = await complete_verification(interaction.user)
        _attempts.pop(uid, None)
        await interaction.followup.send(err or "✅ Vérifié, bienvenue !", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Se vérifier", style=discord.ButtonStyle.success, custom_id="verify:start")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("Utilisable uniquement sur le serveur.", ephemeral=True)
        cfg = await config_service.get_config()
        v = cfg["verification"]
        if not v["enabled"]:
            return await interaction.response.send_message("La vérification est désactivée.", ephemeral=True)
        role = interaction.guild.get_role(cfg["roles"]["member"])
        if role and role in member.roles:
            return await interaction.response.send_message("Tu es déjà vérifié.", ephemeral=True)
        lock = _locks.setdefault(member.id, asyncio.Lock())
        if lock.locked():
            return await interaction.response.send_message("Vérification en cours…", ephemeral=True)
        async with lock:
            if v["mode"] == "question":
                if not v["answers"]:
                    return await interaction.response.send_message("Question mal configurée. Préviens le staff.", ephemeral=True)
                return await interaction.response.send_modal(QuestionModal(v["question"], v["answers"], v["max_attempts"]))
            await interaction.response.defer(ephemeral=True)
            err = await complete_verification(member)
            await interaction.followup.send(err or "✅ Vérifié, bienvenue !", ephemeral=True)

class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(VerifyView())
        self.expire.start()

    async def cog_unload(self):
        self.expire.cancel()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = await config_service.get_config()
        if not cfg["verification"]["enabled"] or member.bot:
            return
        role = member.guild.get_role(cfg["roles"]["unverified"])
        if role:
            try:
                await member.add_roles(role, reason="Nouveau membre non vérifié")
            except discord.HTTPException as e:
                await log_service.record("verification", target_id=member.id, result="error", details=f"rôle non vérifié : {e}")

    @app_commands.command(name="verification-publier", description="Publie le message de vérification dans le salon configuré")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def publish(self, interaction: discord.Interaction):
        cfg = await config_service.get_config()
        v, ch = cfg["verification"], interaction.guild.get_channel(cfg["channels"]["verification"])
        if ch is None:
            return await interaction.response.send_message("Salon de vérification non configuré.", ephemeral=True)
        view = VerifyView()
        view.start.label = v["button_label"]
        try:
            await ch.send(embed=discord.Embed(title=v["title"], description=v["description"],
                          color=discord.Color.from_str(cfg["welcome"]["color"])), view=view)
        except discord.Forbidden:
            return await interaction.response.send_message("Je ne peux pas écrire dans ce salon.", ephemeral=True)
        await interaction.response.send_message(f"Message publié dans {ch.mention}.", ephemeral=True)

    @tasks.loop(minutes=1)
    async def expire(self):
        cfg = await config_service.get_config()
        v = cfg["verification"]
        if not v["enabled"] or v["on_timeout"] != "kick" or v["timeout_minutes"] <= 0:
            return
        limit = datetime.now(timezone.utc) - timedelta(minutes=v["timeout_minutes"])
        for guild in self.bot.guilds:
            role = guild.get_role(cfg["roles"]["unverified"])
            if not role:
                continue
            for m in role.members:
                if m.joined_at and m.joined_at < limit:
                    try:
                        await m.kick(reason="Vérification non effectuée dans le délai")
                        await log_service.record("verification_timeout", target_id=m.id, details="expulsé")
                    except discord.HTTPException as e:
                        await log_service.record("verification_timeout", target_id=m.id, result="error", details=str(e))

    @expire.before_loop
    async def _wait(self):
        await self.bot.wait_until_ready()

    @expire.error
    async def _err(self, exc: BaseException):
        log.exception("Tâche d'expiration en erreur", exc_info=exc)

async def setup(bot: commands.Bot):
    await bot.add_cog(Verification(bot))
