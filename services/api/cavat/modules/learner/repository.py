"""Learner module storage: Student Model projection per KC (blueprint PART 25.1, 28.3).

A ``student_kc_states`` document is a deterministic projection of evidence under one
``policy_version``; it can be dropped and rebuilt by replay. Only the assessment projector writes
here, never the LLM or the tutor (CLAUDE.md rule 3). Keyed by (student, KC, policy_version).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from cavat.core.repository import (
    ASCENDING,
    IndexSpec,
    TenantDocument,
    TenantScopedRepository,
    new_id,
    utc_now,
)


class StudentKCState(TenantDocument):
    student_id: str
    kc_id: str
    policy_version: str
    state: dict[str, Any]  # mastery, confidence, dimensions, status (PART 25.1); shaped by T10
    source_evidence_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class StudentKCStateRepository(TenantScopedRepository):
    collection_name = "student_kc_states"
    indexes = (
        IndexSpec(
            (
                ("school_id", ASCENDING),
                ("student_id", ASCENDING),
                ("kc_id", ASCENDING),
                ("policy_version", ASCENDING),
            ),
            "student_kc_policy_unique",
            unique=True,
        ),
    )

    async def put(
        self,
        student_id: str,
        kc_id: str,
        policy_version: str,
        state: dict[str, Any],
        source_evidence_count: int,
    ) -> StudentKCState:
        """Write the projection result (upsert). Replaying the same evidence gives the same document."""
        now = utc_now()
        doc = await self._find_one_and_update(
            {"student_id": student_id, "kc_id": kc_id, "policy_version": policy_version},
            {
                "$set": {"state": state, "source_evidence_count": source_evidence_count, "updated_at": now},
                "$setOnInsert": {"_id": new_id(), "created_at": now},
            },
            upsert=True,
        )
        return StudentKCState.from_doc(doc)

    async def get(self, student_id: str, kc_id: str, policy_version: str) -> StudentKCState | None:
        doc = await self._find_one(
            {"student_id": student_id, "kc_id": kc_id, "policy_version": policy_version}
        )
        return StudentKCState.from_doc(doc) if doc else None

    async def list_for_student(self, student_id: str, policy_version: str) -> list[StudentKCState]:
        docs = await self._find(
            {"student_id": student_id, "policy_version": policy_version}, sort=[("kc_id", ASCENDING)]
        )
        return [StudentKCState.from_doc(d) for d in docs]
