"""Interfaces between the tutor components (blueprint PART 13-16).

These dataclasses are the **frozen contract** that lets the policy engine (T02), the renderer and
validator (T03), the item loop (T04) and the LLM renderer (T06b) be built in parallel by different
sessions. Change a field only in a PR that updates every consumer; adding a field with a default is safe.

Data flow of one tutor turn:

    student text --check_answer--> CheckResult
    (ItemState, CheckResult, StudentSnapshot, time) --policy.decide--> PolicyDecision
    (PolicyDecision, Item, LessonPackage, ItemState) --MessageRenderer.render--> RenderedMessage
    RenderedMessage --MessageValidator--> ValidationResult  (fail -> retry once -> fallback template)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal, Protocol

from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, ItemResolution, Move
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.content.lesson_package import Item, LessonPackage, Persona

MessageSource = Literal["TEMPLATE", "GENERIC", "LLM", "FALLBACK"]
TurnTrigger = Literal["START", "ANSWER", "HINT_REQUEST", "EXPLANATION", "SILENCE", "TICK"]


@dataclass(frozen=True)
class StudentSnapshot:
    """What the tutor knows about the student at session start (deterministic, from the Student Model)."""

    kc_mastery: dict[str, float] = field(default_factory=dict)  # 0..1; a missing KC means unknown
    kc_confidence: dict[str, float] = field(default_factory=dict)  # 0..1
    hint_dependency: float = 0.0  # mean recent hint level divided by 7
    low_confidence_profile: bool = False  # the student tends to say "con không biết" when they know


@dataclass
class ItemState:
    """Mutable per-item state kept by the item loop and read by the policy engine."""

    item_id: str
    activity: ActivityType
    attempt_no: int = 0  # graded attempts so far (CORRECT, WRONG or PARTIAL)
    hint_levels: list[HintLevel] = field(default_factory=list)  # hints delivered, in order
    hint_targets: list[HintTarget] = field(default_factory=list)
    answer_changes: int = 0
    seconds_since_shown: float = 0.0
    seconds_since_last_message: float = 0.0
    nudges_sent: int = 0  # silence nudges (never counted as wrong answers)
    unproductive_turns: int = 0  # turns without progress (blueprint R-FRUSTRATION)
    help_requests: int = 0
    clarify_requests: int = 0  # "là sao ạ?" (ADR-019): never a wrong answer
    off_topic_turns: int = 0  # talk outside the lesson (ADR-019): never a wrong answer
    affect_signals: int = 0  # "chán quá", "con ngu toán" (ADR-019)
    explanations: int = 0  # EXPLAIN moves on the item (CTX-1): asked again past the limit, the next hint
    choice_offered: bool = False  # "gợi ý thêm hay tự thử lại?" is asked once per item (DI-35)
    explanation_asked_again: bool = False  # "vì sao" asked once more after "là sao?" or off-topic talk
    last_explanation_vague: bool = False  # DI-55: the last "vì sao" reply said nothing of this item
    # REFORM-5 (DI-77): the tutor's last message asked what a few unreadable letters meant
    # (ASK_CONFIRM); if the next message is unreadable too, the tutor helps instead of asking a third
    # time.
    confirm_open: bool = False
    probes_sent: int = 0  # "con làm thế nào?" asked after the first wrong answer (R-FIRST-WRONG asks once)
    counter_examples_shown: int = 0  # FIX-6: the next counterexample of the item is a different one
    misconception_counts: dict[str, int] = field(default_factory=dict)
    verified: bool = False  # a "why" question was asked and answered
    dialogue_version: int = 1  # policy changes opt in per recorded student input
    worked_shown: bool = False  # H6/H7 content was delivered
    resolution: ItemResolution | None = None  # set when the item ends

    @property
    def max_hint_level(self) -> HintLevel:
        return max(self.hint_levels, default=HintLevel.H0)


@dataclass(frozen=True)
class PolicyInput:
    item: Item
    state: ItemState
    check: CheckResult | None  # None for START, SILENCE and TICK
    trigger: TurnTrigger
    snapshot: StudentSnapshot = field(default_factory=StudentSnapshot)
    time_left_s: float = float("inf")
    assessment_reserve_s: float = 0.0  # time that must stay available for EXIT_ASSESSMENT and SUMMARY


@dataclass(frozen=True)
class PolicyDecision:
    """What the tutor does this turn. Deterministic for the same ``PolicyInput`` and config."""

    move: Move
    level: HintLevel | None = None  # for HINT-like moves
    target: HintTarget | None = None
    misconception_id: str | None = None
    resolution: ItemResolution | None = (
        None  # set when the move ends the item (CLOSE_ITEM, CONFIRM_ADVANCE...)
    )
    reason_codes: tuple[str, ...] = ()
    rule_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderContext:
    decision: PolicyDecision
    item: Item
    package: LessonPackage
    state: ItemState
    student_text: str | None = None
    persona: Persona = field(default_factory=Persona)
    max_words: int = 60
    # CTX-1: what the child asks about (EXPLAIN), the tutor's previous message, and approved passages the
    # Hybrid RAG retrieved for it: the evidence an explanation may rest on.
    focus: str | None = None
    last_tutor: str | None = None
    evidence: tuple[str, ...] = ()
    # REFORM-5 (ASK_CONFIRM): what the reader guessed the child meant, and the question it proposed, already
    # passed by the validator (the tutor says it as it is). Empty: the template asks.
    guessed_meaning: str | None = None
    clarification: str | None = None
    # BRAIN-1 (DI-84): the checker's verdict on the child's last graded answer, and whether that answer is
    # right (a right answer is the child's own, so the tutor may say it and the calculation behind it).
    # ``free_numbers``: the message is a model's, which may build a new example, so its numbers are checked
    # by arithmetic (``brain.math_errors``) and not by being in the lesson.
    check: CheckResult | None = None
    solved: bool = False
    free_numbers: bool = False
    follow_up: str = ""  # only the uncompleted part of a multi-part task (BRAIN-3)


@dataclass(frozen=True)
class RenderedMessage:
    text: str
    source: MessageSource
    hint_ref: str | None = None  # e.g. "GP-02:STEP:H4" when a stored hint template was used


class MessageRenderer(Protocol):
    """Turns a policy decision into Vietnamese text. The template renderer (T03) needs no network."""

    def render(self, ctx: RenderContext) -> RenderedMessage: ...


class ValidationCode(StrEnum):
    ANSWER_LEAK = "ANSWER_LEAK"
    MULTIPLE_QUESTIONS = "MULTIPLE_QUESTIONS"
    MISSING_QUESTION = "MISSING_QUESTION"
    TOO_LONG = "TOO_LONG"
    PII_REQUEST = "PII_REQUEST"
    INTELLIGENCE_PRAISE = "INTELLIGENCE_PRAISE"
    UNGROUNDED_NUMBER = "UNGROUNDED_NUMBER"  # a number that is not in the item, its hints or its solution
    EMPTY = "EMPTY"
    # Qwen sometimes slips into Chinese or English mid-sentence ("số chữ số thập分 like nha", seen live)
    FOREIGN_TEXT = "FOREIGN_TEXT"
    # Qwen called the child "em" although the lesson says "con" ("…trong số đếm của em", seen live, TQ-3)
    WRONG_ADDRESS = "WRONG_ADDRESS"
    # FIX-2: "Đúng rồi!" on a turn that follows an answer that is not right (R-STRONG-PRIOR's "vì sao")
    WRONG_PRAISE = "WRONG_PRAISE"
    # FIX-5: the turn repeats the child's words as the tutor's own ("cô ơi con chơi game được không, nhưng…")
    ECHOES_CHILD = "ECHOES_CHILD"


@dataclass(frozen=True)
class ValidationIssue:
    code: ValidationCode
    detail: str = ""


@dataclass(frozen=True)
class ValidationResult:
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(i.code.value for i in self.issues)


class MessageValidator(Protocol):
    def __call__(self, text: str, ctx: RenderContext) -> ValidationResult: ...
