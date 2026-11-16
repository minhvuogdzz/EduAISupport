"""What the report views add for an English unit (ENG-7b, ADR-067; ADR-060 §8-§9, DI-109, DI-113, DI-114).

The teacher, parent and student views of an English unit are the Mathematics views of the same chapter
(``session.teacher_view``, ``session.progress``: the same projector, groups, qualitative states of DI-113,
attention of DI-20, the four outcome groups of DI-114 already in ``activity``). This module only adds, on a
copy of such a view, the fields the English pages read and Mathematics has none of:

- ``subject`` on the chapter references, the English units as the chapters to pick from;
- ``pattern`` beside a node's Vietnamese name, ``example`` beside a home tip (DI-144);
- ``current_step`` of the six-step cycle for the student (ADR-059);
- ``mistakes`` beside a node to practise (parent, student) and every node (teacher): the typical mistakes
  the child made on the node, in Vietnamese with a short example "eat → ate" (ENG-7c, DI-153);
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
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from cavat.core.en_text import IRREGULAR_PAST, normalize_answer
from cavat.core.events import EventType, NodeDecisionMade
from cavat.core.pedagogy import ErrorClass, Outcome, TeachAction
from cavat.modules.assessment.answer_check import check_answer, is_english_answer
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.session.chapter_service import STEP_OF, chapters
from cavat.modules.session.progress import STUDENT_EVENTS, Folded, learning_seconds, local_day
from cavat.modules.session.repository import LifecycleState

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


# ------------------------------------------------------------------------- typical mistakes (ENG-7c, DI-153)

MISTAKES_SHOWN = 3  # DI-153: the most frequent kinds of mistake listed for a node
EXAMPLES_SHOWN = 2  # DI-153: distinct examples per kind, newest first
OFTEN = 2  # DI-153: "còn hay nhầm" from this many graded answers of a kind; one is "có lúc nhầm"
PAIR_WORDS = 3  # DI-153: an example "said → right" is at most three words on each side
NEAR = 0.5  # DI-153: below this word similarity to every accepted answer, no example is drawn
SLIP_NEAR = 0.75  # DI-153: one word for one word this close letter by letter is a spelling slip

# DI-153: the English error codes of DI-107 in the parent's words. A misconception of the lesson keeps its
# approved name; these words are for a mistake no misconception names.
MISTAKE_LABEL = {
    "EN_TENSE": "Kể chuyện đã qua mà chưa đổi động từ sang quá khứ",
    "EN_VERB_FORM": "Thêm -ed vào động từ có dạng quá khứ riêng",
    "EN_STRUCTURE": "Hỏi chuyện đã qua với did chưa đúng (thiếu did hoặc đổi động từ sau did)",
    "EN_SHORT_ANSWER": "Trả lời ngắn chưa khớp câu hỏi (Yes, I did. / No, I didn't.)",
    "EN_MEANING": "Hiểu nhầm nghĩa của câu hoặc cụm từ",
    "EN_SLIP": "Viết hoặc nói sai chính tả một từ",
    "EN_L1": "Trả lời bằng tiếng Việt khi bài cần nói tiếng Anh",
    "MISSING": "Câu còn thiếu một phần",
    "WORD": "Dùng chưa đúng từ trong câu",
}


def _accepted(item: Any) -> list[str]:
    """The right sentences of an English item, from its approved answer (the checker's own source)."""
    answer = item.answer
    if answer.type == "word_order":
        return [" ".join(order) for order in answer.accept]
    return list(answer.accept) or [" ".join(group[0] for group in answer.required)]


def _pair(said: str, right: str) -> str | None:
    """The first place the child's sentence differs from a right one, as "said → right" ("eat → ate"), or
    the part left out ("thiếu “around the bay”"). None when the two are not close enough to compare."""
    a, b = normalize_answer(said).split(), normalize_answer(right).split()
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        x, y = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if tag == "replace" and i2 - i1 <= PAIR_WORDS and j2 - j1 <= PAIR_WORDS:
            return f"{x} → {y}"
        if tag == "insert" and j2 - j1 <= PAIR_WORDS + 1:
            return f"thiếu “{y}”"
        if tag == "delete" and i2 - i1 <= PAIR_WORDS:
            return f"thừa “{x}”"
        if tag != "equal":
            return None
    return None


def _example(item: Any, payload: Mapping[str, Any]) -> str | None:
    """DI-153: a short example of the mistake, derived from the answer, never the child's whole sentence
    (rule F4): the words that differ from the nearest accepted answer, or the option picked and the right
    one of a choice item."""
    answer = item.answer
    if answer.type == "choice":
        said = str(payload.get("normalized") or payload.get("raw_text") or "").strip()
        picked = next((o for o in answer.options if o.id == said), None)
        right = next((o for o in answer.options if o.correct), None)
        if picked is None or right is None or picked is right:
            return None
        return f"chọn “{picked.text}” thay vì “{right.text}”"
    if not is_english_answer(answer):
        return None
    said = normalize_answer(payload.get("raw_text") or "")
    candidates = [
        (SequenceMatcher(a=said.split(), b=normalize_answer(r).split()).ratio(), r) for r in _accepted(item)
    ]
    if not said or not candidates:
        return None
    ratio, nearest = max(candidates, key=lambda c: c[0])
    return (_pair(said, nearest) if ratio >= NEAR else None) or _wrong_form(said)


def _wrong_ed() -> dict[str, str]:
    out: dict[str, str] = {}
    for past, base in IRREGULAR_PAST.items():  # past -> base
        for wrong in (f"{base}ed", f"{base}{base[-1]}ed", f"{base}d", f"{past}ed"):
            if wrong != past:
                out.setdefault(wrong, past)
    return out


_WRONG_ED = _wrong_ed()


def _wrong_form(said: str) -> str | None:
    """ENG-5h (DI-176): a wrong past form in an answer too short to compare with a whole sentence ("eated"
    for "Yesterday we … seafood"): the example is the form and the right one ("eated → ate"), not []."""
    return next((f"{w} → {_WRONG_ED[w]}" for w in said.split() if w in _WRONG_ED), None)


def _slip(example: str | None) -> bool:
    """One word for one word, close letter by letter ("seafod → seafood"): a spelling slip (DI-153)."""
    if not example or " → " not in example:
        return False
    x, y = example.split(" → ")
    return " " not in x and " " not in y and SequenceMatcher(a=x, b=y).ratio() >= SLIP_NEAR


def _kind(
    chapter: Chapter, item: Any, payload: Mapping[str, Any], example: str | None
) -> tuple[str, str] | None:
    """DI-153: what kind of mistake a graded answer shows, and its words: the lesson's misconception when
    the checker named one; else the DI-107 code the deterministic checker gives the same answer again (it
    never calls a model); else a part left out, a spelling slip or a wrong word read from the example."""
    names = {m.id: m.name for lesson in chapter.lessons.values() for m in lesson.misconceptions}
    mis = payload.get("misconception_id")
    if mis in names:
        return f"M:{mis}", names[mis]
    if payload.get("error_class") == ErrorClass.L1:
        return "EN_L1", MISTAKE_LABEL["EN_L1"]
    code = None
    if is_english_answer(item.answer):
        try:
            result = check_answer(item, payload.get("raw_text") or "", chapter.lesson_of(payload["item_id"]))
        except (KeyError, TypeError, ValueError):
            result = None
        if result is not None:
            code = (result.detail or {}).get("en_code")
    if code in MISTAKE_LABEL:
        return code, MISTAKE_LABEL[code]
    if _slip(example):
        return "EN_SLIP", MISTAKE_LABEL["EN_SLIP"]
    if example and example.startswith("thiếu"):
        return "MISSING", MISTAKE_LABEL["MISSING"]
    if example and " → " in example:
        return "WORD", MISTAKE_LABEL["WORD"]
    return None


def mistakes(chapter: Chapter, folded: Folded, node_id: str) -> list[dict[str, Any]]:
    """DI-153: the typical mistakes of the child on a node, the most frequent first (at most three): each
    kind in Vietnamese, how many graded answers showed it and up to two examples, newest first. Read from
    ANSWER_SUBMITTED (outcome WRONG or PARTIAL) on the node's items; nothing is graded or written here."""
    found: dict[str, dict[str, Any]] = {}
    for e in folded.events:
        if e.event_type != EventType.ANSWER_SUBMITTED:
            continue
        p = e.payload
        if p.get("outcome") not in (Outcome.WRONG, Outcome.PARTIAL):
            continue
        try:
            item = chapter.item(p["item_id"])
        except KeyError:
            continue
        if node_id not in item.kc_ids:
            continue
        example = _example(item, p)
        kind = _kind(chapter, item, p, example)
        if kind is None:
            continue
        row = found.setdefault(kind[0], {"label": kind[1], "count": 0, "examples": [], "last": e.occurred_at})
        row["count"] += 1
        row["last"] = max(row["last"], e.occurred_at)
        if example:
            row["examples"] = [example, *(x for x in row["examples"] if x != example)]
    rows = sorted(found.values(), key=lambda r: (-r["count"], -_seconds(r["last"])))
    return [
        {
            "label": r["label"],
            "count": r["count"],
            "examples": [shown(x) for x in r["examples"][:EXAMPLES_SHOWN]],
        }
        for r in rows[:MISTAKES_SHOWN]
    ]


def shown(example: str) -> str:
    """ENG-5i (DI-186): an example in the words a parent reads without guessing the direction: what the child
    said, then the right words ("con nói “eat”, đúng là “ate”"). "eat → ate" read as the rule "eat becomes
    ate" (the third live run's report), not as the child's mistake."""
    if " → " not in example:
        return example
    said, right = example.split(" → ", 1)
    return f"con nói “{said}”, đúng là “{right}”"


def _seconds(moment: datetime) -> float:
    return moment.timestamp()


def mistake_reason(found: Sequence[Mapping[str, Any]]) -> str | None:
    """DI-153: the sentence "cần luyện" says, as concrete as Mathematics's "Còn hay nhầm: …": the most
    frequent mistake and its newest example. None when the child made no mistake a kind names."""
    if not found:
        return None
    top = found[0]
    lead = "Còn hay nhầm" if top["count"] >= OFTEN else "Có lúc nhầm"
    example = f", ví dụ {top['examples'][0]}" if top["examples"] else ""
    return f"{lead}: {top['label'][0].lower()}{top['label'][1:]}{example}"


# ------------------------------------------------------------------------------------- the views, enriched


def _with_patterns(chapter: Chapter, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{**r, "pattern": pattern(chapter, r["node_id"])} for r in rows]


def _to_practise(chapter: Chapter, folded: Folded, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """DI-153: each node to practise with the child's typical mistakes, its reason the most frequent one
    (the shared reason stays when no mistake has a kind)."""
    out = []
    for row in _with_patterns(chapter, rows):
        found = mistakes(chapter, folded, row["node_id"])
        out.append({**row, "reason": mistake_reason(found) or row.get("reason"), "mistakes": found or None})
    return out


def studied(session: Any) -> bool:
    """ENG-5h (DI-176): a session in which the child said, asked or chose something. A session opened when
    every part was passed already ("mình dừng ở đây"), or opened and left without a word, is no study."""
    return any(e.event_type in STUDENT_EVENTS for e in session.events)


def sessions_count(folded: Folded) -> dict[str, int]:
    """The ``sessions`` block of an English view, counting only the sessions studied (DI-176)."""
    mine = [s for s in folded.sessions if studied(s)]
    return {
        "total": len(mine),
        "completed": sum(1 for s in mine if s.state.lifecycle == LifecycleState.COMPLETED),
        "unfinished": sum(1 for s in folded.unfinished if studied(s)),
        "minutes": round(sum(learning_seconds(s) for s in mine) / 60),
    }


def overview(view: Mapping[str, Any], chapter: Chapter, folded: Folded) -> dict[str, Any]:
    """The student's (and the parent's) overview of an English unit: the subject, the patterns, the step,
    the typical mistakes of what to practise and of every node (DI-176: a node passed after many mistakes
    still shows them), the sessions studied."""
    return {
        **view,
        "chapter": chapter_ref(chapter),
        "chapters": chapter_refs(),
        "sessions": sessions_count(folded),
        "nodes": [
            {**n, "mistakes": mistakes(chapter, folded, n["node_id"]) or None}
            for n in _with_patterns(chapter, view["nodes"])
        ],
        "going_well": [
            {**n, "mistakes": mistakes(chapter, folded, n["node_id"]) or None}
            for n in _with_patterns(chapter, view["going_well"])
        ],
        "to_practise": _to_practise(chapter, folded, view["to_practise"])
        + _passed_with_mistakes(chapter, folded, view),
        "current_step": current_step(folded),
    }


def _passed_with_mistakes(chapter: Chapter, folded: Folded, view: Mapping[str, Any]) -> list[dict[str, Any]]:
    """ENG-5i (DI-186): a node passed after mistakes is also said where the mistakes are ("Có lúc nhầm: …"),
    after the nodes still to practise, so a parent reads them in one place (the third live run: VOCAB and PAST
    passed with "seafod", "bot", "eated" and only the node being learnt was there)."""
    listed = {r["node_id"] for r in view["to_practise"]}
    out = []
    for row in _with_patterns(chapter, view["nodes"]):
        if not row.get("passed") or row["node_id"] in listed:
            continue
        found = mistakes(chapter, folded, row["node_id"])
        if found:
            topic = {k: row[k] for k in ("node_id", "name", "quality", "pattern") if k in row}
            out.append({**topic, "reason": mistake_reason(found), "mistakes": found})
    return out


def parent(view: Mapping[str, Any], folded: Folded | None = None) -> dict[str, Any]:
    """The parent's view of an English unit: each home tip with its sentence to say at home (DI-144); the
    list of sessions without the ones the child did not study in (DI-176)."""
    out = {**view, "home_tips": [{**t, "example": home_example(t["tip"])} for t in view["home_tips"]]}
    if folded is not None and "session_list" in view:
        kept = {s.id for s in folded.sessions if studied(s)}
        out["session_list"] = [r for r in view["session_list"] if r["session_id"] in kept]
    return out


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
        "nodes": [{**n, "mistakes": mistakes(chapter, folded, n["node_id"]) or None} for n in view["nodes"]],
        "voice_turns": voice_turn_list(chapter, folded),
    }
