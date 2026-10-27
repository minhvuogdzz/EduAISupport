"""In-memory stand-in for the subset of the async PyMongo API that the repositories use.

Offline tests (and the demo API) run the real repository code against this instead of Atlas.
Operators follow MongoDB semantics; anything not implemented raises ``NotImplementedError`` so a
repository can never silently depend on behaviour the fake does not reproduce. Every operation
runs without awaiting in between, so it is atomic with respect to other coroutines, like a
single-document write in MongoDB.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError

from cavat.core.repository import DUPLICATE_KEY

_QUERY_OPS = {"$eq", "$ne", "$in", "$nin", "$gt", "$gte", "$lt", "$lte", "$exists"}


# --- query matching -----------------------------------------------------------------------------


def _resolve(doc: Any, path: str) -> list[Any]:
    """Values found at a dotted path; arrays of sub-documents are traversed like MongoDB does."""
    current = [doc]
    for part in path.split("."):
        found: list[Any] = []
        for value in current:
            if isinstance(value, dict):
                if part in value:
                    found.append(value[part])
            elif isinstance(value, list):
                if part.isdigit():
                    if int(part) < len(value):
                        found.append(value[int(part)])
                else:
                    found.extend(el[part] for el in value if isinstance(el, dict) and part in el)
        current = found
    return current


def _candidates(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    for value in values:
        out.append(value)
        if isinstance(value, list):
            out.extend(value)
    return out


def _equals(values: list[Any], target: Any) -> bool:
    if target is None and not values:
        return True
    return any(v == target for v in _candidates(values))


def _compare(values: list[Any], target: Any, op: str) -> bool:
    for value in _candidates(values):
        try:
            if (
                (op == "$gt" and value > target)
                or (op == "$gte" and value >= target)
                or (op == "$lt" and value < target)
                or (op == "$lte" and value <= target)
            ):
                return True
        except TypeError:
            continue
    return False


def _match_condition(values: list[Any], cond: Any) -> bool:
    if not (isinstance(cond, dict) and cond and all(k.startswith("$") for k in cond)):
        return _equals(values, cond)
    for op, arg in cond.items():
        if op not in _QUERY_OPS:
            raise NotImplementedError(f"query operator {op}")
        if op == "$eq":
            ok = _equals(values, arg)
        elif op == "$ne":
            ok = not _equals(values, arg)
        elif op == "$in":
            ok = any(_equals(values, a) for a in arg)
        elif op == "$nin":
            ok = not any(_equals(values, a) for a in arg)
        elif op == "$exists":
            ok = bool(values) == bool(arg)
        else:
            ok = _compare(values, arg, op)
        if not ok:
            return False
    return True


def matches(doc: dict[str, Any], flt: Mapping[str, Any]) -> bool:
    for key, cond in flt.items():
        if key == "$and":
            ok = all(matches(doc, sub) for sub in cond)
        elif key == "$or":
            ok = any(matches(doc, sub) for sub in cond)
        elif key.startswith("$"):
            raise NotImplementedError(f"query operator {key}")
        else:
            ok = _match_condition(_resolve(doc, key), cond)
        if not ok:
            return False
    return True


# --- updates ------------------------------------------------------------------------------------


def _parent(doc: dict[str, Any], path: str, create: bool) -> tuple[dict[str, Any] | None, str]:
    parts = path.split(".")
    node: Any = doc
    for part in parts[:-1]:
        if not isinstance(node, dict):
            raise NotImplementedError(f"update path through non-document: {path}")
        if part not in node:
            if not create:
                return None, parts[-1]
            node[part] = {}
        node = node[part]
    if not isinstance(node, dict):
        raise NotImplementedError(f"update path through non-document: {path}")
    return node, parts[-1]


def apply_update(doc: dict[str, Any], update: Mapping[str, Any], *, inserting: bool = False) -> None:
    for op, fields in update.items():
        if not op.startswith("$"):
            raise NotImplementedError("replacement updates are not supported")
        for path, value in fields.items():
            value = copy.deepcopy(value)
            if op == "$setOnInsert":
                if inserting:
                    parent, key = _parent(doc, path, create=True)
                    parent[key] = value
                continue
            if path == "_id":
                raise NotImplementedError("_id is immutable")
            if op == "$unset":
                parent, key = _parent(doc, path, create=False)
                if parent is not None:
                    parent.pop(key, None)
                continue
            parent, key = _parent(doc, path, create=True)
            current = parent.get(key)
            if op == "$set":
                parent[key] = value
            elif op == "$inc":
                parent[key] = (current or 0) + value
            elif op == "$max":
                parent[key] = value if current is None or value > current else current
            elif op == "$min":
                parent[key] = value if current is None or value < current else current
            elif op == "$push":
                items = value["$each"] if isinstance(value, dict) and "$each" in value else [value]
                parent[key] = [*(current or []), *items]
            else:
                raise NotImplementedError(f"update operator {op}")


def _project(doc: dict[str, Any], projection: Mapping[str, Any] | None) -> dict[str, Any]:
    doc = copy.deepcopy(doc)
    if not projection:
        return doc
    flags = {k: bool(v) for k, v in projection.items() if k != "_id"}
    if any("." in k for k in flags):
        raise NotImplementedError("projection on nested fields")
    if flags and all(flags.values()):
        out = {k: doc[k] for k in flags if k in doc}
        if projection.get("_id", 1):
            out["_id"] = doc["_id"]
        return out
    if any(flags.values()):
        raise NotImplementedError("mixed inclusion/exclusion projection")
    for key in flags:
        doc.pop(key, None)
    if not projection.get("_id", 1):
        doc.pop("_id", None)
    return doc


def _sort_key(path: str):
    def key(doc: dict[str, Any]) -> tuple[int, Any]:
        values = _resolve(doc, path)
        return (0, None) if not values else (1, values[0])

    return key


# --- collection and database --------------------------------------------------------------------


@dataclass
class InsertOneResult:
    inserted_id: Any


@dataclass
class InsertManyResult:
    inserted_ids: list[Any]


@dataclass
class UpdateResult:
    matched_count: int
    modified_count: int
    upserted_id: Any = None


@dataclass(frozen=True)
class DeleteResult:
    deleted_count: int


@dataclass
class _Index:
    keys: tuple[tuple[str, int], ...]
    unique: bool


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        return self._docs if length is None else self._docs[:length]

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for doc in self._docs:
            yield doc


@dataclass
class InMemoryCollection:
    name: str
    _docs: list[dict[str, Any]] = field(default_factory=list)
    _indexes: dict[str, _Index] = field(default_factory=dict)

    # -- indexes

    async def create_index(self, keys: Sequence[tuple[str, int]], *, name: str | None = None, unique=False):
        keys = tuple((k, d) for k, d in keys)
        name = name or "_".join(f"{k}_{d}" for k, d in keys)
        self._indexes[name] = _Index(keys, unique)
        return name

    async def index_information(self) -> dict[str, dict[str, Any]]:
        info = {"_id_": {"key": [("_id", 1)]}}
        for name, ix in self._indexes.items():
            info[name] = {"key": list(ix.keys), **({"unique": True} if ix.unique else {})}
        return info

    def _check_unique(self, doc: dict[str, Any], ignore: dict[str, Any] | None = None) -> None:
        others = [d for d in self._docs if d is not ignore]
        if any(d["_id"] == doc["_id"] for d in others):
            raise DuplicateKeyError(f"E11000 duplicate key _id: {doc['_id']!r}", DUPLICATE_KEY)
        for name, ix in self._indexes.items():
            if not ix.unique:
                continue
            key = tuple(repr(_resolve(doc, k)[:1] or [None]) for k, _ in ix.keys)
            for other in others:
                if tuple(repr(_resolve(other, k)[:1] or [None]) for k, _ in ix.keys) == key:
                    raise DuplicateKeyError(f"E11000 duplicate key index {name}: {key}", DUPLICATE_KEY)

    # -- reads

    def _matching(self, flt: Mapping[str, Any] | None) -> list[dict[str, Any]]:
        return [d for d in self._docs if matches(d, flt or {})]

    def find(
        self,
        flt: Mapping[str, Any] | None = None,
        projection: Mapping[str, Any] | None = None,
        *,
        sort: Sequence[tuple[str, int]] | None = None,
        limit: int = 0,
        skip: int = 0,
    ) -> _Cursor:
        docs = self._matching(flt)
        for path, direction in reversed(list(sort or [])):
            docs.sort(key=_sort_key(path), reverse=direction < 0)
        docs = docs[skip:]
        if limit:
            docs = docs[:limit]
        return _Cursor([_project(d, projection) for d in docs])

    async def find_one(self, flt: Mapping[str, Any] | None = None, projection=None, **kwargs: Any):
        docs = await self.find(flt, projection, limit=1, **kwargs).to_list()
        return docs[0] if docs else None

    async def count_documents(self, flt: Mapping[str, Any]) -> int:
        return len(self._matching(flt))

    # -- writes

    def _insert(self, doc: Mapping[str, Any]) -> Any:
        doc = copy.deepcopy(dict(doc))
        doc.setdefault("_id", ObjectId())
        self._check_unique(doc)
        self._docs.append(doc)
        return doc["_id"]

    async def insert_one(self, doc: Mapping[str, Any]) -> InsertOneResult:
        return InsertOneResult(self._insert(doc))

    async def insert_many(self, docs: Sequence[Mapping[str, Any]], ordered: bool = True) -> InsertManyResult:
        inserted: list[Any] = []
        errors: list[dict[str, Any]] = []
        for index, doc in enumerate(docs):
            try:
                inserted.append(self._insert(doc))
            except DuplicateKeyError as exc:
                errors.append({"index": index, "code": DUPLICATE_KEY, "errmsg": str(exc)})
                if ordered:
                    break
        if errors:
            raise BulkWriteError({"writeErrors": errors, "nInserted": len(inserted)})
        return InsertManyResult(inserted)

    def _upsert_doc(self, flt: Mapping[str, Any], update: Mapping[str, Any]) -> dict[str, Any]:
        doc: dict[str, Any] = {}
        for key, cond in flt.items():
            if key.startswith("$") or (isinstance(cond, dict) and any(k.startswith("$") for k in cond)):
                continue
            parent, leaf = _parent(doc, key, create=True)
            parent[leaf] = copy.deepcopy(cond)
        apply_update(doc, update, inserting=True)
        return doc

    def _update(self, flt: Mapping[str, Any], update: Mapping[str, Any], upsert: bool):
        """Returns (document after update or None, matched, upserted_id)."""
        target = next(iter(self._matching(flt)), None)
        if target is None:
            if not upsert:
                return None, 0, None
            inserted_id = self._insert(self._upsert_doc(flt, update))
            return self._docs[-1], 0, inserted_id
        updated = copy.deepcopy(target)
        apply_update(updated, update)
        self._check_unique(updated, ignore=target)
        self._docs[self._docs.index(target)] = updated
        return updated, 1, None

    async def delete_one(self, flt: Mapping[str, Any]) -> DeleteResult:
        found = self._matching(flt)
        if not found:
            return DeleteResult(0)
        self._docs.remove(found[0])
        return DeleteResult(1)

    async def update_one(self, flt: Mapping[str, Any], update: Mapping[str, Any], upsert: bool = False):
        doc, matched, upserted_id = self._update(flt, update, upsert)
        return UpdateResult(matched, matched, upserted_id)

    async def find_one_and_update(
        self,
        flt: Mapping[str, Any],
        update: Mapping[str, Any],
        projection: Mapping[str, Any] | None = None,
        *,
        upsert: bool = False,
        return_document: bool = ReturnDocument.BEFORE,
    ):
        before = next(iter(self._matching(flt)), None)
        before = copy.deepcopy(before) if before is not None else None
        after, _, _ = self._update(flt, update, upsert)
        doc = after if return_document == ReturnDocument.AFTER else before
        return _project(doc, projection) if doc is not None else None


class InMemoryDatabase:
    def __init__(self, name: str = "cavat_memory") -> None:
        self.name = name
        self._collections: dict[str, InMemoryCollection] = {}

    def __getitem__(self, name: str) -> InMemoryCollection:
        return self.get_collection(name)

    def get_collection(self, name: str) -> InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = InMemoryCollection(name)
        return self._collections[name]

    async def list_collection_names(self) -> list[str]:
        return sorted(self._collections)

    async def drop_collection(self, name: str) -> None:
        self._collections.pop(name, None)
