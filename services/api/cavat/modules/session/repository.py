"""Session module storage: learning sessions and the event ledger (blueprint PART 10.3, 16.4, D-T7).

Atlas M0 has no multi-document transaction, so one learning session is **one document** holding
the 3-tier state (lifecycle, activity, item) and the append-only array of its events. A command
changes state and appends its events in a single ``find_one_and_update`` conditioned on
``state_version`` (optimistic concurrency): if another writer got there first, nothing is written
and :class:`StateVersionConflict` is raised (the API answers 409).

Events are then copied, at least once and idempotently, into the ``events`` collection for queries
across sessions (by student, by time). The unique index ``(session_id, sequence_no)`` makes the
copy safe to repeat. The session document stays the source of truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from cavat.core.repository import (
    ASCENDING,
    DESCENDING,
    IndexSpec,
    NotFound,
    RepositoryError,
    TenantDocument,
    TenantScopedRepository,
    new_id,
    utc_now,
)

EVENT_SCHEMA_VERSION = 1


class LifecycleState(StrEnum):
    """Tier 1 of the session state machine (blueprint PART 16.2)."""

    SCHEDULED = "SCHEDULED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    INTERRUPTED = "INTERRUPTED"
    EXITED = "EXITED"
    WRAPPING_UP = "WRAPPING_UP"
    COMPLETED = "COMPLETED"
    INCOMPLETE = "INCOMPLETE"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


TERMINAL_STATES = frozenset(
    {
        LifecycleState.COMPLETED,
        LifecycleState.INCOMPLETE,
        LifecycleState.MISSED,
        LifecycleState.CANCELLED,
        LifecycleState.FAILED,
    }
)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True, validate_default=True)


class SessionState(_Model):
    """The 3 tiers. Tiers 2 and 3 are owned by the orchestrator (T04/T08) and stored as-is."""

    lifecycle: LifecycleState = LifecycleState.SCHEDULED
    activity: dict[str, Any] | None = None
    item: dict[str, Any] | None = None


class Actor(_Model):
    type: Literal["student", "tutor", "system", "teacher"]
    id: str | None = None


class SessionEvent(_Model):
    """Event envelope (blueprint PART 10.3)."""

    event_id: str
    event_type: str
    schema_version: int = EVENT_SCHEMA_VERSION
    occurred_at: datetime
    recorded_at: datetime
    school_id: str
    student_id: str
    session_id: str
    contract_id: str | None = None
    activity_id: str | None = None
    item_attempt_id: str | None = None
    sequence_no: int
    actor: Actor
    correlation: dict[str, str | None] = Field(default_factory=dict)
    idempotency_key: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NewEvent(_Model):
    """What a caller supplies for an event; the repository fills in ids, tenant, sequence and times."""

    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    actor: Actor = Field(default_factory=lambda: Actor(type="system"))
    activity_id: str | None = None
    item_attempt_id: str | None = None
    correlation: dict[str, str | None] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class LearningSession(TenantDocument):
    student_id: str
    student_display_name: str | None = None  # given name only (CLAUDE.md rule 8)
    lesson_id: str
    lesson_version: str
    kind: Literal["LESSON", "HOMEWORK", "REVIEW"] = "LESSON"
    schedule_id: str | None = None
    contract_id: str | None = None
    state: SessionState = Field(default_factory=SessionState)
    state_version: int = 0
    next_sequence_no: int = 1
    events: list[SessionEvent] = Field(default_factory=list)
    events_copied_upto: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    end_reason: str | None = None


class StateVersionConflict(RepositoryError):
    """The session changed since the caller read it (``expected_state_version`` is stale)."""

    def __init__(self, session_id: str, expected: int, current: int) -> None:
        super().__init__(f"session {session_id}: expected state_version {expected}, current {current}")
        self.session_id = session_id
        self.expected = expected
        self.current = current


class DuplicateCommand(RepositoryError):
    """A command with this idempotency key was already applied; nothing new was written."""

    def __init__(self, session: LearningSession, idempotency_key: str) -> None:
        super().__init__(f"session {session.id}: idempotency key {idempotency_key!r} already applied")
        self.session = session
        self.idempotency_key = idempotency_key


# Top-level fields a commit may set besides the state. Everything else is identity or bookkeeping.
MUTABLE_FIELDS = frozenset({"contract_id", "started_at", "ended_at", "end_reason"})


class LearningSessionRepository(TenantScopedRepository):
    collection_name = "learning_sessions"
    indexes = (
        IndexSpec(
            (("school_id", ASCENDING), ("student_id", ASCENDING), ("state.lifecycle", ASCENDING)),
            "student_lifecycle",
        ),
        IndexSpec((("school_id", ASCENDING), ("schedule_id", ASCENDING)), "schedule"),
        IndexSpec((("school_id", ASCENDING), ("updated_at", DESCENDING)), "school_recent"),
    )

    def _envelope(
        self,
        session: LearningSession,
        event: NewEvent,
        seq: int,
        key: str | None,
        now: datetime,
        contract_id: str | None,
    ) -> SessionEvent:
        return SessionEvent(
            event_id=new_id(),
            event_type=event.event_type,
            occurred_at=event.occurred_at or now,
            recorded_at=now,
            school_id=self.school_id,
            student_id=session.student_id,
            session_id=session.id,
            contract_id=contract_id,
            activity_id=event.activity_id,
            item_attempt_id=event.item_attempt_id,
            sequence_no=seq,
            actor=event.actor,
            correlation=event.correlation,
            idempotency_key=key,
            payload=event.payload,
        )

    async def create(self, session: LearningSession, events: Sequence[NewEvent] = ()) -> LearningSession:
        if session.state_version != 0 or session.events or session.next_sequence_no != 1:
            raise ValueError("a new session starts at state_version 0 with no events")
        now = utc_now()
        envelopes = [
            self._envelope(session, e, i + 1, None, now, session.contract_id) for i, e in enumerate(events)
        ]
        session = session.model_copy(update={"events": envelopes, "next_sequence_no": len(events) + 1})
        await self._insert(session.to_doc())
        return session

    async def get(self, session_id: str) -> LearningSession | None:
        doc = await self._find_one({"_id": session_id})
        return LearningSession.from_doc(doc) if doc else None

    async def list_recent(self, limit: int = 100) -> list[LearningSession]:
        """The school's latest sessions, newest first (the teacher's review list)."""
        docs = await self._find({}, sort=[("updated_at", DESCENDING)], limit=limit)
        return [LearningSession.from_doc(d) for d in docs]

    async def list_for_student(
        self, student_id: str, lifecycle: Sequence[LifecycleState] | None = None
    ) -> list[LearningSession]:
        flt: dict[str, Any] = {"student_id": student_id}
        if lifecycle is not None:
            flt["state.lifecycle"] = {"$in": [str(s) for s in lifecycle]}
        docs = await self._find(flt, sort=[("created_at", ASCENDING)])
        return [LearningSession.from_doc(d) for d in docs]

    async def commit(
        self,
        session: LearningSession,
        *,
        state: SessionState,
        events: Sequence[NewEvent] = (),
        idempotency_key: str | None = None,
        **fields: Any,
    ) -> LearningSession:
        """Atomically replace the state and append events if the session is still at its read version.

        ``session`` is the snapshot the caller decided from. Raises :class:`StateVersionConflict` when
        it is stale and :class:`DuplicateCommand` when ``idempotency_key`` was already applied.
        """
        unknown = set(fields) - MUTABLE_FIELDS
        if unknown:
            raise ValueError(f"fields cannot be changed by commit: {sorted(unknown)}")
        if idempotency_key is not None and not events:
            raise ValueError("an idempotent command must record at least one event")

        now = utc_now()
        contract_id = fields.get("contract_id", session.contract_id)
        envelopes = [
            self._envelope(session, e, session.next_sequence_no + i, idempotency_key, now, contract_id)
            for i, e in enumerate(events)
        ]
        flt: dict[str, Any] = {"_id": session.id, "state_version": session.state_version}
        if idempotency_key is not None:
            flt["events.idempotency_key"] = {"$ne": idempotency_key}
        update: dict[str, Any] = {
            "$set": {"state": state.model_dump(), "updated_at": now, **fields},
            "$inc": {"state_version": 1, "next_sequence_no": len(envelopes)},
        }
        if envelopes:
            update["$push"] = {"events": {"$each": [e.model_dump() for e in envelopes]}}

        doc = await self._find_one_and_update(flt, update)
        if doc is not None:
            return LearningSession.from_doc(doc)

        current = await self.get(session.id)
        if current is None:
            raise NotFound(f"session {session.id}")
        if idempotency_key is not None and any(e.idempotency_key == idempotency_key for e in current.events):
            raise DuplicateCommand(current, idempotency_key)
        raise StateVersionConflict(session.id, session.state_version, current.state_version)

    async def copy_events_to_ledger(self, session_id: str, ledger: EventRepository) -> int:
        """Copy events not yet copied into the ``events`` collection. Safe to repeat or run concurrently."""
        if ledger.school_id != self.school_id:
            raise ValueError("ledger must belong to the same school")
        session = await self.get(session_id)
        if session is None:
            raise NotFound(f"session {session_id}")
        pending = [e for e in session.events if e.sequence_no > session.events_copied_upto]
        if not pending:
            return 0
        inserted = await ledger.append_copies(pending)
        # $max, not $set: a slower concurrent copier must never move the marker backwards.
        # The marker is bookkeeping, not state, so it does not bump state_version.
        await self._update_one({"_id": session_id}, {"$max": {"events_copied_upto": pending[-1].sequence_no}})
        return inserted


class EventRepository(TenantScopedRepository):
    """Append-only copy of session events for cross-session queries. No update or delete methods."""

    collection_name = "events"
    indexes = (
        IndexSpec(
            (("session_id", ASCENDING), ("sequence_no", ASCENDING)), "session_sequence_unique", unique=True
        ),
        IndexSpec(
            (("school_id", ASCENDING), ("student_id", ASCENDING), ("occurred_at", ASCENDING)), "student_time"
        ),
        IndexSpec(
            (("school_id", ASCENDING), ("event_type", ASCENDING), ("occurred_at", ASCENDING)), "type_time"
        ),
    )

    async def append_copies(self, events: Sequence[SessionEvent]) -> int:
        docs: list[Mapping[str, Any]] = [{"_id": e.event_id, **e.model_dump()} for e in events]
        return await self._insert_many_ignoring_duplicates(docs)

    async def list_for_session(self, session_id: str, after_sequence_no: int = 0) -> list[SessionEvent]:
        docs = await self._find(
            {"session_id": session_id, "sequence_no": {"$gt": after_sequence_no}},
            sort=[("sequence_no", ASCENDING)],
            projection={"_id": 0},
        )
        return [SessionEvent.model_validate(d) for d in docs]

    async def list_for_student(self, student_id: str, since: datetime | None = None) -> list[SessionEvent]:
        flt: dict[str, Any] = {"student_id": student_id}
        if since is not None:
            flt["occurred_at"] = {"$gte": since}
        docs = await self._find(
            flt, sort=[("occurred_at", ASCENDING), ("sequence_no", ASCENDING)], projection={"_id": 0}
        )
        return [SessionEvent.model_validate(d) for d in docs]
