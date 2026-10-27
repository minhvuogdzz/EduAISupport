"""Runtime settings, read from environment variables and services/api/.env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    mongodb_uri: SecretStr | None = None
    mongodb_db: str = "cavat_dev"
    # Tutor brain (ADR-017): Qwen on Groq; the router's default chain reads its name from here.
    # Gemini only for vision/OCR and the RAG vectors.
    groq_api_key: SecretStr | None = None
    groq_model: str = "qwen/qwen3.8-27b"
    # CFG-3: a key of another Groq project for the evaluations, the simulated child and the batch drafts
    # (`for_eval` in ``build_router``), so they spend that project's quota and not the child's. Unset: the
    # same key as GROQ_API_KEY. Quota is per organization: a key of the same project changes nothing.
    groq_api_key_eval: SecretStr | None = None
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
    gemini_embedding_model: str = "gemini-embedding-001"  # Hybrid RAG vectors (plan v1 5.5.2)
    # BRAIN-1 (ADR-034): the models that write the tutor's words, first to last, comma separated
    # ("openai/gpt-oss-120b,qwen/qwen3.8-27b"). A name that starts with "gemini" is answered by the Gemini
    # key. Empty: the router's default chain (see ``default_chat_chains``). One line changes the voice.
    tutor_models: str = ""
    # Hard cap on LLM calls per session; above it the tutor runs on approved templates only. DI-71 (REFORM-1):
    # 40, from 15. A Qwen call spends 1.126 token on average (prompt and output, measured 2026-10-25; the
    # prompt <= 3.000, reasoning off): a full session about 45.000 of the 200.000 token a day of a Groq
    # project, at worst (2.600 a call) 104.000 (docs/poc/free-tier-quota.md).
    max_llm_calls_per_session: int = 40
    # DI-90: a chapter has 7–8 lessons; its voice must not disappear during lesson one.
    max_llm_calls_per_chapter: int = 160
    # "template": approved sentences only. "llm": Qwen phrases the moves, templates as fallback. REFORM-1:
    # unset, it is "llm" when a Groq key is set and "template" without one (the tests blank the key).
    tutor_renderer: Literal["template", "llm"] = "template"
    # AUTO-1 (ADR-031): with the LLM tutor, Qwen picks one of the moves the policy allows on a turn;
    # "policy" keeps the policy's own move (the ablation of AUTO-1).
    tutor_chooser: Literal["policy", "llm"] = "llm"
    # BRAIN-2 (ADR-038): related theory missing in the RAG may use verified official publications.
    # "wikipedia" keeps the legacy adapter with the same lesson scope gate; "off" disables web lookup.
    web_lookup: Literal["off", "official", "wikipedia"] = "official"
    storage_dir: Path = REPO_ROOT / "var" / "storage"
    # ACC-1: "accounts": one student, one parent, one teacher log in with a PIN (`make accounts`).
    # "demo": the old X-Demo-* headers, for the offline tests and the in-memory demo only.
    auth_mode: Literal["accounts", "demo"] = "accounts"
    # Key that signs login tokens. Unset: a random key per process (every restart logs everyone out).
    auth_secret: SecretStr | None = None
    # REL-1 (ADR-035): one port. The API serves the web app that `make run` built in this folder, with
    # index.html for the app's own paths; no build there, it is the API alone (the dev server on 5173).
    web_dist: Path = REPO_ROOT / "apps" / "web" / "dist"
    # /docs, /redoc and /openapi.json are off unless API_DOCS=1: a public address should not list the API.
    api_docs: bool = False

    @model_validator(mode="after")
    def _renderer_from_key(self) -> Settings:
        if "tutor_renderer" not in self.model_fields_set:
            key = self.groq_api_key.get_secret_value().strip() if self.groq_api_key else ""
            self.tutor_renderer = "llm" if key else "template"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
