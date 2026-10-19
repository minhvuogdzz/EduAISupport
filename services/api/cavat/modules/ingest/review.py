"""The teacher's review of a draft teaching plan (INGEST-4): decisions that outlive every rebuild.

The plan is rebuilt from the documents, the item bank and Qwen's cached drafts; the teacher's decisions are
applied on top, so fixing a misread answer key or rewording a hint is never lost. A decision names a target:

- ``item:<id>``: approve or reject an item; ``item:<id>/stem`` and ``item:<id>/answer``: what the item asks
  and its right answer, as the teacher writes them. An item whose answer the teacher wrote is taught
  (status TEACHER) even when the documents' answer was disputed or in conflict; the checks still run and
  their findings are shown;
- ``hint:<item>:H<n>``: approve, reject or edit (the text) one hint;
- ``item:<id>/stage``: put an item at another stage of its period (checks, completion, practice, transfer);
- ``item:<id>/facts``: what a right answer to an open question must say (``KeyFacts``, DI-48), when the
  key does not let the builder read it;
- ``node:<id>``: approve a period as a whole; ``node:<id>/<path>``: edit one part of it, e.g.
  ``node:STP-T01/theory/T1/reply``, ``node:STP-T01/method/rule``, ``node:STP-T01/explain/key_ideas``; an
  explanation or worked example the documents lack is added by its first edit
  (``node:STP-T03/theory/T2/text``); ``node:<id>/pass_rule/min_forms``: how many question forms the
  period asks, when its documents give fewer than the default two;
- ``node:<id>/verify/prompt``: the "vì sao" asked after a right answer to an item of the period (FIX-3);
  edit, or reject to ask the generic one; it reaches every item of the period that has no "vì sao" of its own;
- ``misconception:<id>/counter_examples``: the counterexamples of a mistake, one per line (edit), or none
  (reject), when one names an answer or does not fit (FIX-3).

A plan is published only when every period is approved and the tutor's validation asks for nothing: the
teacher, not the builder, decides what is taught (CLAUDE.md: the owner approves pedagogical content).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from cavat.core.pedagogy import HintLevel
from cavat.modules.content.chapter_package import validate_chapter
from cavat.modules.content.lesson_package import HintTemplate
from cavat.modules.ingest.build import ItemDraft, judge
from cavat.modules.ingest.teaching import Plan

ACTIONS = frozenset({"approve", "reject", "edit"})
NODE_FIELDS = {
    "theory": ("text", "ask", "reply", "accept", "representation"),
    "method": ("rule", "steps"),
    "explain": ("prompt", "key_ideas"),
    "worked_examples": ("problem", "steps", "answer"),
    # A period whose documents give one question form only: the teacher lowers its pass rule (a DI).
    "pass_rule": ("min_forms",),
    "verify": ("prompt",),  # FIX-3: the period's "vì sao"
}
STAGES = {  # where the teacher may put an item: node list, purpose, level, transfer
    "checks": ("CONCEPT_CHECK", "A", "none"),
    "completion": ("PRACTICE", "B", "none"),
    "practice": ("PRACTICE", "B", "none"),
    "transfer": ("PRACTICE", "D", "near"),
}


class ReviewError(ValueError):
    """A decision that names nothing in the plan, or an action the target does not take."""


def check_decision(target: str, action: str, value: Any) -> None:
    if action not in ACTIONS:
        raise ReviewError(f"unknown action {action!r}")
    kind = target.split(":", 1)[0]
    if kind not in ("item", "hint", "node", "misconception"):
        raise ReviewError(f"unknown target {target!r}")
    if kind == "misconception" and not target.endswith("/counter_examples"):
        raise ReviewError(f"{target}: a mistake edits its counter_examples")
    editable = target.count("/") > 0 or kind == "hint"
    if action == "edit" and not editable:
        raise ReviewError(f"{target} is approved or rejected, its parts are edited")
    if action == "edit" and (value is None or value == "" or value == []):
        raise ReviewError("an edit needs a value")
    if kind == "item" and target.endswith("/stage") and value not in STAGES:
        raise ReviewError(f"{target}: one of " + ", ".join(STAGES))
    if kind == "item" and target.endswith("/facts"):
        from pydantic import ValidationError

        from cavat.modules.content.lesson_package import KeyFacts

        try:
            KeyFacts.model_validate(value)
        except ValidationError as exc:
            raise ReviewError(f"{target}: {exc.errors()[0]['msg']}") from exc
    if kind == "node" and "/" in target:
        path = target.split("/")[1:]
        if path[0] not in NODE_FIELDS or path[-1] not in NODE_FIELDS[path[0]]:
            raise ReviewError(
                f"{target}: a node edits " + ", ".join(f"{k}/{v}" for k, v in NODE_FIELDS.items())
            )


def apply_item_overrides(
    drafts: list[ItemDraft], decisions: Mapping[str, Mapping[str, Any]]
) -> list[ItemDraft]:
    """The bank with the teacher's stems and answers; a rejected item is never taught."""
    out = []
    for draft in drafts:
        stem = decisions.get(f"item:{draft.item_id}/stem")
        answer = decisions.get(f"item:{draft.item_id}/answer")
        verdict = decisions.get(f"item:{draft.item_id}", {}).get("action")
        if stem or answer:
            if stem:
                draft.stem = str(stem["value"])
                draft.check_stem = draft.stem.split("\n")[-1].removeprefix(f"{draft.part}) ").strip()
            if answer:
                draft.answer = str(answer["value"])
            judge(draft, set())  # the checks still run on the teacher's text, and are shown
            draft.status = "TEACHER"
        if verdict == "reject":
            draft.status = "REJECTED"
        out.append(draft)
    return out


def apply_plan_decisions(plan: Plan, decisions: Mapping[str, Mapping[str, Any]]) -> None:
    """Hints and parts of periods as the teacher decided; the plan's problems are computed again."""
    for lesson_id, lesson in list(plan.lessons.items()):
        items = []
        for item in lesson.items:
            hints = []
            for hint in item.hints:
                decision = decisions.get(f"hint:{item.id}:H{int(hint.level)}", {})
                if decision.get("action") == "reject":
                    continue
                if decision.get("action") == "edit":
                    hint = hint.model_copy(update={"text": str(decision["value"])})
                hints.append(hint)
            present = {int(h.level) for h in hints}
            for target, decision in decisions.items():  # a hint the teacher wrote where Qwen gave none
                m = re.fullmatch(rf"hint:{re.escape(item.id)}:H(\d)", target)
                if m and decision.get("action") == "edit" and int(m.group(1)) not in present:
                    level = HintLevel(int(m.group(1)))
                    hints.append(
                        HintTemplate(target=_TARGETS[level], level=level, text=str(decision["value"]))
                    )
            update: dict[str, Any] = {"hints": sorted(hints, key=lambda h: int(h.level))}
            facts = decisions.get(f"item:{item.id}/facts", {})
            if facts.get("action") == "edit" and item.answer.type == "open":
                from cavat.modules.content.lesson_package import KeyFacts

                update["answer"] = item.answer.model_copy(
                    update={"facts": KeyFacts.model_validate(facts["value"])}
                )
            items.append(item.model_copy(update=update))
        plan.lessons[lesson_id] = lesson.model_copy(update={"items": items})
    nodes = []
    for node in plan.package.nodes:
        for target, decision in decisions.items():
            if target.startswith(f"node:{node.id}/") and decision.get("action") == "edit":
                node = _edit_node(node, target.split("/")[1:], decision["value"])
        if decisions.get(f"node:{node.id}/verify/prompt", {}).get("action") == "reject":
            node = node.model_copy(update={"verify_prompt": ""})
        nodes.append(node)
    plan.package = plan.package.model_copy(update={"nodes": nodes})
    _move_items(plan, decisions)
    _counter_examples(plan, decisions)
    _verify_to_items(plan)
    plan.problems = validate_chapter(plan.chapter())


def _counter_examples(plan: Plan, decisions: Mapping[str, Mapping[str, Any]]) -> None:
    """The counterexamples of a mistake as the teacher wrote them, or none (FIX-3)."""
    chosen = {
        t.removeprefix("misconception:").removesuffix("/counter_examples"): d
        for t, d in decisions.items()
        if t.startswith("misconception:") and d.get("action") in ("edit", "reject")
    }
    if not chosen:
        return
    for lesson_id, lesson in list(plan.lessons.items()):
        mistakes = []
        for m in lesson.misconceptions:
            d = chosen.get(m.id)
            if d is not None:
                lines = [] if d["action"] == "reject" else _as("steps", d["value"])
                m = m.model_copy(update={"counter_examples": lines})
            mistakes.append(m)
        plan.lessons[lesson_id] = lesson.model_copy(update={"misconceptions": mistakes})


def _verify_to_items(plan: Plan) -> None:
    """FIX-3: the period's "vì sao" for each of its items that has none of its own."""
    asked = {}
    for node in plan.package.nodes:
        if node.verify_prompt:
            for item_id in (*node.checks, *node.completion, *node.practice, *node.transfer):
                asked[item_id] = node.verify_prompt
    if not asked:
        return
    for lesson_id, lesson in list(plan.lessons.items()):
        items = [
            i.model_copy(update={"verify_prompt": asked[i.id]})
            if i.id in asked and not i.verify_prompt
            else i
            for i in lesson.items
        ]
        plan.lessons[lesson_id] = lesson.model_copy(update={"items": items})


_TARGETS = {}


def _init_targets() -> None:
    from cavat.core.pedagogy import HintTarget

    _TARGETS.update({HintLevel.H1: HintTarget.TASK, HintLevel.H2: HintTarget.CONCEPT})
    _TARGETS.update(
        {HintLevel.H3: HintTarget.STRATEGY, HintLevel.H4: HintTarget.STEP, HintLevel.H5: HintTarget.STEP}
    )


_init_targets()


def _edit_node(node: Any, path: list[str], value: Any) -> Any:
    """One part of a period as the teacher writes it; an explanation or a worked example the documents do
    not have is created by its first edit ("node:STP-T03/theory/T2/text")."""
    from cavat.modules.content.chapter_package import TheoryVariant, WorkedExample

    part, field = path[0], path[-1]
    if part == "verify":
        return node.model_copy(update={"verify_prompt": str(value).strip()})
    if part in ("theory", "worked_examples"):
        element_id = path[1]
        elements = list(getattr(node, part))
        if not any(e.id == element_id for e in elements):
            empty = (
                TheoryVariant(id=element_id, representation=f"cách giảng {element_id}", text="", ask="")
                if part == "theory"
                else WorkedExample(id=element_id, problem="", steps=[], answer="")
            )
            elements.append(empty)
        elements = [
            e.model_copy(update={field: _as(field, value)}) if e.id == element_id else e for e in elements
        ]
        return node.model_copy(update={part: elements})
    owner = getattr(node, part)
    return node.model_copy(update={part: owner.model_copy(update={field: _as(field, value)})})


def _move_items(plan: Plan, decisions: Mapping[str, Mapping[str, Any]]) -> None:
    """Items the teacher put at another stage of their period ("item:STP-BT-31/stage" = "transfer")."""
    moves = {
        t.removeprefix("item:").removesuffix("/stage"): str(d["value"])
        for t, d in decisions.items()
        if t.startswith("item:") and t.endswith("/stage")
    }
    if not moves:
        return
    nodes = []
    for node in plan.package.nodes:
        lists = {name: [i for i in getattr(node, name) if i not in moves] for name in STAGES}
        for item_id, stage in moves.items():
            if any(item_id in getattr(node, name) for name in STAGES):
                lists[stage].append(item_id)
        nodes.append(node.model_copy(update=lists))
    plan.package = plan.package.model_copy(update={"nodes": nodes})
    for lesson_id, lesson in list(plan.lessons.items()):
        items = []
        for item in lesson.items:
            if item.id in moves:
                purpose, level, transfer = STAGES[moves[item.id]]
                item = item.model_copy(
                    update={"purpose": purpose, "cognitive_level": level, "transfer": transfer}
                )
            items.append(item)
        plan.lessons[lesson_id] = lesson.model_copy(update={"items": items})


def _as(field: str, value: Any) -> Any:
    """Lists are written one per line by the teacher; key ideas one idea per line, phrasings split by "/"."""
    if field == "min_forms":
        return int(value)
    if field == "key_ideas":
        lines = value if isinstance(value, list) else str(value).splitlines()
        return [
            [p.strip() for p in (line if isinstance(line, list) else str(line).split("/")) if p.strip()]
            for line in lines
            if line
        ]
    if field in ("accept", "steps"):
        return (
            value
            if isinstance(value, list)
            else [line.strip() for line in str(value).splitlines() if line.strip()]
        )
    return str(value)


def review_state(
    plan_nodes: list[dict[str, Any]], decisions: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """What is approved and what still waits for the teacher, period by period."""
    approved = [
        n["id"] for n in plan_nodes if decisions.get(f"node:{n['id']}", {}).get("action") == "approve"
    ]
    return {
        "approved_nodes": approved,
        "waiting_nodes": [n["id"] for n in plan_nodes if n["id"] not in approved],
    }


def publish_blockers(
    plan_nodes: list[dict[str, Any]], problems: list[str], decisions: Mapping[str, Any]
) -> list[str]:
    """Why the plan cannot be published yet (empty: it can)."""
    waiting = review_state(plan_nodes, decisions)["waiting_nodes"]
    return [f"{node}: chưa duyệt" for node in waiting] + list(problems)
