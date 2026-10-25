"""What the model calls of the real sessions cost: model, tokens, 429s and their limit (CFG-3, ADR-032).

Usage: ``make model-usage`` (the last 7 days), ``make model-usage DAYS=1``, ``make model-usage SESSION=<id>``.
Reads the database of services/api/.env and writes nothing, so it is safe after a test day with students.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta

from cavat import db
from cavat.config import get_settings
from cavat.core.repository import utc_now
from cavat.modules.session import model_usage
from cavat.modules.session.service import DEMO_SCHOOL_ID


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=float, default=7, help="sessions updated in the last N days")
    parser.add_argument("--session", help="one session by id (instead of --days)")
    args = parser.parse_args()
    settings = get_settings()
    print(f"Database: {settings.mongodb_db} (chỉ đọc)")

    async def read() -> list[dict]:
        database = db.get_db(settings)
        try:
            since = utc_now() - timedelta(days=args.days)
            return await model_usage.load(database, DEMO_SCHOOL_ID, since=since, session_id=args.session)
        finally:
            await db.close_client()

    docs = asyncio.run(read())
    print(model_usage.render(model_usage.summarize(docs)) if docs else "Không có buổi học nào.")


if __name__ == "__main__":
    main()
