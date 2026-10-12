"""Build and keep the draft item bank of a chapter (INGEST-2): the API and ``make item-bank`` share this."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from cavat.modules.ingest.build import BUILDER_VERSION, build_bank
from cavat.modules.ingest.repository import ItemBank, ItemBankRepository
from cavat.modules.library.repository import DocumentRepository

# The code of each chapter in item ids (the owner's file names: STP-baitap.pdf, DTTGHT-baitap.pdf).
PREFIXES = {"math-g5-decimals": "STP", "math-g5-area-triangle-trapezoid": "DTTGHT"}
STATUSES = ("VERIFIED", "REVIEW", "CONFLICT", "DISPUTED", "UNCHECKED", "NO_ANSWER")


async def rebuild(database: Any, school_id: str, chapter_id: str) -> ItemBank:
    """The bank of the chapter from its documents of now, replacing the one kept."""
    documents = [
        d for d in await DocumentRepository(database, school_id).list_all() if d.chapter_id == chapter_id
    ]
    items = build_bank(chapter_id, PREFIXES.get(chapter_id, "CH"), documents)
    counts = Counter(i.status for i in items)
    bank = ItemBank(
        school_id=school_id,
        chapter_id=chapter_id,
        version=BUILDER_VERSION,
        sources=sorted(d.id for d in documents),
        stats={"items": len(items), **{s: counts.get(s, 0) for s in STATUSES}},
        items=[asdict(i) for i in items],
    )
    repo = ItemBankRepository(database, school_id)
    await repo.save(bank)
    return await repo.get(chapter_id) or bank
