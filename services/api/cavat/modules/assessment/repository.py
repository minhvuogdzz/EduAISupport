"""Assessment module storage: evidence (blueprint PART 10.2 layer L1, PART 28.3).

Evidence is append-only: a wrong record is corrected by a new record whose ``supersedes_id``
points at it, never by an update. This repository therefore has no update or delete method.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from cavat.core.pedagogy import ErrorClass, ItemResolution
from cavat.core.repository import ASCENDING, IndexSpec, TenantDocument, TenantScopedRepository, utc_now

Dimension = Literal["C", "R", "A", "T", "I", "S", "D"]  # blueprint 09, PART 25


class Evidence(TenantDocument):
    student_id: str
    session_id: str
    source_event_ids: list[str] = Field(min_length=1)
    kc_id: str | None = None
    skill_id: str | None = None
    dimension: Dimension
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    validity: Literal["VALID", "LOW_VALIDITY", "INVALID"] = "VALID"
    construct_name: str | None = Field(default=None, alias="construct")  # "construct" shadows BaseModel
    support_level: ItemResolution | None = None
    error_class: ErrorClass | None = None
    misconception_id: str | None = None
    policy_version: str
    supersedes_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceRepository(TenantScopedRepository):
    collection_name = "evidence"
    indexes = (
        IndexSpec(
            (
                ("school_id", ASCENDING),
                ("student_id", ASCENDING),
                ("kc_id", ASCENDING),
                ("created_at", ASCENDING),
            ),
            "student_kc_time",
        ),
        IndexSpec((("school_id", ASCENDING), ("session_id", ASCENDING)), "session"),
    )

    async def append(self, evidence: Evidence) -> Evidence:
        if evidence.kc_id is None and evidence.skill_id is None:
            raise ValueError("evidence must target a KC or a skill")
        await self._insert(evidence.to_doc())
        return evidence

    async def list_for_student(self, student_id: str, kc_id: str | None = None) -> list[Evidence]:
        flt = {"student_id": student_id, **({"kc_id": kc_id} if kc_id else {})}
        docs = await self._find(flt, sort=[("created_at", ASCENDING), ("_id", ASCENDING)])
        return [Evidence.from_doc(d) for d in docs]

    async def list_for_session(self, session_id: str) -> list[Evidence]:
        docs = await self._find(
            {"session_id": session_id}, sort=[("created_at", ASCENDING), ("_id", ASCENDING)]
        )
        return [Evidence.from_doc(d) for d in docs]
