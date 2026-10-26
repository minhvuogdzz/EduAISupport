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
from typing import Any, Literal

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
    MODEL_CALLED = "MODEL_CALLED"
    SAFETY_FLAGGED = "SAFETY_FLAGGED"
    # voice
    VOICE_UTTERANCE = "VOICE_UTTERANCE"
    VOICE_FALLBACK_TO_TEXT = "VOICE_FALLBACK_TO_TEXT"
    # teaching on the chapter graph (plan v1)
    NODE_DECISION = "NODE_DECISION"
    TEACH_MESSAGE_SENT = "TEACH_MESSAGE_SENT"
    RETELL_JUDGED = "RETELL_JUDGED"
    # grounded speech (RAG-2)
    RAG_RETRIEVED = "RAG_RETRIEVED"
    QUESTION_PARKED = "QUESTION_PARKED"
    # contextual reading (CTX-1)
    MESSAGE_READ = "MESSAGE_READ"
    MOVE_CHOSEN = "MOVE_CHOSEN"
    ITEM_RESTARTED = "ITEM_RESTARTED"
    CONTEXT_ROUTED = "CONTEXT_ROUTED"
    WEB_LOOKED = "WEB_LOOKED"
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
    # BRAIN-1 (DI-84): the model that wrote an LLM message (the teacher's page shows who spoke)
    model: str | None = None


class OutputRejected(_Payload):
    item_id: str
    move: Move
    issue_codes: list[str]
    source: Literal["TEMPLATE", "GENERIC", "LLM", "FALLBACK"]


class ModelFallback(_Payload):
    """CFG-2: the chain of a model class moved on (ADR-017, blueprint PART 12.6): ``from_model`` did not
    answer and ``to_model`` was tried next. Written after the command's other events
    (``session/model_calls.py``), never replayed."""

    model_class: str
    from_model: str
    to_model: str
    reason: Literal["QUOTA", "UNAVAILABLE", "INVALID_OUTPUT", "TIMEOUT", "BLOCKED"]
    purpose: str = ""  # the request's schema name, as in MODEL_CALLED


class ModelAttempt(_Payload):
    model: str
    sent: bool  # False: skipped (known out of quota) or refused before sending (prompt too long)
    error: str | None = None  # the gateway's error class; None: this model answered
    # CFG-3: the provider's words without the organization id, the limit a 429 names (ITPM: input tokens per
    # minute; TPD: tokens per day; RPM, RPD: requests) and the seconds until it frees up, when known.
    detail: str = ""
    limit: str | None = None
    retry_after_s: float | None = Field(default=None, ge=0)


class ModelCalled(_Payload):
    """CFG-2: one call of the AI gateway during a session command: the model that answered, the tokens the
    provider counted, and what the gateway estimated before sending (``ai_gateway/base.py``, the cap of
    3.000 tokens). Written after the command's other events, never replayed."""

    model_class: str
    purpose: str  # the request's schema name: tutor_turn, reading, move_choice, grounded_turn
    model: str | None = None  # None: no model answered, the caller used its own fallback
    fallback_reason: str | None = None  # the router's FallbackReason when no model answered
    attempts: list[ModelAttempt] = Field(default_factory=list)
    prompt_tokens: int = Field(default=0, ge=0)  # counted by the provider; 0 when no model answered
    completion_tokens: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)  # estimate_prompt_tokens, checked against the cap
    prompt_chars: int = Field(default=0, ge=0)  # characters of the messages
    schema_chars: int = Field(default=0, ge=0)  # characters of the JSON schema sent with them
    messages: int = Field(default=0, ge=0)


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
    # DI-52: RECALL is the child recalling a node learnt before, asked when a related node starts or its
    # check fails; it is evidence on that earlier node like any retell (R).
    purpose: Literal["RETELL", "RECALL"] = "RETELL"
    label_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    modality: Literal["TEXT", "VOICE"] = "TEXT"
    # REFORM-6 (4.1, DI-83): the ideas the model found beyond the keywords, each with the words of the child
    # it
    # rests on (checked to be in ``text``). ``ideas_found`` already holds them: a replay reads this event and
    # never asks the model again. Empty for a judgement by keywords alone (label_source RUBRIC_RULE).
    model_ideas: list[int] = Field(default_factory=list)
    quotes: list[str] = Field(default_factory=list)


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

    kind: Literal[
        "NODE", "THEORY", "EXAMPLE", "RETELL_PROMPT", "FEEDBACK", "ANSWER", "PASS", "STOP", "SUMMARY"
    ]
    text: str
    node_id: str | None = None
    ref: str | None = None  # theory variant or worked example id
    templates_version: str
    # RAG-2: who wrote the words. TEMPLATE: approved text; LLM: Qwen, checked against its sources;
    # EXTRACT: a sentence of a retrieved passage, word for word.
    source: Literal["TEMPLATE", "LLM", "EXTRACT", "WEB"] = "TEMPLATE"
    sources: list[str] = Field(default_factory=list)  # titles of the passages the words rest on
    rejected: list[list[str]] = Field(default_factory=list)  # check codes of each refused model output


class RagRetrieved(_Payload):
    """One retrieval of the Hybrid RAG for a tutor turn, with every signal (plan v1 5.5.3, step 6)."""

    purpose: Literal["QUESTION", "BRIDGE"]
    node_id: str | None = None
    query: str
    mode: str
    grounded: bool
    grounding: str  # why: "cosine 0.74 ≥ 0.65", "độ phủ từ khóa 0.31 < 0.50"
    semantic: str  # the embedding model, or "off"
    chunks: list[dict[str, Any]] = Field(
        default_factory=list
    )  # chunk_id, title, final, bm25, cosine, coverage


class MessageRead(_Payload):
    """How an unclear message of the child was read in context (CTX-1, ``tutor/reader.py``). Replayed from
    this record, never read again."""

    item_id: str
    turn: int  # the item loop's student turn the reading was made on
    label: Literal[
        "ANSWER",
        "STEP_ANSWER",
        "ASKS_ABOUT",
        "ASK_TASK",
        "DONT_KNOW",
        "OFF_TOPIC",
        "AFFECT",
        "OTHER",
        "AMBIGUOUS_TYPO",  # REFORM-5: a typo with a likely meaning ("ki" for "ko")
        "GIBBERISH",  # REFORM-5: a key slip or laughter with none ("ể", "êr", "tt", "kkk")
    ]
    focus: str = ""
    answer: str = ""
    source: Literal["RULE", "LLM"]
    # REFORM-5 (3.1): what the reader guessed the child meant, and the question it proposes to ask. Both are
    # said or shown to the teacher only after the validator passed them; a replay reads them from here.
    guessed_meaning: str = ""
    clarification: str = ""


class MoveChosen(_Payload):
    """AUTO-1 (ADR-031): the policy offered several allowed moves for one turn and Qwen picked one, with its
    reason; the policy checked the pick (``accepted``). Replayed from this record, never asked again."""

    item_id: str
    turn: int  # the item loop's student turn the choice was made on
    option_id: str  # the option Qwen named ("A" is always the policy's own move)
    options: list[str]  # the moves offered, in the order of their ids
    move: str  # the move that was played
    reason: str = ""
    accepted: bool = True  # False: the pick was not on the menu; the policy's own move was played
    source: Literal["LLM"] = "LLM"


class ItemRestarted(_Payload):
    """FIX-4: the open item starts again from here, because today's code reads the child's earlier words on
    it differently from the code that taught them, and its replay closed the item before they ran out (a
    session of 2026-10-12 stopped answering on 2026-10-19). A rebuild replays only what follows this mark."""

    item_id: str
    reason: Literal["REPLAY_DIVERGED"] = "REPLAY_DIVERGED"


class QuestionParked(_Payload):
    """A question of the child the tutor did not answer: kept for the teacher (plan v1 5.5.3)."""

    node_id: str | None = None
    text: str
    reason: Literal["NOT_GROUNDED", "SAME_AS_CHECK", "LIMIT", "LATER"]
    later_node: str | None = None  # LATER: the node where the question is taught


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


class ContextRouted(_Payload):
    """What the conductor (``teaching/conductor.py``) did with a message before the loop read it: the text
    as typed, the text the loop read, what it found, and whether it unstuck a repeated tutor turn."""

    raw: str
    text: str
    signals: list[str] = Field(default_factory=list)  # TEENCODE, EMOJI, STRETCHED, LONG, KEYWORD_DUMP...
    route: Literal["PASS", "UNSTICK"] = "PASS"
    version: str


class WebLooked(_Payload):
    """A question the teacher's documents did not answer, looked up in the trusted source (WEB-1, DI-51):
    what was sent, the article it found and whether its words reached the child."""

    node_id: str | None = None
    query: str
    source: str  # "Wikipedia tiếng Việt"
    title: str
    url: str
    answered: bool
    version: str


class SafetyFlagged(_Payload):
    """The model judged the student's message worrying (constitution rule 8). For the teacher to review."""

    item_id: str
    source: Literal["LLM", "RULE"] = "LLM"  # RULE: the distress phrases of DI-41


PAYLOAD_MODELS: dict[EventType, type[BaseModel]] = {
    EventType.SAFETY_FLAGGED: SafetyFlagged,
    EventType.CONTEXT_ROUTED: ContextRouted,
    EventType.WEB_LOOKED: WebLooked,
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
    EventType.MODEL_CALLED: ModelCalled,
    EventType.ITEM_RESOLVED: ItemResolved,
    EventType.RETELL_JUDGED: RetellJudged,
    EventType.NODE_DECISION: NodeDecisionMade,
    EventType.TEACH_MESSAGE_SENT: TeachMessageSent,
    EventType.RAG_RETRIEVED: RagRetrieved,
    EventType.MESSAGE_READ: MessageRead,
    EventType.MOVE_CHOSEN: MoveChosen,
    EventType.ITEM_RESTARTED: ItemRestarted,
    EventType.QUESTION_PARKED: QuestionParked,
}
