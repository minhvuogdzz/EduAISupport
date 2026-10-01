"""Safety guard for tests that touch MongoDB Atlas (CLAUDE.md rules 12-14, 20).

The guard is an **allow-list**: only database names in the ``cavat_test`` family pass, everything
else is refused. There is deliberately no deny-list, so no real database name is hard-coded here.

Allowed names:
    cavat_test                  a shared test database
    cavat_test_<12 hex chars>   a throwaway database for one test (what the fixtures use)
"""

from __future__ import annotations

import re
import uuid
from typing import Any

TEST_DATABASE_PATTERN = re.compile(r"cavat_test(?:_[0-9a-f]{12})?")


class UnsafeDatabaseError(RuntimeError):
    """A test was about to write to, or drop, a database outside the cavat_test family."""


def new_test_database_name() -> str:
    """A fresh throwaway database name, e.g. ``cavat_test_3fa9c1d20b7e``."""
    return f"cavat_test_{uuid.uuid4().hex[:12]}"


def is_test_database(name: object) -> bool:
    return isinstance(name, str) and TEST_DATABASE_PATTERN.fullmatch(name) is not None


def assert_test_database(database: Any) -> str:
    """Return the database name if it is in the test family, else raise ``UnsafeDatabaseError``.

    Accepts a plain name or any object with a ``name`` attribute (a PyMongo database). Call this
    before the first write or drop of every Atlas test.
    """
    name = database if isinstance(database, str) else getattr(database, "name", None)
    if not is_test_database(name):
        raise UnsafeDatabaseError(
            f"refusing to touch database {name!r}: Atlas tests may only use "
            "'cavat_test' or 'cavat_test_<12 hex chars>' (CLAUDE.md rules 12-13)"
        )
    return name


async def drop_test_database(client: Any, database: Any) -> None:
    """Drop a test database, but only after the guard has accepted its name."""
    await client.drop_database(assert_test_database(database))
