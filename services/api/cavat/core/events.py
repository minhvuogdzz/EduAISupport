"""Event vocabulary and typed payloads shared by tutor, session and assessment (blueprint PART 10.3-10.4).

The envelope itself is ``cavat.modules.session.repository.SessionEvent`` (``payload`` is a plain dict).
This module is the **contract between the producers (the item loop, T04; the teaching loop, M1-6) and
the node mastery projector (consumer, ``assessment/projector.py``, M1-3)**: producers build a payload model
and store ``model.model_dump(mode="json")``; consumers validate with ``PAYLOAD_MODELS[event_type]``.
Add fields only with defaults, and bump ``EVENT_SCHEMA_VERSION`` in the session repository when a change
is not backwards compatible.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cavat.core.pedagogy import (
    ActivityType,
    ErrorClass,
    ItemResolution,
    Move,
    Outcome,
    PracticeSupport,
    TeachAction,
)


class EventType(StrEnum):
    # lifecycle
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_PAUSED = "SESSION_PAUSED"
    SESSION_RESUMED = "SESSION_RESUMED"
    SESSION_INTERRUPTED = "SESSION_INTERRUPTED"
    SESSION_EXITED = "SESSION_EXITED"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_ABANDONED = "SESSION_ABANDONED"
    TIME_WARNING = "TIME_WARNING"
    # activity
    ACTIVITY_STARTED = "ACTIVITY_STARTED"
    ACTIVITY_COMPLETED = "ACTIVITY_COMPLETED"
    ACTIVITY_SKIPPED = "ACTIVITY_SKIPPED"
    # item
    QUESTION_SHOWN = "QUESTION_SHOWN"
    ANSWER_SUBMITTED = "ANSWER_SUBMITTED"
    EXPLANATION_SUBMITTED = "EXPLANATION_SUBMITTED"
    ITEM_RESOLVED = "ITEM_RESOLVED"
    # student commands as typed (session API); the item loop adds the graded events
    STUDENT_MESSAGE = "STUDENT_MESSAGE"
    CHOICE_MADE = "CHOICE_MADE"
    # tutor
    POLICY_DECISION = "POLICY_DECISION"
    HINT_REQUESTED = "HINT_REQUESTED"
    HINT_DELIVERED = "HINT_DELIVERED"
    MISCONCEPTION_DETECTED = "MISCONCEPTION_DETECTED"
    VERIFICATION_ASKED = "VERIFICATION_ASKED"
    TUTOR_MESSAGE_SENT = "TUTOR_MESSAGE_SENT"
    OUTPUT_REJECTED = "OUTPUT_REJECTED"
    MODEL_FALLBACK = "MODEL_FALLBACK"
    SAFETY_FLAGGED = "SAFETY_FLAGGED"
    # voice
    VOICE_UTTERANCE = "VOICE_UTTERANCE"
    VOICE_FALLBACK_TO_TEXT = "VOICE_FALLBACK_TO_TEXT"
    # teaching on the chapter graph (plan v1)
    NODE_DECISION = "NODE_DECISION"
    TEACH_MESSAGE_SENT = "TEACH_MESSAGE_SENT"
    RETELL_JUDGED = "RETELL_JUDGED"
    # assessment / teacher
    EVIDENCE_RECORDED = "EVIDENCE_RECORDED"
    TEACHER_OVERRIDE = "TEACHER_OVERRIDE"


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionShown(_Payload):
    item_id: str
    activity_id: str | None = None
    activity_type: ActivityType
    purpose: Literal["CONCEPT_CHECK", "PRACTICE", "EXIT", "REVIEW"]
    kc_ids: list[str]
    cognitive_level: Literal["A", "B", "C", "D", "E", "DIAG"]
    difficulty: float = Field(ge=0.0, le=1.0)
    transfer: Literal["none", "near", "far"] = "none"
    isomorphic_group: str | None = None


class AnswerSubmitted(_Payload):
    """A graded attempt at an item. ``outcome`` and the diagnosis come from the deterministic checker."""

    item_id: str
    attempt_no: int = Field(ge=1)
    raw_text: str
    modality: Literal["TEXT", "VOICE"] = "TEXT"
    latency_ms: int | None = None
    outcome: Outcome
    normalized: str | None = None
    error_class: ErrorClass | None = None
    misconception_id: str | None = None
    misconception_confidence: float = 0.0
    answer_changes: int = 0


class ExplanationSubmitted(_Payload):
    """The student's own reasoning ("vì sao ...?"). Labels come from the LLM and are only proposals."""

    item_id: str
    text: str
    modality: Literal["TEXT", "VOICE"] = "TEXT"
    reasoning_quality: float | None = Field(default=None, ge=0.0, le=1.0)
    label_source: Literal["NONE", "LLM", "RUBRIC_RULE", "TEACHER"] = "NONE"
    label_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    guessed: bool = False


class PolicyDecisionMade(_Payload):
    item_id: str
    move: Move
    hint_level: int | None = Field(default=None, ge=0, le=7)
    hint_target: str | None = None
    misconception_id: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)


class HintDelivered(_Payload):
    item_id: str
    hint_level: int = Field(ge=1, le=7)
    hint_target: str
    source: Literal["TEMPLATE", "GENERIC", "LLM"]
    template_ref: str | None = None


class MisconceptionDetected(_Payload):
    item_id: str
    misconception_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["BUG_RULE", "CHOICE", "NUMERIC", "BOOLEAN", "LLM"]


class TutorMessageSent(_Payload):
    item_id: str
    move: Move
    text: str
    source: Literal["TEMPLATE", "GENERIC", "LLM", "FALLBACK"]
    words: int = Field(ge=0)
    attempts_to_pass_validator: int = Field(default=1, ge=1)


class OutputRejected(_Payload):
    item_id: str
    move: Move
    issue_codes: list[str]
    source: Literal["TEMPLATE", "GENERIC", "LLM", "FALLBACK"]


class ModelFallback(_Payload):
    model_class: str
    from_model: str
    to_model: str
    reason: Literal["QUOTA", "UNAVAILABLE", "INVALID_OUTPUT", "TIMEOUT", "BLOCKED"]


class ItemResolved(_Payload):
    """How an item ended. This is the main input of the assessment projector (blueprint PART 15.4, 26.1)."""

    item_id: str
    purpose: Literal["CONCEPT_CHECK", "PRACTICE", "EXIT", "REVIEW"]
    kc_ids: list[str]
    cognitive_level: Literal["A", "B", "C", "D", "E", "DIAG"]
    difficulty: float = Field(ge=0.0, le=1.0)
    transfer: Literal["none", "near", "far"] = "none"
    resolution: ItemResolution
    max_hint_level: int = Field(ge=0, le=7)
    attempts: int = Field(ge=0)
    hints_count: int = Field(ge=0)
    misconception_ids: list[str] = Field(default_factory=list)
    final_error_class: ErrorClass | None = None
    explained: bool | None = (
        None  # None = no "why" question asked; True/False = the student's explanation was judged
    )
    guessed: bool = False
    time_s: float | None = None
    modality: Literal["TEXT", "VOICE"] = "TEXT"
    asr_confidence: float | None = None


class RetellJudged(_Payload):
    """The student's own retell of a node ("con nói lại", plan v1 step 3), judged against its key ideas.

    ``score`` is the share of key ideas found. RUBRIC_RULE is the deterministic keyword rubric of
    milestone 1; an LLM label (milestone 2) is only a proposal and keeps its confidence (PART 26.5).
    """

    node_id: str
    text: str
    ideas_found: list[int] = Field(default_factory=list)
    ideas_total: int = Field(ge=1)
    score: float = Field(ge=0.0, le=1.0)
    label_source: Literal["RUBRIC_RULE", "LLM", "TEACHER"] = "RUBRIC_RULE"
    label_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    modality: Literal["TEXT", "VOICE"] = "TEXT"


class NodeDecisionMade(_Payload):
    """A decision of the node teaching policy (plan v1, 5.4). The decisions of a session, with the item
    results and retells that follow them, are the whole teaching state (``teaching/state.py``)."""

    action: TeachAction
    node_id: str | None = None
    ref: str | None = None  # theory variant, worked example or item id
    support: PracticeSupport | None = None
    rule_ids: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    policy_version: str


class TeachMessageSent(_Payload):
    """A message of the teaching loop itself: theory, worked example, retell prompt, feedback, node
    transitions, summary (``teaching/loop.py``, ``MessageKind``). Item messages stay TUTOR_MESSAGE_SENT."""

    kind: Literal["NODE", "THEORY", "EXAMPLE", "RETELL_PROMPT", "FEEDBACK", "PASS", "STOP", "SUMMARY"]
    text: str
    node_id: str | None = None
    ref: str | None = None  # theory variant or worked example id
    templates_version: str


# Which payload model validates which event type. Types not listed carry free-form payloads for now.
class StudentMessage(_Payload):
    """What the student sent, before grading. Kept for the transcript and for replaying the item loop."""

    item_id: str
    kind: Literal["ANSWER", "STEP", "EXPLANATION", "MESSAGE"]
    text: str
    modality: Literal["TEXT", "VOICE"] = "TEXT"
    seconds: float = Field(default=0.0, ge=0)


class HintRequested(_Payload):
    item_id: str
    seconds: float = Field(default=0.0, ge=0)


class ChoiceMade(_Payload):
    item_id: str
    choice_id: str
    label: str


class SafetyFlagged(_Payload):
    """The model judged the student's message worrying (constitution rule 8). For the teacher to review."""

    item_id: str
    source: Literal["LLM"] = "LLM"


PAYLOAD_MODELS: dict[EventType, type[BaseModel]] = {
    EventType.SAFETY_FLAGGED: SafetyFlagged,
    EventType.STUDENT_MESSAGE: StudentMessage,
    EventType.HINT_REQUESTED: HintRequested,
    EventType.CHOICE_MADE: ChoiceMade,
    EventType.QUESTION_SHOWN: QuestionShown,
    EventType.ANSWER_SUBMITTED: AnswerSubmitted,
    EventType.EXPLANATION_SUBMITTED: ExplanationSubmitted,
    EventType.POLICY_DECISION: PolicyDecisionMade,
    EventType.HINT_DELIVERED: HintDelivered,
    EventType.MISCONCEPTION_DETECTED: MisconceptionDetected,
    EventType.TUTOR_MESSAGE_SENT: TutorMessageSent,
    EventType.OUTPUT_REJECTED: OutputRejected,
    EventType.MODEL_FALLBACK: ModelFallback,
    EventType.ITEM_RESOLVED: ItemResolved,
    EventType.RETELL_JUDGED: RetellJudged,
    EventType.NODE_DECISION: NodeDecisionMade,
    EventType.TEACH_MESSAGE_SENT: TeachMessageSent,
}
