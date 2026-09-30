"""Org module storage: schools (tenant root), classes and enrollments (blueprint PART 8.1, 28.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from cavat.core.repository import (
    ASCENDING,
    AlreadyExists,
    Document,
    IndexSpec,
    Repository,
    TenantDocument,
    TenantScopedRepository,
    utc_now,
)


class School(Document):
    name: str
    timezone: str = "Asia/Ho_Chi_Minh"
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"
    created_at: datetime = Field(default_factory=utc_now)


class SchoolClass(TenantDocument):
    name: str
    grade: int
    school_year: str  # e.g. "2026-2027"
    created_at: datetime = Field(default_factory=utc_now)


class Enrollment(TenantDocument):
    class_id: str
    student_id: str
    status: Literal["ACTIVE", "WITHDRAWN"] = "ACTIVE"
    enrolled_at: datetime = Field(default_factory=utc_now)


class SchoolRepository(Repository):
    """The tenant root, so not tenant-scoped: a school document's ``_id`` *is* the ``school_id``."""

    collection_name = "schools"

    async def create(self, school: School) -> School:
        await self._insert(school.to_doc())
        return school

    async def get(self, school_id: str) -> School | None:
        doc = await self._col.find_one({"_id": school_id})
        return School.from_doc(doc) if doc else None


class ClassRepository(TenantScopedRepository):
    collection_name = "classes"
    indexes = (IndexSpec((("school_id", ASCENDING), ("school_year", ASCENDING)), "school_year"),)

    async def create(self, cls: SchoolClass) -> SchoolClass:
        await self._insert(cls.to_doc())
        return cls

    async def get(self, class_id: str) -> SchoolClass | None:
        doc = await self._find_one({"_id": class_id})
        return SchoolClass.from_doc(doc) if doc else None

    async def list_for_year(self, school_year: str) -> list[SchoolClass]:
        docs = await self._find({"school_year": school_year}, sort=[("name", ASCENDING)])
        return [SchoolClass.from_doc(d) for d in docs]


class EnrollmentRepository(TenantScopedRepository):
    collection_name = "enrollments"
    indexes = (
        IndexSpec(
            (("school_id", ASCENDING), ("class_id", ASCENDING), ("student_id", ASCENDING)),
            "class_student_unique",
            unique=True,
        ),
        IndexSpec((("school_id", ASCENDING), ("student_id", ASCENDING)), "student"),
    )

    async def enroll(self, enrollment: Enrollment) -> Enrollment:
        try:
            await self._insert(enrollment.to_doc())
        except AlreadyExists as exc:
            raise AlreadyExists(
                f"student {enrollment.student_id} already in class {enrollment.class_id}"
            ) from exc
        return enrollment

    async def students_of(self, class_id: str, *, active_only: bool = True) -> list[Enrollment]:
        flt = {"class_id": class_id, **({"status": "ACTIVE"} if active_only else {})}
        return [Enrollment.from_doc(d) for d in await self._find(flt, sort=[("student_id", ASCENDING)])]

    async def classes_of(self, student_id: str, *, active_only: bool = True) -> list[Enrollment]:
        flt = {"student_id": student_id, **({"status": "ACTIVE"} if active_only else {})}
        return [Enrollment.from_doc(d) for d in await self._find(flt, sort=[("class_id", ASCENDING)])]
