"""Storage of the figures of the questions (FIG-1, ADR-037): a collection of its own, keyed by the question
and the order of the figure ("Hình 1", "Hình 2"), so the text of a question never changes (the teacher's
approvals are bound to the words, DI-74). The picture is a PNG on disk under ``var/storage/figures/``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from cavat.core.repository import ASCENDING, IndexSpec, TenantDocument, TenantScopedRepository, utc_now

# AUTO: found and matched with confidence, shown. REVIEW: matched, but the description and the drawing
# share little: it waits for the teacher and is not shown. APPROVED / REJECTED: the teacher's decision.
FigureStatus = Literal["AUTO", "REVIEW", "APPROVED", "REJECTED"]
SHOWN: tuple[str, ...] = ("AUTO", "APPROVED")  # what a student sees
FIGURE_VERSION = "figures/0.1.0"


class Figure(TenantDocument):
    chapter_id: str
    question_id: str  # "DTTGHT-BT-13": the item id without its sub-question letter
    order: int = Field(ge=1)  # the figure's place in the question, from 1
    tag: str  # the "[Hình: …]" as the question writes it (one line): what the page replaces with the picture
    alt: str  # the description inside it: the picture's alternative text and the tutor's context
    document_id: str = ""  # where the picture was cut from ("" for an uploaded one)
    page: int = 0
    box: list[float] = Field(default_factory=list)  # left, top, right, bottom on the page, in points
    score: float = 0.0  # how much the description and the drawing share (0 to 1)
    status: FigureStatus = "AUTO"
    method: Literal["VECTOR", "UPLOAD"] = "VECTOR"
    file: str = ""  # relative to the storage directory
    sha256: str = ""
    width: int = 0
    height: int = 0
    version: str = FIGURE_VERSION
    built_at: datetime = Field(default_factory=utc_now)
    decided_by: str | None = None
    decided_at: datetime | None = None

    @property
    def shown(self) -> bool:
        return self.status in SHOWN


class FigureRepository(TenantScopedRepository):
    collection_name = "figures"
    indexes = (
        IndexSpec(
            (
                ("school_id", ASCENDING),
                ("chapter_id", ASCENDING),
                ("question_id", ASCENDING),
                ("order", ASCENDING),
            ),
            "school_chapter_question_order",
            unique=True,
        ),
    )

    async def list_chapter(self, chapter_id: str) -> list[Figure]:
        docs = await self._find(
            {"chapter_id": chapter_id}, sort=[("question_id", ASCENDING), ("order", ASCENDING)]
        )
        return [Figure.from_doc(d) for d in docs]

    async def list_all(self) -> list[Figure]:
        docs = await self._find({}, sort=[("chapter_id", ASCENDING), ("question_id", ASCENDING)])
        return [Figure.from_doc(d) for d in docs]

    async def get(self, figure_id: str) -> Figure | None:
        doc = await self._find_one({"_id": figure_id})
        return Figure.from_doc(doc) if doc else None

    async def get_slot(self, chapter_id: str, question_id: str, order: int) -> Figure | None:
        doc = await self._find_one({"chapter_id": chapter_id, "question_id": question_id, "order": order})
        return Figure.from_doc(doc) if doc else None

    async def save(self, figure: Figure) -> Figure:
        """Write the figure of its slot (chapter, question, order); the slot keeps the id it first had."""
        fields = figure.to_doc()
        fields.pop("_id")
        fields.pop("school_id")
        key = {"chapter_id": figure.chapter_id, "question_id": figure.question_id, "order": figure.order}
        await self._update_one(
            key,
            {"$set": fields, "$setOnInsert": {"_id": figure.id, "school_id": self.school_id}},
            upsert=True,
        )
        return await self.get_slot(**key) or figure  # type: ignore[arg-type]

    async def decide(self, figure_id: str, status: FigureStatus, by: str) -> Figure | None:
        await self._update_one(
            {"_id": figure_id}, {"$set": {"status": status, "decided_by": by, "decided_at": utc_now()}}
        )
        return await self.get(figure_id)

    async def delete(self, figure_id: str) -> bool:
        return await self._delete_one({"_id": figure_id})

    async def mark_stale(self, figure_id: str) -> None:
        await self._update_one({"_id": figure_id}, {"$set": {"status": "REVIEW", "score": 0.0}})
