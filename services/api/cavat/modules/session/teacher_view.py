"""The teacher's view of a chapter: the whole class, then one student (blueprint PART 27.1, 27.2).

It follows the dashboard of the Math framework (khung Toán):

- the class: the Student × KC matrix (§46) shown as a heatmap in the colour zones of §25, the class average
  per KC (§45), the misconception chart (§28) and the students who need attention (PART 27.1);
- one student: the overview of §23 and §43, the radar of §24, the mastery timeline of §27 with the
  velocity of §39, the learning activity timeline of §56 and, per KC, the detail screen of §57.

Every number is replayed from the event log through the node projection (rule 3); nothing here writes a
score. Thresholds that the two frameworks do not give are DI, listed in ``apps/web/README.md``.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
from statistics import fmean
from typing import Any

from cavat.core.events import EventType, ItemResolved
from cavat.core.pedagogy import ItemResolution
from cavat.modules.assessment.projector import DEFAULT_POLICY, DIMENSIONS, ChapterProjection, NodeState
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.session.progress import (
    STUDENT_EVENTS,
    Folded,
    fold,
    learning_seconds,
    local_day,
    misconception_names,
    sessions_list,
)
from cavat.modules.session.repository import LearningSession, LifecycleState

CONFIDENCE_FLOOR = 30.0  # DI-7: below it the teacher still sees M, with a warning (PART 27.3, item 7)
RED_BELOW = 40.0  # §25: the red zone (0-39)
WEAK_BELOW = 60.0  # §25: the orange and red zones; a KC there is "yếu" (§43) once confidence allows
STRONG_FROM = 75.0  # §25: the green zones; a dimension this high is a strength (§23)
RECENT_DAYS = 14  # §28: "xuất hiện 7 lần / 14 ngày"
REPEATED = 2  # DI-20: an active misconception seen this many times needs the teacher
INACTIVE_DAYS = 7  # DI-20: an unfinished session and no learning for a week needs the teacher
TREND_SPAN = 3  # DI-24: M is compared with its value three changes earlier
TREND_STEP = 3.0  # DI-24: a change of at least this many points is a rise or a fall (§27)


def band(mastery: float) -> int:
    """The level 0-5 whose band of M holds this value (§4-§8)."""
    return sum(mastery >= lower for lower in DEFAULT_POLICY.bands)


def recommendation(mastery: float | None) -> str:
    """The next move for a KC by its band of M: DI-8 (blueprint 26.1, waiting for approval)."""
    if mastery is None:
        return "DIAGNOSE"
    if mastery < RED_BELOW:
        return "EXPLAIN"
    if mastery < WEAK_BELOW:
        return "GUIDED"
    if mastery < STRONG_FROM:
        return "PRACTICE"
    if mastery < 90:
        return "TRANSFER"
    return "CHALLENGE"


def group(ns: NodeState) -> str:
    """§43 sorts the KCs into mastered ✓, not yet stable ⚠ and weak ✕ (DI-27 for the boundaries).

    A KC is ✓ once its pass rule held (DI-15). "Làm chủ" in the sense of §53 needs retention evidence,
    which no delayed probe gives yet, so the web says "đã qua bài".
    """
    if ns.passed_at is not None:
        return "PASSED"
    if ns.mastery is None:
        return "NOT_STARTED"
    if ns.insufficient_data:
        return "INSUFFICIENT"
    return "WEAK" if ns.mastery < WEAK_BELOW else "UNSTABLE"


def direction(values: Sequence[float]) -> str | None:
    """§27: progress ↗, standing still →, decline ↘ (DI-24)."""
    if len(values) < 2:
        return None
    change = values[-1] - values[max(0, len(values) - 1 - TREND_SPAN)]
    if change >= TREND_STEP:
        return "UP"
    return "DOWN" if change <= -TREND_STEP else "FLAT"


def overall(projection: ChapterProjection) -> dict[str, Any]:
    """§23 "Overall Mastery" and "Knowledge Coverage" (DI-21): the mean M of the KCs with a score, and the
    share of the chapter's KCs that have one. Confidence is the mean of the same KCs."""
    scored = [ns for ns in projection.nodes.values() if ns.mastery is not None]
    values = [ns.mastery for ns in scored if ns.mastery is not None]
    if not values:
        return {"mastery": None, "confidence": None, "level": None, "coverage": 0.0}
    mastery = fmean(values)
    return {
        "mastery": round(mastery, 1),
        "confidence": round(fmean(ns.confidence for ns in scored), 1),
        "level": band(mastery),
        "coverage": round(100 * len(values) / len(projection.nodes), 1),
    }


def dimensions(projection: ChapterProjection) -> dict[str, dict[str, Any]]:
    """Each dimension over the chapter (DI-22): the mean of the KCs where it counts in M (DI-1), weighted
    by its effective evidence. No such KC: no value, shown as "chưa đủ dữ liệu" as in §55."""
    out: dict[str, dict[str, Any]] = {}
    for d in DIMENSIONS:
        parts = [(s.mean, s.n_eff) for ns in projection.nodes.values() if (s := ns.dimensions[d]).in_mastery]
        weight = sum(w for _, w in parts)
        value = round(100 * sum(m * w for m, w in parts) / weight, 1) if weight else None
        out[d] = {"value": value, "n_eff": round(weight, 2)}
    return out


def _resolved(events: Iterable[Any]) -> Iterable[tuple[Any, ItemResolved]]:
    for e in events:
        if e.event_type == EventType.ITEM_RESOLVED:
            yield e, ItemResolved.model_validate(e.payload)


def _last_learning(folded: Folded) -> Any:
    times = [e.occurred_at for e in folded.events if e.event_type in STUDENT_EVENTS]
    return max(times) if times else None


def attention(chapter: Chapter, folded: Folded, today: date) -> list[dict[str, Any]]:
    """Why the teacher should look at this student (PART 27.1 "học sinh cần chú ý", DI-20)."""
    reasons: list[dict[str, Any]] = []
    for node_id in chapter.topological_order():
        ns = folded.projection.nodes[node_id]
        if folded.statuses[node_id] == "STOPPED":
            reasons.append({"kind": "STOPPED", "node_id": node_id})
        for m in ns.misconceptions:
            if m.status == "ACTIVE" and (m.count >= REPEATED or m.severity == "CRITICAL"):
                reasons.append(
                    {"kind": "MISCONCEPTION", "node_id": node_id, "misconception_id": m.id, "count": m.count}
                )
        if (
            ns.passed_at is None
            and ns.mastery is not None
            and ns.mastery < RED_BELOW
            and not ns.insufficient_data
        ):
            reasons.append({"kind": "WEAK", "node_id": node_id, "mastery": ns.mastery})
    last = _last_learning(folded)
    if folded.unfinished and last is not None:
        idle = (today - local_day(last)).days
        if idle >= INACTIVE_DAYS:
            reasons.append({"kind": "INACTIVE", "days": idle})
    return reasons


def _cell(node_id: str, ns: NodeState, status: str) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "mastery": ns.mastery,
        "confidence": ns.confidence,
        "level": ns.level,
        "state": ns.state,
        "insufficient_data": ns.insufficient_data,
        "passed": ns.passed_at is not None,
        "status": status,
        "active_misconceptions": sum(1 for m in ns.misconceptions if m.status != "RESOLVED"),
    }


def _sessions(folded: Folded) -> dict[str, int]:
    return {
        "total": len(folded.sessions),
        "completed": sum(1 for s in folded.sessions if s.state.lifecycle == LifecycleState.COMPLETED),
        "unfinished": len(folded.unfinished),
        "minutes": round(sum(learning_seconds(s) for s in folded.sessions) / 60),
    }


def _chapter_info(chapter: Chapter) -> dict[str, Any]:
    return {"chapter_id": chapter.package.chapter_id, "title": chapter.package.title}


def _nodes_info(chapter: Chapter) -> list[dict[str, Any]]:
    return [
        {
            "node_id": node_id,
            "name": chapter.node(node_id).name,
            "layer": chapter.node(node_id).layer,
            "order": order,
            "min_mastery": round(100 * chapter.node(node_id).pass_rule.min_mastery, 1),
        }
        for order, node_id in enumerate(chapter.topological_order())
    ]


def class_overview(
    chapter: Chapter, by_student: Mapping[str, Sequence[LearningSession]], today: date
) -> dict[str, Any]:
    """The class on the chapter: one row per student, one column per KC, and what the class shares."""
    order = chapter.topological_order()
    folded = {sid: fold(chapter, sessions) for sid, sessions in by_student.items()}
    folded = {sid: f for sid, f in folded.items() if f.sessions}
    week_start = today - timedelta(days=today.weekday())

    students = []
    for sid, f in folded.items():
        last = _last_learning(f)
        students.append(
            {
                "student_id": sid,
                "display_name": f.display_name or sid,
                "sessions": _sessions(f),
                "last_active_at": last,
                "passed": sum(1 for n in order if f.projection.nodes[n].passed_at is not None),
                "overall": overall(f.projection),
                "cells": [_cell(n, f.projection.nodes[n], f.statuses[n]) for n in order],
                "attention": attention(chapter, f, today),
            }
        )
    students.sort(key=lambda s: (s["display_name"].casefold(), s["student_id"]))

    by_node = []
    for node_id in order:
        values = [m for f in folded.values() if (m := f.projection.nodes[node_id].mastery) is not None]
        by_node.append(
            {
                "node_id": node_id,
                "mean_mastery": round(fmean(values), 1) if values else None,
                "students": len(values),
                "passed": sum(
                    1 for f in folded.values() if f.projection.nodes[node_id].passed_at is not None
                ),
            }
        )

    means = [s["overall"]["mastery"] for s in students if s["overall"]["mastery"] is not None]
    return {
        "chapter": _chapter_info(chapter),
        "nodes": _nodes_info(chapter),
        "students": students,
        "by_node": by_node,
        "misconceptions": class_misconceptions(chapter, folded, today),
        "kpis": {
            "students": len(students),
            "active_this_week": sum(
                1 for s in students if s["last_active_at"] and local_day(s["last_active_at"]) >= week_start
            ),
            "sessions": sum(s["sessions"]["total"] for s in students),
            "minutes": sum(s["sessions"]["minutes"] for s in students),
            "passed": sum(s["passed"] for s in students),
            "cells": len(students) * len(order),
            "mean_mastery": round(fmean(means), 1) if means else None,
            "attention": sum(1 for s in students if s["attention"]),
        },
    }


def class_misconceptions(chapter: Chapter, folded: Mapping[str, Folded], today: date) -> list[dict[str, Any]]:
    """§28: how often each misconception was detected in the class, its share of all detections, how many
    students it touched and still touches, and how often in the last 14 days."""
    info = {m.id: m for lesson in chapter.lessons.values() for m in lesson.misconceptions}
    count: Counter[str] = Counter()
    recent: Counter[str] = Counter()
    students: dict[str, set[str]] = defaultdict(set)
    for sid, f in folded.items():
        for event, item in _resolved(f.events):
            for mis_id in item.misconception_ids:
                count[mis_id] += 1
                students[mis_id].add(sid)
                if (today - local_day(event.occurred_at)).days < RECENT_DAYS:
                    recent[mis_id] += 1
    active: Counter[str] = Counter(
        m.id
        for f in folded.values()
        for ns in f.projection.nodes.values()
        for m in ns.misconceptions
        if m.status != "RESOLVED"
    )
    total = sum(count.values())
    out = [
        {
            "id": mis_id,
            "name": info[mis_id].name if mis_id in info else mis_id,
            "node_id": info[mis_id].kc_id if mis_id in info else None,
            "severity": info[mis_id].severity if mis_id in info else "NORMAL",
            "count": n,
            "share": round(100 * n / total, 1),
            "students": len(students[mis_id]),
            "active_students": active[mis_id],
            "recent": recent[mis_id],
        }
        for mis_id, n in count.items()
    ]
    return sorted(out, key=lambda m: (-m["count"], m["name"]))


def _item_stats(events: Sequence[Any]) -> dict[str, dict[str, Any]]:
    """§57: items, solved, attempts, hints and time per KC, from how each item ended."""
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"items": 0, "solved": 0, "attempts": 0, "hints": 0, "seconds": []}
    )
    for _, item in _resolved(events):
        for kc in item.kc_ids:
            st = stats[kc]
            st["items"] += 1
            st["solved"] += item.resolution != ItemResolution.UNRESOLVED
            st["attempts"] += item.attempts
            st["hints"] += item.hints_count
            if item.time_s is not None:
                st["seconds"].append(item.time_s)
    return stats


def _timeline(folded: Folded) -> list[dict[str, Any]]:
    """§27 mastery timeline (DI-26): the overall M of §23 at the end of each day with new evidence."""
    latest: dict[str, float] = {}
    by_day: dict[date, float] = {}
    for point in folded.projection.trace:
        if point.mastery is None:
            continue
        latest[point.node_id] = point.mastery
        by_day[local_day(folded.events[point.seq].occurred_at)] = round(fmean(latest.values()), 1)
    return [{"date": d.isoformat(), "mastery": m} for d, m in sorted(by_day.items())]


def _velocity(timeline: Sequence[Mapping[str, Any]], today: date) -> dict[str, Any] | None:
    """§39 learning velocity (DI-25): overall M now against its value before this week (Monday)."""
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    before = [t for t in timeline if t["date"] < week_start]
    now = [t for t in timeline if t["date"] >= week_start]
    if not before or not now:
        return None
    return {"change": round(now[-1]["mastery"] - before[-1]["mastery"], 1), "since": before[-1]["date"]}


def _activity(folded: Folded) -> list[dict[str, Any]]:
    """§56 learning activity timeline: per day, how the items ended, the hints and the KCs passed."""
    keys = ("independent", "supported", "worked", "unresolved", "hints", "passed")
    days: dict[date, dict[str, int]] = defaultdict(lambda: dict.fromkeys(keys, 0))
    for event, item in _resolved(folded.events):
        day = days[local_day(event.occurred_at)]
        day[item.resolution.lower()] += 1
        day["hints"] += item.hints_count
    for ns in folded.projection.nodes.values():
        if ns.passed_at is not None:
            days[local_day(folded.events[ns.passed_at].occurred_at)]["passed"] += 1
    return [{"date": d.isoformat(), **counts} for d, counts in sorted(days.items())]


def student_detail(
    chapter: Chapter, student_id: str, sessions: Sequence[LearningSession], today: date
) -> dict[str, Any]:
    """One student on the chapter, for the teacher: §23 overview, §24 radar, §27 timeline, §39 velocity,
    §43 KC groups, §56 activity and the §57 detail of every KC, with its evidence-based trend."""
    f = fold(chapter, sessions)
    names = misconception_names(chapter)
    stats = _item_stats(f.events)
    trend: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for point in f.projection.trace:
        if point.mastery is not None:
            trend[point.node_id].append({"at": f.events[point.seq].occurred_at, "mastery": point.mastery})

    nodes = []
    for info in _nodes_info(chapter):
        node_id = info["node_id"]
        ns, st = f.projection.nodes[node_id], stats.get(node_id)
        points = trend[node_id]
        nodes.append(
            {
                **info,
                **_cell(node_id, ns, f.statuses[node_id]),
                "group": group(ns),
                "dimensions": {
                    d: {
                        "value": round(100 * s.mean, 1),
                        "n_eff": round(s.n_eff, 2),
                        "in_mastery": s.in_mastery,
                    }
                    for d, s in ns.dimensions.items()
                },
                "items": st["items"] if st else 0,
                "solved": st["solved"] if st else 0,
                "attempts": st["attempts"] if st else 0,
                "hints": st["hints"] if st else 0,
                "seconds": round(fmean(st["seconds"])) if st and st["seconds"] else None,
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
                "trend": points,
                "direction": direction([p["mastery"] for p in points]),
                "recommendation": recommendation(ns.mastery),
            }
        )

    timeline = _timeline(f)
    dims = dimensions(f.projection)
    valued = [(d, v["value"]) for d, v in dims.items() if v["value"] is not None]
    return {
        "student_id": student_id,
        "display_name": f.display_name or student_id,
        "chapter": _chapter_info(chapter),
        "relations": [
            {"source": r.source, "target": r.target, "type": r.type} for r in chapter.package.relations
        ],
        "sessions": _sessions(f),
        "session_list": sessions_list(chapter, f.sessions),
        "last_active_at": _last_learning(f),
        "overall": {
            **overall(f.projection),
            "passed": sum(1 for n in nodes if n["passed"]),
            "total": len(nodes),
        },
        "dimensions": dims,
        # §23 "điểm mạnh / điểm yếu" (DI-23): the dimensions in the green zones, then those below 60.
        "strengths": [d for d, v in sorted(valued, key=lambda x: -x[1]) if v >= STRONG_FROM][:2],
        "weaknesses": [d for d, v in sorted(valued, key=lambda x: x[1]) if v < WEAK_BELOW][:2],
        "nodes": nodes,
        "timeline": timeline,
        "velocity": _velocity(timeline, today),
        "activity": _activity(f),
        "attention": attention(chapter, f, today),
    }
