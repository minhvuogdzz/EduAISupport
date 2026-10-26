"""Back up the database to files: `make backup` (REL-1, ADR-035).

Atlas M0 has no automatic backup, so before and after a trial with students the owner exports every
collection of the database of services/api/.env (accounts, sessions and their events, evidence, knowledge
states, teaching plans, item banks, the teacher's documents...) to
``var/storage/backups/<time>/<collection>.jsonl``. One JSON document per line in MongoDB's extended JSON
(relaxed), so dates and ids keep their type when read back with ``bson.json_util.loads`` or ``mongoimport``.

It only reads: no write, no index, no delete in the database (CLAUDE.md rules 11 and 25). The files hold the
accounts (PIN as a scrypt hash, never the PIN) and what the children said: they stay on this machine, readable
by its owner only. The original files of the library and the audio are in ``var/storage/`` itself: copy that
folder too. How to restore: docs/pilot/README.md ("Khôi phục").
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import json_util

from cavat import db
from cavat.config import Settings, get_settings

MANIFEST = "manifest.json"


def backup_dir(settings: Settings, now: datetime | None = None) -> Path:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return settings.storage_dir / "backups" / stamp


def _line(doc: dict[str, Any]) -> str:
    return json_util.dumps(doc, json_options=json_util.RELAXED_JSON_OPTIONS, ensure_ascii=False)


async def export_database(database: Any, out_dir: Path) -> dict[str, int]:
    """Write every collection of ``database`` to ``out_dir`` (a new folder); how many documents each had."""
    out_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    counts: dict[str, int] = {}
    for name in sorted(await database.list_collection_names()):
        if name.startswith("system."):
            continue
        count = 0
        # O_EXCL: never over a file that is there; 0600: this folder holds the children's words
        fd = os.open(out_dir / f"{name}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            async for doc in database[name].find({}):
                out.write(_line(doc) + "\n")
                count += 1
        counts[name] = count
    manifest = {
        "database": getattr(database, "name", None),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "format": "one document per line, MongoDB extended JSON (relaxed)",
        "documents": counts,
    }
    fd = os.open(out_dir / MANIFEST, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write(_line(manifest) + "\n")
    return counts


async def main() -> int:
    settings = get_settings()
    if settings.mongodb_uri is None:
        print("MONGODB_URI chưa có trong services/api/.env.")
        return 1
    out_dir = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else backup_dir(settings)
    print(f"Database: {settings.mongodb_db} (chỉ đọc, không ghi gì vào database)")
    try:
        counts = await export_database(db.get_db(settings), out_dir)
    finally:
        await db.close_client()
    width = max((len(name) for name in counts), default=0)
    for name, count in counts.items():
        print(f"  {name:<{width}}  {count:>7}")
    print(f"Đã sao lưu {sum(counts.values())} bản ghi của {len(counts)} bộ sưu tập vào {out_dir}")
    print("Thư mục này có tài khoản và lời các em nói: giữ trên máy này.")
    print("Chép cả var/storage (tài liệu gốc, âm thanh): sao lưu này chỉ có database.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
