#!/usr/bin/env python3
"""Create a private server handoff from existing exports and local API settings."""

from __future__ import annotations

import argparse
import hashlib
import secrets
import shutil
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from cavat.config import Settings  # noqa: E402


def quote(value: str) -> str:
    if "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError("Environment values must be single-line strings")
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("storage", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if not settings.groq_api_key or not settings.groq_api_key.get_secret_value().strip():
        raise SystemExit("Thiếu GROQ_API_KEY trong services/api/.env")
    values = {
        "GROQ_API_KEY": settings.groq_api_key.get_secret_value(),
        "GROQ_MODEL": settings.groq_model,
        "GROQ_STT_MODEL": settings.groq_stt_model,
        "GEMINI_API_KEY": settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else "",
        "TAVILY_API_KEY": settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else "",
        "MONGO_PASSWORD": secrets.token_hex(24),
        "AUTH_SECRET": settings.auth_secret.get_secret_value()
        if settings.auth_secret
        else secrets.token_hex(32),
        "ADMIN_PASSWORD": secrets.token_urlsafe(24),
        "MONGODB_DB": "cavat_prod",
        "PORT": "8080",
        "TTS": "vieneu",
        "VIENEU_VOICE": settings.vieneu_voice,
        "TUTOR_MODELS": settings.tutor_models,
        "WEB_LOOKUP": settings.web_lookup,
        "ALLOW_TUTOR_KNOWLEDGE": str(settings.allow_tutor_knowledge).lower(),
        "MAX_LLM_CALLS_PER_SESSION": str(settings.max_llm_calls_per_session),
        "MAX_LLM_CALLS_PER_CHAPTER": str(settings.max_llm_calls_per_chapter),
        "OBSERVABILITY_ENABLED": "true",
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    handoff = ROOT / "db-dump" / f"handoff-{stamp}"
    handoff.mkdir(mode=0o700)
    (handoff / "db-dump").mkdir(mode=0o700)
    env = handoff / ".env"
    env.touch(mode=0o600, exist_ok=False)
    env.write_text("".join(f"{key}={quote(value)}\n" for key, value in values.items()), encoding="utf-8")
    hashes = []
    for source, name in ((args.database, "cavat-db.tar.gz"), (args.storage, "cavat-storage.tar.gz")):
        target = handoff / "db-dump" / name
        shutil.copyfile(source, target)
        target.chmod(0o600)
        digest = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
        hashes.append(f"{digest}  {name}\n")
    checksum = handoff / "db-dump" / "SHA256SUMS"
    checksum.write_text("".join(hashes), encoding="ascii")
    checksum.chmod(0o600)

    # Package as a single archive for the simplest DevOps handoff
    bundle = ROOT / "db-dump" / f"cavat-handoff-{stamp}.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        tar.add(env, arcname=".env")
        for member in sorted((handoff / "db-dump").iterdir()):
            tar.add(member, arcname=f"db-dump/{member.name}")
    bundle.chmod(0o600)
    latest_bundle = ROOT / "db-dump" / "cavat-handoff-latest.tar.gz"
    shutil.copyfile(bundle, latest_bundle)
    latest_bundle.chmod(0o600)

    print(f"Bàn giao riêng (thư mục): {handoff}")
    print(f"Gói nén một tệp: {bundle}")
    print(f"Gói mới nhất: {latest_bundle}")
    print("DevOps chỉ cần giải nén gói này ở thư mục repo trên server:")
    print("  tar -xzf cavat-handoff-latest.tar.gz")
    print("  docker compose up -d --build")
    print("  sh deploy/import.sh")


if __name__ == "__main__":
    main()
