"""The teacher's draft item bank (INGEST-2) and teaching plan (INGEST-3a): read them, build them again from
the documents of now.

Teacher only: the bank holds the answers of the tests, which never reach a student or a prompt
(CLAUDE.md rule 2).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from cavat.modules.ingest.repository import ItemBankRepository, TeachingPlanRepository
from cavat.modules.ingest.service import PREFIXES, rebuild, rebuild_plan
from cavat.modules.library.api import LibraryError


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
        return plan.to_doc()

    @plans.post("/{chapter_id}/build")
    async def build_teaching_plan(chapter_id: str, database: Any = database_dep, teacher: str = teacher_dep):
        known(chapter_id)
        plan = await rebuild_plan(database, school_id, chapter_id)
        return {
            "chapter_id": chapter_id,
            "version": plan.version,
            "nodes": len(plan.package.get("nodes", [])),
            "problems": len(plan.problems),
            "left_out": len(plan.left_out),
        }

    root = APIRouter()
    root.include_router(router)
    root.include_router(plans)
    return root
