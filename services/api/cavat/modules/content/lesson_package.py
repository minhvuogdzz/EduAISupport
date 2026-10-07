"""Lesson package: the approved, versioned lesson content the tutor runtime consumes.

Loaded from YAML (see docs/pedagogy/**/lesson.yaml). Blueprint PART 22.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from cavat.core.pedagogy import HintLevel, HintTarget


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


AnswerType = Literal["compare", "order", "numeric", "choice", "boolean", "open"]


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


class OpenAnswer(_Model):
    type: Literal["open"]
    rubric: str
    sample_answer: str


AnswerSpec = Annotated[
    CompareAnswer | OrderAnswer | NumericAnswer | ChoiceAnswer | BooleanAnswer | OpenAnswer,
    Field(discriminator="type"),
]


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

    @property
    def is_assessment(self) -> bool:
        return self.purpose == "EXIT"

    @property
    def requires_explanation(self) -> bool:
        return isinstance(self.answer, BooleanAnswer) and self.answer.requires_explanation


class Misconception(_Model):
    id: str
    kc_id: str
    name: str
    description: str
    bug_rule: str | None = None
    severity: Literal["CRITICAL", "NORMAL"] = "NORMAL"
    counter_examples: list[str] = Field(default_factory=list)


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
        elif isinstance(ans, NumericAnswer | BooleanAnswer):
            referenced += list(ans.wrong_answers.values())
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
    return problems
