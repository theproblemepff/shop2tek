"""Configuration persistante partagée entre le bot et le panel (source unique : la base)."""
from copy import deepcopy
from database.models import Setting
from database.session import session

DEFAULTS: dict = {
    "general": {"guild_id": 0, "language": "fr", "accent": "#7c5cff"},
    "roles": {"admin": [], "staff": [], "member": 0, "unverified": 0},
    "channels": {"welcome": 0, "goodbye": 0, "verification": 0, "logs": 0},
    "welcome": {
        "enabled": True,
        "title": "Bienvenue {user} !",
        "description": "Tu es le membre n°{count} de {server}. Lis le règlement puis vérifie-toi.",
        "color": "#7c5cff",
        "show_avatar": True,
    },
    "verification": {
        "enabled": False,
        "mode": "button",  # button | rules | question
        "title": "Vérification",
        "description": "Clique sur le bouton pour accéder au serveur.",
        "button_label": "Se vérifier",
        "question": "",
        "answers": [],
        "max_attempts": 3,
        "timeout_minutes": 0,
        "on_timeout": "none",  # none | kick
    },
    "goodbye": {"enabled": True, "message": "{username} a quitté le serveur."},
    "honeypot": {
        "enabled": False,
        "simulate": True,
        "channel": 0,
        "warning_text": "⚠️ Ne rien écrire dans ce salon : tout message entraîne une expulsion automatique du serveur.",
    },
}

# Les identifiants Discord dépassent 2^53 : le navigateur les déformerait en nombres.
# L'API les expose donc en texte et les convertit en entiers à l'enregistrement.
ID_KEYS: dict[str, set[str]] = {
    "general": {"guild_id"},
    "roles": {"admin", "staff", "member", "unverified"},
    "channels": {"welcome", "goodbye", "verification", "logs"},
    "honeypot": {"channel"},
}

def _coerce_ids(section: str, values: dict) -> dict:
    out = dict(values)
    for k in ID_KEYS.get(section, ()):
        if k not in out:
            continue
        v = out[k]
        try:
            out[k] = [int(x) for x in v] if isinstance(v, list) else int(v or 0)
        except (TypeError, ValueError):
            raise ValueError(f"{k} : identifiant invalide (chiffres uniquement)")
        if any(n < 0 for n in (out[k] if isinstance(out[k], list) else [out[k]])):
            raise ValueError(f"{k} : identifiant invalide")
    return out

def public_section(section: str, values: dict) -> dict:
    out = deepcopy(values)
    for k in ID_KEYS.get(section, ()):
        if k in out:
            out[k] = [str(x) for x in out[k]] if isinstance(out[k], list) else str(out[k])
    return out

def to_public(cfg: dict) -> dict:
    return {sec: public_section(sec, vals) for sec, vals in cfg.items()}

def _merge(base: dict, over: dict) -> dict:
    out = deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out

async def get_config() -> dict:
    cfg = deepcopy(DEFAULTS)
    async with session() as s:
        for row in (await s.execute(Setting.__table__.select())).all():
            if row.key in cfg and isinstance(row.value, dict):
                cfg[row.key] = _merge(cfg[row.key], row.value)
    return cfg

async def update_section(section: str, values: dict) -> dict:
    if section not in DEFAULTS:
        raise KeyError(section)
    unknown = set(values) - set(DEFAULTS[section])
    if unknown:
        raise ValueError(f"Clés inconnues : {sorted(unknown)}")
    values = _coerce_ids(section, values)
    async with session() as s:
        row = await s.get(Setting, section)
        merged = _merge(row.value if row else {}, values)
        if row:
            row.value = merged
        else:
            s.add(Setting(key=section, value=merged))
        await s.commit()
    return (await get_config())[section]
