"""English sessions of Unit 11 for the report tests (ENG-7b), offline.

The English session path is ENG-5b; until it is merged, a session of the unit cannot be started through the
API. These helpers make the same event log the API would store:

- the real teaching loop of ``teaching.loop`` runs the real unit (``docs/pedagogy/english-g5``) with a
  scripted learner, offline and with templates only: its decisions, items, gradings and resolutions;
- the spoken turns are synthetic: on the answers chosen by the test, the STUDENT_MESSAGE becomes
  ``modality: VOICE``, a VOICE_TURN_RECORDED (ADR-064) follows it with the q the test gives, and the
  ITEM_RESOLVED that answer decided carries ``modality: VOICE`` and that q, as ``session.voice_turns`` does;
- the log is stored as a chapter session of the unit through the real repository.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cavat.core.events import EventType, VoiceTurnRecorded
from cavat.modules.session import chapter_service
from cavat.modules.session.repository import LearningSession, LearningSessionRepository, NewEvent
from cavat.modules.session.service import DEMO_SCHOOL_ID
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from cavat.modules.tutor.item_loop import Phase
from cavat.modules.voice.turns import student_hash

UNIT_ID = "eng-g5-u11-family-time"
UNIT = chapter_service.chapters("english")[UNIT_ID]
T0 = datetime(2026, 11, 12, 1, 0, tzinfo=UTC)  # 08:00 in Hà Nội
TODAY = (T0 + timedelta(hours=7)).date()
EXPLAINING = (Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON)
AUDIO = b"\x1aE\xdf\xa3 opus of a child"


def right(item_id: str) -> str:
    """A right answer of an item of the unit, from its approved answer."""
    ans = UNIT.item(item_id).answer
    if ans.type == "choice":
        return next(o.id for o in ans.options if o.correct)
    if ans.type == "phrase":
        return ans.accept[0] if ans.accept else " ".join(group[0] for group in ans.required)
    if ans.type == "word_order":
        return " ".join(ans.accept[0])
    if ans.type == "boolean":
        return "đúng" if ans.value else "sai"
    return getattr(ans, "sample_answer", "")


@dataclass
class Learner:
    """Answers right, except the items of ``wrong`` the first time (with the wrong words given)."""

    wrong: dict[str, str] = field(default_factory=dict)
    _done: set[str] = field(default_factory=set)

    def reply(self, turn: Any) -> str:
        if turn.awaiting == Awaiting.THEORY_REPLY:
            variant = next(t for t in UNIT.node(turn.node_id).theory if t.ask == turn.prompt)
            return variant.accept[0]
        if turn.awaiting == Awaiting.RETELL:
            return ". ".join(ideas[0] for ideas in UNIT.node(turn.node_id).explain.key_ideas)
        item = UNIT.item(turn.item_id)
        if turn.item_phase in EXPLAINING:
            return item.explanation or "Vì con làm theo mẫu cô dạy."
        if turn.item_id in self.wrong and turn.item_id not in self._done:
            self._done.add(turn.item_id)
            return self.wrong[turn.item_id]
        return right(turn.item_id)


def converse(learner: Learner, start: datetime, turns: int) -> list[Any]:
    """The events of the real teaching loop over ``turns`` replies of the learner, ten seconds apart."""
    loop = TeachingLoop(UNIT, "draft")
    said = [loop.start(start)]
    while len(said) <= turns and said[-1].awaiting != Awaiting.NOTHING:
        now = start + timedelta(seconds=10 * len(said))
        said.append(loop.on_student(learner.reply(said[-1]), now, seconds=10))
    return list(loop.events)


def audio_ref(student: str, at: datetime, n: int) -> str:
    uuid = hashlib.sha256(f"{student}-{at.isoformat()}-{n}".encode()).hexdigest()[:32]
    return f"in/{at.date().isoformat()}/{student_hash(student)}/{uuid}.webm"


def voiced(
    events: list[Any], student: str, qs: list[float | None], voice_dir: Path | None = None
) -> list[Any]:
    """The log with its first ``len(qs)`` answers to an item said aloud, the n-th heard with q ``qs[n]``.

    The language is the item's: ``en`` for an answer in English, ``vi`` otherwise (rule V2). The recording
    is written under ``voice_dir`` when given."""
    out: list[Any] = []
    last_voice: dict[str, float | None] = {}  # item -> q of its last spoken answer (None: typed)
    n = 0
    for e in events:
        kind = str(e.event_type)
        if kind == EventType.ITEM_RESOLVED and e.payload["item_id"] in last_voice:
            q = last_voice[e.payload["item_id"]]
            if q != "TEXT":
                e = replace(e, payload={**e.payload, "modality": "VOICE", "asr_confidence": q})
        if kind != EventType.STUDENT_MESSAGE or e.payload["kind"] != "ANSWER":
            out.append(e)
            continue
        item_id = e.payload["item_id"]
        if n >= len(qs):
            last_voice[item_id] = "TEXT"
            out.append(e)
            continue
        q = qs[n]
        ref = audio_ref(student, e.occurred_at, n)
        language = "en" if UNIT.item(item_id).response_language == "en" else "vi"
        out.append(replace(e, payload={**e.payload, "modality": "VOICE"}))
        turn = VoiceTurnRecorded(
            school_id=DEMO_SCHOOL_ID,
            voice_turn_id=f"{e.occurred_at.date().isoformat()}/{ref[-37:-5]}",
            message_ref=item_id,
            audio_ref=ref,
            language=language,
            asr_confidence=q,
            model="whisper-large-v3",
            heard=e.payload["text"],
        )
        out.append(replace(e, event_type=EventType.VOICE_TURN_RECORDED, payload=turn.model_dump(mode="json")))
        if voice_dir is not None:
            path = voice_dir / ref
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(AUDIO)
        last_voice[item_id] = q
        n += 1
    return out


async def store(database: Any, student: str, name: str, events: list[Any], school: str = DEMO_SCHOOL_ID):
    """The log as a chapter session of the unit, through the real repository."""
    session = chapter_service.new_session(UNIT, school, student, name)
    new = [
        NewEvent(
            event_type=str(e.event_type),
            payload=e.payload,
            actor=chapter_service.actor_for(EventType(str(e.event_type)), student),
            occurred_at=e.occurred_at,
        )
        for e in events
    ]
    created: LearningSession = await LearningSessionRepository(database, school).create(session, new)
    return created
