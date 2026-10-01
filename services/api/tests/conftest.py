"""Shared fixtures.

``db`` runs each storage test twice: against the in-memory database (always, offline) and against
a throwaway database on MongoDB Atlas (``atlas`` marker; skipped when ``MONGODB_URI`` is unset).
The Atlas run doubles as a check that the in-memory fake behaves like the real server.

Atlas tests only ever use ``cavat_test_<12 hex>`` databases; ``cavat.core.db_guard`` enforces that
before the first write and before the cleanup drop (CLAUDE.md rules 12-14).
"""

import pytest
from cavat.config import get_settings
from cavat.core.db_guard import assert_test_database, drop_test_database, new_test_database_name
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from pymongo import AsyncMongoClient


def _mongodb_uri() -> str:
    uri = get_settings().mongodb_uri
    return uri.get_secret_value() if uri else ""


def pytest_collection_modifyitems(config, items):
    if _mongodb_uri():
        return
    skip = pytest.mark.skip(reason="needs MONGODB_URI (MongoDB Atlas)")
    for item in items:
        if "atlas" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(params=["memory", pytest.param("atlas", marks=pytest.mark.atlas)])
async def db(request):
    if request.param == "memory":
        database = InMemoryDatabase()
        await ensure_indexes(database)
        yield database
        return
    client = AsyncMongoClient(_mongodb_uri(), tz_aware=True, serverSelectionTimeoutMS=5000)
    database = client[new_test_database_name()]
    try:
        assert_test_database(database)  # fail before the first write if the name is not a test database
        await ensure_indexes(database)
        yield database
    finally:
        try:
            await drop_test_database(client, database)  # guarded; runs even when the test failed
        finally:
            await client.close()
