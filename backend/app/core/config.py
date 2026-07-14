"""Central configuration for ContextOS, loaded from environment / backend/.env."""
from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
# Load into os.environ too, so non-Settings consumers (e.g. CONTEXTOS_WATCH_DIR) see it.
load_dotenv(_ENV_FILE, override=False)

# backend/.contextos holds local-only state (persistent user id, etc.)
STATE_DIR = Path(__file__).resolve().parents[2] / ".contextos"
STATE_DIR.mkdir(parents=True, exist_ok=True)
_USER_ID_FILE = STATE_DIR / "user_id"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supermemory_base_url: str = "http://localhost:6767"
    supermemory_api_key: str = ""
    contextos_user_id: str = ""

    contextos_host: str = "127.0.0.1"
    contextos_port: int = 8765
    frontend_url: str = "http://localhost:5173"

    # Ambient retrieval tuning
    contextos_surface_threshold: float = 0.42
    contextos_chunk_threshold: float = 0.0

    def resolved_user_id(self) -> str:
        """Return a stable local user id, generating + persisting one on first run."""
        if self.contextos_user_id:
            return self.contextos_user_id
        if _USER_ID_FILE.exists():
            return _USER_ID_FILE.read_text(encoding="utf-8").strip()
        uid = f"local-{uuid.uuid4().hex[:12]}"
        _USER_ID_FILE.write_text(uid, encoding="utf-8")
        return uid


@lru_cache
def get_settings() -> Settings:
    return Settings()
