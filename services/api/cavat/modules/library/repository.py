"""Storage of the teacher's documents: metadata and extracted text on the database, the original file
on disk under ``var/storage/documents/<id>/`` (gitignored, CLAUDE.md "Chạy local")."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from cavat.core.repository import (
    ASCENDING,
    DESCENDING,
    IndexSpec,
    TenantDocument,
    TenantScopedRepository,
    utc_now,
)

DocumentKind = Literal[
    "SGK", "BAI_GIANG", "GIAO_AN", "BAI_TAP", "PHIEU", "DE_KIEM_TRA", "DAP_AN", "LOI_SAI", "KHAC"
]
# NEEDS_REVIEW: read, but some pages could not be checked (INGEST-1); the teacher looks at those pages.
DocumentStatus = Literal["READ", "NEEDS_REVIEW", "NEEDS_OCR", "FAILED"]

# What the Hybrid RAG may read (INGEST-1). Never an answer key or a test: a passage of the RAG can reach a
# prompt, and an answer of an assessment item never may (CLAUDE.md rule 2).
RAG_KINDS: frozenset[str] = frozenset({"SGK", "BAI_GIANG", "GIAO_AN", "BAI_TAP", "PHIEU", "LOI_SAI", "KHAC"})


class PageReadRecord(BaseModel):
    """How one page was read (``extract.PageRead``)."""

    page: int
    method: str
    reason: str = ""
    status: str = "OK"
    missing: list[str] = Field(default_factory=list)
    added: list[str] = Field(default_factory=list)
    note: str = ""
    disputed: list[str] = Field(default_factory=list)


class TeacherDocument(TenantDocument):
    title: str = Field(min_length=1, max_length=200)
    kind: DocumentKind = "KHAC"
    chapter_id: str | None = None  # the chapter it serves (math-g5-decimals, ...), None: not decided yet
    filename: str
    content_type: str
    size: int
    sha256: str
    stored_path: str  # relative to the storage directory
    uploaded_by: str  # the teacher account
    uploaded_at: datetime = Field(default_factory=utc_now)
    status: DocumentStatus = "READ"
    method: str = ""  # how the text was read: pdf-text, pdf-text+ocr, docx, text, ocr-gemini
    pages: int = 0
    text: str = ""
    error: str | None = None
    page_reads: list[PageReadRecord] = Field(default_factory=list)  # PDF, page by page (INGEST-1)
    answers_for: str | None = None  # an answer key: the document of the questions it answers


class DocumentRepository(TenantScopedRepository):
    collection_name = "documents"
    indexes = (IndexSpec((("school_id", ASCENDING), ("uploaded_at", DESCENDING)), "school_recent"),)

    async def create(self, document: TeacherDocument) -> TeacherDocument:
        await self._insert(document.to_doc())
        return document

    async def get(self, document_id: str) -> TeacherDocument | None:
        doc = await self._find_one({"_id": document_id})
        return TeacherDocument.from_doc(doc) if doc else None

    async def list_recent(self, limit: int = 200) -> list[TeacherDocument]:
        docs = await self._find({}, sort=[("uploaded_at", DESCENDING)], limit=limit, projection={"text": 0})
        return [TeacherDocument.from_doc({**d, "text": ""}) for d in docs]

    async def list_all(self) -> list[TeacherDocument]:
        """Every document with its text (the RAG index reads them)."""
        return [TeacherDocument.from_doc(d) for d in await self._find({})]

    async def delete(self, document_id: str) -> bool:
        return await self._delete_one({"_id": document_id})
