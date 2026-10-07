"""Storage of the teacher's documents: metadata and extracted text on the database, the original file
on disk under ``var/storage/documents/<id>/`` (gitignored, CLAUDE.md "Chạy local")."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from cavat.core.repository import (
    ASCENDING,
    DESCENDING,
    IndexSpec,
    TenantDocument,
    TenantScopedRepository,
    utc_now,
)

DocumentKind = Literal["SGK", "GIAO_AN", "BAI_TAP", "DE_KIEM_TRA", "KHAC"]
DocumentStatus = Literal["READ", "NEEDS_OCR", "FAILED"]


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
    method: str = ""  # how the text was read: pdf-text, docx, text, ocr-gemini
    pages: int = 0
    text: str = ""
    error: str | None = None


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
