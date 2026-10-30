#!/usr/bin/env python3
"""Create a private server handoff from existing exports and local API settings."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import tarfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from cavat.config import Settings  # noqa: E402


def copy_release_source(root: Path, destination: Path) -> str:
    """Only committed source, never the working tree's keys, runtime data or dependencies."""
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    if dirty.strip():
        raise ValueError("Commit/merge các thay đổi trước khi tạo gói có mã nguồn.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    with subprocess.Popen(
        ["git", "archive", "--format=tar", revision], cwd=root, stdout=subprocess.PIPE
    ) as proc:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
            for member in archive:
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                    raise ValueError(f"Unsafe source member: {member.name}")
                target = destination / path
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as inp, target.open("xb") as out:
                        shutil.copyfileobj(inp, out)
                    target.chmod(member.mode & 0o777)
        if proc.wait() != 0:
            raise ValueError("git archive failed")
    return revision


def quote(value: str) -> str:
    if "\n" in value or "\r" in value or "\x00" in value:
        raise ValueError("Environment values must be single-line strings")
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("storage", type=Path)
    parser.add_argument(
        "--include-source", action="store_true", help="Gói đầy đủ: mã nguồn đã commit + cấu hình + dữ liệu"
    )
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
        "ADMIN_PASSWORD": settings.admin_password.get_secret_value()
        if settings.admin_password.get_secret_value() != "1234"
        else secrets.token_urlsafe(24),
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
        "TUTOR_CHOOSER": settings.tutor_chooser,
        "TUTOR_MENTOR_MODEL": settings.tutor_mentor_model,
        "GEMINI_TUTOR_FALLBACKS": json.dumps(settings.gemini_tutor_fallbacks),
        "GEMINI_VISION_MODEL": settings.gemini_vision_model,
        "GEMINI_VISION_FALLBACKS": json.dumps(settings.gemini_vision_fallbacks),
        "GEMINI_EMBEDDING_MODEL": settings.gemini_embedding_model,
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    handoff = ROOT / "db-dump" / f"handoff-{stamp}"
    handoff.mkdir(mode=0o700)
    if args.include_source:
        values["CAVAT_REVISION"] = copy_release_source(ROOT, handoff)
    (handoff / "db-dump").mkdir(mode=0o700, exist_ok=True)
    env = handoff / ".env"
    env.touch(mode=0o600, exist_ok=False)
    env.write_text("".join(f"{key}={quote(value)}\n" for key, value in values.items()), encoding="utf-8")
    hashes = []
    for source, name in ((args.database, "cavat-db.tar.gz"), (args.storage, "cavat-storage.tar.gz")):
        target = handoff / "db-dump" / name
        shutil.copyfile(source, target)
        target.chmod(0o600)
        with target.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        hashes.append(f"{digest}  {name}\n")
    checksum = handoff / "db-dump" / "SHA256SUMS"
    checksum.write_text("".join(hashes), encoding="ascii")
    checksum.chmod(0o600)
    if args.include_source:
        (handoff / "RELEASE.json").write_text(
            json.dumps(
                {
                    "revision": values["CAVAT_REVISION"],
                    "created_at": stamp,
                    "database": "db-dump/cavat-db.tar.gz",
                    "storage": "db-dump/cavat-storage.tar.gz",
                    "commands": ["docker compose build --pull", "sh deploy/import.sh"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    # Package as a single archive for the simplest DevOps handoff
    bundle = ROOT / "db-dump" / f"cavat-handoff-{stamp}.tar.gz"
    with tarfile.open(bundle, "w:gz") as tar:
        if args.include_source:
            for member in sorted(handoff.iterdir()):
                tar.add(member, arcname=member.name)
        else:
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
    print("DevOps giải nén gói đầy đủ vào THƯ MỤC MỚI, sau đó chạy:")
    if not args.include_source:
        print("  python3 deploy/unpack_handoff.py cavat-handoff-latest.tar.gz (gói chỉ có dữ liệu/cấu hình)")
    print("  docker compose build --pull")
    print("  sh deploy/import.sh")


if __name__ == "__main__":
    main()
