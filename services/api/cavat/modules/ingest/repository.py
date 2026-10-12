"""Storage of the draft item bank of each chapter (INGEST-2): one document per chapter.

The bank is rebuilt from the teacher's documents, never edited in place by a model: building it again
replaces the document. Its items are teaching content of the school (``school_id``), not learner data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from cavat.core.repository import ASCENDING, IndexSpec, TenantDocument, TenantScopedRepository, utc_now


class ItemBank(TenantDocument):
    chapter_id: str
    version: str  # the builder (``build.BUILDER_VERSION``)
    built_at: datetime = Field(default_factory=utc_now)
    sources: list[str] = Field(default_factory=list)  # the documents it was built from
    stats: dict[str, int] = Field(default_factory=dict)  # items by status
    items: list[dict[str, Any]] = Field(default_factory=list)  # ``build.ItemDraft`` as dicts


class ItemBankRepository(TenantScopedRepository):
    collection_name = "item_banks"
    indexes = (
        IndexSpec((("school_id", ASCENDING), ("chapter_id", ASCENDING)), "school_chapter", unique=True),
    )

    async def save(self, bank: ItemBank) -> ItemBank:
        """Replace the bank of this chapter (one document per chapter, written at once)."""
        fields = bank.to_doc()
        fields.pop("_id")
        fields.pop("school_id")
        await self._update_one(
            {"chapter_id": bank.chapter_id},
            {"$set": fields, "$setOnInsert": {"_id": bank.id, "school_id": self.school_id}},
            upsert=True,
        )
        return bank

    async def get(self, chapter_id: str) -> ItemBank | None:
        doc = await self._find_one({"chapter_id": chapter_id})
        return ItemBank.from_doc(doc) if doc else None
