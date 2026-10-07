"""Shared persistence layer: document base models, repository base classes and errors.

MongoDB Atlas M0 has no row-level security and no multi-document transaction (blueprint D-T7), so:

- every learner/school document carries ``school_id`` and every query on it goes through
  :class:`TenantScopedRepository`, which injects the tenant filter and rejects cross-tenant access;
- whatever must change atomically lives in one document (see ``modules/session/repository.py``).

Repositories take any object that behaves like an async PyMongo ``Database``: the real one from
``cavat.db.get_db()`` or ``cavat.core.memory_db.InMemoryDatabase`` for offline tests.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field
from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError

ASCENDING = 1
DESCENDING = -1
DUPLICATE_KEY = 11000


# --- errors -------------------------------------------------------------------------------------


class RepositoryError(Exception):
    pass


class NotFound(RepositoryError):
    pass


class AlreadyExists(RepositoryError):
    pass


class TenantViolation(RepositoryError):
    """A query or write tried to reach outside the repository's school."""


class ImmutableRecord(RepositoryError):
    """Attempt to modify a record that is immutable (published lesson, append-only log)."""


# --- helpers ------------------------------------------------------------------------------------


def utc_now() -> datetime:
    """Current UTC time truncated to milliseconds (BSON datetime precision)."""
    now = datetime.now(UTC)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


_id_lock = threading.Lock()
_id_last = [0, 0]  # [unix ms, 12-bit counter] of the last id issued by this process


def new_id() -> str:
    """UUIDv7 (RFC 9562) as a string, sortable by creation time (PART 28.1).

    Monotonic within the process (RFC 9562 §6.2 method 1: a counter in ``rand_a``), so ids
    created in the same millisecond still sort in creation order.
    """
    with _id_lock:
        ms = time.time_ns() // 1_000_000
        if ms > _id_last[0]:
            counter = int.from_bytes(os.urandom(2)) & 0x7FF  # random start, room to count up
        else:
            ms, counter = _id_last[0], _id_last[1] + 1
            if counter > 0xFFF:
                ms, counter = ms + 1, 0
        _id_last[:] = [ms, counter]
    rand_b = int.from_bytes(os.urandom(8)) & ((1 << 62) - 1)
    value = ms << 80 | 0x7 << 76 | counter << 64 | 0x2 << 62 | rand_b
    return str(uuid.UUID(int=value))


@dataclass(frozen=True)
class IndexSpec:
    keys: tuple[tuple[str, int], ...]
    name: str
    unique: bool = False


# --- documents ----------------------------------------------------------------------------------


class Document(BaseModel):
    """A stored document. ``id`` maps to MongoDB ``_id``."""

    model_config = ConfigDict(
        populate_by_name=True, extra="forbid", use_enum_values=True, validate_default=True
    )

    id: str = Field(default_factory=new_id, alias="_id")

    def to_doc(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)

    @classmethod
    def from_doc(cls, doc: Mapping[str, Any]) -> Self:
        return cls.model_validate(doc)


class TenantDocument(Document):
    """Document owned by one school (learner data or school content)."""

    school_id: str


# --- repositories -------------------------------------------------------------------------------


class Repository:
    """Base class: one repository per collection. Subclasses declare the collection and its indexes."""

    collection_name: ClassVar[str]
    indexes: ClassVar[tuple[IndexSpec, ...]] = ()
    tenant_scoped: ClassVar[bool] = False

    def __init__(self, db: Any) -> None:
        self._db = db
        self._col = db[self.collection_name]

    async def _insert(self, doc: Mapping[str, Any]) -> None:
        try:
            await self._col.insert_one(dict(doc))
        except DuplicateKeyError as exc:
            raise AlreadyExists(f"{self.collection_name}: {doc.get('_id')}") from exc

    @classmethod
    async def ensure_indexes(cls, db: Any) -> list[str]:
        col = db[cls.collection_name]
        return [await col.create_index(list(ix.keys), name=ix.name, unique=ix.unique) for ix in cls.indexes]


class TenantScopedRepository(Repository):
    """Repository bound to one school. Every read and write is forced through ``school_id``.

    MongoDB has no RLS, so this class is the only tenancy guard (ADR-003, v0.3). Subclasses must
    use the ``_find*``/``_insert*``/``_update*`` helpers below and never touch ``self._col`` directly.
    """

    tenant_scoped: ClassVar[bool] = True

    def __init__(self, db: Any, school_id: str) -> None:
        if not isinstance(school_id, str) or not school_id.strip():
            raise TenantViolation("school_id is required")
        super().__init__(db)
        self.school_id = school_id

    # -- guards

    def _check_school_refs(self, obj: Any) -> None:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                if key == "school_id" and value != self.school_id:
                    raise TenantViolation(f"filter references another school: {value!r}")
                self._check_school_refs(value)
        elif isinstance(obj, list | tuple):
            for value in obj:
                self._check_school_refs(value)

    def _scope(self, flt: Mapping[str, Any] | None = None) -> dict[str, Any]:
        flt = dict(flt or {})
        self._check_school_refs(flt)
        flt["school_id"] = self.school_id
        return flt

    def _stamp(self, doc: Mapping[str, Any]) -> dict[str, Any]:
        if doc.get("school_id", self.school_id) != self.school_id:
            raise TenantViolation(f"document belongs to another school: {doc.get('school_id')!r}")
        return {**doc, "school_id": self.school_id}

    def _check_update(self, update: Mapping[str, Any]) -> None:
        for op, fields in update.items():
            if not op.startswith("$"):
                raise ValueError("replacement documents are not allowed; use update operators")
            for field, value in fields.items():
                if field == "school_id" or field.startswith("school_id."):
                    if op == "$setOnInsert" and value == self.school_id:
                        continue
                    raise TenantViolation("school_id cannot be changed")

    # -- scoped operations

    async def _find_one(self, flt: Mapping[str, Any], **kwargs: Any) -> dict[str, Any] | None:
        return await self._col.find_one(self._scope(flt), **kwargs)

    async def _find(
        self,
        flt: Mapping[str, Any] | None = None,
        *,
        sort: Sequence[tuple[str, int]] | None = None,
        limit: int = 0,
        projection: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._col.find(self._scope(flt), projection=projection, sort=sort, limit=limit)
        return await cursor.to_list(length=None)

    async def _count(self, flt: Mapping[str, Any] | None = None) -> int:
        return await self._col.count_documents(self._scope(flt))

    async def _insert(self, doc: Mapping[str, Any]) -> None:
        await super()._insert(self._stamp(doc))

    async def _insert_many_ignoring_duplicates(self, docs: Iterable[Mapping[str, Any]]) -> int:
        """Insert documents, skipping those that violate a unique index. Returns the number inserted."""
        docs = [self._stamp(d) for d in docs]
        if not docs:
            return 0
        try:
            result = await self._col.insert_many(docs, ordered=False)
        except BulkWriteError as exc:
            errors = exc.details.get("writeErrors", [])
            if any(err.get("code") != DUPLICATE_KEY for err in errors):
                raise
            return exc.details.get("nInserted", len(docs) - len(errors))
        return len(result.inserted_ids)

    async def _delete_one(self, flt: Mapping[str, Any]) -> bool:
        """Delete one document of this school; True when one was found."""
        result = await self._col.delete_one(self._scope(flt))
        return result.deleted_count == 1

    async def _update_one(self, flt: Mapping[str, Any], update: Mapping[str, Any], *, upsert: bool = False):
        self._check_update(update)
        return await self._col.update_one(self._scope(flt), dict(update), upsert=upsert)

    async def _find_one_and_update(
        self,
        flt: Mapping[str, Any],
        update: Mapping[str, Any],
        *,
        upsert: bool = False,
        projection: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        self._check_update(update)
        return await self._col.find_one_and_update(
            self._scope(flt),
            dict(update),
            projection=projection,
            upsert=upsert,
            return_document=ReturnDocument.AFTER,
        )
