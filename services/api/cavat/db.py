"""MongoDB Atlas access (async PyMongo).

Run `python -m cavat.db` to ping the cluster, `python -m cavat.db --ensure-indexes` to create indexes.
"""

import asyncio
import sys

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


def repository_classes() -> tuple[type, ...]:
    """Every repository, one per collection. Imported lazily so modules never import this file."""
    from cavat.modules.assessment.repository import EvidenceRepository
    from cavat.modules.content.repository import LessonRepository
    from cavat.modules.identity.repository import UserRepository
    from cavat.modules.ingest.repository import ItemBankRepository
    from cavat.modules.learner.repository import StudentKCStateRepository
    from cavat.modules.library.repository import DocumentRepository
    from cavat.modules.org.repository import ClassRepository, EnrollmentRepository, SchoolRepository
    from cavat.modules.scheduling.repository import ScheduleRepository
    from cavat.modules.session.repository import EventRepository, LearningSessionRepository

    return (
        SchoolRepository,
        UserRepository,
        ClassRepository,
        EnrollmentRepository,
        LessonRepository,
        ScheduleRepository,
        LearningSessionRepository,
        EventRepository,
        EvidenceRepository,
        StudentKCStateRepository,
        DocumentRepository,
        ItemBankRepository,
    )


async def ensure_indexes(database=None) -> dict[str, list[str]]:
    """Create every declared index (idempotent). Accepts the Atlas database or an in-memory one."""
    database = get_db() if database is None else database
    return {repo.collection_name: await repo.ensure_indexes(database) for repo in repository_classes()}


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


async def _main() -> None:
    try:
        print("MongoDB ping:", await ping())
        if "--ensure-indexes" in sys.argv[1:]:
            for collection, names in (await ensure_indexes()).items():
                print(f"{collection}: {', '.join(names) or '(only _id)'}")
    except DatabaseNotConfiguredError as exc:
        print("Not configured:", exc)
    finally:
        await close_client()


if __name__ == "__main__":
    asyncio.run(_main())
