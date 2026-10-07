"""Shared persistence layer: ids, tenant guard, index registry, and parity of the in-memory database."""

import uuid

import pytest
from cavat.core import repository as core
from cavat.core.repository import (
    ASCENDING,
    DESCENDING,
    AlreadyExists,
    IndexSpec,
    TenantDocument,
    TenantScopedRepository,
    TenantViolation,
    new_id,
    utc_now,
)
from cavat.db import ensure_indexes, repository_classes
from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError


class _Things(TenantScopedRepository):
    collection_name = "things"
    indexes = (IndexSpec((("school_id", ASCENDING), ("code", ASCENDING)), "code_unique", unique=True),)


# --- ids and time -------------------------------------------------------------------------------


def test_new_id_is_uuid7():
    value = uuid.UUID(new_id())
    assert value.version == 7
    assert value.variant == uuid.RFC_4122


def test_new_id_sorts_by_time(monkeypatch):
    monkeypatch.setattr(core, "_id_last", [0, 0])  # fake clock must not leak into other tests
    monkeypatch.setattr(core.time, "time_ns", lambda: 1_700_000_000_000 * 1_000_000)
    earlier = new_id()
    monkeypatch.setattr(core.time, "time_ns", lambda: 1_700_000_000_001 * 1_000_000)
    later = new_id()
    assert later > earlier
    assert uuid.UUID(later).int >> 80 == 1_700_000_000_001


def test_new_id_is_monotonic_within_a_millisecond(monkeypatch):
    monkeypatch.setattr(core, "_id_last", [0, 0])
    monkeypatch.setattr(core.time, "time_ns", lambda: 1_800_000_000_000 * 1_000_000)
    ids = [new_id() for _ in range(5000)]  # more than the 12-bit counter holds
    assert ids == sorted(ids) and len(set(ids)) == len(ids)


def test_utc_now_has_millisecond_precision():
    now = utc_now()
    assert now.tzinfo is not None and now.utcoffset().total_seconds() == 0
    assert now.microsecond % 1000 == 0


# --- tenant guard -------------------------------------------------------------------------------


@pytest.mark.parametrize("school_id", ["", "   ", None])
def test_tenant_repository_requires_school_id(school_id):
    with pytest.raises(TenantViolation):
        _Things({"things": None}, school_id)


def test_scope_injects_school_id():
    repo = _Things({"things": None}, "sch-A")
    assert repo._scope({"code": "x"}) == {"code": "x", "school_id": "sch-A"}
    assert repo._scope(None) == {"school_id": "sch-A"}
    assert repo._scope({"school_id": "sch-A"}) == {"school_id": "sch-A"}


@pytest.mark.parametrize(
    "flt",
    [
        {"school_id": "sch-B"},
        {"school_id": {"$in": ["sch-A", "sch-B"]}},
        {"school_id": {"$ne": "sch-A"}},
        {"$or": [{"code": "x"}, {"school_id": "sch-B"}]},
    ],
)
def test_scope_rejects_other_school(flt):
    repo = _Things({"things": None}, "sch-A")
    with pytest.raises(TenantViolation):
        repo._scope(flt)


def test_stamp_rejects_document_of_other_school():
    repo = _Things({"things": None}, "sch-A")
    assert repo._stamp({"code": "x"})["school_id"] == "sch-A"
    with pytest.raises(TenantViolation):
        repo._stamp({"code": "x", "school_id": "sch-B"})


@pytest.mark.parametrize(
    "update",
    [
        {"$set": {"school_id": "sch-B"}},
        {"$set": {"school_id.x": 1}},
        {"$unset": {"school_id": ""}},
        {"$setOnInsert": {"school_id": "sch-B"}},
    ],
)
def test_update_cannot_change_school_id(update):
    repo = _Things({"things": None}, "sch-A")
    with pytest.raises(TenantViolation):
        repo._check_update(update)


def test_update_must_use_operators():
    repo = _Things({"things": None}, "sch-A")
    with pytest.raises(ValueError):
        repo._check_update({"code": "y"})


async def test_tenant_repositories_are_isolated(db):
    await _Things.ensure_indexes(db)
    a, b = _Things(db, "sch-A"), _Things(db, "sch-B")
    await a._insert({"_id": "t1", "code": "x"})
    await b._insert({"_id": "t2", "code": "x"})  # same code, other school: allowed
    with pytest.raises(AlreadyExists):
        await a._insert({"_id": "t3", "code": "x"})
    assert await a._find_one({"_id": "t2"}) is None
    assert [d["_id"] for d in await a._find()] == ["t1"]
    assert await b._count() == 1
    result = await a._update_one({"_id": "t2"}, {"$set": {"code": "hijack"}})
    assert result.matched_count == 0
    assert (await b._find_one({"_id": "t2"}))["code"] == "x"


# --- registry -----------------------------------------------------------------------------------

EXPECTED_COLLECTIONS = {
    "schools",
    "users",
    "classes",
    "enrollments",
    "lessons",
    "schedules",
    "learning_sessions",
    "events",
    "evidence",
    "student_kc_states",
    "documents",
}


def test_every_collection_has_one_repository():
    names = [repo.collection_name for repo in repository_classes()]
    assert sorted(names) == sorted(EXPECTED_COLLECTIONS)


def test_learner_data_is_tenant_scoped():
    for repo in repository_classes():
        if repo.collection_name == "schools":
            assert not repo.tenant_scoped  # the tenant root: its _id is the school_id
        else:
            assert repo.tenant_scoped, repo.__name__
            assert issubclass(repo, TenantScopedRepository)


def test_tenant_documents_carry_school_id():
    tenant_models = [cls for cls in _all_subclasses(TenantDocument)]
    assert len(tenant_models) >= 8
    for cls in tenant_models:
        assert cls.model_fields["school_id"].is_required(), cls.__name__


def _all_subclasses(cls):
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


def test_index_names_are_unique_per_collection():
    for repo in repository_classes():
        names = [ix.name for ix in repo.indexes]
        assert len(names) == len(set(names)), repo.__name__


async def test_ensure_indexes_is_idempotent(db):
    first = await ensure_indexes(db)
    second = await ensure_indexes(db)
    assert first == second
    assert "session_sequence_unique" in first["events"]
    info = await db["events"].index_information()
    assert info["session_sequence_unique"].get("unique") is True


# --- in-memory database parity (also runs against Atlas when configured) -------------------------


async def test_array_of_subdocuments_matching(db):
    col = db["parity"]
    await col.insert_one({"_id": 1, "events": [{"k": "a"}, {"k": "b"}]})
    await col.insert_one({"_id": 2, "events": []})
    assert {d["_id"] for d in await col.find({"events.k": "a"}).to_list()} == {1}
    assert {d["_id"] for d in await col.find({"events.k": {"$ne": "a"}}).to_list()} == {2}
    assert {d["_id"] for d in await col.find({"events.k": {"$in": ["b", "z"]}}).to_list()} == {1}


async def test_comparison_sort_limit_and_projection(db):
    col = db["parity"]
    for i in range(5):
        await col.insert_one({"_id": i, "n": i, "blob": "x" * i})
    docs = await col.find(
        {"n": {"$gte": 1, "$lt": 4}}, {"blob": 0}, sort=[("n", DESCENDING)], limit=2
    ).to_list()
    assert docs == [{"_id": 3, "n": 3}, {"_id": 2, "n": 2}]
    assert await col.count_documents({"n": {"$gt": 2}}) == 2
    assert await col.find_one({"_id": 4}, {"n": 1, "_id": 0}) == {"n": 4}


async def test_update_operators(db):
    col = db["parity"]
    await col.insert_one({"_id": 1, "v": 1, "mark": 5, "list": [1], "gone": True})
    doc = await col.find_one_and_update(
        {"_id": 1, "v": 1},
        {
            "$inc": {"v": 1},
            "$max": {"mark": 3},
            "$push": {"list": {"$each": [2, 3]}},
            "$set": {"a.b": "c"},
            "$unset": {"gone": ""},
        },
        return_document=ReturnDocument.AFTER,
    )
    assert doc == {"_id": 1, "v": 2, "mark": 5, "list": [1, 2, 3], "a": {"b": "c"}}
    assert await col.find_one_and_update({"_id": 1, "v": 1}, {"$inc": {"v": 1}}) is None


async def test_upsert_takes_equality_fields_from_filter(db):
    col = db["parity"]
    update = {"$set": {"n": 1}, "$setOnInsert": {"created": True}}
    result = await col.update_one({"k": "a", "s": "x"}, update, upsert=True)
    assert result.upserted_id is not None and result.matched_count == 0
    result = await col.update_one(
        {"k": "a", "s": "x"}, {"$set": {"n": 2}, "$setOnInsert": {"created": False}}, upsert=True
    )
    assert result.upserted_id is None and result.matched_count == 1
    doc = await col.find_one({"k": "a"}, {"_id": 0})
    assert doc == {"k": "a", "s": "x", "n": 2, "created": True}


async def test_unique_index_and_bulk_insert(db):
    col = db["parity"]
    await col.create_index([("a", ASCENDING), ("b", ASCENDING)], name="ab", unique=True)
    await col.insert_one({"_id": 1, "a": 1, "b": 1})
    with pytest.raises(DuplicateKeyError):
        await col.insert_one({"_id": 2, "a": 1, "b": 1})
    with pytest.raises(DuplicateKeyError):
        await col.insert_one({"_id": 1, "a": 9, "b": 9})
    with pytest.raises(BulkWriteError) as info:
        await col.insert_many([{"_id": 3, "a": 1, "b": 1}, {"_id": 4, "a": 2, "b": 2}], ordered=False)
    assert info.value.details["nInserted"] == 1
    assert [e["code"] for e in info.value.details["writeErrors"]] == [11000]
    assert await col.count_documents({}) == 2
