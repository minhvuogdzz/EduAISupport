"""Content module storage: lessons, one document per lesson version with its package embedded.

A version is editable while it is a draft; once published its package is immutable (PART 8.4)
and sessions bind to it by ``(lesson_id, version)``. ``content_hash`` is the SHA-256 of the
canonical JSON of the package, so a contract can prove which content it was compiled from.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from cavat.core.repository import (
    ASCENDING,
    DESCENDING,
    AlreadyExists,
    ImmutableRecord,
    IndexSpec,
    NotFound,
    TenantDocument,
    TenantScopedRepository,
    utc_now,
)
from cavat.modules.content.lesson_package import LessonPackage

LessonStatus = Literal["DRAFT", "APPROVED", "PUBLISHED", "ARCHIVED"]


def package_hash(pkg: LessonPackage) -> str:
    canonical = json.dumps(
        pkg.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_field_names(value: Any, path: str = "package") -> None:
    """Keys with ``.`` or a leading ``$`` cannot be queried or updated reliably in MongoDB."""
    if isinstance(value, dict):
        for key, sub in value.items():
            if "." in key or key.startswith("$"):
                raise ValueError(f"{path}: field name {key!r} cannot be stored in MongoDB")
            _check_field_names(sub, f"{path}.{key}")
    elif isinstance(value, list):
        for index, sub in enumerate(value):
            _check_field_names(sub, f"{path}[{index}]")


class LessonVersion(TenantDocument):
    lesson_id: str
    version: str
    status: LessonStatus
    subject: Literal["math", "english"]
    grade: int
    title: str
    package: dict[str, Any]
    content_hash: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    published_at: datetime | None = None

    @classmethod
    def from_package(cls, school_id: str, pkg: LessonPackage) -> LessonVersion:
        package = pkg.model_dump(mode="json")
        _check_field_names(package)
        return cls(
            school_id=school_id,
            lesson_id=pkg.lesson_id,
            version=pkg.version,
            status=pkg.status,
            subject=pkg.subject,
            grade=pkg.grade,
            title=pkg.title,
            package=package,
            content_hash=package_hash(pkg),
        )

    def to_package(self) -> LessonPackage:
        return LessonPackage.model_validate(self.package)


class LessonRepository(TenantScopedRepository):
    collection_name = "lessons"
    indexes = (
        IndexSpec(
            (("school_id", ASCENDING), ("lesson_id", ASCENDING), ("version", ASCENDING)),
            "lesson_version_unique",
            unique=True,
        ),
        IndexSpec((("school_id", ASCENDING), ("subject", ASCENDING), ("grade", ASCENDING)), "subject_grade"),
    )

    async def save(self, pkg: LessonPackage) -> LessonVersion:
        """Insert a new version, or replace the package of a version that is not published yet."""
        new = LessonVersion.from_package(self.school_id, pkg)
        try:
            await self._insert(new.to_doc())
            return new
        except AlreadyExists:
            pass
        doc = await self._find_one_and_update(
            {
                "lesson_id": pkg.lesson_id,
                "version": pkg.version,
                "status": {"$nin": ["PUBLISHED", "ARCHIVED"]},
            },
            {
                "$set": {
                    "status": new.status,
                    "subject": new.subject,
                    "grade": new.grade,
                    "title": new.title,
                    "package": new.package,
                    "content_hash": new.content_hash,
                    "updated_at": utc_now(),
                }
            },
        )
        if doc is None:
            raise ImmutableRecord(f"{pkg.lesson_id}@{pkg.version} is published and cannot be changed")
        return LessonVersion.from_doc(doc)

    async def publish(self, lesson_id: str, version: str) -> LessonVersion:
        now = utc_now()
        doc = await self._find_one_and_update(
            {"lesson_id": lesson_id, "version": version, "status": {"$nin": ["PUBLISHED", "ARCHIVED"]}},
            {"$set": {"status": "PUBLISHED", "published_at": now, "updated_at": now}},
        )
        if doc is None:
            current = await self.get(lesson_id, version)
            if current is None:
                raise NotFound(f"{lesson_id}@{version}")
            raise ImmutableRecord(f"{lesson_id}@{version} is already {current.status}")
        return LessonVersion.from_doc(doc)

    async def get(self, lesson_id: str, version: str) -> LessonVersion | None:
        doc = await self._find_one({"lesson_id": lesson_id, "version": version})
        return LessonVersion.from_doc(doc) if doc else None

    async def latest_published(self, lesson_id: str) -> LessonVersion | None:
        docs = await self._find(
            {"lesson_id": lesson_id, "status": "PUBLISHED"}, sort=[("published_at", DESCENDING)], limit=1
        )
        return LessonVersion.from_doc(docs[0]) if docs else None

    async def list_versions(self, lesson_id: str) -> list[LessonVersion]:
        docs = await self._find({"lesson_id": lesson_id}, sort=[("created_at", ASCENDING)])
        return [LessonVersion.from_doc(d) for d in docs]
