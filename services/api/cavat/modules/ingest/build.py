"""The draft item bank of a chapter from the teacher's documents (INGEST-2).

Each exercise, worksheet and test document is paired with its answer key (``answers_for``, INGEST-1),
cut into questions and sub-questions (``parse``), each answer checked against its question (``verify``)
and each question placed in the periods of the lesson plan that practise it (``plan``).

Nothing here is taught yet: the bank is a draft for the teacher (INGEST-4) and the input of the teaching
plan (INGEST-3). An answer whose numbers one of the two Gemini readings disputed (DI-43) is marked, so a
misread fraction never becomes a "right answer" without the teacher.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field

from cavat.modules.ingest.parse import Block, options_of, parse_blocks, split_parts
from cavat.modules.ingest.plan import Period, parse_periods
from cavat.modules.ingest.verify import Finding, check_item
from cavat.modules.library.repository import TeacherDocument

BUILDER_VERSION = "item-bank/0.1.0"
LAYOUTS = {"BAI_TAP": "BAI_TAP", "PHIEU": "PHIEU", "DE_KIEM_TRA": "DE_KIEM_TRA"}
CODES = {"BAI_TAP": "BT", "PHIEU": "PH", "DE_KIEM_TRA": "DE"}


@dataclass
class ItemDraft:
    item_id: str  # STP-BT-07c, STP-PH03-5, STP-DE1-B2
    chapter_id: str
    source: str  # BAI_TAP | PHIEU | DE_KIEM_TRA
    document_id: str
    answer_document_id: str
    page: int
    section: str  # "Phần 2", "Phiếu 3", "Đề 1 · II"
    label: str  # "7", "B2"
    part: str  # "c", "" for a question without sub-questions
    stage: str  # KIEM_TRA_HIEU, CUNG_LAM, LUYEN_TAP, VAN_DUNG, TIET, TRAC_NGHIEM, TU_LUAN
    stem: str  # what the child reads: the shared stem and the sub-question
    answer: str  # the answer key, as written
    options: dict[str, str] = field(default_factory=dict)
    periods: list[int] = field(default_factory=list)  # lesson-plan periods that practise it
    assessment: bool = False  # a test question: its answer never reaches a prompt (CLAUDE.md rule 2)
    figure: bool = False  # the question rests on a figure (described in "[Hình: …]")
    status: str = "UNCHECKED"  # VERIFIED | REVIEW | CONFLICT | DISPUTED | UNCHECKED | NO_ANSWER
    findings: list[dict[str, object]] = field(default_factory=list)
    disputed: list[str] = field(default_factory=list)
    check_stem: str = ""  # what the checks read: the sub-question (or the question)
    context: str = ""  # and around it: the title of the part or sheet, the shared stem
    question: str = ""  # the whole question as printed, every sub-question


def build_bank(chapter_id: str, prefix: str, documents: Sequence[TeacherDocument]) -> list[ItemDraft]:
    """The draft items of one chapter from its documents (questions, answer keys, the lesson plan)."""
    by_id = {d.id: d for d in documents}
    keys = {d.answers_for: d for d in documents if d.kind == "DAP_AN" and d.answers_for}
    plan = next((d for d in documents if d.kind == "GIAO_AN"), None)
    periods = parse_periods(plan.text) if plan else []
    items: list[ItemDraft] = []
    for doc in documents:
        if doc.kind not in LAYOUTS or doc.chapter_id != chapter_id:
            continue
        key = keys.get(doc.id)
        items += _items_of(chapter_id, prefix, doc, key, periods, by_id)
    return items


def _items_of(
    chapter_id: str,
    prefix: str,
    doc: TeacherDocument,
    key: TeacherDocument | None,
    periods: list[Period],
    by_id: dict[str, TeacherDocument],
) -> list[ItemDraft]:
    layout = LAYOUTS[doc.kind]
    questions = parse_blocks(doc.text, layout)
    answers = _answers_by_question(parse_blocks(key.text, layout, answers=True)) if key else {}
    disputed = _disputed(doc) | (_disputed(key) if key else set())
    items: list[ItemDraft] = []
    for q in questions:
        answer_parts = answers.get(q.key, [])
        shared, parts = split_parts(q.text)
        # Options "A. … B. …" in a test or in an exercise ("Số nào dưới đây bằng 0,25? A. … B. …").
        shared_stem, options = options_of(shared)
        context = f"{q.title}\n{shared_stem}"
        answer_text = "\n".join(t for _, t in answer_parts)
        by_letter = _answer_letters(answer_parts, [p for p, _ in parts])
        units = parts or [("", "")]
        for letter, part_text in units:
            stem = f"{shared_stem}\n{letter}) {part_text}".strip() if letter else shared_stem
            answer = by_letter.get(letter, "") if letter else answer_text
            item = ItemDraft(
                item_id=_item_id(prefix, layout, q, letter),
                chapter_id=chapter_id,
                source=layout,
                document_id=doc.id,
                answer_document_id=key.id if key else "",
                page=q.page,
                section=q.section,
                label=q.label,
                part=letter,
                stage=q.stage,
                stem=stem,
                answer=answer,
                options=options,
                periods=_periods_of(layout, q, periods),
                assessment=layout == "DE_KIEM_TRA",
                figure="[Hình" in q.text,
            )
            item.context = context
            item.check_stem = part_text or shared_stem
            item.question = q.text
            items.append(judge(item, disputed))
    return items


def _answers_by_question(blocks: Iterable[Block]) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """Answers grouped by the question they answer: "B1a", "B1b" both answer B1 (sub-letter kept)."""
    out: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for b in blocks:
        m = re.match(r"^(B?\d+)([a-e]?)$", b.label)
        if not m:
            continue
        out.setdefault((b.section, m.group(1)), []).append((m.group(2), b.text))
    return out


def _answer_letters(answer_parts: list[tuple[str, str]], letters: list[str]) -> dict[str, str]:
    """The answer of each sub-question: labelled "B1a" in a test key, "a) …" inside the text otherwise."""
    labelled = {letter: text for letter, text in answer_parts if letter}
    if labelled and set(letters) <= set(labelled):
        return labelled
    whole = "\n".join(text for _, text in answer_parts)
    _, parts = split_parts(whole)
    if parts:
        return dict(parts)
    if labelled:  # steps of one answer ("B2a: đổi đơn vị", "B2b: tính"): the whole is each part's answer
        return {letter: whole for letter in letters}
    return {}


def _periods_of(layout: str, q: Block, periods: list[Period]) -> list[int]:
    if layout == "PHIEU":
        number = int(q.section.split()[-1])
        return [p.number for p in periods if p.sheet == number] or ([q.period] if q.period else [])
    if layout == "BAI_TAP" and q.label.isdigit():
        return [p.number for p in periods if int(q.label) in p.exercises]
    if layout == "DE_KIEM_TRA":
        return [p.number for p in periods if not p.lesson][-1:]  # the review and test period
    return []


def _item_id(prefix: str, layout: str, q: Block, letter: str) -> str:
    code = CODES[layout]
    if layout == "PHIEU":
        return f"{prefix}-{code}{int(q.section.split()[-1]):02d}-{q.label}{letter}"
    if layout == "DE_KIEM_TRA":
        test = re.search(r"Đề (\d)", q.section)
        return f"{prefix}-{code}{test.group(1) if test else 1}-{q.label}{letter}"
    return f"{prefix}-{code}-{int(q.label):02d}{letter}"


def _disputed(doc: TeacherDocument) -> set[str]:
    return {n for r in doc.page_reads for n in r.disputed}


def judge(item: ItemDraft, disputed: set[str] | None = None) -> ItemDraft:
    """Check the item's answer against its question; ``disputed``: numbers the two readings disputed."""
    disputed = disputed if disputed is not None else set(item.disputed)
    if not item.answer.strip():
        item.status = "NO_ANSWER"
        return item
    findings: list[Finding] = check_item(
        item.check_stem,
        item.answer,
        options=item.options or None,
        context=item.context,
        question=item.question,
    )
    item.findings = [asdict(f) for f in findings]
    numbers = set(re.findall(r"\d+(?:[.,/]\d+)*", f"{item.stem} {item.answer}"))
    item.disputed = sorted(n for n in disputed if n in numbers)
    wrong = [f for f in findings if not f.ok]
    if item.disputed:
        item.status = "DISPUTED"
    elif wrong and all(f.check == "GROUNDED" for f in wrong):
        item.status = "REVIEW"  # the answer holds; its explanation has a number to look at
    elif wrong:
        item.status = "CONFLICT"
    elif findings:
        item.status = "VERIFIED"
    else:
        item.status = "UNCHECKED"
    return item
