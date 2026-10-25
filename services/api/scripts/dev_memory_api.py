"""Run the API on an in-memory database: ``make api-memory`` (and the API half of ``make demo``).

For trying the web app (``make web-live``) without MongoDB Atlas. Nothing is written to ``cavat_dev``
and every session is lost when the process stops. No demo data is created (CLAUDE.md rules 11 and 16).
The port is 8000 unless ``CAVAT_API_PORT`` says otherwise.
"""

import asyncio
import os

import uvicorn
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session.api import get_database


async def _trial_accounts(database: InMemoryDatabase) -> None:
    """``CAVAT_MEMORY_ACCOUNTS=1``: the fixed accounts of `make accounts` (student Vuong, a parent, a teacher;
    every PIN 1234) in the in-memory database only, to try the login without Atlas."""
    from cavat.modules.identity.accounts import FIXED_LOGINS, hash_pin
    from cavat.modules.identity.repository import User, UserRepository
    from cavat.modules.session.service import DEMO_SCHOOL_ID

    repo = UserRepository(database, DEMO_SCHOOL_ID)
    student = await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="STUDENT",
            login_name=FIXED_LOGINS["STUDENT"],
            display_name="Vuong",
            grade=5,
            pin_hash=hash_pin("1234"),
        )
    )
    await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="PARENT",
            login_name=FIXED_LOGINS["PARENT"],
            display_name="Phụ huynh Vuong",
            pin_hash=hash_pin("1234"),
            child_id=student.id,
        )
    )
    await repo.save(
        User(
            school_id=DEMO_SCHOOL_ID,
            kind="TEACHER",
            login_name=FIXED_LOGINS["TEACHER"],
            display_name="Giáo viên Vuong",
            pin_hash=hash_pin("1234"),
        )
    )


def main() -> None:
    database = InMemoryDatabase()
    asyncio.run(ensure_indexes(database))
    if os.environ.get("CAVAT_MEMORY_ACCOUNTS") == "1":
        asyncio.run(_trial_accounts(database))
    app.dependency_overrides[get_database] = lambda: database
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("CAVAT_API_PORT", "8000")))


if __name__ == "__main__":
    main()
