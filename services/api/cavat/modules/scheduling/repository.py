"""Scheduling module storage: weekly schedule rules of a class (blueprint PART 23.1).

Dates are ISO strings (``YYYY-MM-DD``) because BSON has no date-only type; times are local
``HH:MM`` in the rule's timezone.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from cavat.core.repository import ASCENDING, IndexSpec, TenantDocument, TenantScopedRepository, utc_now

_DATE = r"^\d{4}-\d{2}-\d{2}$"


class ScheduleRule(TenantDocument):
    class_id: str
    subject: Literal["math", "english"]
    weekdays: list[Annotated[int, Field(ge=1, le=7)]] = Field(min_length=1)  # ISO: 1 = Monday … 7 = Sunday
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration_min: int = Field(gt=0, le=180)
    valid_from: str = Field(pattern=_DATE)
    valid_to: str | None = Field(default=None, pattern=_DATE)
    timezone: str = "Asia/Ho_Chi_Minh"
    lesson_id: str | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ScheduleRepository(TenantScopedRepository):
    collection_name = "schedules"
    indexes = (
        IndexSpec((("school_id", ASCENDING), ("class_id", ASCENDING), ("subject", ASCENDING)), "class"),
    )

    async def create(self, rule: ScheduleRule) -> ScheduleRule:
        await self._insert(rule.to_doc())
        return rule

    async def get(self, rule_id: str) -> ScheduleRule | None:
        doc = await self._find_one({"_id": rule_id})
        return ScheduleRule.from_doc(doc) if doc else None

    async def list_for_class(self, class_id: str) -> list[ScheduleRule]:
        docs = await self._find(
            {"class_id": class_id}, sort=[("subject", ASCENDING), ("start_time", ASCENDING)]
        )
        return [ScheduleRule.from_doc(d) for d in docs]
