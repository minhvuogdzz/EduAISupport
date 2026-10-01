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


def main() -> None:
    database = InMemoryDatabase()
    asyncio.run(ensure_indexes(database))
    app.dependency_overrides[get_database] = lambda: database
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("CAVAT_API_PORT", "8000")))


if __name__ == "__main__":
    main()
