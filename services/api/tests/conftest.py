"""Shared fixtures.

``db`` runs each storage test twice: against the in-memory database (always, offline) and against
a throwaway database on MongoDB Atlas (``atlas`` marker; skipped when ``MONGODB_URI`` is unset).
The Atlas run doubles as a check that the in-memory fake behaves like the real server.
"""

import uuid

import pytest
from cavat.config import get_settings
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
    database = client[f"cavat_test_{uuid.uuid4().hex[:12]}"]
    try:
        await ensure_indexes(database)
        yield database
    finally:
        await client.drop_database(database.name)
        await client.close()
