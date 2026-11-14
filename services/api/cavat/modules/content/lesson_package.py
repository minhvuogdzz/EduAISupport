"""Lesson package: the approved, versioned lesson content the tutor runtime consumes.

Loaded from YAML (see docs/pedagogy/**/lesson.yaml). Blueprint PART 22.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cavat.core.pedagogy import HintLevel, HintTarget


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


AnswerType = Literal["compare", "order", "numeric", "choice", "boolean", "open", "phrase", "word_order"]


class HintTemplate(_Model):
    target: HintTarget
    level: HintLevel
    text: str
    # A generic hint of the lesson can name the kinds of item it fits (ADR-019, DI-37): "viết số vào bảng
    # hàng" helps with a number to write, not with choosing a fraction. Empty: every kind.
    answer_types: list[AnswerType] = []


class CompareAnswer(_Model):
    type: Literal["compare"]
    left: str
    right: str
    ask: Literal["sign", "larger", "smaller"] = "sign"


class OrderAnswer(_Model):
    type: Literal["order"]
    numbers: list[str]
    direction: Literal["asc", "desc"] = "asc"


class NumericAnswer(_Model):
    type: Literal["numeric"]
    value: str
    # Specific wrong answers that reveal a misconception, e.g. {"1": "DEC-M01"}.
    wrong_answers: dict[str, str] = Field(default_factory=dict)
    # The form the question asks: "fraction" with the key's denominator ("0,475 = ……" asks 475/1000; 0,475
    # written back, or 19/40, is not what is asked); "decimal" ("49/100 = ……" asks 0,49, not 49/100).
    form: Literal["fraction", "decimal"] | None = None


class Probe(_Model):
    """A follow-up comparison that separates two causes of the same wrong choice (e.g. GP-08)."""

    prompt: str
    left: str
    right: str
    if_wrong: str  # misconception recorded when the student also compares the numbers wrongly
    if_correct: str  # misconception recorded when the numbers are compared correctly (another cause)


class ChoiceOption(_Model):
    id: str
    text: str
    correct: bool = False
    probe: Probe | None = None
    aliases: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    misconception_confidence: float = 0.6


class ChoiceAnswer(_Model):
    type: Literal["choice"]
    options: list[ChoiceOption]


class BooleanAnswer(_Model):
    type: Literal["boolean"]
    value: bool
    requires_explanation: bool = True
    # Keys "true"/"false": the wrong verdict that reveals a misconception.
    wrong_answers: dict[str, str] = Field(default_factory=dict)


class KeyFacts(_Model):
    """What a right answer to an open question must say, read by the checker without a model (DI-48).

    Every listed fact must hold: ``numbers`` (each group: one of its values, written as a number or in
    words), ``phrases`` (each group: one of its phrasings), ``relations`` (the signs <, >, = in this order),
    ``order`` (these words in this order), ``pairs`` ([word, name]: one clause says both),
    ``reading`` (this number written in words, without digits). ``only_numbers``: no other value is given.
    """

    numbers: list[list[str]] = Field(default_factory=list)
    only_numbers: bool = False
    phrases: list[list[str]] = Field(default_factory=list)
    relations: list[Literal["<", ">", "="]] = Field(default_factory=list)
    order: list[str] = Field(default_factory=list)
    pairs: list[tuple[str, str]] = Field(default_factory=list)
    reading: str | None = None


class OpenAnswer(_Model):
    type: Literal["open"]
    rubric: str
    sample_answer: str
    facts: KeyFacts | None = None  # without facts the answer can only be read by a model or the teacher


class PhraseAnswer(_Model):
    """An English word or sentence the student says or types (ENG-3b, ADR-062, DI-125; README G2).

    Right when the answer, normalized by ``normalize`` (DI-110), is one of ``accept`` (whole sentences), or
    when every group of ``required`` has one of its phrasings in it (each group is one idea, said one of
    several ways). ``wrong_answers``: a wrong answer as the student would say it, mapped to the misconception
    it reveals ("we eat seafood" -> the misconception of the present tense). ``allow_name``: a proper name the
    student puts in (their own family, place) does not make the answer wrong. The grading itself is the
    English checker's (ENG-4); this is only the data.
    """

    type: Literal["phrase"]
    accept: list[str] = Field(default_factory=list)
    required: list[list[str]] = Field(default_factory=list)
    normalize: Literal["en-vi/1"] = "en-vi/1"
    wrong_answers: dict[str, str] = Field(default_factory=dict)
    allow_name: bool = False


class WordOrderAnswer(_Model):
    """Put the given words in order to make a sentence (README G3). ``accept``: the right orders, each a
    permutation of ``tokens``. ``OrderAnswer`` is for numbers only."""

    type: Literal["word_order"]
    tokens: list[str]
    accept: list[list[str]]


AnswerSpec = Annotated[
    CompareAnswer
    | OrderAnswer
    | NumericAnswer
    | ChoiceAnswer
    | BooleanAnswer
    | OpenAnswer
    | PhraseAnswer
    | WordOrderAnswer,
    Field(discriminator="type"),
]

# ENG-3b (ADR-062, DI-126; README G4, G5, G10). Where an item and its answer come from, and in which
# language the student answers. Optional for Mathematics (its packages do not change); required on every item
# of an English package (``validate_package``).
Origin = Literal["BOOK", "AUTHORED"]
AnswerStatus = Literal["VERIFIED_SGV", "FROM_TEXT", "AUTHORED", "NO_ANSWER"]
ResponseLanguage = Literal["en", "vi", "either"]
ItemKind = Literal["say_after_me"]


class ItemSource(_Model):
    """A place in a source document: ``doc`` its id (``SGK``, ``SGV``, ``TAPHUAN``), ``page`` the printed page
    (or range), ``ref`` the exercise or line on it."""

    doc: str = Field(min_length=1)
    page: str = Field(min_length=1)
    ref: str = Field(min_length=1)


class Review(_Model):
    """The owner's review of an item the session wrote (``answer_status: AUTHORED``). Only an APPROVED item
    is taught (DI-126)."""

    status: Literal["PENDING", "APPROVED", "REJECTED"]
    reviewed_by: str = ""
    reviewed_on: date | None = None  # not "on": YAML 1.1 reads that key as a boolean


class Item(_Model):
    id: str
    purpose: Literal["CONCEPT_CHECK", "PRACTICE", "EXIT", "REVIEW"]
    kc_ids: list[str]
    cognitive_level: Literal["A", "B", "C", "D", "E", "DIAG"]
    difficulty: float = Field(ge=0.0, le=1.0)
    transfer: Literal["none", "near", "far"] = "none"
    expected_time_s: int = 60
    stem: str
    answer: AnswerSpec
    hints: list[HintTemplate] = Field(default_factory=list)
    worked_solution: list[str] = Field(default_factory=list)
    explanation: str | None = None
    isomorphic_group: str | None = None
    rephrase: str | None = None
    verify_prompt: str | None = None
    leak_patterns: list[str] = Field(default_factory=list)
    # ENG-3b (ADR-062): provenance and answer language; all optional, Mathematics items leave them out.
    source: ItemSource | None = None  # where the question comes from
    answer_source: ItemSource | None = (
        None  # where its answer is printed (the SGV key) when that is elsewhere
    )
    origin: Origin | None = None
    answer_status: AnswerStatus | None = None
    review: Review | None = None
    response_language: ResponseLanguage | None = None
    kind: ItemKind | None = None  # say_after_me: the student repeats the tutor's model sentence (DI-108)

    @property
    def is_assessment(self) -> bool:
        return self.purpose == "EXIT"

    @property
    def requires_explanation(self) -> bool:
        return isinstance(self.answer, BooleanAnswer) and self.answer.requires_explanation


# The English error codes of ADR-060 section 5 (DI-107) a misconception can belong to. The general
# ``ErrorClass`` the projector reads follows from the code and the node (DI-107); that is ENG-4's.
EnglishErrorCode = Literal[
    "EN_SHORT_ANSWER",
    "EN_TENSE",
    "EN_MEANING",
    "EN_STRUCTURE",
    "EN_VERB_FORM",
    "EN_SLIP",
    "EN_PRONUNCIATION",
    "EN_L1",
]


class Misconception(_Model):
    id: str
    kc_id: str
    name: str
    description: str
    bug_rule: str | None = None
    severity: Literal["CRITICAL", "NORMAL"] = "NORMAL"
    counter_examples: list[str] = Field(default_factory=list)
    error_class: EnglishErrorCode | None = None  # README G8: required in an English package (DI-127)


class KnowledgeComponent(_Model):
    id: str
    name: str
    description: str
    prerequisites: list[str] = Field(default_factory=list)


class Objective(_Model):
    id: str
    text: str
    kc_ids: list[str]


class Concept(_Model):
    id: str
    name: str
    explanation: str
    representations: list[str] = Field(default_factory=list)


class Persona(_Model):
    tutor_self: str = "cô"
    student_address: str = "con"


class LessonPackage(_Model):
    lesson_id: str
    version: str
    status: Literal["DRAFT", "APPROVED", "PUBLISHED", "ARCHIVED"]
    subject: Literal["math", "english"]
    grade: int
    locale: str = "vi-VN"
    title: str
    persona: Persona = Field(default_factory=Persona)
    objectives: list[Objective]
    kcs: list[KnowledgeComponent]
    concepts: list[Concept] = Field(default_factory=list)
    misconceptions: list[Misconception] = Field(default_factory=list)
    generic_hints: list[HintTemplate] = Field(default_factory=list)
    # Asked after a correct answer when the policy chooses VERIFY and the item has no verify_prompt.
    default_verify_prompt: str | None = None
    items: list[Item]

    def item(self, item_id: str) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise KeyError(item_id)

    def misconception(self, mis_id: str) -> Misconception | None:
        return next((m for m in self.misconceptions if m.id == mis_id), None)

    def items_for(self, purpose: str) -> list[Item]:
        return [it for it in self.items if it.purpose == purpose]

    def siblings(self, item: Item) -> list[Item]:
        """Other items of the same isomorphic group (used for independent re-checks)."""
        if not item.isomorphic_group:
            return []
        return [it for it in self.items if it.isomorphic_group == item.isomorphic_group and it.id != item.id]


def load_lesson_package(path: str | Path) -> LessonPackage:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return LessonPackage.model_validate(data)


REQUIRED_PRACTICE_HINT_LEVELS = (HintLevel.H1, HintLevel.H2, HintLevel.H4)


def validate_package(pkg: LessonPackage) -> list[str]:
    """Invariant checks beyond the schema (blueprint PART 22.2, step 7). Returns a list of problems."""
    problems: list[str] = []
    kc_ids = {kc.id for kc in pkg.kcs}
    mis_ids = {m.id for m in pkg.misconceptions}
    ids = [it.id for it in pkg.items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate item ids")

    for kc in pkg.kcs:
        for pre in kc.prerequisites:
            if pre not in kc_ids:
                problems.append(f"{kc.id}: unknown prerequisite {pre}")
    for obj in pkg.objectives:
        for kc in obj.kc_ids:
            if kc not in kc_ids:
                problems.append(f"{obj.id}: unknown KC {kc}")
    for m in pkg.misconceptions:
        if m.kc_id not in kc_ids:
            problems.append(f"{m.id}: unknown KC {m.kc_id}")

    for it in pkg.items:
        for kc in it.kc_ids:
            if kc not in kc_ids:
                problems.append(f"{it.id}: unknown KC {kc}")
        referenced: list[str] = []
        ans = it.answer
        if isinstance(ans, ChoiceAnswer):
            if sum(o.correct for o in ans.options) != 1:
                problems.append(f"{it.id}: choice item must have exactly one correct option")
            for o in ans.options:
                referenced += o.misconceptions
                if o.probe is not None:
                    referenced += [o.probe.if_wrong, o.probe.if_correct]
        elif isinstance(ans, NumericAnswer | BooleanAnswer | PhraseAnswer):
            referenced += list(ans.wrong_answers.values())
        problems += _answer_shape_problems(it)
        for mid in referenced:
            if mid not in mis_ids:
                problems.append(f"{it.id}: unknown misconception {mid}")

        if it.purpose == "PRACTICE":
            levels = {h.level for h in it.hints}
            for lvl in REQUIRED_PRACTICE_HINT_LEVELS:
                if lvl not in levels:
                    problems.append(f"{it.id}: missing required hint level H{int(lvl)}")
            if len(it.worked_solution) < 2:
                problems.append(f"{it.id}: worked_solution needs at least 2 steps")
            if not it.explanation:
                problems.append(f"{it.id}: missing explanation (needed for H7)")
            if it.isomorphic_group and not pkg.siblings(it):
                problems.append(f"{it.id}: isomorphic group {it.isomorphic_group} has no sibling item")
        problems += _provenance_problems(it, english=pkg.subject == "english")
    if pkg.subject == "english":
        problems += [
            f"{m.id}: an English misconception needs an error_class"
            for m in pkg.misconceptions
            if not m.error_class
        ]
    return problems


def _answer_shape_problems(it: Item) -> list[str]:
    """The English answer types (ADR-062, DI-125): something to compare with, and nothing empty."""
    ans = it.answer
    problems: list[str] = []
    if isinstance(ans, PhraseAnswer):
        if not ans.accept and not ans.required:
            problems.append(f"{it.id}: a phrase answer needs at least one accept or required group")
        if any(not a.strip() for a in ans.accept):
            problems.append(f"{it.id}: empty accepted answer")
        if any(not group or any(not p.strip() for p in group) for group in ans.required):
            problems.append(f"{it.id}: empty required group or phrasing")
        if any(not w.strip() for w in ans.wrong_answers):
            problems.append(f"{it.id}: empty wrong answer")
    elif isinstance(ans, WordOrderAnswer):
        if len(ans.tokens) < 2 or any(not t.strip() for t in ans.tokens):
            problems.append(f"{it.id}: word_order needs at least two non-empty tokens")
        if not ans.accept:
            problems.append(f"{it.id}: word_order needs at least one accepted order")
        if any(Counter(order) != Counter(ans.tokens) for order in ans.accept):
            problems.append(f"{it.id}: every accepted order must use exactly the given tokens")
    return problems


def _provenance_problems(it: Item, *, english: bool) -> list[str]:
    """Where an item comes from and whether it may be taught (ADR-062, DI-126; english-module-rules N3).

    Checked on every item that states it; an English item must state all of it. A book item names its page,
    and the page of its answer when the SGV key holds it; an item the session wrote is taught only once the
    owner approved it; an exercise without an answer is never an item.
    """
    problems: list[str] = []
    if english:
        for name in ("origin", "answer_status", "response_language"):
            if getattr(it, name) is None:
                problems.append(f"{it.id}: an English item needs {name}")
    if it.origin == "BOOK":
        if it.source is None:
            problems.append(f"{it.id}: a book item needs its source page")
        if it.answer_status not in (None, "VERIFIED_SGV", "FROM_TEXT"):
            problems.append(
                f"{it.id}: a book item's answer is VERIFIED_SGV or FROM_TEXT, not {it.answer_status}"
            )
    if it.origin == "AUTHORED" and it.answer_status not in (None, "AUTHORED"):
        problems.append(f"{it.id}: an authored item has answer_status AUTHORED, not {it.answer_status}")
    if it.answer_status == "AUTHORED" and it.origin == "BOOK":
        problems.append(f"{it.id}: answer_status AUTHORED needs origin AUTHORED")
    if it.answer_status == "VERIFIED_SGV" and it.answer_source is None:
        problems.append(f"{it.id}: a VERIFIED_SGV answer needs its answer_source page")
    if it.answer_status == "NO_ANSWER":
        problems.append(f"{it.id}: an exercise without an answer cannot be taught (N3)")
    if it.answer_status == "AUTHORED" and (it.review is None or it.review.status != "APPROVED"):
        problems.append(f"{it.id}: an authored item is taught only after the owner approved it")
    if (
        it.review is not None
        and it.review.status == "APPROVED"
        and not (it.review.reviewed_by and it.review.reviewed_on)
    ):
        problems.append(f"{it.id}: an approval names who approved it and when")
    if it.kind == "say_after_me":
        if it.purpose != "PRACTICE":
            problems.append(f"{it.id}: a say_after_me item is a PRACTICE item")
        if it.response_language not in (None, "en"):
            problems.append(f"{it.id}: a say_after_me item is answered in English")
    return problems
