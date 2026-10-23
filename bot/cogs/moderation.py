import logging
from datetime import timedelta
import discord
from discord import app_commands
from discord.ext import commands
from services import config_service, log_service
from services import moderation_service as ms

log = logging.getLogger("bot.moderation")
COLORS = {"warn": 0xF1C40F, "timeout": 0xE67E22, "untimeout": 0x2ECC71, "kick": 0xE74C3C, "ban": 0x992D22, "unban": 0x2ECC71}

def fmt_duration(s: int | None) -> str:
    if not s:
        return "—"
    m = s // 60
    return f"{m // 1440} j {m % 1440 // 60} h {m % 60} min".replace("0 j ", "").replace(" 0 h", "").strip()

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "Tu n'as pas la permission d'utiliser cette commande."
        else:
            log.exception("Erreur de commande", exc_info=error)
            await log_service.record("command_error", actor_id=interaction.user.id, result="error", details=str(error)[:200])
            msg = "Une erreur est survenue. Elle a été enregistrée."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    def _hierarchy_error(self, interaction: discord.Interaction, target: discord.Member) -> str | None:
        g, me = interaction.guild, interaction.guild.me
        return ms.check_action(actor_id=interaction.user.id, actor_top=interaction.user.top_role.position,
                               target_id=target.id, target_top=target.top_role.position,
                               owner_id=g.owner_id, bot_id=me.id, bot_top=me.top_role.position)

    async def _publish_log(self, guild: discord.Guild, kind: str, actor, target_id: int, reason: str, duration_s=None):
        cfg = await config_service.get_config()
        ch = guild.get_channel(cfg["channels"]["logs"]) if cfg["channels"]["logs"] else None
        await log_service.record(kind, actor_id=actor.id, target_id=target_id, details=reason)
        if ch is None:
            return
        e = discord.Embed(title=f"Modération : {kind}", color=COLORS.get(kind, 0x7C5CFF))
        e.add_field(name="Cible", value=f"<@{target_id}> (`{target_id}`)")
        e.add_field(name="Auteur", value=actor.mention)
        e.add_field(name="Durée", value=fmt_duration(duration_s))
        e.add_field(name="Motif", value=reason[:1000], inline=False)
        try:
            await ch.send(embed=e)
        except discord.HTTPException:
            log.warning("Impossible d'écrire dans le salon de logs")

    async def _apply(self, interaction, kind, target, reason, action, duration_s=None, dm=True):
        """Vérifie la hiérarchie, exécute `action`, enregistre. Ne confirme que si l'action a réussi."""
        if isinstance(target, discord.Member) and (err := self._hierarchy_error(interaction, target)):
            return await interaction.response.send_message(f"❌ {err}", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        try:
            await action()
        except discord.Forbidden:
            await log_service.record(kind, actor_id=interaction.user.id, target_id=target.id, result="error", details="Forbidden")
            return await interaction.followup.send("❌ Permission manquante pour le bot.", ephemeral=True)
        except discord.HTTPException as e:
            await log_service.record(kind, actor_id=interaction.user.id, target_id=target.id, result="error", details=str(e))
            return await interaction.followup.send(f"❌ Discord a refusé l'action : {e.text}", ephemeral=True)
        await ms.add_sanction(guild_id=interaction.guild_id, target_id=target.id, actor_id=interaction.user.id,
                              kind=kind, reason=reason, duration_s=duration_s)
        await self._publish_log(interaction.guild, kind, interaction.user, target.id, reason, duration_s)
        await interaction.followup.send(f"✅ {kind} appliqué à <@{target.id}>.", ephemeral=True)

    @app_commands.command(name="warn", description="Avertir un membre")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warn(self, i: discord.Interaction, membre: discord.Member, motif: str):
        async def noop(): return None
        await self._apply(i, "warn", membre, motif, noop)

    @app_commands.command(name="warnings", description="Afficher les avertissements d'un membre")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def warnings(self, i: discord.Interaction, membre: discord.User):
        rows = await ms.list_sanctions(i.guild_id, membre.id, "warn", limit=15)
        text = "\n".join(f"`#{r.id}` <t:{int(r.created_at.timestamp())}:d> — {r.reason[:100]}" for r in rows) or "Aucun avertissement."
        await i.response.send_message(embed=discord.Embed(title=f"Avertissements de {membre}", description=text), ephemeral=True)

    @app_commands.command(name="timeout", description="Exclure temporairement un membre")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout(self, i: discord.Interaction, membre: discord.Member, minutes: app_commands.Range[int, 1, 40320], motif: str = "Aucun motif"):
        await self._apply(i, "timeout", membre, motif, lambda: membre.timeout(timedelta(minutes=minutes), reason=motif), minutes * 60)

    @app_commands.command(name="untimeout", description="Lever le timeout d'un membre")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout(self, i: discord.Interaction, membre: discord.Member, motif: str = "Aucun motif"):
        await self._apply(i, "untimeout", membre, motif, lambda: membre.timeout(None, reason=motif))

    @app_commands.command(name="kick", description="Expulser un membre")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(self, i: discord.Interaction, membre: discord.Member, motif: str = "Aucun motif"):
        await self._apply(i, "kick", membre, motif, lambda: membre.kick(reason=motif))

    @app_commands.command(name="ban", description="Bannir un utilisateur")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, i: discord.Interaction, utilisateur: discord.User, motif: str = "Aucun motif"):
        target = i.guild.get_member(utilisateur.id) or utilisateur
        await self._apply(i, "ban", target, motif, lambda: i.guild.ban(utilisateur, reason=motif))

    @app_commands.command(name="unban", description="Débannir un utilisateur (par identifiant)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, i: discord.Interaction, identifiant: str, motif: str = "Aucun motif"):
        if not identifiant.isdigit():
            return await i.response.send_message("❌ Identifiant invalide (chiffres uniquement).", ephemeral=True)
        user = discord.Object(int(identifiant))
        await self._apply(i, "unban", user, motif, lambda: i.guild.unban(user, reason=motif))

    @app_commands.command(name="purge", description="Supprimer des messages récents")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge(self, i: discord.Interaction, nombre: app_commands.Range[int, 1, 100]):
        await i.response.defer(ephemeral=True)
        try:
            deleted = await i.channel.purge(limit=nombre)
        except discord.Forbidden:
            return await i.followup.send("❌ Permission manquante (gérer les messages).", ephemeral=True)
        await self._publish_log(i.guild, "purge", i.user, i.user.id, f"{len(deleted)} messages dans #{i.channel}")
        await i.followup.send(f"✅ {len(deleted)} message(s) supprimé(s).", ephemeral=True)

    @app_commands.command(name="slowmode", description="Définir le mode lent du salon (0 = désactivé)")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(self, i: discord.Interaction, secondes: app_commands.Range[int, 0, 21600]):
        try:
            await i.channel.edit(slowmode_delay=secondes)
        except discord.Forbidden:
            return await i.response.send_message("❌ Permission manquante (gérer les salons).", ephemeral=True)
        await self._publish_log(i.guild, "slowmode", i.user, i.user.id, f"{secondes}s dans #{i.channel}")
        await i.response.send_message(f"✅ Mode lent : {secondes}s.", ephemeral=True)

    async def _set_lock(self, i: discord.Interaction, lock: bool):
        everyone = i.guild.default_role
        try:
            await i.channel.set_permissions(everyone, send_messages=False if lock else None, reason=f"{i.user} : {'lock' if lock else 'unlock'}")
        except discord.Forbidden:
            return await i.response.send_message("❌ Permission manquante (gérer les salons).", ephemeral=True)
        await self._publish_log(i.guild, "lock" if lock else "unlock", i.user, i.user.id, f"#{i.channel}")
        await i.response.send_message("🔒 Salon verrouillé." if lock else "🔓 Salon déverrouillé.", ephemeral=True)

    @app_commands.command(name="lock", description="Verrouiller le salon actuel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, i: discord.Interaction):
        await self._set_lock(i, True)

    @app_commands.command(name="unlock", description="Déverrouiller le salon actuel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, i: discord.Interaction):
        await self._set_lock(i, False)

    @app_commands.command(name="history", description="Historique complet de modération d'un membre")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def history(self, i: discord.Interaction, membre: discord.User):
        rows = await ms.list_sanctions(i.guild_id, membre.id, limit=15)
        text = "\n".join(f"`#{r.id}` **{r.kind}** <t:{int(r.created_at.timestamp())}:d> — {r.reason[:80]}" for r in rows) or "Aucun historique."
        await i.response.send_message(embed=discord.Embed(title=f"Historique de {membre}", description=text), ephemeral=True)

    @app_commands.command(name="modlogs", description="Dernières actions de modération du serveur")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(moderate_members=True)
    async def modlogs(self, i: discord.Interaction):
        rows = await ms.list_sanctions(i.guild_id, limit=15)
        text = "\n".join(f"`#{r.id}` **{r.kind}** <@{r.target_id}> par <@{r.actor_id}> — {r.reason[:60]}" for r in rows) or "Rien pour l'instant."
        await i.response.send_message(embed=discord.Embed(title="Journal de modération", description=text), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
