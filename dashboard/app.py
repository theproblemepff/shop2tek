import hmac
import math
import time
from collections import defaultdict
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature
from config.settings import get_env
from services import config_service, stats_service, export_service
from services.help_texts import COMMAND_HELP, FIELD_HELP, SECTION_HELP, PLACEHOLDERS

STATIC = Path(__file__).parent / "static"
_attempts: dict[str, list[float]] = defaultdict(list)

def client_ip(request: Request) -> str:
    """IP utilisée pour limiter les essais de connexion.
    Derrière un hébergeur, PANEL_IP_HEADER désigne l'en-tête fiable (ex. fly-client-ip, x-forwarded-for).
    Pour x-forwarded-for on prend la DERNIÈRE valeur : c'est celle ajoutée par le proxy, non falsifiable par le visiteur."""
    header = get_env().ip_header
    if header:
        value = request.headers.get(header, "")
        if value:
            return value.split(",")[-1].strip()
    return request.client.host if request.client else "?"

def create_app(bot=None) -> FastAPI:
    env = get_env()
    app = FastAPI(title="Panel", docs_url=None, redoc_url=None)
    signer = URLSafeTimedSerializer(env.panel_secret or "dev-insecure")

    def require_admin(request: Request):
        try:
            signer.loads(request.cookies.get("session", ""), max_age=8 * 3600)
        except BadSignature:
            raise HTTPException(401, "Non authentifié")

    @app.post("/api/login")
    async def login(request: Request, body: dict):
        ip = client_ip(request)
        _attempts[ip] = [t for t in _attempts[ip] if time.time() - t < 300]
        if len(_attempts[ip]) >= 5:
            raise HTTPException(429, "Trop de tentatives")
        pw = str(body.get("password", ""))
        if not env.panel_password or not hmac.compare_digest(pw, env.panel_password):
            _attempts[ip].append(time.time())
            raise HTTPException(401, "Mot de passe invalide")
        resp = JSONResponse({"ok": True})
        resp.set_cookie("session", signer.dumps("admin"), httponly=True, samesite="strict", secure=env.cookie_secure, max_age=8 * 3600)
        return resp

    @app.get("/api/status", dependencies=[Depends(require_admin)])
    async def status():
        if bot is None or not bot.is_ready():
            return {"bot": "déconnecté", "modules": getattr(bot, "module_status", {})}
        lat = bot.latency
        return {"bot": "connecté", "user": str(bot.user), "guilds": len(bot.guilds),
                "latency_ms": round(lat * 1000) if math.isfinite(lat) else None,
                "modules": bot.module_status}

    @app.get("/api/config", dependencies=[Depends(require_admin)])
    async def read_config():
        return config_service.to_public(await config_service.get_config())

    @app.put("/api/config/{section}", dependencies=[Depends(require_admin)])
    async def write_config(section: str, body: dict):
        try:
            return config_service.public_section(section, await config_service.update_section(section, body))
        except KeyError:
            raise HTTPException(404, "Section inconnue")
        except ValueError as e:
            raise HTTPException(422, str(e))

    def pick_guild(gid: int):
        if bot is None or not bot.is_ready():
            return None
        return bot.get_guild(gid) if gid else (bot.guilds[0] if bot.guilds else None)

    @app.get("/api/help", dependencies=[Depends(require_admin)])
    async def help_texts():
        return {"sections": SECTION_HELP, "fields": FIELD_HELP, "placeholders": PLACEHOLDERS}

    @app.get("/api/guild", dependencies=[Depends(require_admin)])
    async def guild_info():
        cfg = await config_service.get_config()
        ready = bot is not None and bot.is_ready()
        guilds = [{"id": str(g.id), "name": g.name} for g in bot.guilds] if ready else []
        g = pick_guild(cfg["general"]["guild_id"])
        if g is None:
            return {"available": False, "guilds": guilds, "channels": [], "roles": []}
        return {"available": True, "guilds": guilds, "name": g.name, "member_count": g.member_count,
                "channels": [{"id": str(c.id), "name": c.name} for c in g.text_channels],
                "roles": [{"id": str(r.id), "name": r.name} for r in sorted(g.roles, key=lambda r: -r.position) if not r.is_default()]}

    @app.get("/api/commands", dependencies=[Depends(require_admin)])
    async def commands_list():
        live = {c.name: c.description for c in bot.tree.get_commands()} if bot is not None else {}
        out = [{**c, "loaded": (c["name"] in live) if bot is not None else None} for c in COMMAND_HELP]
        known = {c["name"] for c in COMMAND_HELP}
        out += [{"name": n, "category": "Autres", "permission": "", "description": d, "usage": "/" + n,
                 "example": "", "loaded": True} for n, d in live.items() if n not in known]
        return out

    @app.get("/api/stats", dependencies=[Depends(require_admin)])
    async def stats():
        return await stats_service.overview()

    @app.get("/api/logs", dependencies=[Depends(require_admin)])
    async def logs(kind: str = "", result: str = "", limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return await stats_service.page_logs(kind, result, limit, offset)

    @app.get("/api/sanctions", dependencies=[Depends(require_admin)])
    async def sanctions(kind: str = "", target: str = "", limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return await stats_service.page_sanctions(kind, target, limit, offset)

    @app.get("/api/members", dependencies=[Depends(require_admin)])
    async def members(q: str = "", verified: str = "", limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return await stats_service.page_members(q, limit, offset, verified == "1")

    @app.get("/api/ids/export.txt", dependencies=[Depends(require_admin)])
    async def ids_export(scope: str = "verified"):
        ids = await (export_service.all_ids() if scope == "all" else export_service.verified_ids())
        name = "ids_tous.txt" if scope == "all" else "ids_verifies.txt"
        return PlainTextResponse("".join(f"{i}\n" for i in ids), headers={"Content-Disposition": f'attachment; filename="{name}"'})

    @app.post("/api/ids/sync", dependencies=[Depends(require_admin)])
    async def ids_sync():
        path, count = await export_service.sync_verified_ids()
        return {"path": str(path), "count": count}

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    return app
