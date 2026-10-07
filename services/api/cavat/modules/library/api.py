"""The teacher's library and lesson content (DOC-1, ADR-020).

- ``/v1/teachers/documents``: the teacher uploads documents (textbook pages, lesson plans, worksheets with
  answers); the original file is kept on disk, its text is read at once and becomes a source of the
  Hybrid RAG (RAG-1).
- ``/v1/teachers/chapters``: what the tutor teaches, node by node, with the answers: theory and its
  question, worked examples, method, items with their hints and solutions, misconceptions. Only the
  teacher sees the answers (rule 2 keeps them out of every prompt).
"""

from __future__ import annotations

import hashlib
import re
from fractions import Fraction
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from cavat.config import REPO_ROOT, get_settings
from cavat.core.repository import new_id
from cavat.modules.assessment.math_checker import parse_literal
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.content.lesson_package import Item
from cavat.modules.library.extract import KINDS, OCR_PROMPT, Extraction, extension_of, extract
from cavat.modules.library.repository import DocumentKind, DocumentRepository, TeacherDocument

MAX_BYTES = 25 * 1024 * 1024  # DI: a chapter of a textbook as a PDF fits


class LibraryError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class DocumentView(BaseModel):
    document_id: str
    title: str
    kind: DocumentKind
    chapter_id: str | None
    filename: str
    content_type: str
    size: int
    uploaded_at: Any
    status: str
    method: str
    pages: int
    chars: int
    error: str | None


class DocumentDetail(DocumentView):
    text: str


def _view(doc: TeacherDocument, with_text: bool = False) -> dict[str, Any]:
    out = {
        "document_id": doc.id,
        "title": doc.title,
        "kind": doc.kind,
        "chapter_id": doc.chapter_id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size": doc.size,
        "uploaded_at": doc.uploaded_at,
        "status": doc.status,
        "method": doc.method,
        "pages": doc.pages,
        "chars": len(doc.text),
        "error": doc.error,
    }
    if with_text:
        out["text"] = doc.text
    return out


def _safe_name(filename: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "tai-lieu"
    return stem[-120:]


def _ocr():
    """Gemini OCR when a key is configured (ADR-017); None leaves scans and photos as NEEDS_OCR."""
    settings = get_settings()
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        return None
    from cavat.modules.ai_gateway.router import build_router

    router = build_router(settings)
    return lambda data, mime: router.describe_image(data, OCR_PROMPT, mime_type=mime).text


def answer_text(item: Item) -> str:
    """The right answer of an item as the teacher reads it."""
    ans = item.answer
    if ans.type == "compare":
        left, right = parse_literal(ans.left).value, parse_literal(ans.right).value
        sign = "<" if left < right else ">" if left > right else "="
        if ans.ask == "sign":
            return f"{ans.left} {sign} {ans.right}"
        larger, smaller = (ans.left, ans.right) if left > right else (ans.right, ans.left)
        return larger if ans.ask == "larger" else smaller
    if ans.type == "order":
        ordered = sorted(ans.numbers, key=lambda n: Fraction(parse_literal(n).value))
        return "; ".join(reversed(ordered) if ans.direction == "desc" else ordered)
    if ans.type == "numeric":
        return ans.value
    if ans.type == "choice":
        right = next(o for o in ans.options if o.correct)
        return f"{right.id}. {right.text}"
    if ans.type == "boolean":
        return "Đúng" if ans.value else "Sai"
    return ans.sample_answer


def chapter_content(chapter: Chapter, source: str) -> dict[str, Any]:
    """Everything the tutor uses to teach the chapter, for the teacher to read and check."""

    def item_view(item_id: str, stage: str) -> dict[str, Any]:
        item = chapter.item(item_id)
        lesson = chapter.lesson_of(item_id)
        return {
            "item_id": item.id,
            "stage": stage,
            "purpose": item.purpose,
            "cognitive_level": item.cognitive_level,
            "difficulty": item.difficulty,
            "stem": item.stem,
            "answer_type": item.answer.type,
            "answer": answer_text(item),
            "hints": [{"level": int(h.level), "target": h.target.value, "text": h.text} for h in item.hints],
            "worked_solution": item.worked_solution,
            "explanation": item.explanation,
            "wrong_answers": dict(getattr(item.answer, "wrong_answers", {}) or {}),
            "lesson_id": lesson.lesson_id,
        }

    nodes = []
    for node_id in chapter.topological_order():
        node = chapter.node(node_id)
        stages = (
            ("Kiểm tra hiểu", node.checks),
            ("Cùng làm", node.completion),
            ("Luyện tập", node.practice),
            ("Vận dụng", node.transfer),
        )
        nodes.append(
            {
                "node_id": node.id,
                "name": node.name,
                "layer": node.layer,
                "description": node.description,
                "home_tip": node.home_tip,
                "theory": [t.model_dump() for t in node.theory],
                "method": node.method.model_dump(),
                "worked_examples": [w.model_dump() for w in node.worked_examples],
                "retell": {"prompt": node.explain.prompt, "key_ideas": node.explain.key_ideas},
                "items": [item_view(i, stage) for stage, ids in stages for i in ids],
                "pass_rule": {"min_mastery": round(100 * node.pass_rule.min_mastery, 1)},
            }
        )
    misconceptions = [
        {
            "id": m.id,
            "kc_id": m.kc_id,
            "name": m.name,
            "description": m.description,
            "severity": m.severity,
            "counter_examples": m.counter_examples,
        }
        for lesson in chapter.lessons.values()
        for m in lesson.misconceptions
    ]
    package = chapter.package
    return {
        "chapter_id": package.chapter_id,
        "title": package.title,
        "version": package.version,
        "status": package.status,
        "source": source,
        "nodes": nodes,
        "relations": [{"source": r.source, "target": r.target, "type": r.type} for r in package.relations],
        "misconceptions": misconceptions,
    }


def build_router(
    database_dependency: Any, teacher_dependency: Any, school_id: str, chapters: Any
) -> APIRouter:
    """``chapters()``: the chapter packages by id with their source file (``chapter_service``)."""
    router = APIRouter(prefix="/v1/teachers", tags=["teacher-library"])
    database_dep, teacher_dep = Depends(database_dependency), Depends(teacher_dependency)

    def repo(database: Any) -> DocumentRepository:
        return DocumentRepository(database, school_id)

    @router.post("/documents", status_code=201, response_model=DocumentView)
    async def upload(
        file: UploadFile,
        title: Annotated[str, Form()] = "",
        kind: Annotated[DocumentKind, Form()] = "KHAC",
        chapter_id: Annotated[str, Form()] = "",
        database: Any = database_dep,
        teacher: str = teacher_dep,
    ):
        """Keep the file, read its text at once (OCR for scans and photos when Gemini is configured)."""
        filename = file.filename or "tai-lieu"
        ext = extension_of(filename)
        if ext not in KINDS:
            raise LibraryError(415, "VALIDATION_ERROR", "PDF, DOCX, TXT, MD, PNG, JPG hoặc WEBP")
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise LibraryError(413, "VALIDATION_ERROR", "the file is larger than 25 MB")
        if not data:
            raise LibraryError(422, "VALIDATION_ERROR", "the file is empty")
        document_id = new_id()
        relative = f"documents/{document_id}/{_safe_name(filename)}"
        target = get_settings().storage_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        status, error = "READ", None
        try:
            found: Extraction = await run_in_threadpool(extract, data, filename, _ocr())
            if found.needs_ocr:
                status = "NEEDS_OCR"
        except Exception as exc:  # a broken file or a failed OCR must not lose the upload
            found, status, error = Extraction("", 0, ""), "FAILED", f"{type(exc).__name__}: {exc}"[:300]
        document = TeacherDocument(
            id=document_id,
            school_id=school_id,
            title=title.strip() or filename,
            kind=kind,
            chapter_id=chapter_id or None,
            filename=filename,
            content_type=KINDS[ext],
            size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            stored_path=relative,
            uploaded_by=teacher,
            status=status,  # type: ignore[arg-type]
            method=found.method,
            pages=found.pages,
            text=found.text,
            error=error,
        )
        await repo(database).create(document)
        return _view(document)

    @router.get("/documents", response_model=list[DocumentView])
    async def documents(database: Any = database_dep, teacher: str = teacher_dep):
        return [_view(d) for d in await repo(database).list_recent()]

    @router.get("/documents/{document_id}", response_model=DocumentDetail)
    async def document(document_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        found = await repo(database).get(document_id)
        if found is None:
            raise LibraryError(404, "NOT_FOUND", "no document with this id")
        return _view(found, with_text=True)

    @router.get("/documents/{document_id}/file")
    async def original(document_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        found = await repo(database).get(document_id)
        if found is None:
            raise LibraryError(404, "NOT_FOUND", "no document with this id")
        path = get_settings().storage_dir / found.stored_path
        if not path.is_file():
            raise LibraryError(404, "NOT_FOUND", "the original file is missing from the storage")
        return FileResponse(path, media_type=found.content_type, filename=found.filename)

    @router.delete("/documents/{document_id}", status_code=204)
    async def remove(document_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        found = await repo(database).get(document_id)
        if found is None:
            raise LibraryError(404, "NOT_FOUND", "no document with this id")
        await repo(database).delete(document_id)
        path = get_settings().storage_dir / found.stored_path
        if path.is_file():
            path.unlink()
            if not any(path.parent.iterdir()):
                path.parent.rmdir()
        return Response(status_code=204)

    @router.get("/chapters")
    async def chapter_list(teacher: str = teacher_dep):
        return [
            {
                "chapter_id": cid,
                "title": ch.package.title,
                "status": ch.package.status,
                "nodes": len(ch.package.nodes),
                "items": sum(
                    len(n.checks) + len(n.completion) + len(n.practice) + len(n.transfer)
                    for n in ch.package.nodes
                ),
            }
            for cid, (ch, _) in chapters().items()
        ]

    @router.get("/chapters/{chapter_id}")
    async def chapter_detail(chapter_id: str, teacher: str = teacher_dep):
        found = chapters().get(chapter_id)
        if found is None:
            raise LibraryError(404, "NOT_FOUND", "no chapter with this id")
        chapter, path = found
        return chapter_content(chapter, str(path.relative_to(REPO_ROOT)))

    return router
