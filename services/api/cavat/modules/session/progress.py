"""A student's progress on a chapter across sessions, for the student and the parent (blueprint PART 27.1).

The chapter sessions of the student are folded, oldest first, into the node projection (M1-3), then said
in the words each role needs:

- understanding per topic as the qualitative states of DI-14, never the score itself;
- study days, the streak (without pressure) and an estimate of the time spent learning;
- two or three things going well and two or three to practise, each with its reason;
- for the parent: the progress day by day over four weeks and how to help at home.

Everything is computed from the event log (rule 3); nothing here writes a score.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from cavat.core.events import EventType
from cavat.modules.assessment.projector import NodeState, project_chapter
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.session.chapter_service import is_chapter, node_statuses
from cavat.modules.session.repository import LearningSession, LifecycleState
from cavat.modules.teaching.state import TeachingState, teaching_state

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")  # dates are the student's dates (PART 28.1)
GAP_CAP = timedelta(minutes=5)  # DI: a longer pause between two events is not counted as learning time
TREND_DAYS = 28  # "xu hướng 4 tuần" (PART 27.1)

# DI-14: the qualitative states shared with the parent. NOT_STARTED is added for topics never begun.
QUALITY_BY_LEVEL = {
    0: "FAMILIAR",
    1: "FAMILIAR",
    2: "WITH_SUPPORT",
    3: "INDEPENDENT",
    4: "INDEPENDENT",
    5: "SOLID",
}
GOING_WELL = ("INDEPENDENT", "SOLID")
STUDENT_EVENTS = (EventType.STUDENT_MESSAGE, EventType.HINT_REQUESTED, EventType.CHOICE_MADE)


def parent_code(student_id: str) -> str:
    """The code a parent enters to follow the child (demo guardian link until accounts exist, T12)."""
    return hashlib.sha256(student_id.encode()).hexdigest()[:6].upper()


def quality(state: NodeState) -> str:
    """DI-14: NOT_STARTED, INSUFFICIENT_DATA, FAMILIAR, WITH_SUPPORT, INDEPENDENT, SOLID."""
    if state.mastery is None:
        return "NOT_STARTED"
    if state.insufficient_data and state.passed_at is None:
        return "INSUFFICIENT_DATA"
    return QUALITY_BY_LEVEL.get(state.level, "FAMILIAR")


def chapter_sessions(chapter: Chapter, sessions: Sequence[LearningSession]) -> list[LearningSession]:
    chapter_id = chapter.package.chapter_id
    found = [s for s in sessions if is_chapter(s) and s.lesson_id == chapter_id]
    return sorted(found, key=lambda s: s.created_at)


def _local_day(moment: datetime) -> date:
    return moment.astimezone(LOCAL_TZ).date()


def _learning_seconds(session: LearningSession) -> float:
    times = sorted(e.occurred_at for e in session.events)
    return sum(min(b - a, GAP_CAP).total_seconds() for a, b in zip(times, times[1:], strict=False))


def _streak(days: set[date], today: date) -> int:
    """Consecutive study days ending today, or yesterday when the student has not studied yet today."""
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def overview(
    chapter: Chapter, sessions: Sequence[LearningSession], today: date, display_name: str | None = None
) -> dict[str, Any]:
    """The student's progress on the chapter, from every session of the student (oldest first)."""
    mine = chapter_sessions(chapter, sessions)
    events = [e for s in mine for e in s.events]
    projection = project_chapter(events, chapter)
    unfinished = [s for s in mine if s.state.lifecycle in (LifecycleState.READY, LifecycleState.ACTIVE)]
    current = unfinished[-1] if unfinished else None
    state = teaching_state(current.events) if current else TeachingState()
    statuses = node_statuses(chapter, projection, state)
    names = {m.id: m.name for lesson in chapter.lessons.values() for m in lesson.misconceptions}

    nodes = []
    for order, node_id in enumerate(chapter.topological_order()):
        ns, node = projection.nodes[node_id], chapter.node(node_id)
        nodes.append(
            {
                "node_id": node_id,
                "name": node.name,
                "layer": node.layer,
                "status": statuses[node_id],
                "level": ns.level if ns.mastery is not None else None,
                "quality": quality(ns),
                "order": order,
                "passed": ns.passed_at is not None,
            }
        )

    going_well = sorted(
        (n for n in nodes if n["quality"] in GOING_WELL),
        key=lambda n: -(projection.nodes[n["node_id"]].mastery or 0.0),
    )
    to_practise = []
    for n in nodes:
        ns = projection.nodes[n["node_id"]]
        active = [m for m in ns.misconceptions if m.status != "RESOLVED"]
        if active:
            reason = f"Còn hay nhầm: {names.get(active[0].id, active[0].id)}"
        elif statuses[n["node_id"]] == "STOPPED" or (ns.mastery is not None and not n["passed"]):
            reason = "Cần luyện thêm để tự làm được"
        else:
            continue
        to_practise.append({**n, "reason": reason, "severity": 0 if active else 1, "m": ns.mastery or 0.0})
    to_practise.sort(key=lambda n: (n["severity"], n["m"]))

    days = {_local_day(e.occurred_at) for s in mine for e in s.events if e.event_type in STUDENT_EVENTS}
    week_start = today - timedelta(days=today.weekday())
    passed_this_week = sum(
        1
        for n in nodes
        if n["passed"]
        and _local_day(events[projection.nodes[n["node_id"]].passed_at].occurred_at) >= week_start
    )
    latest = mine[-1] if mine else None
    return {
        "student_display_name": display_name
        or next((s.student_display_name for s in reversed(mine) if s.student_display_name), "")
        or "",
        "chapter": {"chapter_id": chapter.package.chapter_id, "title": chapter.package.title},
        "nodes": nodes,
        "relations": [
            {"source": r.source, "target": r.target, "type": r.type} for r in chapter.package.relations
        ],
        "passed": sum(1 for n in nodes if n["passed"]),
        "total": len(nodes),
        "sessions": {
            "total": len(mine),
            "completed": sum(1 for s in mine if s.state.lifecycle == LifecycleState.COMPLETED),
            "unfinished": len(unfinished),
            "minutes": round(sum(_learning_seconds(s) for s in mine) / 60),
        },
        "study_days": sorted(d.isoformat() for d in days),
        "streak": _streak(days, today),
        "this_week": {
            "study_days": sum(1 for d in days if d >= week_start),
            "passed": passed_this_week,
        },
        "going_well": [
            {"node_id": n["node_id"], "name": n["name"], "quality": n["quality"]} for n in going_well[:3]
        ],
        "to_practise": [
            {"node_id": n["node_id"], "name": n["name"], "quality": n["quality"], "reason": n["reason"]}
            for n in to_practise[:3]
        ],
        "current_session_id": current.id if current else None,
        "last_session_at": latest.updated_at if latest else None,
    }


def trend(chapter: Chapter, sessions: Sequence[LearningSession], today: date) -> list[dict[str, Any]]:
    """Day by day over the last four weeks: topics passed so far, and the topics' states that day."""
    mine = chapter_sessions(chapter, sessions)
    events = [e for s in mine for e in s.events]
    projection = project_chapter(events, chapter)
    day_of = [_local_day(e.occurred_at) for e in events]
    studied_days = {day_of[i] for i, e in enumerate(events) if e.event_type in STUDENT_EVENTS}
    first = today - timedelta(days=TREND_DAYS - 1)
    passed_on = {
        node_id: day_of[ns.passed_at] for node_id, ns in projection.nodes.items() if ns.passed_at is not None
    }
    last_mastery: dict[str, float] = {}
    by_day: dict[date, dict[str, float]] = {}
    for point in projection.trace:
        if point.mastery is not None:
            last_mastery[point.node_id] = point.mastery
            by_day[day_of[point.seq]] = dict(last_mastery)
    out = []
    running: dict[str, float] = {}
    for offset in range(TREND_DAYS):
        day = first + timedelta(days=offset)
        for d in sorted(k for k in by_day if k <= day):
            running = by_day[d]
        studied = day in studied_days
        out.append(
            {
                "date": day.isoformat(),
                "studied": studied,
                "passed": sum(1 for d in passed_on.values() if d <= day),
                "started": len(running),
            }
        )
    return out


def home_tips(chapter: Chapter, practise: Sequence[dict[str, Any]]) -> list[dict[str, str]]:
    """How to help at home: the tip of each topic to practise, else of the next topic to learn."""
    tips = [
        {"node_id": n["node_id"], "name": n["name"], "tip": chapter.node(n["node_id"]).home_tip}
        for n in practise
        if chapter.node(n["node_id"]).home_tip
    ]
    return tips[:3]


def sessions_list(chapter: Chapter, sessions: Sequence[LearningSession]) -> list[dict[str, Any]]:
    """The sessions for the parent, newest first: when, how long, what was passed. No transcript."""
    mine = chapter_sessions(chapter, sessions)
    out = []
    history: list[Any] = []
    before = project_chapter([], chapter)
    for s in mine:
        after = project_chapter([*history, *s.events], chapter)
        newly = [
            chapter.node(n).name
            for n in chapter.topological_order()
            if after.nodes[n].passed_at is not None and before.nodes[n].passed_at is None
        ]
        out.append(
            {
                "session_id": s.id,
                "started_at": s.started_at or s.created_at,
                "minutes": round(_learning_seconds(s) / 60),
                "lifecycle_state": s.state.lifecycle,
                "passed_names": newly,
            }
        )
        history.extend(s.events)
        before = after
    return list(reversed(out))
