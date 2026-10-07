"""Chapter sessions (M1-7): the teaching loop of plan v1 behind the session API.

A chapter session is a ``LearningSession`` whose ``lesson_id`` is a chapter id and whose
``state.activity["mode"]`` is ``"CHAPTER"``. Every command rebuilds the teaching loop from the
session's own events (``TeachingLoop.resume``, templates only), applies the student's input, and returns
the new events and state, so a session stays one document written atomically (rule 10).

The student's view (node map, step of the teaching cycle, what to answer) and the teacher's report
(scores per node with the evidence behind them, the policy's decisions) are folds of the same events.

**History.** Every function takes ``history``: the events of the student's earlier sessions of the same
chapter, oldest first (the API reads them from the student's session documents). The scores are folded
over history then this session, so a new session continues where the student stopped: nodes passed
stay passed, the next node starts from its prerequisites' scores (DI-16), and its prerequisites get a
warm-up item (N-WARMUP). The teaching state (what was taught, asked, decided) is this session's own.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from cavat.config import REPO_ROOT
from cavat.core.events import EventType, NodeDecisionMade, SafetyFlagged
from cavat.core.pedagogy import ITEM_ACTIONS, ActivityType, TeachAction
from cavat.core.repository import new_id
from cavat.modules.assessment.projector import (
    MASTERY_POLICY_VERSION,
    ChapterProjection,
    project_chapter,
)
from cavat.modules.content.chapter_package import Chapter, load_chapter
from cavat.modules.content.lesson_package import ChoiceAnswer
from cavat.modules.session.repository import LearningSession, LifecycleState, NewEvent, SessionState
from cavat.modules.session.service import (
    _EXPECTS_WORDS,
    _EXPLAINING,
    CHOICES,
    CommandNotAllowed,
    CommandType,
    Step,
    build_teacher_transcript,
    transcript,
)
from cavat.modules.session.service import (
    _actor as actor_for,
)
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import (
    ACTIVITY_FOR,
    TEMPLATES_VERSION,
    Awaiting,
    LoopEvent,
    TeachingLoop,
    TeachTurn,
)
from cavat.modules.teaching.state import NODE_POLICY_VERSION, TeachingState, teaching_state
from cavat.modules.tutor.contracts import MessageRenderer
from cavat.modules.tutor.item_loop import Phase

MODE = "CHAPTER"
DEFAULT_CHAPTER_ID = "math-g5-decimals"

# Step of the teaching cycle (plan v1, 5.2) that each decision carries out.
STEP_OF: dict[TeachAction, int] = {
    TeachAction.WARMUP_ITEM: 1,
    TeachAction.TEACH_THEORY: 2,
    TeachAction.CHECK_ITEM: 3,
    TeachAction.ASK_RETELL: 3,
    TeachAction.SHOW_WORKED_EXAMPLE: 4,
    TeachAction.COMPLETION_ITEM: 4,
    TeachAction.PRACTICE_ITEM: 5,
    TeachAction.TRANSFER_ITEM: 6,
    TeachAction.REVIEW_ITEM: 7,
    TeachAction.PASS_NODE: 7,
    TeachAction.STOP_NODE: 7,
}

# Events of the item loop: they carry the attempt id of the item they belong to.
_ITEM_EVENTS = frozenset(
    {
        EventType.QUESTION_SHOWN,
        EventType.ANSWER_SUBMITTED,
        EventType.EXPLANATION_SUBMITTED,
        EventType.POLICY_DECISION,
        EventType.HINT_DELIVERED,
        EventType.MISCONCEPTION_DETECTED,
        EventType.TUTOR_MESSAGE_SENT,
        EventType.OUTPUT_REJECTED,
        EventType.ITEM_RESOLVED,
        EventType.STUDENT_MESSAGE,
        EventType.HINT_REQUESTED,
        EventType.CHOICE_MADE,
    }
)


@lru_cache
def chapter_sources() -> dict[str, tuple[Chapter, Path]]:
    """Every chapter.yaml under docs/pedagogy, by chapter_id, with its file. Content is a versioned repo
    artifact; the teacher reads it on the web (DOC-1)."""
    found = sorted((REPO_ROOT / "docs" / "pedagogy").glob("**/chapter.yaml"))
    return {chapter.package.chapter_id: (chapter, path) for path in found for chapter in [load_chapter(path)]}


def chapters() -> dict[str, Chapter]:
    return {cid: chapter for cid, (chapter, _) in chapter_sources().items()}


def is_chapter(session: LearningSession) -> bool:
    return (session.state.activity or {}).get("mode") == MODE


def new_session(
    chapter: Chapter, school_id: str, student_id: str, display_name: str | None
) -> LearningSession:
    pkg = chapter.package
    state = SessionState(
        lifecycle=LifecycleState.READY, activity={"mode": MODE, "chapter_id": pkg.chapter_id}
    )
    return LearningSession(
        school_id=school_id,
        student_id=student_id,
        student_display_name=display_name,
        lesson_id=pkg.chapter_id,
        lesson_version=pkg.version,
        state=state,
    )


def join(chapter: Chapter, session: LearningSession, now: datetime, history: Sequence[Any] = ()) -> Step:
    """READY -> ACTIVE: the teaching loop starts on the first node the student has not passed yet."""
    loop = TeachingLoop(chapter, session.id, history)
    turn = loop.start(now)
    started = NewEvent(
        event_type=EventType.SESSION_STARTED.value,
        payload={"lesson_id": session.lesson_id},
        actor=actor_for(EventType.SESSION_STARTED, session.student_id),
    )
    events, attempt, node_id = _convert(session, turn.events, None, None)
    state = _state_after(chapter, loop, turn, attempt, node_id, llm_calls=0)
    return Step(state, [started, *events], {"started_at": now})


def allowed_commands(session: LearningSession) -> list[CommandType]:
    st = session.state
    if st.lifecycle != LifecycleState.ACTIVE:
        return []
    awaiting = (st.activity or {}).get("awaiting")
    if awaiting in (Awaiting.THEORY_REPLY, Awaiting.RETELL):
        return ["ANSWER"]
    item = st.item or {}
    if awaiting != Awaiting.ANSWER or not item.get("item_id"):
        return []
    if item.get("choice_open"):
        return ["ANSWER", "CHOICE"]
    if Phase(item["phase"]) in _EXPLAINING:
        return ["ANSWER"]
    return ["ANSWER", "HINT_REQUEST"]


def apply_command(
    chapter: Chapter,
    session: LearningSession,
    command: CommandType,
    now: datetime,
    *,
    text: str = "",
    kind: str = "ANSWER",  # noqa: ARG001 - the loop knows what it asked for
    modality: str = "TEXT",  # noqa: ARG001 - text only in the demo (D-T9)
    choice_id: str | None = None,
    live_renderer: MessageRenderer | None = None,
    speaker: GroundedSpeaker | None = None,
    history: Sequence[Any] = (),
) -> Step:
    """One student command. Raises ``CommandNotAllowed`` when it does not fit what the loop waits for.

    ``live_renderer`` and ``speaker`` serve this turn only (the replay above them uses templates): the item
    renderer phrases item moves, the speaker answers the child's questions from the RAG (RAG-2).
    """
    if command not in allowed_commands(session):
        raise CommandNotAllowed(command)
    if command == "CHOICE" and choice_id not in CHOICES:
        raise CommandNotAllowed(f"unknown choice {choice_id!r}")
    act = session.state.activity or {}
    loop = TeachingLoop.resume(chapter, session.id, history, session.events)
    if live_renderer is not None:  # the replay above used templates; only this turn may call the model
        loop.item_renderer = live_renderer
        if loop.tutor is not None:
            loop.tutor.renderer = live_renderer
    loop.speaker = speaker
    seconds = max((now - session.updated_at).total_seconds(), 0.0)
    if command == "CHOICE":
        assert choice_id is not None
        turn = loop.on_choice(choice_id, now, seconds)
    elif command == "HINT_REQUEST":
        turn = loop.on_hint_request(now, seconds)
    else:
        turn = loop.on_student(text, now, seconds)

    events, attempt, node_id = _convert(session, turn.events, session.state.item, act.get("node_id"))
    if events:  # lets the API answer a repeated Idempotency-Key with the version this command made
        events[0].correlation["state_version"] = str(session.state_version + 1)
    trace = getattr(live_renderer, "last_trace", None)
    if trace is not None and trace.safety_flag and turn.item_id:
        flagged = SafetyFlagged(item_id=turn.item_id).model_dump(mode="json")
        events.append(
            NewEvent(event_type=EventType.SAFETY_FLAGGED.value, payload=flagged, item_attempt_id=attempt)
        )
    llm_calls = getattr(live_renderer, "calls_used", act.get("llm_calls", 0))
    llm_calls += speaker.calls_made if speaker is not None else 0
    state = _state_after(chapter, loop, turn, attempt, node_id, llm_calls)
    if turn.awaiting == Awaiting.NOTHING:
        events.append(NewEvent(event_type=EventType.SESSION_COMPLETED.value, payload={}))
        return Step(state, events, {"ended_at": now, "end_reason": "COMPLETED"})
    return Step(state, events, {})


# --------------------------------------------------------------------------- events and state


def _convert(
    session: LearningSession,
    loop_events: Sequence[LoopEvent],
    open_item: dict[str, Any] | None,
    node_id: str | None,
) -> tuple[list[NewEvent], str | None, str | None]:
    """Loop events as session events. The item loop's events carry the attempt id of their item."""
    attempt = open_item["item_attempt_id"] if open_item and open_item.get("item_id") else None
    out: list[NewEvent] = []
    for e in loop_events:
        kind = EventType(e.event_type)
        if kind == EventType.NODE_DECISION:
            decision = NodeDecisionMade.model_validate(e.payload)
            node_id = decision.node_id or node_id
            attempt = new_id() if decision.action in ITEM_ACTIONS else None
        teaching_reply = kind == EventType.STUDENT_MESSAGE and ":" in e.payload.get("item_id", "")
        tag = attempt if kind in _ITEM_EVENTS and not teaching_reply else None
        out.append(
            NewEvent(
                event_type=e.event_type,
                payload=e.payload,
                actor=actor_for(kind, session.student_id),
                activity_id=node_id,
                item_attempt_id=tag,
                occurred_at=e.occurred_at,
            )
        )
        if kind == EventType.ITEM_RESOLVED:
            attempt = None
    return out, attempt, node_id


def _state_after(
    chapter: Chapter,
    loop: TeachingLoop,
    turn: TeachTurn,
    attempt: str | None,
    node_id: str | None,
    llm_calls: int,
) -> SessionState:
    decisions = [e for e in loop.events if e.event_type == EventType.NODE_DECISION]
    last = NodeDecisionMade.model_validate(decisions[-1].payload)
    step = STEP_OF.get(last.action)
    activity = {
        "mode": MODE,
        "chapter_id": chapter.package.chapter_id,
        "awaiting": turn.awaiting.value,
        "node_id": turn.node_id or node_id,
        "step": step,
        "prompt": turn.prompt,
        "llm_calls": llm_calls,
    }
    if turn.awaiting == Awaiting.NOTHING:
        return SessionState(lifecycle=LifecycleState.COMPLETED, activity=activity)
    if turn.awaiting == Awaiting.ANSWER:
        asked = sum(1 for e in decisions if e.payload["action"] in ITEM_ACTIONS)
        assert turn.item_phase is not None and attempt is not None
        item = {
            "item_attempt_id": attempt,
            "item_id": turn.item_id,
            "activity": ACTIVITY_FOR[last.action].value,
            "activity_id": f"{activity['node_id']}:{step}",
            "position": asked,
            "phase": turn.item_phase.value,
            "choice_open": turn.choice_open,
        }
    else:  # a theory question or a retell: the student answers in words, no item is open
        activity_type = (
            ActivityType.TEACH if turn.awaiting == Awaiting.THEORY_REPLY else ActivityType.CONCEPT_CHECK
        )
        item = {
            "item_attempt_id": new_id(),
            "item_id": None,
            "activity": activity_type.value,
            "activity_id": f"{activity['node_id']}:{step}",
            "position": None,
            "phase": None,
            "choice_open": False,
        }
    return SessionState(lifecycle=LifecycleState.ACTIVE, activity=activity, item=item)


# --------------------------------------------------------------------------- student view


def node_statuses(chapter: Chapter, projection: ChapterProjection, state: TeachingState) -> dict[str, str]:
    """PASSED, CURRENT, ON_HOLD (waits for a prerequisite), STOPPED ("cần học lại"), AVAILABLE, LOCKED."""
    current = state.current.node_id if state.current else None
    out: dict[str, str] = {}
    for node_id in chapter.topological_order():
        passed = projection.nodes[node_id].passed_at is not None
        if node_id == current:
            out[node_id] = "CURRENT"
        elif node_id in state.waiting:
            out[node_id] = "ON_HOLD"
        elif passed:
            out[node_id] = "PASSED"
        elif node_id in state.stopped:
            out[node_id] = "STOPPED"
        elif all(projection.nodes[p].passed_at is not None for p in chapter.prerequisites(node_id)):
            out[node_id] = "AVAILABLE"
        else:
            out[node_id] = "LOCKED"
    return out


def _relations(chapter: Chapter) -> list[dict[str, str]]:
    return [{"source": r.source, "target": r.target, "type": r.type} for r in chapter.package.relations]


def student_view(chapter: Chapter, session: LearningSession, history: Sequence[Any] = ()) -> dict[str, Any]:
    """``SessionState`` of the web contract, with ``teaching``: the node map and the step of the cycle.

    The student sees the level of each node (0-5, in words on screen), never the scores behind it.
    """
    st, pkg = session.state, chapter.package
    act, item = st.activity or {}, st.item or {}
    projection = project_chapter([*history, *session.events], chapter)
    state = teaching_state(session.events)
    statuses = node_statuses(chapter, projection, state)
    order = chapter.topological_order()
    nodes = [
        {
            "node_id": node_id,
            "name": chapter.node(node_id).name,
            "layer": chapter.node(node_id).layer,
            "status": statuses[node_id],
            "level": projection.nodes[node_id].level
            if projection.nodes[node_id].mastery is not None
            else None,
            "order": i,
        }
        for i, node_id in enumerate(order)
    ]
    passed = sum(1 for node_id in order if projection.nodes[node_id].passed_at is not None)

    item_view = None
    if item.get("item_id"):
        it = chapter.item(item["item_id"])
        ans = it.answer
        options = [{"id": o.id, "text": o.text} for o in ans.options] if isinstance(ans, ChoiceAnswer) else []
        item_view = {
            "item_attempt_id": item["item_attempt_id"],
            "item_id": it.id,
            "stem": it.stem,
            "answer_format": ans.type,
            "options": options,
            "expecting": "EXPLANATION" if Phase(item["phase"]) in _EXPECTS_WORDS else "ANSWER",
            "position": item["position"],
        }
    if item:
        activity_view = {"activity_id": item["activity_id"], "type": item["activity"]}
    elif st.lifecycle == LifecycleState.COMPLETED:
        activity_view = {"activity_id": "summary", "type": ActivityType.SUMMARY.value}
    else:
        activity_view = None
    active = st.lifecycle == LifecycleState.ACTIVE
    return {
        "session_id": session.id,
        "state_version": session.state_version,
        "lifecycle_state": st.lifecycle,
        "lesson": {"lesson_id": pkg.chapter_id, "title": pkg.title},
        "student_display_name": session.student_display_name or "",
        "persona": {"tutor_self": pkg.persona.tutor_self, "student_address": pkg.persona.student_address},
        "activity": activity_view,
        "item": item_view,
        "pending_choice": (
            [{"choice_id": k, "label": v} for k, v in CHOICES.items()] if item.get("choice_open") else None
        ),
        "allowed_commands": allowed_commands(session),
        "progress": {"items_done": passed, "items_total": len(order)},
        "transcript": transcript(session),
        "teaching": {
            "chapter": {"chapter_id": pkg.chapter_id, "title": pkg.title},
            "current_node_id": state.current.node_id if state.current else None,
            "step": act.get("step") if active else None,
            "awaiting": act.get("awaiting", Awaiting.NOTHING.value) if active else Awaiting.NOTHING.value,
            "input_id": item.get("item_attempt_id") if active else None,
            "prompt": act.get("prompt") if active else None,
            "nodes": nodes,
            "relations": _relations(chapter),
            "passed": passed,
            "total": len(order),
        },
    }


# --------------------------------------------------------------------------- teacher views


def _misconception_names(chapter: Chapter) -> dict[str, str]:
    return {m.id: m.name for lesson in chapter.lessons.values() for m in lesson.misconceptions}


def summary(chapter: Chapter, session: LearningSession, history: Sequence[Any] = ()) -> dict[str, Any]:
    """``SessionSummary`` of the web contract; progress counts the nodes passed so far, history included."""
    projection = project_chapter([*history, *session.events], chapter)
    misconceptions: list[str] = []
    for e in session.events:
        if e.event_type == EventType.MISCONCEPTION_DETECTED:
            mis = e.payload.get("misconception_id")
            if mis and mis not in misconceptions:
                misconceptions.append(mis)
    passed = sum(1 for s in projection.nodes.values() if s.passed_at is not None)
    return {
        "session_id": session.id,
        "student_display_name": session.student_display_name or "",
        "lesson_title": chapter.package.title,
        "lifecycle_state": session.state.lifecycle,
        "started_at": session.started_at,
        "updated_at": session.updated_at,
        "progress": {"items_done": passed, "items_total": len(projection.nodes)},
        "misconception_ids": misconceptions,
        "engine": "live",
        "mode": "CHAPTER",
    }


def teacher_transcript(
    chapter: Chapter, session: LearningSession, history: Sequence[Any] = ()
) -> dict[str, Any]:
    stems = {it.id: it.stem for lesson in chapter.lessons.values() for it in lesson.items}
    names = _misconception_names(chapter)
    return build_teacher_transcript(stems, names, summary(chapter, session, history), session)


def report(chapter: Chapter, session: LearningSession, history: Sequence[Any] = ()) -> dict[str, Any]:
    """The tutor's reasoning for the teacher: per node the score, its 7 dimensions, the gates and what is
    still missing; every piece of evidence with its reason (``earlier`` when it comes from an earlier
    session); the score after each event; every decision of the teaching policy in this session with its
    rule. All of it is replayed from the events (rule 3)."""
    events = [*history, *session.events]
    earlier = len(history)
    projection = project_chapter(events, chapter)
    state = teaching_state(session.events)
    statuses = node_statuses(chapter, projection, state)
    names = _misconception_names(chapter)
    nodes = []
    for node_id in chapter.topological_order():
        ns, node = projection.nodes[node_id], chapter.node(node_id)
        rule = node.pass_rule
        nodes.append(
            {
                "node_id": node_id,
                "name": node.name,
                "layer": node.layer,
                "status": statuses[node_id],
                "prior": ns.prior,
                "mastery": ns.mastery,
                "confidence": ns.confidence,
                "level": ns.level,
                "state": ns.state,
                "insufficient_data": ns.insufficient_data,
                "dimensions": {
                    d: {"mean": s.mean, "n_eff": s.n_eff, "in_mastery": s.in_mastery}
                    for d, s in ns.dimensions.items()
                },
                "items": ns.items,
                "successes": ns.successes,
                "levels": ns.levels,
                "forms": ns.forms,
                "understood": ns.understood,
                "has_explanation": ns.has_explanation,
                "has_application": ns.has_application,
                "misconceptions": [
                    {
                        "id": m.id,
                        "name": names.get(m.id, m.id),
                        "severity": m.severity,
                        "count": m.count,
                        "status": m.status,
                    }
                    for m in ns.misconceptions
                ],
                "pass_now": ns.pass_now,
                "passed": ns.passed_at is not None,
                "missing": ns.missing,
                "pass_rule": {
                    "min_mastery": round(100 * rule.min_mastery, 1),
                    "min_successes": rule.min_successes,
                    "min_levels": rule.min_levels,
                    "min_forms": rule.min_forms,
                    "max_items": rule.max_items,
                },
            }
        )

    def at(seq: int) -> dict[str, Any]:
        e = events[seq]
        return {"sequence_no": e.sequence_no, "occurred_at": e.occurred_at, "earlier": seq < earlier}

    evidence = [
        {
            **at(e.seq),
            "node_id": e.node_id,
            "dimension": e.dimension,
            "score": e.score,
            "weight": e.weight,
            "reason": e.reason,
            "item_id": e.item_id,
        }
        for e in projection.evidence
    ]
    trace = [{**at(t.seq), "node_id": t.node_id, "mastery": t.mastery} for t in projection.trace]
    decisions = []
    for i, e in enumerate(events[earlier:], start=earlier):
        if e.event_type == EventType.NODE_DECISION:
            d = NodeDecisionMade.model_validate(e.payload)
            decisions.append(
                {
                    **at(i),
                    "action": d.action.value,
                    "node_id": d.node_id,
                    "ref": d.ref,
                    "support": d.support.value if d.support else None,
                    "rule_ids": d.rule_ids,
                    "reason_codes": d.reason_codes,
                }
            )
    pkg = chapter.package
    return {
        "session": summary(chapter, session, history),
        "earlier_sessions": len({e.session_id for e in history}),
        "chapter": {"chapter_id": pkg.chapter_id, "title": pkg.title, "version": pkg.version},
        "versions": {
            "mastery": MASTERY_POLICY_VERSION,
            "policy": NODE_POLICY_VERSION,
            "templates": TEMPLATES_VERSION,
        },
        "current_node_id": state.current.node_id if state.current else None,
        "nodes": nodes,
        "relations": _relations(chapter),
        "evidence": evidence,
        "trace": trace,
        "decisions": decisions,
    }
