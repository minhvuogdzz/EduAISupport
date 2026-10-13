"""The published plans are read once per database, not once per request (they are megabytes)."""

import asyncio

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
