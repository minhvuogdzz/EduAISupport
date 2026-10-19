"""Session API (T08, blueprint PART 24 and 29). Shapes follow apps/web/src/api/contract.ts.

Two kinds of session share the endpoints: a **chapter** session (M1-7, the default) runs the teaching
loop of plan v1 on the chapter's knowledge graph (``chapter_service``); a **lesson** session runs the
fixed demo plan of lesson 1 (``service``). ``GET /{id}/report`` shows the teacher how the tutor scored
and decided in a chapter session.

Not implemented yet: ``GET /v1/sessions/{id}/stream`` (SSE); the web polls ``/state`` after each command.

**Temporary auth:** the student is whoever the ``X-Demo-Student`` header names and every session belongs
to ``DEMO_SCHOOL_ID``. T12 replaces this with real accounts; nothing else may rely on the header.

The backend enforces every session rule (CLAUDE.md rule 4): owner, lifecycle, current item, allowed
commands, ``expected_state_version`` and ``Idempotency-Key``. The key is checked first, so a resent
command gets its first answer back instead of a 409.
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache, partial
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from cavat import db
from cavat.config import get_settings
from cavat.core.events import EventType
from cavat.core.repository import utc_now
from cavat.modules.ai_gateway.router import AIRouter, build_router
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.content.lesson_package import LessonPackage
from cavat.modules.identity.api import AuthError, demo_mode, identity_from, register_auth, require
from cavat.modules.identity.repository import UserRepository
from cavat.modules.ingest import api as ingest_api
from cavat.modules.library import api as library_api
from cavat.modules.rag import api as rag_api
from cavat.modules.rag.service import RagService
from cavat.modules.session import chapter_service, progress, service, teacher_view
from cavat.modules.session.repository import (
    DuplicateCommand,
    EventRepository,
    LearningSession,
    LearningSessionRepository,
    LifecycleState,
    SafetyReviewRepository,
    StateVersionConflict,
)
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.tutor.reader import LiveReader, ModelReader
from cavat.modules.voice import api as voice_api

MAX_TEXT_CHARS = 500


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def _error(status: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return JSONResponse(status_code=status, content=body)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateSession(_In):
    lesson_id: str | None = None
    student_display_name: str | None = Field(default=None, max_length=40)


class TextContent(_In):
    text: str = Field(max_length=MAX_TEXT_CHARS)


class ResponseCommand(_In):
    item_attempt_id: str
    kind: Literal["ANSWER", "STEP", "EXPLANATION", "MESSAGE"] = "ANSWER"
    content: TextContent
    modality: Literal["TEXT", "VOICE"] = "TEXT"
    expected_state_version: int = Field(ge=0)


class HintRequestCommand(_In):
    item_attempt_id: str
    expected_state_version: int = Field(ge=0)


class ChoiceCommand(_In):
    choice_id: str
    expected_state_version: int = Field(ge=0)


class ChatTurn(BaseModel):
    turn_id: str
    sequence_no: int
    item_attempt_id: str | None
    actor: Literal["student", "tutor", "system", "teacher"]
    text: str
    occurred_at: datetime
    move: str | None
    hint_level: int | None
    kind: str | None = None  # chapter sessions: THEORY, EXAMPLE, RETELL_PROMPT, FEEDBACK, NODE, PASS...
    node_id: str | None = None


class ItemOption(BaseModel):
    id: str
    text: str


class CurrentItem(BaseModel):
    item_attempt_id: str
    item_id: str
    stem: str
    answer_format: Literal["compare", "order", "numeric", "choice", "boolean", "open"]
    options: list[ItemOption]
    expecting: Literal["ANSWER", "EXPLANATION"]
    position: int


class MicroChoice(BaseModel):
    choice_id: str
    label: str


class LessonRef(BaseModel):
    lesson_id: str
    title: str


class PersonaView(BaseModel):
    tutor_self: str
    student_address: str


class ActivityView(BaseModel):
    activity_id: str
    type: str


class Progress(BaseModel):
    items_done: int
    items_total: int


class NodeView(BaseModel):
    node_id: str
    name: str
    layer: Literal["BASIC", "IMPLEMENT"]
    status: Literal["PASSED", "CURRENT", "ON_HOLD", "STOPPED", "AVAILABLE", "LOCKED"]
    level: int | None  # 0-5 once the node has evidence
    order: int  # place in the learning order


class RelationView(BaseModel):
    source: str
    target: str
    type: Literal["PREREQUISITE", "SUBCLASS", "SIMILAR", "APPLICATION"]


class ChapterRef(BaseModel):
    chapter_id: str
    title: str


class TeachingView(BaseModel):
    chapter: ChapterRef
    current_node_id: str | None
    step: int | None  # 1-7: the step of the teaching cycle (plan v1, 5.2)
    awaiting: Literal["ANSWER", "THEORY_REPLY", "RETELL", "NOTHING"]
    input_id: str | None  # sent back as item_attempt_id
    prompt: str | None
    nodes: list[NodeView]
    relations: list[RelationView]
    passed: int
    total: int


class SessionStateView(BaseModel):
    session_id: str
    state_version: int
    lifecycle_state: str
    lesson: LessonRef
    student_display_name: str
    persona: PersonaView
    activity: ActivityView | None
    item: CurrentItem | None
    pending_choice: list[MicroChoice] | None
    allowed_commands: list[Literal["ANSWER", "HINT_REQUEST", "CHOICE"]]
    progress: Progress
    transcript: list[ChatTurn]
    teaching: TeachingView | None = None


class SessionSummaryView(BaseModel):
    session_id: str
    student_display_name: str
    lesson_title: str
    lifecycle_state: str
    started_at: datetime | None
    updated_at: datetime
    progress: Progress
    misconception_ids: list[str]
    engine: Literal["mock", "live"]
    mode: Literal["LESSON", "CHAPTER"] = "LESSON"  # CHAPTER: GET /{id}/report explains the teaching


class TutorAnnotation(BaseModel):
    move: str
    hint_level: int | None
    hint_target: str | None
    rule_ids: list[str]
    reason_codes: list[str]
    source: Literal["TEMPLATE", "GENERIC", "LLM", "FALLBACK"]


class MisconceptionView(BaseModel):
    id: str
    name: str
    confidence: float


class RetellView(BaseModel):
    score: float
    ideas_found: int
    ideas_total: int


class StudentAnnotation(BaseModel):
    kind: Literal["ANSWER", "STEP", "EXPLANATION", "MESSAGE", "HINT_REQUEST", "CHOICE"]
    outcome: str | None
    normalized_answer: str | None
    misconception: MisconceptionView | None
    retell: RetellView | None = None
    safety: bool = False  # the child's words raised a safety flag (DI-41 or the model): for the teacher
    read: dict[str, str] | None = None  # CTX-1: how an unclear message was read (label, focus, source)


class TeachAnnotation(BaseModel):
    kind: str
    node_id: str | None
    rule_ids: list[str]
    reason_codes: list[str]
    # RAG-2: TEMPLATE (approved text), LLM (Qwen, checked against its sources), EXTRACT (a passage verbatim)
    source: Literal["TEMPLATE", "LLM", "EXTRACT"] = "TEMPLATE"
    sources: list[str] = []  # titles of the passages the words rest on
    rejected: list[list[str]] = []  # check codes of each refused model output
    grounded: bool | None = None  # a question of the child: did the passages ground it
    grounding: str | None = None
    parked: Literal["NOT_GROUNDED", "SAME_AS_CHECK", "LIMIT", "LATER"] | None = None  # kept for the teacher


class TranscriptTurn(BaseModel):
    sequence_no: int
    occurred_at: datetime
    actor: Literal["student", "tutor", "system", "teacher"]
    text: str
    tutor: TutorAnnotation | None
    student: StudentAnnotation | None
    teach: TeachAnnotation | None = None


class SessionSegment(BaseModel):
    kind: Literal["session"]
    turns: list[TranscriptTurn]


class ItemSegment(BaseModel):
    kind: Literal["item"]
    item_attempt_id: str
    item_id: str
    activity_type: str
    stem: str
    position: int
    resolution: str | None
    max_hint_level: int
    turns: list[TranscriptTurn]


class SessionTranscriptView(BaseModel):
    session: SessionSummaryView
    segments: list[Annotated[SessionSegment | ItemSegment, Field(discriminator="kind")]]


class DimensionView(BaseModel):
    mean: float
    n_eff: float
    in_mastery: bool


class ReportMisconception(BaseModel):
    id: str
    name: str
    severity: str
    count: int
    status: str


class PassRuleView(BaseModel):
    min_mastery: float
    min_successes: int
    min_levels: int
    min_forms: int
    max_items: int


class ReportNode(BaseModel):
    node_id: str
    name: str
    layer: Literal["BASIC", "IMPLEMENT"]
    status: str
    prior: float
    mastery: float | None
    confidence: float
    level: int
    state: str
    insufficient_data: bool
    dimensions: dict[str, DimensionView]
    items: int
    successes: int
    levels: list[str]
    forms: list[str]
    understood: bool
    has_explanation: bool
    has_application: bool
    misconceptions: list[ReportMisconception]
    pass_now: bool
    passed: bool
    missing: list[str]
    pass_rule: PassRuleView


class EvidenceView(BaseModel):
    sequence_no: int
    occurred_at: datetime
    earlier: bool = False  # from an earlier session of the student
    node_id: str
    dimension: str
    score: float
    weight: float
    reason: str
    item_id: str | None


class TraceView(BaseModel):
    sequence_no: int
    occurred_at: datetime
    earlier: bool = False
    node_id: str
    mastery: float | None


class DecisionView(BaseModel):
    sequence_no: int
    occurred_at: datetime
    earlier: bool = False
    action: str
    node_id: str | None
    ref: str | None
    support: str | None
    rule_ids: list[str]
    reason_codes: list[str]


class ChapterVersion(BaseModel):
    chapter_id: str
    title: str
    version: str


class TeachingReportView(BaseModel):
    session: SessionSummaryView
    chapter: ChapterVersion
    versions: dict[str, str]
    current_node_id: str | None
    earlier_sessions: int = 0  # sessions of the student on this chapter before this one
    nodes: list[ReportNode]
    relations: list[RelationView]
    evidence: list[EvidenceView]
    trace: list[TraceView]
    decisions: list[DecisionView]


class ProgressNode(BaseModel):
    node_id: str
    name: str
    layer: Literal["BASIC", "IMPLEMENT"]
    status: str
    level: int | None
    quality: Literal["NOT_STARTED", "INSUFFICIENT_DATA", "FAMILIAR", "WITH_SUPPORT", "INDEPENDENT", "SOLID"]
    order: int
    passed: bool


class ProgressTopic(BaseModel):
    node_id: str
    name: str
    quality: str
    reason: str | None = None


class SessionCounts(BaseModel):
    total: int
    completed: int
    unfinished: int
    minutes: int


class WeekView(BaseModel):
    study_days: int
    passed: int


class StudentOverviewView(BaseModel):
    """GET /v1/students/me/overview: the student's chapter in plain words (PART 27.1, DI-14)."""

    student_display_name: str
    parent_code: str
    chapter: ChapterRef
    nodes: list[ProgressNode]
    relations: list[RelationView]
    passed: int
    total: int
    sessions: SessionCounts
    study_days: list[str]
    streak: int
    this_week: WeekView
    going_well: list[ProgressTopic]
    to_practise: list[ProgressTopic]
    current_session_id: str | None
    last_session_at: datetime | None


class TrendDay(BaseModel):
    date: str
    studied: bool
    passed: int
    started: int


class HomeTip(BaseModel):
    node_id: str
    name: str
    tip: str


class ParentSession(BaseModel):
    session_id: str
    started_at: datetime
    minutes: int
    lifecycle_state: str
    passed_names: list[str]


class ParentChildView(StudentOverviewView):
    """GET /v1/parents/children/{code}: the same picture, plus four weeks of trend and how to help at
    home. No transcript: the parent view has no drill-down into the conversation (PART 27.4)."""

    trend: list[TrendDay]
    home_tips: list[HomeTip]
    session_list: list[ParentSession]


# ---------------------------------------------------------------- the teacher's class view (PART 27.1, §56)


class TeacherNode(BaseModel):
    node_id: str
    name: str
    layer: Literal["BASIC", "IMPLEMENT"]
    order: int
    min_mastery: float


class MasteryCell(BaseModel):
    """One student on one KC: M, confidence (DI-7 below 30), the level of §4-§8 and the pass (DI-15)."""

    node_id: str
    mastery: float | None
    confidence: float
    level: int
    state: str
    insufficient_data: bool
    passed: bool
    status: str
    active_misconceptions: int


class AttentionReason(BaseModel):
    # SAFETY (SAFE-1): the child said something worrying in a session; first in the list
    kind: Literal["SAFETY", "STOPPED", "MISCONCEPTION", "WEAK", "INACTIVE"]
    node_id: str | None = None
    misconception_id: str | None = None
    count: int | None = None
    mastery: float | None = None
    days: int | None = None
    session_id: str | None = None  # SAFETY: the session to open
    at: datetime | None = None  # SAFETY: when the last flag was raised


class OverallView(BaseModel):
    """§23: overall mastery and knowledge coverage (DI-21)."""

    mastery: float | None
    confidence: float | None
    level: int | None
    coverage: float


class ClassStudent(BaseModel):
    student_id: str
    display_name: str
    sessions: SessionCounts
    last_active_at: datetime | None
    passed: int
    overall: OverallView
    cells: list[MasteryCell]
    attention: list[AttentionReason]


class ClassNodeSummary(BaseModel):
    """§45: the class on one KC."""

    node_id: str
    mean_mastery: float | None
    students: int
    passed: int


class ClassMisconception(BaseModel):
    """§28: one misconception in the class."""

    id: str
    name: str
    node_id: str | None
    severity: str
    count: int
    share: float
    students: int
    active_students: int
    recent: int


class ClassKpis(BaseModel):
    students: int
    active_this_week: int
    sessions: int
    minutes: int
    passed: int
    cells: int
    mean_mastery: float | None
    attention: int


class ClassOverviewView(BaseModel):
    """GET /v1/teachers/class: the Student × KC heatmap (§46, zones of §25), the class per KC (§45),
    the misconception chart (§28) and the students who need attention."""

    chapter: ChapterRef
    nodes: list[TeacherNode]
    students: list[ClassStudent]
    by_node: list[ClassNodeSummary]
    misconceptions: list[ClassMisconception]
    kpis: ClassKpis


class DimensionValue(BaseModel):
    value: float | None
    n_eff: float


class NodeDimension(BaseModel):
    value: float
    n_eff: float
    in_mastery: bool


class TrendPoint(BaseModel):
    at: datetime
    mastery: float


class NodeMisconception(BaseModel):
    id: str
    name: str
    severity: str
    count: int
    status: str


class TeacherNodeDetail(TeacherNode, MasteryCell):
    """§57: one KC of one student."""

    group: Literal["PASSED", "UNSTABLE", "WEAK", "INSUFFICIENT", "NOT_STARTED"]
    dimensions: dict[str, NodeDimension]
    items: int
    solved: int
    attempts: int
    hints: int
    seconds: int | None
    misconceptions: list[NodeMisconception]
    trend: list[TrendPoint]
    direction: Literal["UP", "FLAT", "DOWN"] | None
    recommendation: Literal["DIAGNOSE", "EXPLAIN", "GUIDED", "PRACTICE", "TRANSFER", "CHALLENGE"]


class StudentOverall(OverallView):
    passed: int
    total: int


class TimelinePoint(BaseModel):
    date: str
    mastery: float


class Velocity(BaseModel):
    change: float
    since: str


class ActivityDay(BaseModel):
    date: str
    independent: int
    supported: int
    worked: int
    unresolved: int
    hints: int
    passed: int


class JourneyStep(BaseModel):
    node_id: str
    item_id: str
    resolution: str
    attempts: int
    hints: int
    at: datetime


class CurvePoint(BaseModel):
    at: datetime
    mastery: float
    node_id: str
    node_mastery: float
    passed: str | None = None


class ConversationStats(BaseModel):
    messages: int = 0
    hint_button: int = 0
    questions: int = 0
    parked: int = 0
    safety: int = 0
    signals: dict[str, int] = Field(default_factory=dict)
    intents: dict[str, int] = Field(default_factory=dict)


class TeacherStudentView(BaseModel):
    """GET /v1/teachers/students/{id}: §23 and §43 overview, §24 radar, §27 timeline, §39 velocity, §56
    activity and the §57 detail of every KC."""

    student_id: str
    display_name: str
    chapter: ChapterRef
    relations: list[RelationView]
    sessions: SessionCounts
    session_list: list[ParentSession]
    last_active_at: datetime | None
    overall: StudentOverall
    dimensions: dict[str, DimensionValue]
    strengths: list[str]
    weaknesses: list[str]
    nodes: list[TeacherNodeDetail]
    timeline: list[TimelinePoint]
    velocity: Velocity | None
    activity: list[ActivityDay]
    attention: list[AttentionReason]
    journey: list[JourneyStep] = Field(default_factory=list)
    curve: list[CurvePoint] = Field(default_factory=list)
    conversation: ConversationStats = Field(default_factory=ConversationStats)


class CommandAck(BaseModel):
    accepted: Literal[True] = True
    state_version: int
    tutor_turn_id: str | None


def get_database() -> Any:
    """The application database. Tests override this dependency with an in-memory database."""
    return db.get_db()


@lru_cache
def _shared_router() -> AIRouter:
    return build_router()  # one per process: it remembers which models are out of quota


def tutor_router() -> AIRouter | None:
    """None keeps sessions on approved templates (default). ``TUTOR_RENDERER=llm`` lets Qwen phrase hints."""
    return _shared_router() if get_settings().tutor_renderer == "llm" else None


def demo_student(x_demo_student: Annotated[str | None, Header()] = None) -> str:
    """Temporary identity (see module docstring)."""
    if not x_demo_student or len(x_demo_student) > 64 or not x_demo_student.replace("-", "").isalnum():
        raise ApiError(401, "NOT_SESSION_OWNER", "X-Demo-Student header is required")
    return x_demo_student


def demo_parent(x_demo_parent: Annotated[str | None, Header()] = None) -> str:
    """Temporary (T12 adds parent accounts and guardian links): any ``X-Demo-Parent`` header marks a
    parent, who sees one child through the code the child's page shows (``progress.parent_code``)."""
    if not x_demo_parent:
        raise ApiError(401, "NOT_SESSION_OWNER", "X-Demo-Parent header is required")
    return x_demo_parent


def local_today() -> date:
    """Today on the student's clock (Asia/Ho_Chi_Minh). Tests override it."""
    return datetime.now(progress.LOCAL_TZ).date()


def demo_teacher(x_demo_teacher: Annotated[str | None, Header()] = None) -> str:
    """Temporary (T12 adds accounts and roles): any ``X-Demo-Teacher`` header marks the teacher."""
    if not x_demo_teacher:
        raise ApiError(401, "NOT_SESSION_OWNER", "X-Demo-Teacher header is required")
    return x_demo_teacher


def student_identity(
    authorization: Annotated[str | None, Header()] = None,
    x_demo_student: Annotated[str | None, Header()] = None,
) -> str:
    """The student account (ACC-1), or the demo header in ``AUTH_MODE=demo``."""
    if demo_mode():
        return demo_student(x_demo_student)
    return require(identity_from(authorization), "STUDENT").user_id


def teacher_identity(
    authorization: Annotated[str | None, Header()] = None,
    x_demo_teacher: Annotated[str | None, Header()] = None,
) -> str:
    if demo_mode():
        return demo_teacher(x_demo_teacher)
    return require(identity_from(authorization), "TEACHER").user_id


def parent_identity(
    authorization: Annotated[str | None, Header()] = None,
    x_demo_parent: Annotated[str | None, Header()] = None,
) -> str:
    if demo_mode():
        return demo_parent(x_demo_parent)
    return require(identity_from(authorization), "PARENT").user_id


def linked_child(authorization: Annotated[str | None, Header()] = None) -> str:
    """The child linked to the parent account (guardian link, ACC-1)."""
    if demo_mode():
        raise ApiError(404, "NOT_FOUND", "the demo mode has no guardian link: use the child's code")
    child = require(identity_from(authorization), "PARENT").child_id
    if not child:
        raise ApiError(404, "NOT_FOUND", "no child is linked to this parent account")
    return child


def account_name(authorization: Annotated[str | None, Header()] = None) -> str | None:
    """The display name of the logged-in account: a session takes it, never a name typed in the web."""
    return None if demo_mode() else identity_from(authorization).display_name


Database = Annotated[Any, Depends(get_database)]
Student = Annotated[str, Depends(student_identity)]
Teacher = Annotated[str, Depends(teacher_identity)]
Parent = Annotated[str, Depends(parent_identity)]
LinkedChild = Annotated[str, Depends(linked_child)]
AccountName = Annotated[str | None, Depends(account_name)]
Today = Annotated[date, Depends(local_today)]
IdempotencyKey = Annotated[str | None, Header(max_length=100)]

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
students = APIRouter(prefix="/v1/students", tags=["students"])
parents = APIRouter(prefix="/v1/parents", tags=["parents"])
teachers = APIRouter(prefix="/v1/teachers", tags=["teachers"])


def _repo(database: Any) -> LearningSessionRepository:
    return LearningSessionRepository(database, service.DEMO_SCHOOL_ID)


def _package(lesson_id: str) -> LessonPackage:
    pkg = service.lesson_packages().get(lesson_id)
    if pkg is None:
        raise ApiError(404, "NOT_FOUND", f"lesson {lesson_id!r} not found")
    return pkg


def _chapter(chapter_id: str, version: str | None = None) -> Chapter:
    """A chapter for a new session (``version`` None), or the one a session started with (INGEST-4)."""
    chapter = (
        chapter_service.chapter_for(chapter_id, version)
        if version
        else chapter_service.chapters().get(chapter_id)
    )
    if chapter is None:
        raise ApiError(404, "NOT_FOUND", f"chapter {chapter_id!r} not found")
    return chapter


async def published_chapters(database: Database) -> None:
    """Every request of the session routers first knows the plans the teacher published (INGEST-4)."""
    await chapter_service.load_published(database, service.DEMO_SCHOOL_ID)


def _earlier(sessions: list[LearningSession], session: LearningSession) -> list[Any]:
    """Events of the student's sessions of the same chapter started before ``session``, oldest first."""
    if not chapter_service.is_chapter(session):
        return []
    before = [
        s
        for s in sessions
        if s.id != session.id
        and s.student_id == session.student_id
        and s.lesson_id == session.lesson_id
        and chapter_service.is_chapter(s)
        and s.created_at < session.created_at
    ]
    return [e for s in sorted(before, key=lambda s: s.created_at) for e in s.events]


async def _history(database: Any, session: LearningSession) -> list[Any]:
    """The student's history on this chapter: what the tutor remembers from earlier sessions."""
    if not chapter_service.is_chapter(session):
        return []
    return _earlier(await _repo(database).list_for_student(session.student_id), session)


async def _view(database: Any, session: LearningSession) -> dict[str, Any]:
    if chapter_service.is_chapter(session):
        history = await _history(database, session)
        return chapter_service.student_view(
            _chapter(session.lesson_id, session.lesson_version), session, history
        )
    return service.student_view(_package(session.lesson_id), session)


def _summaries(sessions: list[LearningSession]) -> list[dict[str, Any]]:
    """Summaries of a list of sessions; chapter progress counts what the student passed before too."""
    packages, chapters = service.lesson_packages(), chapter_service.chapters()
    return [
        chapter_service.summary(
            chapter_service.chapter_for(s.lesson_id, s.lesson_version) or chapters[s.lesson_id],
            s,
            _earlier(sessions, s),
        )
        if chapter_service.is_chapter(s) and s.lesson_id in chapters
        else service.summary(packages.get(s.lesson_id), s)
        for s in sessions
    ]


async def _load(database: Any, session_id: str, student: str) -> LearningSession:
    session = await _repo(database).get(session_id)
    if session is None:
        raise ApiError(404, "NOT_FOUND", "session not found")
    if session.student_id != student:
        raise ApiError(403, "NOT_SESSION_OWNER", "this session belongs to another student")
    return session


def _ack_for_key(session: LearningSession, key: str) -> CommandAck | None:
    """The answer first given to this idempotency key, rebuilt from the events it wrote."""
    events = [e for e in session.events if e.idempotency_key == key]
    if not events:
        return None
    version = next((e.correlation["state_version"] for e in events if "state_version" in e.correlation), None)
    said = (EventType.TUTOR_MESSAGE_SENT, EventType.TEACH_MESSAGE_SENT)
    tutor = [e.event_id for e in events if e.event_type in said]
    return CommandAck(
        state_version=int(version) if version is not None else session.state_version,
        tutor_turn_id=tutor[-1] if tutor else None,
    )


def _web_source() -> Any:
    """WEB-1 (DI-51): the trusted source a question the documents do not answer may be looked up in."""
    settings = get_settings()
    if settings.web_lookup != "wikipedia":
        return None
    from cavat.modules.teaching.web import WikipediaVi

    return WikipediaVi(cache_dir=settings.storage_dir / "web")


async def _command(
    database: Any,
    session_id: str,
    student: str,
    key: str | None,
    expected_version: int,
    command: service.CommandType,
    item_attempt_id: str | None = None,
    **kwargs: Any,
) -> CommandAck:
    if not key:
        raise ApiError(422, "VALIDATION_ERROR", "Idempotency-Key header is required")
    session = await _load(database, session_id, student)
    previous = _ack_for_key(session, key)
    if previous is not None:
        return previous
    if session.state.lifecycle != LifecycleState.ACTIVE:
        raise ApiError(409, "INVALID_STATE", f"session is {session.state.lifecycle}")
    if expected_version != session.state_version:
        details = {"expected": expected_version, "current": session.state_version}
        raise ApiError(409, "STATE_VERSION_CONFLICT", "the session changed, reload its state", details)
    current = (session.state.item or {}).get("item_attempt_id")
    if item_attempt_id is not None and item_attempt_id != current:
        raise ApiError(409, "STALE_ITEM", "this item is no longer the current one")

    router = tutor_router()
    if chapter_service.is_chapter(session):
        content: Any = _chapter(session.lesson_id, session.lesson_version)
        persona = content.package.persona
        # RAG-2: the child's questions are answered from the index of this moment (rebuilt when the
        # teacher's documents changed); without TUTOR_RENDERER=llm the answers are passages word for word.
        speaker = GroundedSpeaker(
            await _rag_service.current(database),
            router,
            tutor_self=persona.tutor_self,
            student_address=persona.student_address,
            student_name=session.student_display_name,
            calls_used=(session.state.activity or {}).get("llm_calls", 0),
            order=content.topological_order(),
            web=_web_source(),
        )
        # CTX-1: an unclear item message is read in context: by Qwen when it may be called, else by rule.
        calls = (session.state.activity or {}).get("llm_calls", 0)
        reader = LiveReader(ModelReader(router, calls_used=calls) if router is not None else None)
        command_fn: Any = partial(
            chapter_service.apply_command,
            history=await _history(database, session),
            speaker=speaker,
            reader=reader,
        )
    else:
        content, command_fn = _package(session.lesson_id), service.apply_command
    try:
        live = service.llm_renderer(session, router) if router is not None else None
        apply = partial(command_fn, content, session, command, utc_now(), live_renderer=live)
        step = await run_in_threadpool(apply, **kwargs)  # the model call blocks; keep the event loop free
    except service.CommandNotAllowed as exc:
        raise ApiError(409, "COMMAND_NOT_ALLOWED_IN_ACTIVITY", f"{exc} is not allowed now") from exc
    repo = _repo(database)
    try:
        saved = await repo.commit(
            session, state=step.state, events=step.events, idempotency_key=key, **step.fields
        )
    except DuplicateCommand as dup:
        return _ack_for_key(dup.session, key) or CommandAck(
            state_version=dup.session.state_version, tutor_turn_id=None
        )
    except StateVersionConflict as exc:
        details = {"expected": exc.expected, "current": exc.current}
        raise ApiError(
            409, "STATE_VERSION_CONFLICT", "the session changed, reload its state", details
        ) from exc
    if saved.state.lifecycle == LifecycleState.COMPLETED:
        # Copy for cross-session queries; idempotent, and the session document stays the source of truth.
        await repo.copy_events_to_ledger(saved.id, EventRepository(database, service.DEMO_SCHOOL_ID))
    return _ack_for_key(saved, key) or CommandAck(state_version=saved.state_version, tutor_turn_id=None)


@router.post("", status_code=201, response_model=SessionStateView)
async def create_session(body: CreateSession, database: Database, student: Student, name: AccountName):
    """Create a session (lifecycle READY). No data is created unless this endpoint is called.

    ``lesson_id`` names a chapter (teaching loop, the default) or a lesson (the fixed plan of lesson 1).
    With accounts (ACC-1) the student's name is the account's; a name sent by the web is ignored.
    """
    target = body.lesson_id or chapter_service.DEFAULT_CHAPTER_ID
    display_name = name or body.student_display_name
    chapter = chapter_service.chapters().get(target)
    if chapter is not None:
        session = chapter_service.new_session(chapter, service.DEMO_SCHOOL_ID, student, display_name)
    else:
        pkg = _package(target)
        session = service.new_session(pkg, service.DEMO_SCHOOL_ID, student, display_name)
    session = await _repo(database).create(session)
    return await _view(database, session)


@router.get("", response_model=list[SessionSummaryView])
async def list_sessions(database: Database, teacher: Teacher):
    """Teacher: the school's latest sessions, newest first."""
    return _summaries(await _repo(database).list_recent())


@router.get("/mine", response_model=list[SessionSummaryView])
async def my_sessions(database: Database, student: Student):
    """Student: this student's sessions, newest first ("Lịch sử học"). Each one opens with its whole
    conversation; an unfinished one can be continued."""
    sessions = await _repo(database).list_for_student(student)
    return list(reversed(_summaries(sessions)))


@router.get("/{session_id}/transcript", response_model=SessionTranscriptView)
async def get_transcript(session_id: str, database: Database, teacher: Teacher):
    """Teacher: the conversation with outcomes, misconceptions, rule ids and message sources."""
    session = await _repo(database).get(session_id)
    if session is None:
        raise ApiError(404, "NOT_FOUND", "session not found")
    if chapter_service.is_chapter(session):
        history = await _history(database, session)
        return chapter_service.teacher_transcript(
            _chapter(session.lesson_id, session.lesson_version), session, history
        )
    return service.teacher_transcript(_package(session.lesson_id), session)


@router.get("/{session_id}/report", response_model=TeachingReportView)
async def get_report(session_id: str, database: Database, teacher: Teacher):
    """Teacher: how the tutor scored and decided in a chapter session (nodes, evidence, rules)."""
    session = await _repo(database).get(session_id)
    if session is None or not chapter_service.is_chapter(session):
        raise ApiError(404, "NOT_FOUND", "no teaching report for this session")
    history = await _history(database, session)
    return chapter_service.report(_chapter(session.lesson_id, session.lesson_version), session, history)


@router.post("/{session_id}/join", response_model=SessionStateView)
async def join_session(session_id: str, database: Database, student: Student):
    """READY -> ACTIVE and show the first item. Joining again returns the current state."""
    session = await _load(database, session_id, student)
    if session.state.lifecycle == LifecycleState.READY:
        if chapter_service.is_chapter(session):
            history = await _history(database, session)
            step = chapter_service.join(
                _chapter(session.lesson_id, session.lesson_version), session, utc_now(), history
            )
        else:
            step = service.join(_package(session.lesson_id), session, utc_now())
        try:
            session = await _repo(database).commit(
                session, state=step.state, events=step.events, **step.fields
            )
        except StateVersionConflict:  # joined from another tab at the same moment
            session = await _load(database, session_id, student)
    return await _view(database, session)


@router.get("/{session_id}/state", response_model=SessionStateView)
async def get_state(session_id: str, database: Database, student: Student):
    session = await _load(database, session_id, student)
    return await _view(database, session)


@router.post("/{session_id}/responses", response_model=CommandAck)
async def submit_response(
    session_id: str,
    body: ResponseCommand,
    database: Database,
    student: Student,
    idempotency_key: IdempotencyKey = None,
):
    return await _command(
        database,
        session_id,
        student,
        idempotency_key,
        body.expected_state_version,
        "ANSWER",
        body.item_attempt_id,
        text=body.content.text,
        kind=body.kind,
        modality=body.modality,
    )


@router.post("/{session_id}/hint-requests", response_model=CommandAck)
async def request_hint(
    session_id: str,
    body: HintRequestCommand,
    database: Database,
    student: Student,
    idempotency_key: IdempotencyKey = None,
):
    return await _command(
        database,
        session_id,
        student,
        idempotency_key,
        body.expected_state_version,
        "HINT_REQUEST",
        body.item_attempt_id,
    )


@router.post("/{session_id}/choices", response_model=CommandAck)
async def make_choice(
    session_id: str,
    body: ChoiceCommand,
    database: Database,
    student: Student,
    idempotency_key: IdempotencyKey = None,
):
    return await _command(
        database,
        session_id,
        student,
        idempotency_key,
        body.expected_state_version,
        "CHOICE",
        choice_id=body.choice_id,
    )


def _chapter_overview(sessions: list[LearningSession], student_id: str, today: date) -> dict[str, Any]:
    chapter = _chapter(chapter_service.DEFAULT_CHAPTER_ID)
    own = [s for s in sessions if s.student_id == student_id]
    view = progress.overview(chapter, own, today)
    return {**view, "parent_code": progress.parent_code(student_id)}


@students.get("/me/overview", response_model=StudentOverviewView)
async def my_overview(database: Database, student: Student, today: Today):
    """Student: the chapter so far, across sessions: topics in words, streak, what to practise."""
    sessions = await _repo(database).list_for_student(student)
    return _chapter_overview(sessions, student, today)


@parents.get("/me/child", response_model=ParentChildView)
async def my_child(database: Database, child: LinkedChild, today: Today):
    """Parent account: the linked child's progress (ACC-1), with no code to type."""
    return await _child_view(database, child, today)


@parents.get("/children/{code}", response_model=ParentChildView)
async def child_overview(code: str, database: Database, parent: Parent, today: Today):
    """Parent: the child's progress in plain words, the trend over four weeks and how to help at home."""
    repo = _repo(database)
    wanted = code.strip().upper()
    student_id = next((s for s in await repo.student_ids() if progress.parent_code(s) == wanted), None)
    if student_id is None:
        raise ApiError(404, "NOT_FOUND", "no student has this code")
    return await _child_view(database, student_id, today)


async def _child_view(database: Any, student_id: str, today: date) -> dict[str, Any]:
    repo = _repo(database)
    chapter = _chapter(chapter_service.DEFAULT_CHAPTER_ID)
    own = await repo.list_for_student(student_id)
    view = _chapter_overview(own, student_id, today)
    practise = view["to_practise"] or [n for n in view["nodes"] if not n["passed"]][:1]
    return {
        **view,
        "trend": progress.trend(chapter, own, today),
        "home_tips": progress.home_tips(chapter, practise),
        "session_list": progress.sessions_list(chapter, own),
    }


def _teacher_chapter(chapter_id: str | None) -> Any:
    """The chapter a teacher's view is about (``?chapter=``), the default one when none is named."""
    chapter_id = chapter_id or chapter_service.DEFAULT_CHAPTER_ID
    if chapter_id not in chapter_service.chapters():
        raise ApiError(404, "NOT_FOUND", f"no chapter {chapter_id!r}")
    return _chapter(chapter_id)


@teachers.get("/taught-chapters", response_model=list[ChapterRef])
async def taught_chapters(teacher: Teacher):
    """Teacher: the chapters the tutor teaches now (built in or published from the teacher's documents)."""
    return [
        {"chapter_id": cid, "title": c.package.title} for cid, c in sorted(chapter_service.chapters().items())
    ]


@teachers.get("/class", response_model=ClassOverviewView)
async def class_view(database: Database, teacher: Teacher, today: Today, chapter: str | None = None):
    """Teacher: the class on the chapter, replayed from every student's sessions (rule 3)."""
    chapter = _teacher_chapter(chapter)
    enrolled = await _enrolled(database)
    by_student: dict[str, list[LearningSession]] = {}
    for session in await _repo(database).list_lesson(chapter.package.chapter_id):
        if enrolled is None or session.student_id in enrolled:
            by_student.setdefault(session.student_id, []).append(session)
    reviewed = await _reviews(database).reviewed([s.id for ss in by_student.values() for s in ss])
    return teacher_view.class_overview(chapter, by_student, today, reviewed)


async def _enrolled(database: Any) -> set[str] | None:
    """The students with an account (ACC-1); None in the demo mode, where every session counts.

    Sessions of the trials before the accounts carry random ids: they stay in the database, out of the
    teacher's views."""
    if demo_mode():
        return None
    users = await UserRepository(database, service.DEMO_SCHOOL_ID).list_by_kind("STUDENT")
    return {u.id for u in users}


@teachers.get("/students/{student_id}", response_model=TeacherStudentView)
async def teacher_student(
    student_id: str, database: Database, teacher: Teacher, today: Today, chapter: str | None = None
):
    """Teacher: one student on the chapter (``?chapter=``), with every KC in detail."""
    chapter = _teacher_chapter(chapter)
    enrolled = await _enrolled(database)
    if enrolled is not None and student_id not in enrolled:
        raise ApiError(404, "NOT_FOUND", "no student account has this id")
    sessions = await _repo(database).list_for_student(student_id)
    if not progress.chapter_sessions(chapter, sessions):
        raise ApiError(404, "NOT_FOUND", "this student has no session on the chapter")
    reviewed = await _reviews(database).reviewed([s.id for s in sessions])
    return teacher_view.student_detail(chapter, student_id, sessions, today, reviewed)


def _reviews(database: Any) -> SafetyReviewRepository:
    return SafetyReviewRepository(database, service.DEMO_SCHOOL_ID)


class MarkSafetyReviewed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)


class SafetyReviewView(BaseModel):
    session_id: str
    through_sequence_no: int
    reviewed_at: datetime
    reviewed_by: str


@teachers.post("/safety-reviews", response_model=SafetyReviewView)
async def mark_safety_reviewed(body: MarkSafetyReviewed, database: Database, teacher: Teacher):
    """Teacher: "cô đã xem" the worrying words of a session (SAFE-1). The server reads up to which event:
    the session's last flag now, so a later flag shows again. The ledger of the session is not touched."""
    session = await _repo(database).get(body.session_id)
    if session is None:
        raise ApiError(404, "NOT_FOUND", "session not found")
    flags = [e.sequence_no for e in session.events if e.event_type == EventType.SAFETY_FLAGGED]
    if not flags:
        raise ApiError(409, "INVALID_STATE", "this session has no safety flag")
    review = await _reviews(database).mark(session.id, session.student_id, max(flags), teacher, utc_now())
    return {
        "session_id": review.id,
        "through_sequence_no": review.through_sequence_no,
        "reviewed_at": review.reviewed_at,
        "reviewed_by": review.reviewed_by,
    }


# The school's Hybrid RAG index (RAG-1), rebuilt when the chapter content or the documents change.
_rag_service = RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters)


def register(app: FastAPI) -> None:
    """Mount the router and the error format ``{"error": {"code", "message", "details"}}``."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
        return _error(422, "VALIDATION_ERROR", "invalid request", {"fields": fields})

    @app.exception_handler(library_api.LibraryError)
    async def _library_error(_: Request, exc: library_api.LibraryError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(voice_api.VoiceError)
    async def _voice_error(_: Request, exc: voice_api.VoiceError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(AuthError)
    async def _auth_error(_: Request, exc: AuthError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(db.DatabaseNotConfiguredError)
    async def _no_database(_: Request, exc: db.DatabaseNotConfiguredError) -> JSONResponse:
        return _error(503, "INVALID_STATE", "database is not configured")

    app.include_router(register_auth(get_database, service.DEMO_SCHOOL_ID))
    app.include_router(
        library_api.build_router(
            get_database, teacher_identity, service.DEMO_SCHOOL_ID, chapter_service.chapter_sources
        )
    )
    app.include_router(rag_api.build_router(get_database, teacher_identity, lambda: _rag_service))
    app.include_router(ingest_api.build_router(get_database, teacher_identity, service.DEMO_SCHOOL_ID))
    app.include_router(voice_api.build_router(student_identity, lambda: _shared_router()))
    published = [Depends(published_chapters)]  # INGEST-4: the teacher's published plans
    app.include_router(router, dependencies=published)
    app.include_router(students, dependencies=published)
    app.include_router(parents, dependencies=published)
    app.include_router(teachers, dependencies=published)
