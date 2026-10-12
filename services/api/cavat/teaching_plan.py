"""Build the draft teaching plan of the two demo chapters from the teacher's documents (INGEST-3a):
``make teaching-plan``.

Rebuilds each chapter's item bank, then its plan: one node per period of the lesson plan, what it teaches
from the theory and the plan, its items by stage, its mistakes (``ingest.teaching``). Writes the database of
services/api/.env (collections ``item_banks``, ``teaching_plans``): teaching content of the school, a draft
the teacher approves before it is taught. Nothing runs it at startup or in a test.
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections import Counter

from cavat import db
from cavat.config import get_settings
from cavat.modules.ingest.service import PREFIXES, rebuild_plan
from cavat.modules.session.service import DEMO_SCHOOL_ID


def _kind(problem: str) -> str:
    """ "STP-T05: needs at least 1 transfer item(s)" → "needs at least 1 transfer item(s)"."""
    return re.sub(r"^[^:]+:\s*", "", problem)


async def main() -> None:
    settings = get_settings()
    if settings.mongodb_uri is None:
        sys.exit("MONGODB_URI chưa có trong services/api/.env.")
    database = db.get_db(settings)
    print(f"Database: {settings.mongodb_db}")
    for chapter_id in PREFIXES:
        plan = await rebuild_plan(database, DEMO_SCHOOL_ID, chapter_id)
        nodes = plan.package["nodes"]
        print(f"  {chapter_id}: {len(nodes)} bài, kiểm tra cuối chương {len(plan.assessment)} câu")
        for node in nodes:
            items = sum(len(node[k]) for k in ("checks", "completion", "practice", "transfer"))
            print(f"    {node['id']} {node['name']}: {items} câu, {len(node['worked_examples'])} ví dụ")
        print(f"    còn thiếu ({len(plan.problems)}):")
        for kind, count in Counter(_kind(p) for p in plan.problems).most_common():
            print(f"      {count} × {kind}")
        for line in plan.left_out:
            print(f"    không đưa vào: {line}")
    await db.close_client()


if __name__ == "__main__":
    asyncio.run(main())
