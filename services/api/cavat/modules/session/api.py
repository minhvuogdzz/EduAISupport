"""Session API for one lesson (T08, blueprint PART 24 and 29). Shapes follow apps/web/src/api/contract.ts.

Not implemented yet: ``GET /v1/sessions/{id}/stream`` (SSE); the web polls ``/state`` after each command.

**Temporary auth:** the student is whoever the ``X-Demo-Student`` header names and every session belongs
to ``DEMO_SCHOOL_ID``. T12 replaces this with real accounts; nothing else may rely on the header.

The backend enforces every session rule (CLAUDE.md rule 4): owner, lifecycle, current item, allowed
commands, ``expected_state_version`` and ``Idempotency-Key``. The key is checked first, so a resent
command gets its first answer back instead of a 409.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from cavat import db
from cavat.core.events import EventType
from cavat.core.repository import utc_now
from cavat.modules.content.lesson_package import LessonPackage
from cavat.modules.session import service
from cavat.modules.session.repository import (
    DuplicateCommand,
    EventRepository,
    LearningSession,
    LearningSessionRepository,
    LifecycleState,
    StateVersionConflict,
)

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


class CommandAck(BaseModel):
    accepted: Literal[True] = True
    state_version: int
    tutor_turn_id: str | None


def get_database() -> Any:
    """The application database. Tests override this dependency with an in-memory database."""
    return db.get_db()


def demo_student(x_demo_student: Annotated[str | None, Header()] = None) -> str:
    """Temporary identity (see module docstring)."""
    if not x_demo_student or len(x_demo_student) > 64 or not x_demo_student.replace("-", "").isalnum():
        raise ApiError(401, "NOT_SESSION_OWNER", "X-Demo-Student header is required")
    return x_demo_student


Database = Annotated[Any, Depends(get_database)]
Student = Annotated[str, Depends(demo_student)]
IdempotencyKey = Annotated[str | None, Header(max_length=100)]

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


def _repo(database: Any) -> LearningSessionRepository:
    return LearningSessionRepository(database, service.DEMO_SCHOOL_ID)


def _package(lesson_id: str) -> LessonPackage:
    pkg = service.lesson_packages().get(lesson_id)
    if pkg is None:
        raise ApiError(404, "NOT_FOUND", f"lesson {lesson_id!r} not found")
    return pkg


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
    tutor = [e.event_id for e in events if e.event_type == EventType.TUTOR_MESSAGE_SENT]
    return CommandAck(
        state_version=int(version) if version is not None else session.state_version,
        tutor_turn_id=tutor[-1] if tutor else None,
    )


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

    pkg = _package(session.lesson_id)
    try:
        step = service.apply_command(pkg, session, command, utc_now(), **kwargs)
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
async def create_session(body: CreateSession, database: Database, student: Student):
    """Create a demo session (lifecycle READY). No data is created unless this endpoint is called."""
    packages = service.lesson_packages()
    lesson_id = body.lesson_id or next(iter(packages), "")
    pkg = _package(lesson_id)
    session = service.new_session(pkg, service.DEMO_SCHOOL_ID, student, body.student_display_name)
    session = await _repo(database).create(session)
    return service.student_view(pkg, session)


@router.post("/{session_id}/join", response_model=SessionStateView)
async def join_session(session_id: str, database: Database, student: Student):
    """READY -> ACTIVE and show the first item. Joining again returns the current state."""
    session = await _load(database, session_id, student)
    pkg = _package(session.lesson_id)
    if session.state.lifecycle == LifecycleState.READY:
        step = service.join(pkg, session, utc_now())
        try:
            session = await _repo(database).commit(
                session, state=step.state, events=step.events, **step.fields
            )
        except StateVersionConflict:  # joined from another tab at the same moment
            session = await _load(database, session_id, student)
    return service.student_view(pkg, session)


@router.get("/{session_id}/state", response_model=SessionStateView)
async def get_state(session_id: str, database: Database, student: Student):
    session = await _load(database, session_id, student)
    return service.student_view(_package(session.lesson_id), session)


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


def register(app: FastAPI) -> None:
    """Mount the router and the error format ``{"error": {"code", "message", "details"}}``."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(str(p) for p in e["loc"]) for e in exc.errors()]
        return _error(422, "VALIDATION_ERROR", "invalid request", {"fields": fields})

    @app.exception_handler(db.DatabaseNotConfiguredError)
    async def _no_database(_: Request, exc: db.DatabaseNotConfiguredError) -> JSONResponse:
        return _error(503, "INVALID_STATE", "database is not configured")

    app.include_router(router)
