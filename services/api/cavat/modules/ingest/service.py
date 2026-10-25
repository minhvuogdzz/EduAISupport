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
    from cavat.modules.ingest.review import apply_item_overrides, apply_plan_decisions, bind_hint_decisions

    repo = TeachingPlanRepository(database, school_id)
    before = await repo.get(chapter_id)
    # Bound to the words of the plan as it was stored, before the new drafts replace them (REFORM-3b).
    decisions = bind_hint_decisions(before.decisions, before.lessons, before.drafts) if before else {}
    bank = await rebuild(database, school_id, chapter_id)
    documents = [
        d for d in await DocumentRepository(database, school_id).list_all() if d.chapter_id == chapter_id
    ]
    drafts_in = apply_item_overrides([ItemDraft(**item) for item in bank.items], decisions)
    plan = build_plan(
        chapter_id, TITLES.get(chapter_id, chapter_id), PREFIXES.get(chapter_id, "CH"), documents, drafts_in
    )
    drafted = drafter.draft(plan) if drafter is not None else []
    kept = _keep_earlier_drafts(plan, before) if before is not None else set()
    if drafted or kept:
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
        drafts=_records(drafted, before, kept) if drafted else (before.drafts if before else []),
        decisions=decisions,
        published=before.published if before else {},
        current=before.current if before else None,
    )
    await repo.save(stored)
    return await repo.get(chapter_id) or stored


def _keep_earlier_drafts(plan: Any, before: TeachingPlan) -> set[str]:
    """FIX-3: what the drafter could not give again stays as it was in the stored plan.

    The drafts are cached by their request, and a request carries the item's answer as the builder reads it.
    INGEST-5 changed how answers are read after the plan was last built (2026-10-12): 55 hint requests no
    longer met their cache, and a rebuild from the cache (any review decision) dropped the hints of about
    270 items, while a rebuild with Qwen drafted new ones under the old "approve" decisions. Now an item
    with no drafted hint keeps the hints it had, when its stem is the same; a period keeps its "vì sao".
    Returns the draft targets kept ("STP-BT-07a:H2", "STP-T01")."""
    from cavat.modules.content.lesson_package import LessonPackage

    kept: set[str] = set()
    earlier = {
        item.id: item for raw in before.lessons.values() for item in LessonPackage.model_validate(raw).items
    }
    for lesson_id, lesson in list(plan.lessons.items()):
        items = []
        for item in lesson.items:
            old = earlier.get(item.id)
            if not item.hints and old is not None and old.hints and old.stem == item.stem:
                item = item.model_copy(update={"hints": old.hints})
                kept |= {f"{item.id}:H{int(h.level)}" for h in old.hints}
            items.append(item)
        plan.lessons[lesson_id] = lesson.model_copy(update={"items": items})
    old_nodes = {n.get("id"): n for n in before.package.get("nodes", [])}
    nodes = []
    for node in plan.package.nodes:
        old_verify = old_nodes.get(node.id, {}).get("verify_prompt", "")
        if not node.verify_prompt and old_verify:
            node = node.model_copy(update={"verify_prompt": old_verify})
            kept.add(node.id)
        nodes.append(node)
    plan.package = plan.package.model_copy(update={"nodes": nodes})
    return kept


def _records(drafted: list[Any], before: TeachingPlan | None, kept: set[str]) -> list[dict[str, Any]]:
    """The drafts of this build, and the earlier records of what was kept (still shown as "AI soạn")."""
    from cavat.modules.ingest.drafting import as_records

    records = as_records(drafted)
    fresh = {(r["kind"], r["target"]) for r in records if r["ok"]}
    for r in before.drafts if before else []:
        target = r["target"].removesuffix(":retry")
        if r["ok"] and target in kept and (r["kind"], r["target"]) not in fresh:
            records.append(r)
    return records


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
    from cavat.modules.ingest.review import check_decision, decided_text, hint_target, hint_text_now

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
        if (key := hint_target(d["target"])) and d["action"] in ("approve", "reject"):
            # The words the teacher read: given with the decision, else the hint the plan shows (REFORM-3b).
            text = decided_text(decisions[d["target"]]) or hint_text_now(plan.lessons, plan.drafts, *key)
            if text:
                decisions[d["target"]]["text"] = text
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
