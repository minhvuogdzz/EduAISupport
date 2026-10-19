"""The teacher's draft item bank (INGEST-2) and teaching plan (INGEST-3a): read them, build them again from
the documents of now.

Teacher only: the bank holds the answers of the tests, which never reach a student or a prompt
(CLAUDE.md rule 2).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cavat.modules.ingest.repository import ItemBankRepository, TeachingPlanRepository
from cavat.modules.ingest.review import ReviewError, publish_blockers, review_state
from cavat.modules.ingest.service import (
    PREFIXES,
    cached_drafter,
    decide,
    publish,
    rebuild,
    rebuild_plan,
    undo,
)
from cavat.modules.library.api import LibraryError
from cavat.modules.session import chapter_service


class Decision(BaseModel):
    """One decision of the teacher (``ingest.review``)."""

    target: str
    action: str
    value: Any = None


def _plan_view(plan: Any) -> dict[str, Any]:
    """The stored plan, with what is approved, what waits and why it cannot be published yet."""
    view = plan.to_doc()
    nodes = plan.package.get("nodes", [])
    view["review"] = {
        **review_state(nodes, plan.decisions),
        "blockers": publish_blockers(nodes, plan.problems, plan.decisions),
    }
    return view


def review_view(plan: Any, bank: Any) -> dict[str, Any]:
    from cavat.modules.library.api import chapter_content

    chapter = chapter_service.build_chapter(plan.package, plan.lessons)
    content = chapter_content(chapter, "tài liệu của giáo viên (INGEST-3)")
    drafted = {d["target"].removesuffix(":retry") for d in plan.drafts if d["kind"] == "HINT" and d["ok"]}
    bank_items = {i["item_id"]: i for i in (bank.items if bank else [])}

    def item_note(item_id: str) -> dict[str, Any]:
        draft = bank_items.get(item_id, {})
        return {
            "status": draft.get("status", ""),
            "findings": [f for f in draft.get("findings", []) if not f.get("ok")],
            "page": draft.get("page"),
            "document_id": draft.get("document_id"),
            "answer_document_id": draft.get("answer_document_id"),
            "ai_hints": sorted(int(t.rsplit(":H", 1)[1]) for t in drafted if t.startswith(f"{item_id}:H")),
        }

    in_plan = {it.id for lesson in chapter.lessons.values() for it in lesson.items}
    left_out = [
        {
            "item_id": i,
            "reason": reason,
            **item_note(i),
            "stem": bank_items.get(i, {}).get("stem", ""),
            "answer": bank_items.get(i, {}).get("answer", ""),
        }
        for line in plan.left_out
        for i, reason in [line.split(": ", 1)]
        if i not in in_plan
    ]
    return {
        "chapter_id": plan.chapter_id,
        "status": plan.status,
        "current": plan.current,
        "built_at": plan.built_at,
        "content": content,
        "sources": plan.sources,
        "items": {i: item_note(i) for i in in_plan},
        "left_out": left_out,
        "decisions": plan.decisions,
        "assessment": plan.assessment,
        "review": _plan_view(plan)["review"],
        "drafted": {
            "hints": len(drafted),
            "parts": sum(1 for d in plan.drafts if d["kind"] != "HINT" and d["ok"]),
        },
        # FIX-3: the periods whose "vì sao" Qwen drafted (they wait for the teacher)
        "ai_verify": sorted({d["target"] for d in plan.drafts if d["kind"] == "VERIFY" and d["ok"]}),
    }


def build_router(database_dependency: Any, teacher_dependency: Any, school_id: str) -> APIRouter:
    router = APIRouter(prefix="/v1/teachers/item-banks", tags=["teacher-item-bank"])
    database_dep, teacher_dep = Depends(database_dependency), Depends(teacher_dependency)

    def known(chapter_id: str) -> None:
        if chapter_id not in PREFIXES:
            raise LibraryError(404, "NOT_FOUND", "unknown chapter")

    @router.get("/{chapter_id}")
    async def get_bank(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        known(chapter_id)
        bank = await ItemBankRepository(database, school_id).get(chapter_id)
        if bank is None:
            raise LibraryError(404, "NOT_FOUND", "the item bank of this chapter is not built yet")
        return bank.to_doc()

    @router.post("/{chapter_id}/build")
    async def build(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        known(chapter_id)
        bank = await rebuild(database, school_id, chapter_id)
        return {"chapter_id": chapter_id, "version": bank.version, "stats": bank.stats}

    plans = APIRouter(prefix="/v1/teachers/teaching-plans", tags=["teacher-teaching-plan"])

    @plans.get("/{chapter_id}")
    async def get_plan(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        known(chapter_id)
        plan = await TeachingPlanRepository(database, school_id).get(chapter_id)
        if plan is None:
            raise LibraryError(404, "NOT_FOUND", "the teaching plan of this chapter is not built yet")
        return _plan_view(plan)

    @plans.get("/{chapter_id}/view")
    async def view_plan(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        """The plan as the teacher reviews it: the chapter it would teach, read like a chapter file, with
        where each period comes from, what the checks said of each item, which hints Qwen wrote, the
        teacher's decisions, and the items left out (a misread answer key, a conflict) to fix."""
        known(chapter_id)
        plan = await TeachingPlanRepository(database, school_id).get(chapter_id)
        if plan is None:
            raise LibraryError(404, "NOT_FOUND", "the teaching plan of this chapter is not built yet")
        bank = await ItemBankRepository(database, school_id).get(chapter_id)
        return review_view(plan, bank)

    @plans.post("/{chapter_id}/build")
    async def build_teaching_plan(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        known(chapter_id)
        plan = await rebuild_plan(database, school_id, chapter_id, cached_drafter())
        return {
            "chapter_id": chapter_id,
            "version": plan.version,
            "nodes": len(plan.package.get("nodes", [])),
            "problems": len(plan.problems),
            "left_out": len(plan.left_out),
        }

    async def _decided(call) -> dict[str, Any]:
        try:
            plan = await call
        except ReviewError as exc:
            raise LibraryError(409, "VALIDATION_ERROR", str(exc)) from exc
        return _plan_view(plan)

    @plans.post("/{chapter_id}/decisions")
    async def decide_one(
        chapter_id: str, body: Decision, database: Any = database_dep, teacher: str = teacher_dep
    ):
        """One decision of the teacher (approve, reject, edit) on an item, a hint or a period."""
        known(chapter_id)
        return await _decided(
            decide(database, school_id, chapter_id, body.target, body.action, body.value, teacher)
        )

    @plans.delete("/{chapter_id}/decisions")
    async def undo_one(
        chapter_id: str, target: str, database: Any = database_dep, teacher: str = teacher_dep
    ):
        known(chapter_id)
        return await _decided(undo(database, school_id, chapter_id, target))

    @plans.post("/{chapter_id}/publish")
    async def publish_plan(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        """The tutor teaches this plan from now on (new sessions); refused while anything waits."""
        known(chapter_id)
        view = await _decided(publish(database, school_id, chapter_id, teacher))
        snap = view["published"][view["current"]]
        chapter_service.register_published(
            chapter_id, view["current"], snap["package"], snap["lessons"], current=True
        )
        return view

    root = APIRouter()
    root.include_router(router)
    root.include_router(plans)
    return root
