def exempt_reason(*, is_owner: bool, is_admin: bool, role_ids: set[int], staff_role_ids: set[int],
                  top_position: int, bot_top_position: int) -> str | None:
    """Pourquoi un membre ne doit PAS être expulsé par le salon piège (None = il peut l'être)."""
    if is_owner:
        return "propriétaire du serveur"
    if is_admin:
        return "administrateur"
    if role_ids & staff_role_ids:
        return "rôle staff"
    if bot_top_position <= top_position:
        return "rôle supérieur ou égal à celui du bot (expulsion impossible)"
    return None
