"""Build and keep the draft item bank of a chapter (INGEST-2): the API and ``make item-bank`` share this."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from typing import Any

from cavat.core.repository import new_id
from cavat.modules.ingest.build import BUILDER_VERSION, ItemDraft, build_bank
from cavat.modules.ingest.repository import ItemBank, ItemBankRepository, TeachingPlan, TeachingPlanRepository
from cavat.modules.ingest.teaching import PLAN_VERSION, build_plan
from cavat.modules.library.repository import DocumentRepository

# The code of each chapter in item ids (the owner's file names: STP-baitap.pdf, DTTGHT-baitap.pdf).
PREFIXES = {"math-g5-decimals": "STP", "math-g5-area-triangle-trapezoid": "DTTGHT"}
TITLES = {
    "math-g5-decimals": "Số thập phân",
    "math-g5-area-triangle-trapezoid": "Diện tích hình tam giác, hình thang",
}
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


async def rebuild_plan(database: Any, school_id: str, chapter_id: str, drafter: Any = None) -> TeachingPlan:
    """The draft teaching plan of the chapter from its documents and its item bank, both of now. With a
    ``drafting.Drafter``, what the documents leave out is drafted by Qwen and checked (INGEST-3b). The
    teacher's decisions and published versions are kept and applied on top (INGEST-4)."""
    from cavat.modules.content.chapter_package import validate_chapter
    from cavat.modules.ingest.drafting import as_records
    from cavat.modules.ingest.review import apply_item_overrides, apply_plan_decisions

    repo = TeachingPlanRepository(database, school_id)
    before = await repo.get(chapter_id)
    decisions = before.decisions if before else {}
    bank = await rebuild(database, school_id, chapter_id)
    documents = [
        d for d in await DocumentRepository(database, school_id).list_all() if d.chapter_id == chapter_id
    ]
    drafts_in = apply_item_overrides([ItemDraft(**item) for item in bank.items], decisions)
    plan = build_plan(
        chapter_id, TITLES.get(chapter_id, chapter_id), PREFIXES.get(chapter_id, "CH"), documents, drafts_in
    )
    drafted = drafter.draft(plan) if drafter is not None else []
    if drafted:
        plan.problems = validate_chapter(plan.chapter())
    apply_plan_decisions(plan, decisions)
    stored = TeachingPlan(
        id=before.id if before else new_id(),
        school_id=school_id,
        chapter_id=chapter_id,
        version=PLAN_VERSION,
        status="PUBLISHED" if before and before.current else "DRAFT",
        package=plan.package.model_dump(),
        lessons={k: v.model_dump() for k, v in plan.lessons.items()},
        assessment=plan.assessment,
        problems=plan.problems,
        sources=plan.sources,
        left_out=plan.left_out,
        drafts=as_records(drafted) if drafted else (before.drafts if before else []),
        decisions=decisions,
        published=before.published if before else {},
        current=before.current if before else None,
    )
    await repo.save(stored)
    return await repo.get(chapter_id) or stored


def cached_drafter() -> Any:
    """Qwen's drafts from the disk cache only: a teacher's decision rebuilds the plan without a model call."""
    from cavat.config import get_settings
    from cavat.modules.ingest.drafting import Drafter

    return Drafter(None, get_settings().storage_dir / "cache" / "drafts")


async def decide(
    database: Any, school_id: str, chapter_id: str, target: str, action: str, value: Any, by: str
) -> TeachingPlan:
    """Record one decision of the teacher and rebuild the plan with it."""
    return await decide_many(
        database, school_id, chapter_id, [{"target": target, "action": action, "value": value}], by
    )


async def decide_many(
    database: Any, school_id: str, chapter_id: str, batch: list[dict[str, Any]], by: str
) -> TeachingPlan:
    """Record several decisions at once (``target``, ``action``, ``value``, and why: ``reason``) and rebuild
    the plan once; every decision is checked before any is written."""
    from cavat.core.repository import utc_now
    from cavat.modules.ingest.review import check_decision

    for d in batch:
        check_decision(d["target"], d["action"], d.get("value"))
    repo = TeachingPlanRepository(database, school_id)
    plan = await repo.get(chapter_id)
    if plan is None:
        plan = await rebuild_plan(database, school_id, chapter_id, cached_drafter())
    decisions = dict(plan.decisions)
    at = utc_now().isoformat()
    for d in batch:
        decisions[d["target"]] = {"action": d["action"], "value": d.get("value"), "by": by, "at": at}
        if d.get("reason"):
            decisions[d["target"]]["reason"] = d["reason"]
    await repo.save(plan.model_copy(update={"decisions": decisions}))
    return await rebuild_plan(database, school_id, chapter_id, cached_drafter())


async def undo(database: Any, school_id: str, chapter_id: str, target: str) -> TeachingPlan:
    """Forget one decision: the target goes back to what the documents and Qwen give."""
    repo = TeachingPlanRepository(database, school_id)
    plan = await repo.get(chapter_id)
    if plan is None or target not in plan.decisions:
        from cavat.modules.ingest.review import ReviewError

        raise ReviewError(f"no decision on {target}")
    decisions = {k: v for k, v in plan.decisions.items() if k != target}
    await repo.save(plan.model_copy(update={"decisions": decisions}))
    return await rebuild_plan(database, school_id, chapter_id, cached_drafter())


async def publish(database: Any, school_id: str, chapter_id: str, by: str) -> TeachingPlan:
    """Make the reviewed plan the one the tutor teaches; refused while anything waits for the teacher."""
    from cavat.core.repository import utc_now
    from cavat.modules.ingest.review import ReviewError, publish_blockers

    repo = TeachingPlanRepository(database, school_id)
    plan = await repo.get(chapter_id)
    if plan is None:
        raise ReviewError("the teaching plan of this chapter is not built yet")
    blockers = publish_blockers(plan.package.get("nodes", []), plan.problems, plan.decisions)
    if blockers:
        raise ReviewError("; ".join(blockers[:20]))
    now = utc_now()
    version = f"tl-{now:%Y%m%d%H%M%S}"  # a version of the teacher's documents, never one of the YAML files
    package = {**plan.package, "version": version, "status": "PUBLISHED"}
    lessons = {k: {**v, "version": version, "status": "PUBLISHED"} for k, v in plan.lessons.items()}
    published = {
        **plan.published,
        version: {"package": package, "lessons": lessons, "by": by, "at": now.isoformat()},
    }
    await repo.save(
        plan.model_copy(update={"published": published, "current": version, "status": "PUBLISHED"})
    )
    return await repo.get(chapter_id) or plan
