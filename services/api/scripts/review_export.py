"""Export the teacher's review decisions of every chapter (``make review-export``), read-only.

Writes ``var/storage/reports/<date>-review-decisions.json`` (gitignored: it quotes the teacher's documents):
for each chapter the published version, the chapter test, what was left out, and every decision with who
made it, when and why. Evidence for the thesis that the teacher (or Claude on the teacher's authority, see
``evals/reports/2026-10-12-review-log.md``) controls what is taught.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from cavat import db
from cavat.config import get_settings
from cavat.modules.ingest.repository import TeachingPlanRepository
from cavat.modules.ingest.service import PREFIXES
from cavat.modules.session.service import DEMO_SCHOOL_ID


async def main() -> None:
    settings = get_settings()
    database = db.get_db(settings)
    repo = TeachingPlanRepository(database, DEMO_SCHOOL_ID)
    out = {}
    for chapter_id in PREFIXES:
        plan = await repo.get(chapter_id)
        if plan is not None:
            out[chapter_id] = {
                "published": plan.current,
                "versions": sorted(plan.published),
                "assessment": plan.assessment,
                "left_out": plan.left_out,
                "decisions": dict(sorted(plan.decisions.items())),
            }
    await db.close_client()
    path = settings.storage_dir / "reports" / f"{datetime.now(UTC):%Y-%m-%d}-review-decisions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"Database: {settings.mongodb_db} → {path}")
    for chapter_id, data in out.items():
        print(f"  {chapter_id}: {len(data['decisions'])} quyết định, bản dạy {data['published']}")


if __name__ == "__main__":
    asyncio.run(main())
