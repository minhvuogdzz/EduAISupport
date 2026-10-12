"""Build the draft item bank of the two demo chapters from the teacher's documents (INGEST-2):
``make item-bank``.

Reads the documents imported in the database of services/api/.env (``make library-import``), cuts the
exercises, worksheets and tests into items, checks every answer against its question, and keeps one bank
per chapter (collection ``item_banks``). It writes teaching content of the school, not learner or demo
data. Nothing runs it at startup or in a test.
"""

from __future__ import annotations

import asyncio
import sys

from cavat import db
from cavat.config import get_settings
from cavat.modules.ingest.service import PREFIXES, rebuild
from cavat.modules.session.service import DEMO_SCHOOL_ID

LABELS = {
    "VERIFIED": "đã kiểm, khớp",
    "REVIEW": "đáp án khớp, cần xem lời giải",
    "CONFLICT": "mâu thuẫn",
    "DISPUTED": "số đọc chưa chắc",
    "UNCHECKED": "chưa kiểm được",
    "NO_ANSWER": "chưa có đáp án",
}


async def main() -> None:
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    database = db.get_db(settings)
    print(f"Database: {settings.mongodb_db}")
    for chapter_id in PREFIXES:
        bank = await rebuild(database, DEMO_SCHOOL_ID, chapter_id)
        stats = bank.stats
        print(f"  {chapter_id}: {stats['items']} câu")
        for status, label in LABELS.items():
            if stats.get(status):
                print(f"    {label}: {stats[status]}")
        for item in bank.items:
            if item["status"] in ("REVIEW", "CONFLICT", "DISPUTED", "NO_ANSWER"):
                wrong = [f["detail"] for f in item["findings"] if not f["ok"]]
                why = "; ".join(wrong) or item["answer"][:60]
                print(f"    - {item['item_id']} ({LABELS[item['status']]}): {why}")
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
