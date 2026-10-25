"""The published plans are read once per database, not once per request (they are megabytes)."""

import asyncio
from types import SimpleNamespace

import pytest
from cavat.modules.session import chapter_service


class Plans:
    def __init__(self):
        self.reads = 0

    def find(self, *_a, **_k):
        self.reads += 1
        return self

    def sort(self, *_a, **_k):
        return self

    async def to_list(self, *_a, **_k):
        return []


class Database:
    """What ``get_db()`` gives: a new object for every request, on the same client and name."""

    def __init__(self, client, plans):
        self.client, self.name, self.plans = client, "cavat_cache_test", plans

    def __getitem__(self, _name):
        return self.plans


def test_a_new_database_object_per_request_reads_the_plans_once(monkeypatch):
    monkeypatch.setattr(chapter_service, "_loaded", set())
    client, plans = object(), Plans()
    for _ in range(3):
        asyncio.run(chapter_service.load_published(Database(client, plans), "school"))
    assert plans.reads == 1


def test_another_database_is_read_on_its_own(monkeypatch):
    monkeypatch.setattr(chapter_service, "_loaded", set())
    plans, one, other = Plans(), object(), object()  # both alive: ids of freed objects are reused
    asyncio.run(chapter_service.load_published(Database(one, plans), "school"))
    asyncio.run(chapter_service.load_published(Database(other, plans), "school"))
    assert plans.reads == 2


class SlowPlans:
    """A teaching-plan repository whose read takes a while (Atlas over a slow line)."""

    fail = False

    def __init__(self, _database, _school_id):
        pass

    async def list_published(self):
        await asyncio.sleep(0.01)
        if self.fail:
            raise ConnectionError("Atlas is unreachable")
        return [
            SimpleNamespace(
                chapter_id="math-g5-decimals", current="v2", published={"v2": {"package": {}, "lessons": {}}}
            )
        ]


@pytest.fixture
def registered(monkeypatch):
    """The plans the tutor learns about, read from a slow repository."""
    from cavat.modules.ingest import repository

    out: list[str] = []
    monkeypatch.setattr(chapter_service, "_loaded", set())
    monkeypatch.setattr(repository, "TeachingPlanRepository", SlowPlans)
    monkeypatch.setattr(
        chapter_service, "register_published", lambda _cid, version, *_a, **_k: out.append(version)
    )
    return out


def test_a_second_request_waits_for_the_published_plans(registered):
    """REFORM-1 (Task 1.1): two requests at the start of a session. The second one returned at once (the
    database was marked read before the read ended) and could start the session on the chapter file."""
    seen: list[list[str]] = []

    async def both():
        db = Database(object(), Plans())

        async def request():
            await chapter_service.load_published(db, "school")
            seen.append(list(registered))

        await asyncio.gather(request(), request())

    asyncio.run(both())
    assert seen == [["v2"], ["v2"]]  # both see the published plan, read once


def test_a_failed_read_is_tried_again_by_the_next_request(registered, monkeypatch):
    db = Database(object(), Plans())
    monkeypatch.setattr(SlowPlans, "fail", True)
    with pytest.raises(ConnectionError):
        asyncio.run(chapter_service.load_published(db, "school"))
    monkeypatch.setattr(SlowPlans, "fail", False)
    asyncio.run(chapter_service.load_published(db, "school"))
    assert registered == ["v2"]
