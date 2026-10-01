"""Runs one lesson session on top of the item loop (T08, blueprint PART 16.2 tiers 1-2, PART 24).

The session document is the only state (CLAUDE.md rule 10). The item loop keeps no state of its own
between requests: ``state.item`` stores the student inputs of the current item and every command
rebuilds the ``ItemTutor`` by replaying them. The loop is deterministic, so the replay always lands in
the same place, and a server restart loses nothing.

Minimal activity plan (same 8 items as the web mock): CONCEPT_CHECK -> GUIDED_PRACTICE ->
EXIT_ASSESSMENT -> SUMMARY. No LLM is called here; messages come from the template renderer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Literal

from cavat.config import REPO_ROOT
from cavat.core.events import ChoiceMade, EventType, HintRequested, SafetyFlagged, StudentMessage
from cavat.core.pedagogy import ActivityType
from cavat.core.repository import new_id
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.content.lesson_package import ChoiceAnswer, LessonPackage, load_lesson_package
from cavat.modules.session.repository import (
    Actor,
    LearningSession,
    LifecycleState,
    NewEvent,
    SessionState,
)
from cavat.modules.tutor.contracts import MessageRenderer
from cavat.modules.tutor.item_loop import ItemTutor, Phase, TutorEvent
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.prompt_builder import RECENT_TURNS, Turn
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

# Temporary (T12 adds real accounts): every demo session belongs to this school.
DEMO_SCHOOL_ID = "demo-school"

# DI: minimal plan for lesson 1, the same items as the web mock (apps/web/README.md).
DEMO_PLAN: tuple[tuple[str, ActivityType], ...] = (
    ("CC-01", ActivityType.CONCEPT_CHECK),
    ("CC-02", ActivityType.CONCEPT_CHECK),
    ("GP-01", ActivityType.GUIDED_PRACTICE),
    ("GP-02", ActivityType.GUIDED_PRACTICE),
    ("GP-08", ActivityType.GUIDED_PRACTICE),
    ("GP-09", ActivityType.GUIDED_PRACTICE),
    ("EX-01", ActivityType.EXIT_ASSESSMENT),
    ("EX-03", ActivityType.EXIT_ASSESSMENT),
)

# What the item loop reads when the student presses "gợi ý" (classified as HELP_REQUEST).
HINT_REQUEST_TEXT = "con cần gợi ý"

# Micro choices after OFFER_CHOICE (PART 24.3). DRAFT wording, to be approved by the teacher.
CHOICE_HINT = "HINT"
CHOICE_RETRY = "RETRY"
CHOICES: dict[str, str] = {CHOICE_HINT: "Cho con gợi ý", CHOICE_RETRY: "Con tự thử lại"}

# DRAFT wording. It never says which exit answers were right (assessment feedback is the teacher's).
SUMMARY_TEXT = "{T} và {s} đã học xong bài hôm nay. {S} đã rất cố gắng. Hẹn gặp lại {s} ở buổi sau nhé."

CommandType = Literal["ANSWER", "HINT_REQUEST", "CHOICE"]

_STUDENT_EVENTS = frozenset(
    {
        EventType.ANSWER_SUBMITTED,
        EventType.EXPLANATION_SUBMITTED,
        EventType.STUDENT_MESSAGE,
        EventType.HINT_REQUESTED,
        EventType.CHOICE_MADE,
    }
)
_TUTOR_EVENTS = frozenset({EventType.TUTOR_MESSAGE_SENT, EventType.HINT_DELIVERED})
_EXPLAINING = frozenset({Phase.VERIFYING, Phase.TEACH_BACK})


class CommandNotAllowed(Exception):
    """The command does not fit the current item phase (the API answers 409)."""


@lru_cache
def lesson_packages() -> dict[str, LessonPackage]:
    """Every lesson.yaml under docs/pedagogy, by lesson_id. Content is a versioned repo artifact."""
    found = sorted((REPO_ROOT / "docs" / "pedagogy").glob("**/lesson.yaml"))
    return {pkg.lesson_id: pkg for pkg in map(load_lesson_package, found)}


def plan_for(pkg: LessonPackage) -> list[list[str]]:
    known = {it.id for it in pkg.items}
    return [[item_id, str(activity)] for item_id, activity in DEMO_PLAN if item_id in known]


@dataclass(frozen=True)
class Step:
    """What one command changes: the new state, the events to append and the fields to set."""

    state: SessionState
    events: list[NewEvent]
    fields: dict[str, Any]


def new_session(
    pkg: LessonPackage, school_id: str, student_id: str, display_name: str | None
) -> LearningSession:
    plan = plan_for(pkg)
    if not plan:
        raise ValueError(f"lesson {pkg.lesson_id} has no item of the demo plan")
    state = SessionState(lifecycle=LifecycleState.READY, activity={"plan": plan, "index": 0})
    return LearningSession(
        school_id=school_id,
        student_id=student_id,
        student_display_name=display_name,
        lesson_id=pkg.lesson_id,
        lesson_version=pkg.version,
        state=state,
    )


def _actor(event_type: EventType, student_id: str) -> Actor:
    if event_type in _STUDENT_EVENTS:
        return Actor(type="student", id=student_id)
    return Actor(type="tutor" if event_type in _TUTOR_EVENTS else "system")


def _event(
    event_type: EventType,
    payload: dict[str, Any],
    session: LearningSession,
    attempt_id: str | None,
    activity_id: str | None,
    state_version: int | None = None,
) -> NewEvent:
    correlation = {"state_version": str(state_version)} if state_version is not None else {}
    return NewEvent(
        event_type=event_type.value,
        payload=payload,
        actor=_actor(event_type, session.student_id),
        activity_id=activity_id,
        item_attempt_id=attempt_id,
        correlation=correlation,
    )


def _loop_events(events: tuple[TutorEvent, ...], session: LearningSession, item: dict[str, Any]):
    return [_event(e.type, e.payload, session, item["item_attempt_id"], item["activity_id"]) for e in events]


def _new_tutor(pkg: LessonPackage, item_id: str, activity: str) -> ItemTutor:
    return ItemTutor(pkg.item(item_id), pkg, ActivityType(activity), TemplateRenderer(), validate_message)


def rebuild_tutor(pkg: LessonPackage, item: dict[str, Any]) -> ItemTutor:
    """The item loop exactly where the student left it (deterministic replay of the stored inputs)."""
    tutor = _new_tutor(pkg, item["item_id"], item["activity"])
    tutor.start()
    for inp in item["inputs"]:
        tutor.on_student(inp["text"], inp["seconds"])
    return tutor


def item_history(session: LearningSession) -> list[Turn]:
    """The latest turns of the current item, read from the event log (survives a restart)."""
    attempt = (session.state.item or {}).get("item_attempt_id")
    turns: list[Turn] = []
    for e in session.events:
        if e.item_attempt_id != attempt:
            continue
        if e.event_type == EventType.STUDENT_MESSAGE:
            turns.append(Turn("student", e.payload["text"]))
        elif e.event_type == EventType.HINT_REQUESTED:
            turns.append(Turn("student", CHOICES[CHOICE_HINT]))
        elif e.event_type == EventType.TUTOR_MESSAGE_SENT:
            turns.append(Turn("tutor", e.payload["text"]))
    return turns[-RECENT_TURNS:]


def llm_renderer(session: LearningSession, router: AIRouter) -> LLMRenderer:
    """Renderer for the live turn of this session: Qwen phrases the move, templates are the fallback.

    The number of LLM calls already made is kept in the session document, so the per-session cap holds
    across requests.
    """
    return LLMRenderer(
        router,
        TemplateRenderer(),
        validate_message,
        student_name=session.student_display_name,
        calls_used=(session.state.activity or {}).get("llm_calls", 0),
        history=item_history(session),
        history_item=(session.state.item or {}).get("item_id"),
    )


def _activity(plan: list[list[str]], index: int, llm_calls: int) -> dict[str, Any]:
    return {"plan": plan, "index": index, "llm_calls": llm_calls}


def _activity_id(index: int, activity: str) -> str:
    return f"{index + 1:02d}-{activity}"


def _open_item(
    pkg: LessonPackage, session: LearningSession, plan: list[list[str]], index: int
) -> tuple[dict[str, Any], list[NewEvent]]:
    """Start plan[index]; emit ACTIVITY_STARTED when the activity type changes."""
    item_id, activity = plan[index]
    first = index == 0 or plan[index - 1][1] != activity
    start = next(i for i in range(index, -1, -1) if i == 0 or plan[i - 1][1] != activity)
    item = {
        "item_attempt_id": new_id(),
        "item_id": item_id,
        "activity": activity,
        "activity_id": _activity_id(start, activity),
        "position": index + 1,
        "inputs": [],
        "phase": Phase.AWAITING.value,
        "choice_open": False,
    }
    events: list[NewEvent] = []
    if first:
        events.append(
            _event(
                EventType.ACTIVITY_STARTED, {"activity_type": activity}, session, None, item["activity_id"]
            )
        )
    turn = _new_tutor(pkg, item_id, activity).start()
    item["phase"] = turn.phase.value
    return item, events + _loop_events(turn.events, session, item)


def join(pkg: LessonPackage, session: LearningSession, now: datetime) -> Step:
    """READY -> ACTIVE: open the first item."""
    plan = session.state.activity["plan"]
    item, events = _open_item(pkg, session, plan, 0)
    started = _event(EventType.SESSION_STARTED, {"lesson_id": session.lesson_id}, session, None, None)
    state = SessionState(lifecycle=LifecycleState.ACTIVE, activity={"plan": plan, "index": 0}, item=item)
    return Step(state, [started, *events], {"started_at": now})


def allowed_commands(session: LearningSession) -> list[CommandType]:
    item = session.state.item
    if session.state.lifecycle != LifecycleState.ACTIVE or item is None:
        return []
    if item["choice_open"]:
        return ["ANSWER", "CHOICE"]
    if Phase(item["phase"]) in _EXPLAINING:
        return ["ANSWER"]
    return ["ANSWER", "HINT_REQUEST"]


def _persona(pkg: LessonPackage, template: str) -> str:
    t, s = pkg.persona.tutor_self, pkg.persona.student_address
    return template.format(T=t[:1].upper() + t[1:], t=t, S=s[:1].upper() + s[1:], s=s)


def apply_command(
    pkg: LessonPackage,
    session: LearningSession,
    command: CommandType,
    now: datetime,
    *,
    text: str = "",
    kind: str = "ANSWER",
    modality: str = "TEXT",
    choice_id: str | None = None,
    live_renderer: MessageRenderer | None = None,
) -> Step:
    """One student command on the current item. Raises ``CommandNotAllowed`` when it does not fit."""
    if command not in allowed_commands(session):
        raise CommandNotAllowed(command)
    item = dict(session.state.item or {})
    plan: list[list[str]] = session.state.activity["plan"]
    index: int = session.state.activity["index"]
    llm_calls: int = session.state.activity.get("llm_calls", 0)
    seconds = max((now - session.updated_at).total_seconds(), 0.0)
    item_id, attempt_id, activity_id = item["item_id"], item["item_attempt_id"], item["activity_id"]
    version_after = session.state_version + 1

    def student_event(event_type: EventType, payload) -> NewEvent:
        return _event(
            event_type, payload.model_dump(mode="json"), session, attempt_id, activity_id, version_after
        )

    if command == "CHOICE":
        if choice_id not in CHOICES:
            raise CommandNotAllowed(f"unknown choice {choice_id!r}")
        made = ChoiceMade(item_id=item_id, choice_id=choice_id, label=CHOICES[choice_id])
        events = [student_event(EventType.CHOICE_MADE, made)]
        if choice_id == CHOICE_RETRY:
            # The loop already treats the next message as a normal attempt; only the buttons go away.
            item["choice_open"] = False
            activity = _activity(plan, index, llm_calls)
            return Step(
                SessionState(lifecycle=LifecycleState.ACTIVE, activity=activity, item=item), events, {}
            )
        loop_text = HINT_REQUEST_TEXT
    elif command == "HINT_REQUEST":
        events = [student_event(EventType.HINT_REQUESTED, HintRequested(item_id=item_id, seconds=seconds))]
        loop_text = HINT_REQUEST_TEXT
    else:
        message = StudentMessage(item_id=item_id, kind=kind, text=text, modality=modality, seconds=seconds)
        events = [student_event(EventType.STUDENT_MESSAGE, message)]
        loop_text = text

    tutor = rebuild_tutor(pkg, item)  # the replay uses templates: past turns never call the model again
    if live_renderer is not None:
        tutor.renderer = live_renderer
    turn = tutor.on_student(loop_text, seconds)
    events += _loop_events(turn.events, session, item)
    llm_calls = getattr(live_renderer, "calls_used", llm_calls)
    trace = getattr(live_renderer, "last_trace", None)
    if trace is not None and trace.safety_flag:
        flagged = SafetyFlagged(item_id=item_id).model_dump(mode="json")
        events.append(_event(EventType.SAFETY_FLAGGED, flagged, session, attempt_id, activity_id))
    item["inputs"] = [*item["inputs"], {"text": loop_text, "seconds": seconds}]
    item["phase"] = turn.phase.value
    item["choice_open"] = turn.phase == Phase.AWAITING_CHOICE

    if not turn.resolved:
        activity = _activity(plan, index, llm_calls)
        return Step(SessionState(lifecycle=LifecycleState.ACTIVE, activity=activity, item=item), events, {})

    index += 1
    last_of_activity = index == len(plan) or plan[index][1] != item["activity"]
    if last_of_activity:
        done = {"activity_type": item["activity"]}
        events.append(_event(EventType.ACTIVITY_COMPLETED, done, session, None, activity_id))
    if index < len(plan):
        next_item, opened = _open_item(pkg, session, plan, index)
        activity = _activity(plan, index, llm_calls)
        state = SessionState(lifecycle=LifecycleState.ACTIVE, activity=activity, item=next_item)
        return Step(state, events + opened, {})

    summary = {"summary_text": _persona(pkg, SUMMARY_TEXT), "items_done": len(plan)}
    summary_id = _activity_id(len(plan), ActivityType.SUMMARY.value)
    events.append(_event(EventType.SESSION_COMPLETED, summary, session, None, summary_id))
    state = SessionState(lifecycle=LifecycleState.COMPLETED, activity=_activity(plan, index, llm_calls))
    return Step(state, events, {"ended_at": now, "end_reason": "COMPLETED"})


# --------------------------------------------------------------------------- student view


def transcript(session: LearningSession) -> list[dict[str, Any]]:
    """Chat turns for the student screen: what was said, never rule ids, outcomes or answers."""
    turns: list[dict[str, Any]] = []
    hint_level: int | None = None
    for e in session.events:
        p = e.payload
        text: str | None = None
        move: str | None = None
        level: int | None = None
        actor = e.actor.type
        if e.event_type == EventType.POLICY_DECISION:
            hint_level = p.get("hint_level")
        elif e.event_type == EventType.TUTOR_MESSAGE_SENT:
            text, move, level = p["text"], p["move"], hint_level
        elif e.event_type == EventType.SESSION_COMPLETED:
            text, actor = p.get("summary_text"), "tutor"  # the tutor says the summary
        elif e.event_type == EventType.STUDENT_MESSAGE:
            text = p["text"]
        elif e.event_type == EventType.HINT_REQUESTED:
            text = CHOICES[CHOICE_HINT]
        elif e.event_type == EventType.CHOICE_MADE:
            text = p["label"]
        if text is None:
            continue
        turns.append(
            {
                "turn_id": e.event_id,
                "sequence_no": e.sequence_no,
                "item_attempt_id": e.item_attempt_id,
                "actor": actor,
                "text": text,
                "occurred_at": e.occurred_at,
                "move": move,
                "hint_level": level,
            }
        )
    return turns


def student_view(pkg: LessonPackage, session: LearningSession) -> dict[str, Any]:
    """``SessionState`` of the web contract (apps/web/src/api/contract.ts). Options carry no correctness."""
    st = session.state
    plan = (st.activity or {}).get("plan", [])
    index = (st.activity or {}).get("index", 0)
    item_view = None
    activity_view = None
    if st.item is not None:
        it = pkg.item(st.item["item_id"])
        ans = it.answer
        options = [{"id": o.id, "text": o.text} for o in ans.options] if isinstance(ans, ChoiceAnswer) else []
        item_view = {
            "item_attempt_id": st.item["item_attempt_id"],
            "item_id": it.id,
            "stem": it.stem,
            "answer_format": ans.type,
            "options": options,
            "expecting": "EXPLANATION" if Phase(st.item["phase"]) in _EXPLAINING else "ANSWER",
            "position": st.item["position"],
        }
        activity_view = {"activity_id": st.item["activity_id"], "type": st.item["activity"]}
    elif st.lifecycle == LifecycleState.COMPLETED:
        summary = ActivityType.SUMMARY.value
        activity_view = {"activity_id": _activity_id(len(plan), summary), "type": summary}
    choice_open = bool(st.item and st.item["choice_open"])
    return {
        "session_id": session.id,
        "state_version": session.state_version,
        "lifecycle_state": st.lifecycle,
        "lesson": {"lesson_id": pkg.lesson_id, "title": pkg.title},
        "student_display_name": session.student_display_name or "",
        "persona": {"tutor_self": pkg.persona.tutor_self, "student_address": pkg.persona.student_address},
        "activity": activity_view,
        "item": item_view,
        "pending_choice": [{"choice_id": k, "label": v} for k, v in CHOICES.items()] if choice_open else None,
        "allowed_commands": allowed_commands(session),
        "progress": {"items_done": min(index, len(plan)), "items_total": len(plan)},
        "transcript": transcript(session),
    }
