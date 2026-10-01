"""Runtime settings, read from environment variables and services/api/.env."""

from functools import lru_cache
from pathlib import Path

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
    gemini_api_key: SecretStr | None = None
    gemini_vision_model: str = "gemini-3.8-flash"
    gemini_live_model: str = "gemini-3.8-live"
    llama_cloud_api_key: SecretStr | None = None
    # Hard cap on LLM calls per session; above it the tutor runs on approved templates only.
    max_llm_calls_per_session: int = 15
    storage_dir: Path = REPO_ROOT / "var" / "storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
