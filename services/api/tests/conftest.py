"""Shared fixtures.

``db`` runs each storage test twice: against the in-memory database (always, offline) and against
a throwaway database on MongoDB Atlas (``atlas`` marker; skipped when ``MONGODB_URI`` is unset).
The Atlas run doubles as a check that the in-memory fake behaves like the real server.

Atlas tests only ever use ``cavat_test_<12 hex>`` databases; ``cavat.core.db_guard`` enforces that
before the first write and before the cleanup drop (CLAUDE.md rules 12-14).
"""

import os

# The tests that came before the accounts (ACC-1) identify callers with the X-Demo-* headers; the account
# tests switch to AUTH_MODE=accounts with the `accounts_mode` fixture. Set before the settings are read.
os.environ["AUTH_MODE"] = "demo"
# No test reaches a model, even on the owner's machine where services/api/.env holds real keys (a cloud
# session has none): blank keys win over the .env file, so the gateway stays in template-only mode and the
# Hybrid RAG uses its offline embedder. Tests that need a provider pass a fake one.
os.environ["GROQ_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
# Nor the web (WEB-1): tests that look something up pass a fake source.
os.environ["WEB_LOOKUP"] = "off"
os.environ["TTS"] = "off"  # ADR-030: tests never reach a voice server

import pytest  # noqa: E402
from cavat.config import get_settings  # noqa: E402
from cavat.core.db_guard import assert_test_database, drop_test_database, new_test_database_name  # noqa: E402
from cavat.core.memory_db import InMemoryDatabase  # noqa: E402
from cavat.db import ensure_indexes  # noqa: E402
from pymongo import AsyncMongoClient  # noqa: E402


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


@pytest.fixture
def accounts_mode(monkeypatch):
    """AUTH_MODE=accounts with a fixed signing key, for the tests of the accounts (ACC-1)."""
    monkeypatch.setenv("AUTH_MODE", "accounts")
    monkeypatch.setenv("AUTH_SECRET", "test-signing-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
