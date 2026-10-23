"""Secrets et paramètres d'environnement (jamais de token dans le code)."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Env:
    token: str
    database_url: str
    panel_host: str
    panel_port: int
    panel_secret: str
    panel_password: str
    data_dir: str
    cookie_secure: bool
    ip_header: str

def get_env() -> Env:
    """Lit l'environnement à chaque appel (utile pour les tests)."""
    return Env(
        token=os.getenv("DISCORD_TOKEN", ""),
        database_url=os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data.db"),
        panel_host=os.getenv("PANEL_HOST", "127.0.0.1"),
        panel_port=int(os.getenv("PANEL_PORT", "8000")),
        panel_secret=os.getenv("PANEL_SECRET", ""),
        panel_password=os.getenv("PANEL_ADMIN_PASSWORD", ""),
        data_dir=os.getenv("DATA_DIR", "."),
        cookie_secure=os.getenv("PANEL_COOKIE_SECURE", "0") == "1",
        ip_header=os.getenv("PANEL_IP_HEADER", "").strip().lower(),
    )
