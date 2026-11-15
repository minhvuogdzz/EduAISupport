"""What the report views add for an English unit (ENG-7b, ADR-067; ADR-060 §8-§9, DI-109, DI-113, DI-114).

The teacher, parent and student views of an English unit are the Mathematics views of the same chapter
(``session.teacher_view``, ``session.progress``: the same projector, groups, qualitative states of DI-113,
attention of DI-20, the four outcome groups of DI-114 already in ``activity``). This module only adds, on a
copy of such a view, the fields the English pages read and Mathematics has none of:

- ``subject`` on the chapter references, the English units as the chapters to pick from;
- ``pattern`` beside a node's Vietnamese name, ``example`` beside a home tip (DI-144);
- ``current_step`` of the six-step cycle for the student (ADR-059);
- the spoken turns: per day (``activity[].voice_turns/asr_low``), per item (``journey[].modality``), the
  share of answers said aloud (``kpis.voice_share``), the warning ``ASR_LOW`` (DI-114 item 3, DI-145) and
  the list of turns with what the listener wrote, q, the language and the recording (DI-146).

Everything is read from the event log (rule 3): VOICE_TURN_RECORDED (ADR-064), STUDENT_MESSAGE,
ANSWER_SUBMITTED, ITEM_RESOLVED and NODE_DECISION. Nothing here grades, scores or writes. A Mathematics view
never comes here (``is_english``), so its JSON stays the one before English (english-module-rules F1).
The parent view gets no turn, transcript, recording or score (rule F4): only the words above.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from typing import Any

from cavat.core.events import EventType, NodeDecisionMade
from cavat.core.pedagogy import TeachAction
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.session.chapter_service import STEP_OF, chapters
from cavat.modules.session.progress import Folded, local_day

ENGLISH = "english"
LOW_Q = 0.6  # DI-109: below it the listener was not sure; "nghe chưa rõ (không trừ điểm)" (DI-114 item 2)
ASR_LOW_DAYS = 7  # DI-114 item 3: the last seven days...
ASR_LOW_SHARE = 0.4  # ... at least 40 % of the spoken turns with q < 0,6 ...
ASR_LOW_MIN_TURNS = 5  # ... and at least five spoken turns
TURNS_SHOWN = 50  # DI-146: the newest spoken turns the teacher's page lists
PROMPT_CHARS = 240  # DI-146: the question shown above a turn, cut at a word

# DI-144: the first sentence of an approved home tip written in English between single quotes ('We ate
# seafood.'): Latin letters, spaces and sentence punctuation only, so 'hôm nay con làm gì?' is not one.
_ENGLISH_QUOTE = re.compile(r"'([A-Za-z][A-Za-z ,.?!’-]*[A-Za-z.?!])'")


def is_english(chapter: Chapter) -> bool:
    return chapter.package.subject == ENGLISH


def chapter_ref(chapter: Chapter) -> dict[str, Any]:
    return {"chapter_id": chapter.package.chapter_id, "title": chapter.package.title, "subject": ENGLISH}


def chapter_refs() -> list[dict[str, Any]]:
    """The English units the tutor teaches, what an English page picks from (never a Mathematics chapter)."""
    return [chapter_ref(c) for _, c in sorted(chapters(ENGLISH).items())]


def pattern(chapter: Chapter, node_id: str) -> str | None:
    """DI-144: the node's target pattern as approved in the unit file; None when it has none."""
    return chapter.node(node_id).pattern or None


def home_example(tip: str) -> str | None:
    """DI-144: the English sentence a home tip gives to say at home, quoted from the approved tip."""
    found = _ENGLISH_QUOTE.search(tip or "")
    return found[1] if found else None


# ---------------------------------------------------------------------------------------------- spoken turns


def _voice_turns(folded: Folded) -> list[tuple[int, Any]]:
    """Every VOICE_TURN_RECORDED of the student on the unit, with its index in ``folded.events``."""
    return [(i, e) for i, e in enumerate(folded.events) if e.event_type == EventType.VOICE_TURN_RECORDED]


def _low(payload: Mapping[str, Any]) -> bool:
    """DI-145: a turn whose q is known and below 0,6. A turn without q (no segment metadata) is not low."""
    q = payload.get("asr_confidence")
    return q is not None and q < LOW_Q


def asr_low(folded: Folded, today: date) -> dict[str, Any] | None:
    """DI-114 item 3 (DI-145 for the window): ``ASR_LOW`` when, over the last seven days (today and the six
    before), the student said at least five turns and at least 40 % of them had q < 0,6. Describes what the
    listener heard; it is never a score and never lowers M (DI-109)."""
    since = today - timedelta(days=ASR_LOW_DAYS - 1)
    recent = [e for _, e in _voice_turns(folded) if since <= local_day(e.occurred_at) <= today]
    if len(recent) < ASR_LOW_MIN_TURNS:
        return None
    low = sum(1 for e in recent if _low(e.payload))
    share = low / len(recent)
    if share < ASR_LOW_SHARE:
        return None
    return {"kind": "ASR_LOW", "voice_turns": len(recent), "share": round(share, 2), "count": low}


def voice_by_day(folded: Folded) -> dict[str, dict[str, int]]:
    """DI-145: per local day, the spoken turns and how many had q < 0,6 (ADR-060 §9.1 "hoạt động")."""
    days: dict[str, dict[str, int]] = defaultdict(lambda: {"voice_turns": 0, "asr_low": 0})
    for _, e in _voice_turns(folded):
        day = days[local_day(e.occurred_at).isoformat()]
        day["voice_turns"] += 1
        day["asr_low"] += _low(e.payload)
    return days


def messages(folded: Folded) -> tuple[int, int]:
    """The student's messages on the unit, and how many were said aloud (STUDENT_MESSAGE.modality)."""
    said = [e for e in folded.events if e.event_type == EventType.STUDENT_MESSAGE]
    return len(said), sum(1 for e in said if e.payload.get("modality") == "VOICE")


def voice_share(folded: Sequence[Folded]) -> float | None:
    """DI-145: the share of the class's answers given by voice, 0-100 (ADR-060 §9.2). Describes, never
    graded; None before any message."""
    total = voiced = 0
    for f in folded:
        t, v = messages(f)
        total, voiced = total + t, voiced + v
    return round(100 * voiced / total, 1) if total else None


def _cut(text: str, limit: int = PROMPT_CHARS) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + " …"


def _item_node(chapter: Chapter, item_id: str | None) -> tuple[str | None, str | None]:
    """The item and its node in the unit, from the ``item_id`` of the message ("ENG5-U11-VOCAB:T1" is a
    theory reply of a node, not an item)."""
    if not item_id:
        return None, None
    known = set(chapter.topological_order())
    try:
        item = chapter.item(item_id)
    except KeyError:
        node = item_id.split(":", 1)[0]
        return None, node if node in known else None
    return item_id, next((k for k in item.kc_ids if k in known), None)


def voice_turn_list(chapter: Chapter, folded: Folded) -> list[dict[str, Any]]:
    """DI-146: the spoken turns for the teacher, newest first (at most ``TURNS_SHOWN``): the question the
    child answered, what the listener wrote (``heard``, verbatim, never corrected), q, the language it was
    told to hear, the recording and, when the turn was graded, its outcome. Never for a parent (rule F4)."""
    events = folded.events
    out = []
    for index, turn in _voice_turns(folded):
        p = turn.payload
        item_id, node_id = _item_node(chapter, p.get("message_ref"))
        before = events[:index]
        if item_id is not None:
            prompt = chapter.item(item_id).stem
        else:
            said = (EventType.TUTOR_MESSAGE_SENT, EventType.TEACH_MESSAGE_SENT)
            prompt = next((e.payload.get("text", "") for e in reversed(before) if e.event_type in said), "")
        outcome = None
        for e in events[index + 1 :]:
            if e.event_type == EventType.STUDENT_MESSAGE or e.session_id != turn.session_id:
                break
            if e.event_type == EventType.ANSWER_SUBMITTED and e.payload.get("item_id") == p.get(
                "message_ref"
            ):
                outcome = e.payload.get("outcome")
                break
        out.append(
            {
                "turn_id": p["voice_turn_id"],
                "session_id": turn.session_id,
                "at": turn.occurred_at,
                "node_id": node_id,
                "item_id": item_id,
                "prompt": _cut(prompt),
                "transcript": p.get("heard", ""),
                "asr_confidence": p.get("asr_confidence"),
                "language": p.get("language", "vi"),
                "audio_ref": p.get("audio_ref"),
                "outcome": outcome,
                "teacher_override": False,  # ADR-060 §8: no override of a turn exists yet
            }
        )
    return list(reversed(out))[:TURNS_SHOWN]


def current_step(folded: Folded) -> int | None:
    """The step 1-6 of the cycle (ADR-059) the unfinished session is in: the step of its last node decision
    (``STEP_OF``). None when no session is open or it has made no decision yet."""
    if not folded.unfinished:
        return None
    decisions = [e for e in folded.unfinished[-1].events if e.event_type == EventType.NODE_DECISION]
    if not decisions:
        return None
    return STEP_OF.get(TeachAction(NodeDecisionMade.model_validate(decisions[-1].payload).action))


# ------------------------------------------------------------------------------------- the views, enriched


def _with_patterns(chapter: Chapter, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**r, "pattern": pattern(chapter, r["node_id"])} for r in rows]


def overview(view: Mapping[str, Any], chapter: Chapter, folded: Folded) -> dict[str, Any]:
    """The student's (and the parent's) overview of an English unit: the subject, the patterns, the step."""
    return {
        **view,
        "chapter": chapter_ref(chapter),
        "chapters": chapter_refs(),
        "nodes": _with_patterns(chapter, view["nodes"]),
        "going_well": _with_patterns(chapter, view["going_well"]),
        "to_practise": _with_patterns(chapter, view["to_practise"]),
        "current_step": current_step(folded),
    }


def parent(view: Mapping[str, Any]) -> dict[str, Any]:
    """The parent's view of an English unit: each home tip with its sentence to say at home (DI-144)."""
    return {**view, "home_tips": [{**t, "example": home_example(t["tip"])} for t in view["home_tips"]]}


def _attention(reasons: Sequence[Mapping[str, Any]], folded: Folded, today: date) -> list[dict[str, Any]]:
    low = asr_low(folded, today)
    return [*reasons, low] if low else list(reasons)


def class_view(
    view: Mapping[str, Any], chapter: Chapter, folded: Mapping[str, Folded], today: date
) -> dict[str, Any]:
    """The class on an English unit: ``ASR_LOW`` among the reasons to look at a student, the share of
    answers said aloud."""
    students = [
        {**s, "attention": _attention(s["attention"], folded[s["student_id"]], today)}
        for s in view["students"]
    ]
    kpis = {
        **view["kpis"],
        "attention": sum(1 for s in students if s["attention"]),
        "voice_share": voice_share([folded[s["student_id"]] for s in students]),
    }
    return {**view, "chapter": chapter_ref(chapter), "students": students, "kpis": kpis}


def student(view: Mapping[str, Any], chapter: Chapter, folded: Folded, today: date) -> dict[str, Any]:
    """One student on an English unit, for the teacher: spoken turns per day, how each item was answered,
    ``ASR_LOW`` and the list of turns with their recordings."""
    by_day = voice_by_day(folded)
    activity = [{**a, **by_day.get(a["date"], {"voice_turns": 0, "asr_low": 0})} for a in view["activity"]]
    known = {a["date"] for a in activity}
    for day, counts in sorted(by_day.items()):  # a day with spoken turns but no item ended
        if day not in known:
            activity.append(
                {
                    "date": day,
                    **dict.fromkeys(
                        ("independent", "supported", "worked", "unresolved", "hints", "passed"), 0
                    ),
                    **counts,
                }
            )
    activity.sort(key=lambda a: a["date"])
    known_nodes = set(chapter.topological_order())
    modalities = [
        e.payload.get("modality", "TEXT")
        for e in folded.events
        if e.event_type == EventType.ITEM_RESOLVED
        and any(k in known_nodes for k in e.payload.get("kc_ids", []))
    ]
    journey = [{**j, "modality": m} for j, m in zip(view["journey"], modalities, strict=True)]
    return {
        **view,
        "chapter": chapter_ref(chapter),
        "activity": activity,
        "attention": _attention(view["attention"], folded, today),
        "journey": journey,
        "voice_turns": voice_turn_list(chapter, folded),
    }
