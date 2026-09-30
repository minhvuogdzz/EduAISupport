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
    gemini_api_key: SecretStr | None = None
    tutor_model: str = "gemini-3.8-flash"
    lightweight_model: str = "gemini-3.5-flash-lite"
    storage_dir: Path = REPO_ROOT / "var" / "storage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
