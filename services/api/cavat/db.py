"""MongoDB Atlas access (async PyMongo). Run `python -m cavat.db` to ping the cluster."""

import asyncio

from pymongo import AsyncMongoClient

from cavat.config import Settings, get_settings

_client: AsyncMongoClient | None = None


class DatabaseNotConfiguredError(RuntimeError):
    pass


def get_client(settings: Settings | None = None) -> AsyncMongoClient:
    global _client
    settings = settings or get_settings()
    uri = settings.mongodb_uri.get_secret_value() if settings.mongodb_uri else ""
    if not uri:
        raise DatabaseNotConfiguredError("MONGODB_URI is not set (services/api/.env)")
    if _client is None:
        _client = AsyncMongoClient(uri, appname="cavat-api", serverSelectionTimeoutMS=5000, tz_aware=True)
    return _client


def get_db(settings: Settings | None = None):
    settings = settings or get_settings()
    return get_client(settings)[settings.mongodb_db]


async def ping(settings: Settings | None = None) -> dict:
    return await get_client(settings).admin.command("ping")


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def _main() -> None:
    try:
        print("MongoDB ping:", await ping())
    except DatabaseNotConfiguredError as exc:
        print("Not configured:", exc)
    finally:
        await close_client()


if __name__ == "__main__":
    asyncio.run(_main())
