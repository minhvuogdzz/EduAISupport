"""Draft with Qwen what the teacher's documents leave out, and check it (INGEST-3b): ``make draft-teaching``.

Rebuilds each chapter's plan (``make teaching-plan``), then asks Qwen for the hint ladders of the practice
items and for the answers, accepted phrasings and key ideas of each period; every draft goes through the
checks of ``ingest.drafting`` and only what passes enters the plan, which stays a DRAFT for the teacher.
Uses the free-tier quota, cached on disk: building again is free, and a run the quota stops goes on from
the cache the next day. With ``draft-hints.v2.md`` the hints of the two chapters are about 116 requests (1 500
prompt tokens each, 190 000 in all, and the answers): more than the 200 000 tokens a day of the free tier, so
set GROQ_API_KEY_EVAL (another Groq project) or let it run over two days (REFORM-3).
Writes the database of services/api/.env. Nothing runs it at startup or in a test.
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter

from cavat import db
from cavat.config import get_settings
from cavat.modules.ai_gateway.router import build_router
from cavat.modules.ingest.drafting import Draft, Drafter, summary
from cavat.modules.ingest.service import PREFIXES, rebuild_plan
from cavat.modules.session.service import DEMO_SCHOOL_ID

LABELS = {
    "HINT": "gợi ý",
    "REPLY": "câu trả lời mẫu",
    "ACCEPT": "cách nói được chấp nhận",
    "KEY_IDEA": "ý chính",
    "ASK": "câu hỏi gợi mở",
    "VERIFY": "câu hỏi vì sao của tiết",
}


async def main() -> None:
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    if settings.groq_api_key is None or not settings.groq_api_key.get_secret_value():
        sys.exit("GROQ_API_KEY chưa có trong services/api/.env.")
    # ONLY=VERIFY (FIX-3): only these kinds may call Qwen; the other drafts come from the cache, and what the
    # cache no longer has stays as it is in the stored plan.
    only = frozenset(k for k in sys.argv[1].split(",") if k) if len(sys.argv) > 1 and sys.argv[1] else None
    drafter = Drafter(
        build_router(settings, for_eval=True), settings.storage_dir / "cache" / "drafts", pause=8.0, only=only
    )
    database = db.get_db(settings)
    print(f"Database: {settings.mongodb_db}")
    for chapter_id in PREFIXES:
        plan = await rebuild_plan(database, DEMO_SCHOOL_ID, chapter_id, drafter)
        drafts = [Draft(**d) for d in plan.drafts]
        print(f"  {chapter_id}: còn thiếu {len(plan.problems)}")
        for kind, row in summary(drafts).items():
            print(f"    {LABELS.get(kind, kind)}: giữ {row['kept']}, loại {row['refused']}")
        refused = Counter(code for d in drafts if not d.ok for code in d.codes)
        if refused:
            print("    lý do loại: " + ", ".join(f"{k} {v}" for k, v in refused.most_common()))
        for kind, count in Counter(re.sub(r"^[^:]+:\s*", "", p) for p in plan.problems).most_common():
            print(f"    còn thiếu {count} × {kind}")
    print(f"  Lần gọi model (không tính bộ đệm): {drafter.calls}")
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
