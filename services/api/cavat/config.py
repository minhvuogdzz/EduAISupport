"""Runtime settings, read from environment variables and services/api/.env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_uri: SecretStr | None = None
    mongodb_db: str = "cavat_dev"
    # Tutor brain (ADR-017): Qwen on Groq. Gemini only for vision/OCR and voice.
    groq_api_key: SecretStr | None = None
    groq_model: str = "qwen/qwen3.8-27b"
    groq_stt_model: str = "whisper-large-v3"
    # ADR-030 voice: the tutor's voice from VieNeu-TTS running locally (`make voice`); off or not running,
    # the browser reads with its own Vietnamese voice.
    tts: Literal["vieneu", "off"] = "vieneu"
    vieneu_url: str = "http://127.0.0.1:8010"
    vieneu_voice: str = ""  # a preset voice of VieNeu (empty: its default)
    gemini_api_key: SecretStr | None = None
    gemini_vision_model: str = "gemini-3.8-flash"
    # Free tier (docs/poc/free-tier-quota.md): 20 requests a day per model. When the first model is rate
    # limited the next one reads (INGEST-1: the owner's 18 documents need 31 pages read by Gemini).
    gemini_vision_fallbacks: tuple[str, ...] = ("gemini-2.5-flash", "gemini-3.5-flash-lite")
    gemini_live_model: str = "gemini-3.8-live"
    gemini_embedding_model: str = "gemini-embedding-001"  # Hybrid RAG vectors (plan v1 5.5.2)
    llama_cloud_api_key: SecretStr | None = None
    # Hard cap on LLM calls per session; above it the tutor runs on approved templates only.
    max_llm_calls_per_session: int = 15
    # "template": approved sentences only (default). "llm": Qwen phrases hints, templates as fallback.
    tutor_renderer: Literal["template", "llm"] = "template"
    # WEB-1 (DI-51): a question the teacher's documents do not answer may be looked up in Vietnamese
    # Wikipedia (the only allowed source); "off" keeps such questions for the teacher.
    web_lookup: Literal["off", "wikipedia"] = "wikipedia"
    storage_dir: Path = REPO_ROOT / "var" / "storage"
    # ACC-1: "accounts": one student, one parent, one teacher log in with a PIN (`make accounts`).
    # "demo": the old X-Demo-* headers, for the offline tests and the in-memory demo only.
    auth_mode: Literal["accounts", "demo"] = "accounts"
    # Key that signs login tokens. Unset: a random key per process (every restart logs everyone out).
    auth_secret: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
