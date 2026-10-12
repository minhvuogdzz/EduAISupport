"""The draft teaching plan of a chapter from the teacher's documents (INGEST-3a): its graph, its periods,
what each one teaches and practises, in the chapter package the tutor runs (plan v1, ADR-018).

One node per period of the lesson plan (the owner's decision, 2026-10-12), in the order of the plan. What a
node teaches is the teacher's text, never a model's:

- its two ways of explaining: the "Khám phá" activity of the period with its material ("Chuẩn bị"), and
  the rule of the theory ("GHI NHỚ"), each ending on a "Câu hỏi gợi mở" of the period;
- its method: the rule and its steps; its worked examples: the "VÍ DỤ" boxes with their solutions;
- its retell: the rule the child says back in the "Củng cố" step, cut into its key ideas;
- its items: the questions the plan practises in that period, from the checked item bank (INGEST-2), by
  stage; never one whose answer is in conflict, disputed or missing;
- its mistakes: "Khi bé sai" of the period and the matching "Lỗi …" of the mistakes document.

The theory sections are given to the periods of their lesson by the words they share (DI-45). What the
documents leave out (a reply to a question, a hint ladder) is left empty and listed: INGEST-3b drafts it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from cavat.core.vi_text import fold
from cavat.modules.content.chapter_package import (
    Chapter,
    ChapterPackage,
    ExplainSpec,
    Method,
    Node,
    PassRule,
    Relation,
    TheoryVariant,
    WorkedExample,
    validate_chapter,
)
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    ChoiceOption,
    CompareAnswer,
    Item,
    KnowledgeComponent,
    LessonPackage,
    Misconception,
    NumericAnswer,
    Objective,
    OpenAnswer,
    OrderAnswer,
)
from cavat.modules.ingest.build import ItemDraft
from cavat.modules.ingest.theory import (
    Mistake,
    PeriodPlan,
    Section,
    parse_lesson_plan,
    parse_mistakes,
    parse_theory,
)
from cavat.modules.ingest.verify import MEASURE, UNITS, answer_quantity, evaluate
from cavat.modules.library.repository import TeacherDocument
from cavat.modules.rag.bm25 import content_words

PLAN_VERSION = "teaching-plan/0.1.0"
USABLE = ("VERIFIED", "REVIEW", "UNCHECKED")  # never CONFLICT, DISPUTED or NO_ANSWER
_IMPLEMENT = re.compile(r"luyện tập|ứng dụng|thực tế|vận dụng|hình ghép|công thức ngược", re.IGNORECASE)
_STAGE = {
    "KIEM_TRA_HIEU": ("checks", "CONCEPT_CHECK", "A", 0.2),
    "CUNG_LAM": ("completion", "PRACTICE", "B", 0.35),
    "LUYEN_TAP": ("practice", "PRACTICE", "B", 0.5),
    "TIET": ("practice", "PRACTICE", "B", 0.45),
    "VAN_DUNG": ("transfer", "PRACTICE", "D", 0.7),
}


@dataclass
class Plan:
    """A chapter package and its lessons, with what was left out and why."""

    package: ChapterPackage
    lessons: dict[str, LessonPackage]
    assessment: list[str]  # the test items (EXIT), never in a prompt with their answers
    problems: list[str]  # what the tutor's validation still asks for (for INGEST-3b and the teacher)
    sources: dict[str, list[str]] = field(default_factory=dict)  # node → where its teaching comes from
    left_out: list[str] = field(default_factory=list)  # items not placed, and why

    def chapter(self) -> Chapter:
        items = {it.id: (it, lesson) for lesson in self.lessons.values() for it in lesson.items}
        return Chapter(package=self.package, lessons=self.lessons, _items=items)


def _words(text: str) -> set[str]:
    return {fold(w) for w in content_words(text)}


def _overlap(a: str, b: str) -> int:
    return len(_words(a) & _words(b))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZĐÀ-Ỹ0-9])", text) if s.strip()]


def _about(period: PeriodPlan) -> str:
    return " ".join([period.title, *period.objectives, period.steps.get("Khám phá", ""), *period.questions])


def _weights(periods: Sequence[PeriodPlan]) -> dict[str, float]:
    """How much a word tells the periods of one lesson apart: a word every period uses ("số thập phân")
    tells nothing (an inverse document frequency over the periods)."""
    import math

    docs = [_words(_about(p)) for p in periods]
    words = set().union(*docs) if docs else set()
    return {w: math.log(len(docs) / sum(w in d for d in docs)) for w in words}


def _score(period: PeriodPlan, title: str, body: str, weights: dict[str, float]) -> tuple[float, int]:
    """Words shared with the period, weighted by how much they tell the periods apart: the titles count
    three times (DI-45)."""
    shared_titles = _words(period.title) & _words(title)
    shared = _words(_about(period)) & _words(f"{title} {body}")
    score = 3 * sum(weights.get(w, 0.0) for w in shared_titles) + sum(weights.get(w, 0.0) for w in shared)
    return (score, -period.number)


def assign_sections(periods: Sequence[PeriodPlan], sections: Sequence[Section]) -> dict[int, list[Section]]:
    """Each theory section to the period of its lesson it shares the most telling words with (DI-45). A
    worked example goes on its own: "Ví dụ về khối lượng" belongs to the period on mass even when the
    document prints it under the rule shared by the whole lesson."""
    out: dict[int, list[Section]] = {p.number: [] for p in periods}
    for section in sections:
        candidates = [p for p in periods if p.lesson == section.lesson]
        if not candidates:
            continue
        weights = _weights(candidates)
        rest = [b for b in section.boxes if b.kind != "EXAMPLE"]
        if rest or section.title:
            body = " ".join(b.text for b in rest)
            best = max(candidates, key=lambda p: _score(p, section.title, body, weights))
            out[best.number].append(
                Section(section.lesson, section.lesson_title, section.title, section.page, rest)
            )
        for box in (b for b in section.boxes if b.kind == "EXAMPLE"):
            best = max(candidates, key=lambda p: _score(p, box.title, box.text, weights))
            out[best.number].append(
                Section(section.lesson, section.lesson_title, section.title, box.page, [box])
            )
    return out


def _quoted(text: str) -> str:
    m = re.search(r"[“\"]([^”\"]+)[”\"]", text)
    return m.group(1).strip() if m else ""


def _theory(period: PeriodPlan, sections: list[Section]) -> list[TheoryVariant]:
    asks = [q for q in period.questions if q.rstrip().endswith("?")]
    variants: list[TheoryVariant] = []
    explore = period.steps.get("Khám phá", "")
    if explore:
        material = period.preparation[0] if period.preparation else "hoạt động khám phá"
        variants.append(
            TheoryVariant(id="T1", representation=material, text=explore, ask=asks[0] if asks else "")
        )
    rules = [b for s in sections for b in s.boxes if b.kind == "RULE"]
    texts = [b for s in sections for b in s.boxes if b.kind == "TEXT"]
    source = rules[0] if rules else (texts[0] if texts else None)
    if source is not None:
        text = " ".join(_sentences(source.text)[:4])
        ask = asks[1] if len(asks) > 1 else (asks[0] if asks and not variants else "")
        title = f"khung GHI NHỚ · {source.title}" if source.kind == "RULE" and source.title else "lý thuyết"
        variants.append(TheoryVariant(id=f"T{len(variants) + 1}", representation=title, text=text, ask=ask))
    return variants


def _method(period: PeriodPlan, sections: list[Section], lesson_rules: list[str]) -> Method:
    """The period's own rule ("GHI NHỚ"), else the rule the child says in "Củng cố", else the rule of its
    lesson; its steps are "Bước 1. …" when the rule has them, else its sentences or its arrows."""
    rules = [b.text for s in sections for b in s.boxes if b.kind == "RULE"]
    said = _quoted(period.steps.get("Củng cố", ""))
    rule = (
        rules[0]
        if rules
        else (said if said and not said.endswith("?") else (lesson_rules[0] if lesson_rules else ""))
    )
    if not rule:
        return Method(rule="", steps=[])
    steps = [s.strip() for s in re.split(r"(?=Bước\s+\d+\.)", rule) if s.strip().startswith("Bước")]
    if not steps:
        steps = _sentences(rule)
    if len(steps) < 2 and "→" in rule:
        steps = [p.strip() for p in rule.split("→") if p.strip()]
    return Method(rule=rule, steps=steps)


def _examples(sections: list[Section]) -> list[WorkedExample]:
    out = []
    for section in sections:
        for box in section.boxes:
            if box.kind != "EXAMPLE":
                continue
            problem = re.sub(r"^Ví dụ\s*\d*\s*[–-]\s*", "", box.title).strip() or section.title
            text = box.text
            answer = ""
            if m := re.search(r"Đáp số\s*:\s*(.+)$", text):
                answer, text = m.group(1).strip().rstrip("."), text[: m.start()].strip()
            steps = _steps(text)
            out.append(
                WorkedExample(
                    id=f"WE{len(out) + 1}", problem=problem, steps=steps, answer=answer or steps[-1]
                )
            )
    return out


def _steps(text: str) -> list[str]:
    """The steps of a solution: its sentences, or the links of one computation ("S = 8 × 5 : 2 = 20")."""
    steps = _sentences(text)
    if len(steps) == 1 and text.count("=") >= 2:
        first, *rest = re.split(r"\s+=\s+", text)
        steps = [first] + [f"= {r}" for r in rest]
    return steps or [text]


def _demonstration(period: PeriodPlan) -> list[WorkedExample]:
    """No worked example in the theory: the teacher's demonstration in "Khám phá" is one."""
    explore = period.steps.get("Khám phá", "")
    steps = _steps(explore)
    if len(steps) < 2:
        return []
    return [WorkedExample(id="WE1", problem=period.title, steps=steps, answer=steps[-1])]


def _explain(period: PeriodPlan) -> ExplainSpec:
    consolidate = period.steps.get("Củng cố", "")
    said = _quoted(consolidate)
    if said.endswith("?"):
        return ExplainSpec(prompt=said, key_ideas=[])
    prompt = f"Con nói lại giúp cô bằng lời của con: {period.title.lower()} thế nào?"
    ideas = [[p.strip(" .")] for p in re.split(r"\s*(?:→|;|,\s+(?=\D))\s*", said) if len(p.strip()) > 3]
    return ExplainSpec(prompt=prompt, key_ideas=ideas)


def answer_spec(draft: ItemDraft) -> Any:
    """The answer of a draft item as the checker reads it; an open answer when no typed form fits."""
    first = draft.answer.splitlines()[0].strip() if draft.answer else ""
    stem = " ".join(draft.check_stem.split())
    if draft.options:
        letter = re.match(r"\s*([A-D])\b", first)
        return ChoiceAnswer(
            type="choice",
            options=[
                ChoiceOption(id=k, text=v, correct=bool(letter and letter.group(1) == k))
                for k, v in draft.options.items()
            ],
        )
    if m := re.match(r"\s*(Đ|S)\b", first):
        return BooleanAnswer(type="boolean", value=m.group(1) == "Đ", requires_explanation=False)
    pair = re.search(rf"({MEASURE.pattern})\s*(?:…+|\.{{2,}})\s*({MEASURE.pattern})", stem)
    if pair and re.search(r"[<>=]", first):
        return CompareAnswer(type="compare", left=pair.group(1).strip(), right=pair.group(2).strip())
    lowered = stem.lower()
    if ("sắp xếp" in lowered or "xếp" in lowered) and re.search(r"[<>]", first):
        numbers = re.findall(rf"{MEASURE.pattern}", first)
        direction = "desc" if ">" in first else "asc"
        if numbers and all(evaluate(n) is not None for n in numbers):
            return OrderAnswer(type="order", numbers=[n.strip() for n in numbers], direction=direction)
    blank = re.search(r"(?:=|≈)\s*(?:…+|\.{2,})\s*([^\s.…]*)", stem)
    given = answer_quantity(first)
    if blank and given is not None and not re.search(r"[a-zà-ỹ]{3,}", first.split("=")[-1].lower()):
        unit = blank.group(1).strip()
        value = given.value / UNITS[unit][1] if unit in UNITS and given.dimension else given.value
        from cavat.modules.assessment.vi_numbers import format_vi

        return NumericAnswer(type="numeric", value=format_vi(value))
    return OpenAnswer(
        type="open", rubric=f"Đáp án của giáo viên: {draft.answer}", sample_answer=first or draft.answer
    )


def _item(draft: ItemDraft, node_id: str, stage: str) -> Item:
    _, purpose, level, difficulty = _STAGE[stage]
    return Item(
        id=draft.item_id,
        purpose=purpose,  # type: ignore[arg-type]
        kc_ids=[node_id],
        cognitive_level=level,  # type: ignore[arg-type]
        difficulty=difficulty,
        transfer="near" if stage == "VAN_DUNG" else "none",
        stem=draft.stem,
        answer=answer_spec(draft),
        worked_solution=[line for line in draft.answer.splitlines()[1:] if line.strip()],
    )


def _exit_item(draft: ItemDraft, node_ids: list[str]) -> Item:
    return Item(
        id=draft.item_id,
        purpose="EXIT",
        kc_ids=node_ids,
        cognitive_level="C" if draft.stage == "TU_LUAN" else "B",
        difficulty=0.5,
        stem=draft.stem,
        answer=answer_spec(draft),
    )


def build_plan(
    chapter_id: str,
    title: str,
    prefix: str,
    documents: Sequence[TeacherDocument],
    items: Sequence[ItemDraft],
    *,
    version: str = "0.1.0",
) -> Plan:
    by_kind = {d.kind: d for d in documents if d.chapter_id == chapter_id}
    periods = parse_lesson_plan(by_kind["GIAO_AN"].text) if "GIAO_AN" in by_kind else []
    sections = parse_theory(by_kind["BAI_GIANG"].text) if "BAI_GIANG" in by_kind else []
    mistakes = parse_mistakes(by_kind["LOI_SAI"].text) if "LOI_SAI" in by_kind else []
    teaching = [p for p in periods if p.lesson]  # the review and test period is the chapter's test
    by_period = assign_sections(teaching, sections)
    lesson_rules: dict[str, list[str]] = {}
    for section in sections:
        lesson_rules.setdefault(section.lesson, []).extend(b.text for b in section.boxes if b.kind == "RULE")
    node_of = {p.number: f"{prefix}-T{p.number:02d}" for p in teaching}

    lessons: dict[str, dict[str, Any]] = {}
    nodes: list[Node] = []
    sources: dict[str, list[str]] = {}
    for p in teaching:
        node_id, lesson_id = node_of[p.number], f"{prefix}-{p.lesson.replace(' ', '')}"
        mine = by_period.get(p.number, [])
        layer = "IMPLEMENT" if _IMPLEMENT.search(p.title) else "BASIC"
        nodes.append(
            Node(
                id=node_id,
                name=p.title,
                layer=layer,  # type: ignore[arg-type]
                description=" ".join(p.objectives) or p.title,
                lesson_id=lesson_id,
                theory=_theory(p, mine),
                method=_method(p, mine, lesson_rules.get(p.lesson, [])),
                worked_examples=_examples(mine) or _demonstration(p),
                explain=_explain(p),
                checks=[],
                practice=[],
                transfer=[],
                # DI-6 (owner, 2026-10-12): a basic period passes on understanding and practice; application
                # evidence is asked of the practice periods and of the chapter test.
                pass_rule=PassRule(require_application=layer == "IMPLEMENT"),
            )
        )
        sources[node_id] = [f"Giáo án, tiết {p.number}, trang {p.page}"] + [
            f"Lý thuyết, {s.lesson} · {s.title or s.lesson_title}, trang {s.page}" for s in mine
        ]
        lesson = lessons.setdefault(
            lesson_id,
            {"title": f"{p.lesson}: {mine[0].lesson_title if mine else p.title}", "nodes": [], "items": []},
        )
        lesson["nodes"].append(p)

    node_by_id = {n.id: n for n in nodes}
    left_out: list[str] = []
    placed: set[str] = set()
    review: list[ItemDraft] = []
    for draft in items:
        if draft.assessment:
            continue
        if draft.status not in USABLE:
            left_out.append(f"{draft.item_id}: {draft.status}")
            continue
        period = next((n for n in draft.periods if n in node_of), None)
        if period is None and draft.periods:  # the review period's worksheet: the chapter review
            review.append(draft)
            continue
        if period is None:
            left_out.append(f"{draft.item_id}: no period of the lesson plan practises it")
            continue
        stage = draft.stage if draft.stage in _STAGE else "LUYEN_TAP"
        node = node_by_id[node_of[period]]
        getattr(node, _STAGE[stage][0]).append(draft.item_id)
        lessons[node.lesson_id]["items"].append(_item(draft, node.id, stage))
        placed.add(draft.item_id)

    for node in nodes:  # a node with no question of "Kiểm tra hiểu": the first question of its worksheet
        if node.checks:
            continue
        lesson_items = lessons[node.lesson_id]["items"]
        sheet = next((it for it in lesson_items if it.id in node.practice and "-PH" in it.id), None)
        if sheet is not None:
            node.practice.remove(sheet.id)
            node.checks.append(sheet.id)
            lesson_items[lesson_items.index(sheet)] = sheet.model_copy(
                update={"purpose": "CONCEPT_CHECK", "cognitive_level": "A", "difficulty": 0.25}
            )

    relations = _relations(nodes)
    order = {r.target: [] for r in relations}
    for r in relations:
        order[r.target].append(r.source)
    misconceptions = _misconceptions(teaching, node_of, mistakes, prefix)
    lesson_packages: dict[str, LessonPackage] = {}
    for lesson_id, lesson in lessons.items():
        lesson_nodes = [node_by_id[node_of[p.number]] for p in lesson["nodes"]]
        lesson_packages[lesson_id] = LessonPackage(
            lesson_id=lesson_id,
            version=version,
            status="DRAFT",
            subject="math",
            grade=5,
            title=lesson["title"],
            objectives=[
                Objective(id=f"{node_of[p.number]}-O{i + 1}", text=text, kc_ids=[node_of[p.number]])
                for p in lesson["nodes"]
                for i, text in enumerate(p.objectives)
            ],
            kcs=[
                KnowledgeComponent(
                    id=n.id,
                    name=n.name,
                    description=n.description,
                    # The chapter graph is the truth: what comes before this node in the same lesson.
                    prerequisites=[src for src in order.get(n.id, []) if src in {m.id for m in lesson_nodes}],
                )
                for n in lesson_nodes
            ],
            misconceptions=[m for m in misconceptions if m.kc_id in {n.id for n in lesson_nodes}],
            items=lesson["items"],
        )

    exit_items = [d for d in items if d.assessment and d.status in USABLE]
    if exit_items or review:
        test_id = f"{prefix}-KT"
        lesson_packages[test_id] = LessonPackage(
            lesson_id=test_id,
            version=version,
            status="DRAFT",
            subject="math",
            grade=5,
            title=f"Kiểm tra cuối chương: {title}",
            objectives=[],
            kcs=[],
            items=[_exit_item(d, _nodes_for(d, nodes)) for d in exit_items]
            + [_exit_item(d, _nodes_for(d, nodes)).model_copy(update={"purpose": "REVIEW"}) for d in review],
        )
    left_out += [f"{d.item_id}: {d.status}" for d in items if d.assessment and d.status not in USABLE]

    package = ChapterPackage(
        chapter_id=chapter_id,
        version=version,
        status="DRAFT",
        subject="math",
        grade=5,
        title=title,
        lessons=list(lesson_packages),
        nodes=nodes,
        relations=relations,
    )
    plan = Plan(package, lesson_packages, [d.item_id for d in exit_items], [], sources, left_out)
    plan.problems = validate_chapter(plan.chapter())
    return plan


def _relations(nodes: list[Node]) -> list[Relation]:
    """The plan's order: each basic node needs the basic node before it; a practice node applies the basic
    nodes of its lesson (every basic node before it for a whole-chapter review)."""
    relations: list[Relation] = []
    basics: list[Node] = []
    for node in nodes:
        if node.layer == "BASIC":
            if basics:
                relations.append(Relation(source=basics[-1].id, target=node.id, type="PREREQUISITE"))
            basics.append(node)
        else:
            mine = [b for b in basics if b.lesson_id == node.lesson_id] or basics
            relations += [Relation(source=b.id, target=node.id, type="APPLICATION") for b in mine]
    return relations


def _misconceptions(
    periods: list[PeriodPlan], node_of: dict[int, str], mistakes: list[Mistake], prefix: str
) -> list[Misconception]:
    out: list[Misconception] = []
    for p in periods:
        for i, line in enumerate(p.mistakes, 1):
            sign, _, remedy = line.partition(":")
            out.append(
                Misconception(
                    id=f"{node_of[p.number]}-M{i}",
                    kc_id=node_of[p.number],
                    name=sign.strip(),
                    description=remedy.strip() or line,
                )
            )
    for m in mistakes:
        best = max(
            periods,
            key=lambda p: (_overlap(f"{m.name} {m.signs}", " ".join([p.title, *p.objectives])), -p.number),
        )
        out.append(
            Misconception(
                id=f"{prefix}-L{m.number}",
                kc_id=node_of[best.number],
                name=m.name,
                description=f"{m.signs} {m.cause}".strip(),
                severity="CRITICAL",
                counter_examples=[m.counter_example] if m.counter_example else [],
            )
        )
    return out


def _nodes_for(draft: ItemDraft, nodes: list[Node]) -> list[str]:
    """The node a test question tests: the one whose name and description share the most words with it."""
    best = max(nodes, key=lambda n: (_overlap(draft.stem, f"{n.name} {n.description}"), -nodes.index(n)))
    return [best.id]
