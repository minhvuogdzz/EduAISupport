#!/bin/sh
# Create the indexes the repositories declare (idempotent, the same as `make db-indexes`), then run what the
# container was asked to run: the API by default, or a one-off command such as
#   docker compose run --rm app python -m cavat.restore /dump/cavat-db-....tar.gz
set -eu
if [ "${1:-}" = uvicorn ]; then
  python - <<'PY'
import asyncio
from cavat import db

async def prepare():
    try:
        await db.ping()
        await db.ensure_indexes()
    finally:
        await db.close_client()

asyncio.run(prepare())
PY
fi
exec "$@"
