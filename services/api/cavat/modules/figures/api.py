"""The figures of the questions (FIG-1, ADR-034).

- ``GET /v1/figures?chapter_id=``: the figures a child may see (approved by the teacher, or found with
  confidence and not rejected), for the web to put above the words of a question. A student, a parent or
  the teacher may ask: a picture holds no answer.
- ``GET /v1/figures/{id}/image``: the PNG. A child gets only a figure shown to children (rule 4: the
  backend decides, the page does not hide).
- ``/v1/teachers/figures``: everything found with its status and score, "Duyệt hình", "Bỏ hình" and
  "Thay hình" (the teacher's own picture takes the slot).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from cavat.modules.figures import service
from cavat.modules.figures.matching import SURE_SCORE
from cavat.modules.figures.repository import Figure, FigureRepository
from cavat.modules.library.api import LibraryError


class FigureView(BaseModel):
    """What the page needs to draw a figure above a question."""

    figure_id: str
    question_id: str
    order: int
    tag: str  # the "[Hình: …]" the question's words hold: the page puts the picture in its place
    alt: str
    width: int
    height: int
    version: str  # changes when the picture does: the page keeps a picture by it


class TeacherFigureView(FigureView):
    chapter_id: str
    status: str
    method: str
    score: float
    page: int
    document_id: str
    shown: bool
    decided_by: str | None


class Decision(BaseModel):
    action: Literal["approve", "reject", "undo"]


def _view(figure: Figure) -> dict[str, Any]:
    return {
        "figure_id": figure.id,
        "question_id": figure.question_id,
        "order": figure.order,
        "tag": figure.tag,
        "alt": figure.alt,
        "width": figure.width,
        "height": figure.height,
        "version": figure.sha256[:12],
    }


def _teacher_view(figure: Figure) -> dict[str, Any]:
    return {
        **_view(figure),
        "chapter_id": figure.chapter_id,
        "status": figure.status,
        "method": figure.method,
        "score": figure.score,
        "page": figure.page,
        "document_id": figure.document_id,
        "shown": figure.shown,
        "decided_by": figure.decided_by,
    }


def build_router(
    database_dependency: Any,
    teacher_dependency: Any,
    viewer_dependency: Any,
    school_id: str,
    storage_dir: Callable[[], Path],
) -> APIRouter:
    """``viewer_dependency`` gives who looks ("TEACHER", "STUDENT" or "PARENT"): the page of a figure that
    is not shown to children is for the teacher only."""
    router = APIRouter(tags=["figures"])
    database_dep, teacher_dep, viewer_dep = (
        Depends(database_dependency),
        Depends(teacher_dependency),
        Depends(viewer_dependency),
    )

    def repo(database: Any) -> FigureRepository:
        return FigureRepository(database, school_id)

    @router.get("/v1/figures", response_model=list[FigureView])
    async def shown_figures(chapter_id: str, database: Any = database_dep, viewer: str = viewer_dep):
        figures = await repo(database).list_chapter(chapter_id)
        return [_view(f) for f in figures if f.shown or viewer == "TEACHER"]

    @router.get("/v1/figures/{figure_id}/image")
    async def image(figure_id: str, database: Any = database_dep, viewer: str = viewer_dep):
        figure = await repo(database).get(figure_id)
        if figure is None or not (figure.shown or viewer == "TEACHER"):
            raise LibraryError(404, "NOT_FOUND", "no such figure")
        root = (storage_dir() / "figures").resolve()
        path = (storage_dir() / figure.file).resolve()
        if root not in path.parents or not path.is_file():
            raise LibraryError(404, "NOT_FOUND", "the picture of this figure is not on this disk")
        # The page asks with ?v=<version>: a picture never changes under its version.
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=86400"})

    @router.get("/v1/teachers/figures", response_model=list[TeacherFigureView])
    async def all_figures(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        return [_teacher_view(f) for f in await repo(database).list_chapter(chapter_id)]

    @router.post("/v1/teachers/figures/{figure_id}/decision", response_model=TeacherFigureView)
    async def decide(
        figure_id: str, body: Decision, database: Any = database_dep, teacher: str = teacher_dep
    ):
        """ "Duyệt hình" shows it, "Bỏ hình" hides it, undo gives it back to what the finder said."""
        figures = repo(database)
        figure = await figures.get(figure_id)
        if figure is None:
            raise LibraryError(404, "NOT_FOUND", "no such figure")
        if body.action == "approve":
            status = "APPROVED"
        elif body.action == "reject":
            status = "REJECTED"
        else:
            status = "AUTO" if figure.score >= SURE_SCORE or figure.method == "UPLOAD" else "REVIEW"
        decided = await figures.decide(figure_id, status, teacher)  # type: ignore[arg-type]
        return _teacher_view(decided or figure)

    @router.post("/v1/teachers/figures", status_code=201, response_model=TeacherFigureView)
    async def replace(
        file: UploadFile,
        chapter_id: Annotated[str, Form()],
        question_id: Annotated[str, Form()],
        order: Annotated[int, Form(ge=1)] = 1,
        tag: Annotated[str, Form()] = "",
        alt: Annotated[str, Form()] = "",
        database: Any = database_dep,
        teacher: str = teacher_dep,
    ):
        """ "Thay hình": the teacher's own picture (PNG, JPG, WEBP) takes the figure's place, approved."""
        data = await file.read(service.MAX_UPLOAD_BYTES + 1)
        try:
            figure = await service.put_upload(
                database,
                school_id,
                storage_dir(),
                chapter_id=chapter_id,
                question_id=question_id,
                order=order,
                tag=tag,
                alt=alt,
                data=data,
                by=teacher,
            )
        except ValueError as exc:
            code = str(exc)
            if code == "TOO_BIG":
                raise LibraryError(413, "VALIDATION_ERROR", "ảnh quá lớn (tối đa 5 MB)") from exc
            raise LibraryError(415, "VALIDATION_ERROR", "chỉ nhận ảnh PNG, JPG hoặc WEBP") from exc
        return _teacher_view(figure)

    return router
