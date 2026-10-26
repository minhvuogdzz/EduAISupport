"""Teaching loop (M1-6): runs the teaching cycle on the chapter graph, one student input at a time.

The node policy decides every step; this loop carries it out. It phrases theory, worked examples, the
retell prompt and the transitions with templates, runs the item loop (``ItemTutor``) for every item, judges
retells with the rubric, and records the session's events. After each input it advances on its own until the
student has something to do.

Grounded speech (RAG-2, ``grounded.py``), when a ``speaker`` is given for the live turn: a question the child
asks while a theory question or a retell waits is answered from the passages the Hybrid RAG retrieves (or
kept for the teacher when nothing grounds it), and the reply to a theory answer starts with one sentence on
what the child said, before the approved explanation. Both are checked against their sources.

The state lives in the events only. ``TeachingLoop.resume`` rebuilds a loop from them: the teaching
state is a fold of the events, and the open item replays its inputs with templates, as the session
service already does, so past turns never call a model again.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from cavat.core.events import (
    ChoiceMade,
    EventType,
    HintRequested,
    ItemRestarted,
    MessageRead,
    NodeDecisionMade,
    QuestionParked,
    RagRetrieved,
    RetellJudged,
    SafetyFlagged,
    StudentMessage,
    TeachMessageSent,
    WebLooked,
)
from cavat.core.pedagogy import ITEM_ACTIONS, ActivityType, ItemResolution, Outcome, TeachAction
from cavat.modules.assessment.math_checker import classify_intent
from cavat.modules.assessment.projector import DEFAULT_POLICY, MasteryPolicy, project_chapter
from cavat.modules.assessment.retell import judge_retell
from cavat.modules.assessment.student_intent import (
    expand_short_forms,
    intent_of_guess,
    is_affirmation,
    is_gibberish_or_ambiguous_short,
    known_words,
    signals_distress,
    without_subject,
)
from cavat.modules.assessment.vi_numbers import normalize_text, phrase_regex
from cavat.modules.content.chapter_package import Chapter, Node, TheoryVariant
from cavat.modules.teaching.grounded import GroundedSpeaker, Spoken, retrieval_payload
from cavat.modules.teaching.node_policy import decide
from cavat.modules.teaching.state import DEFAULT_CONFIG, NodePolicyConfig, teaching_state
from cavat.modules.teaching.web import WEB_VERSION, web_query
from cavat.modules.tutor.chooser import MoveChooser, recorded_choices
from cavat.modules.tutor.contracts import MessageRenderer, MessageValidator, StudentSnapshot
from cavat.modules.tutor.item_loop import (
    CHOICE_HINT,
    CHOICE_RETRY,
    CHOICES,
    CONFIRMED_TEXT,
    HINT_REQUEST_TEXT,
    ItemTutor,
    Phase,
    TutorEvent,
)
from cavat.modules.tutor.reader import (
    MAX_INTENT_READS_PER_ITEM,
    ContextReader,
    clarification_problems,
    read_unclear,
    recorded,
)
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message

# 0.6.0: REFORM-5 (DI-76), a few unreadable letters at a theory question or a retell are asked about once
# 0.5.0: DI-53 hint from the earlier node; 0.4.0: DI-52
TEMPLATES_VERSION = "teaching-templates/0.6.0"

RECALL = "RECALL"  # the ref of a recall wait (DI-52)
RECALL_HINT = "RECALL_HINT"  # the ref of the reminder of an earlier node after a wrong answer (DI-53)
# REFORM-5: the ref of the question "con muốn nói gì?" asked about a few unreadable letters
CONFIRM_REF = "ASK_CONFIRM"

# DI-38: how many times talk outside the lesson is parked before the tutor explains and goes on.
MAX_OFF_TOPIC_REDIRECTS = 2
# DI-39: questions of the child answered (or kept for the teacher) while one theory question or retell waits.
MAX_QUESTIONS_PER_WAIT = 2
# Intents that keep their own path even when phrased as a question (ADR-019): "cho con đáp án là gì?" is a
# demand for the answer, "sao con ngu thế?" a feeling, "cô thích đá bóng không?" talk outside the lesson.
_OWN_PATH = frozenset({Outcome.OFF_TOPIC, Outcome.ANSWER_DEMAND, Outcome.NEGATIVE_AFFECT})

# Item phases where the student answers in words ("vì sao", teach-back, "con làm thế nào?").
_WORDS = frozenset({Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON})

# Guard: decisions taken without a student input in between (a node holds about ten steps).
MAX_AUTO_STEPS = 60

ACTIVITY_FOR: dict[TeachAction, ActivityType] = {
    TeachAction.WARMUP_ITEM: ActivityType.WARMUP_REVIEW,
    TeachAction.REVIEW_ITEM: ActivityType.WARMUP_REVIEW,
    TeachAction.CHECK_ITEM: ActivityType.CONCEPT_CHECK,
    TeachAction.COMPLETION_ITEM: ActivityType.GUIDED_PRACTICE,
    TeachAction.PRACTICE_ITEM: ActivityType.GUIDED_PRACTICE,
    TeachAction.TRANSFER_ITEM: ActivityType.INDEPENDENT_PRACTICE,
}

# Teaching templates (versioned with TEMPLATES_VERSION). {T}/{t}: the tutor ("Cô"/"cô"), {S}/{s}: the student.
PHRASES: dict[str, str] = {
    "enter": "Bây giờ {t} và {s} cùng học: {name}.",
    "resume": "Mình quay lại bài {name} nhé.",
    "switch": "Trước khi học tiếp, mình ôn lại {name} một chút nhé.",
    "warmup": "Trước tiên, {s} trả lời nhanh một câu ôn bài cũ nhé.",
    "review": "Mình ôn lại bài cũ một chút nhé.",
    "transfer": "Bây giờ {s} thử một bài vận dụng nhé.",
    "theory_ack": "{T} cảm ơn {s}.",
    # ADR-019 (drafted for the owner's review): the reply to the question that ends a theory explanation.
    "theory_right": "Đúng rồi! {reply}",
    "theory_check": "Mình cùng xem lại nhé: {reply}",
    "theory_explain": "Không sao đâu, {t} giải thích nhé: {reply}",
    "theory_affect": "{T} hiểu, phần này hơi khó một chút. {T} giải thích nhé: {reply}",
    "off_topic": "Chuyện đó để lúc nghỉ mình nói nhé! {ask}",
    # RAG-2 (drafted for the owner's review, DI-39): a question of the child while a question waits.
    "theory_check_lead": "Mình cùng xem lại nhé:",
    "question_back": "Mình quay lại câu của {t} nhé: {ask}",
    "question_parked": (
        "{T} chưa tìm được câu trả lời chắc chắn trong tài liệu của bài, {t} ghi lại để thầy cô trên lớp "
        "giải đáp cho {s} nhé. "
        "Mình quay lại câu của {t}: {ask}"
    ),
    "question_same": "Đó chính là câu {t} đang hỏi {s} đấy! {S} thử nghĩ xem nhé: {ask}",
    "question_later": (
        "Câu này mình sẽ học ở bài {name}, tới bài đó {t} giảng kỹ cho {s} nhé. "
        "Mình quay lại câu của {t}: {ask}"
    ),
    # DI-41 (drafted for the owner's review): the child says something worrying.
    "distress": (
        "{T} nghe {s} nói rồi. Chuyện này quan trọng lắm: {s} hãy kể ngay với thầy cô hoặc bố mẹ, "
        "người lớn mà {s} tin nhé. {T} ghi lại để thầy cô biết."
    ),
    # REFORM-5 (DI-76, drafted for the owner's review): the same two questions as the item loop's, for a
    # theory question or a retell that waits.
    "confirm_typo": "{T} đoán {s} muốn nói là {s} {meaning}, đúng không, hay {s} định gõ ý khác?",
    "confirm_mash": "Hình như bàn phím của {s} vừa gõ ra mấy chữ lạ. {S} gõ lại ý của mình giúp {t} nhé?",
    "question_limit": (
        "{T} ghi lại các câu {s} hỏi để mình nói sau nhé. Bây giờ {s} trả lời câu của {t}: {ask}"
    ),
    # DI-52 (drafted for the owner's review): asking back a related node learnt before, then the bridge.
    "recall_ask": "bài {prior} cho {s} biết những điều gì?",
    "recall": "Bài {name} dùng tới bài {prior} mình đã học. {S} nhớ lại giúp {t} nhé: {ask}",
    "recall_check": "Mình cùng nhớ lại bài {prior} một chút nhé, nó giúp {s} hiểu bài này: {ask}",
    "recall_good": "Đúng rồi, {s} nhớ bài cũ tốt lắm! Mình dùng điều đó cho bài {name} nhé.",
    "recall_partial": (
        "{S} nhớ được một phần rồi. {T} nhắc lại nhé: {idea} Mình dùng điều đó cho bài {name} nhé."
    ),
    "recall_help": "Không sao đâu, {t} nhắc lại bài cũ nhé: {idea} Mình dùng điều đó cho bài {name} nhé.",
    # DI-53 (drafted for the owner's review): after a first wrong answer, the idea of the node it rests on.
    "recall_hint": "Gợi ý từ bài cũ: ở bài {prior}, mình đã học: {idea}",
    "retell_help": "Không sao đâu, {t} nhắc lại ý chính nhé: {idea}",
    "retell_affect": "{S} đã cố gắng nhiều rồi đấy. {T} nhắc lại ý chính nhé: {idea}",
    "retell_again": "{S} đã làm thêm nhiều bài rồi.",
    "retell_good": "{S} nói đúng ý rồi.",
    "retell_partial": "{S} đã nói được một phần ý.",
    "retell_none": "{T} chưa nghe thấy ý chính trong câu trả lời của {s}.",
    "example": "{T} làm mẫu cho {s} xem nhé.",
    "pass": "{S} đã hiểu bài {name} rồi. Giỏi lắm!",
    "stop": "Bài {name} mình tạm dừng ở đây. {T} sẽ ôn lại với {s} vào buổi sau nhé.",
    "summary_done": "Hôm nay {s} đã học xong: {names}.",
    "summary_review": "Còn cần ôn thêm: {names}.",
    "summary_none": "Hôm nay mình dừng ở đây nhé.",
    "summary_end": "{T} khen {s} đã cố gắng!",
}


# "Con nói lại giúp cô: ..." asks for a retell; for a recall only the question after it is kept (DI-52).
_RETELL_LEAD = re.compile(
    r"^[^:?]{0,40}\b(?:nói lại|kể lại|nhắc lại|giải thích lại)\b[^:?]{0,30}:\s*", re.IGNORECASE
)


def recall_question(node: Node) -> str | None:
    """The question of a node's retell prompt without its "nói lại giúp cô" lead, when it asks something of
    its own. None for a prompt that only names the node ("so sánh hai số thập phân thế nào?") or has no such
    lead: such a question is clear just after the theory, not later (seen on the published chapters)."""
    m = _RETELL_LEAD.match(node.explain.prompt)
    rest = node.explain.prompt[m.end() :].strip() if m else ""
    own = rest.lower().replace(node.name.lower(), "").replace("thế nào", "").strip(" ?.")
    return rest if own else None


def _bare_no(text: str) -> bool:
    """A reply that is only "không" or "chưa" ("ko", "k", "hông" included)."""
    words = [w for w in re.findall(r"\w+", expand_short_forms(text)) if w not in ("ạ", "a", "cô", "nhé")]
    return words in (["không"], ["chưa"])


def _yes_no(question: str) -> bool:
    """A question answered by yes or no ("... có dài hơn không?", "... chưa?")."""
    return bool(re.search(r"\b(không|chưa|phải không|đúng không)\s*\?\s*$", question.strip().lower()))


class Awaiting(StrEnum):
    """What the student is expected to do next."""

    ANSWER = "ANSWER"  # an item is open: the item loop reads the reply (answer, "vì sao", help...)
    THEORY_REPLY = "THEORY_REPLY"  # the question that ends a theory explanation
    RETELL = "RETELL"  # "con nói lại"
    NOTHING = "NOTHING"  # the session is finished


class MessageKind(StrEnum):
    NODE = "NODE"  # entering, resuming or switching a node
    THEORY = "THEORY"
    EXAMPLE = "EXAMPLE"
    ANSWER = "ANSWER"  # the reply to a question of the child (RAG-2)
    RETELL_PROMPT = "RETELL_PROMPT"
    FEEDBACK = "FEEDBACK"
    ITEM = "ITEM"  # a message of the item loop (question, hint, verify...)
    PASS = "PASS"
    STOP = "STOP"
    SUMMARY = "SUMMARY"


@dataclass(frozen=True)
class TeachMessage:
    kind: MessageKind
    text: str
    node_id: str | None = None
    ref: str | None = None  # theory variant, worked example or item id
    source: str = "TEMPLATE"  # TEMPLATE, LLM (checked against its sources) or EXTRACT (RAG-2)
    sources: tuple[str, ...] = ()
    rejected: tuple[tuple[str, ...], ...] = ()


# DI-66 (PRIOR-1): the hint dependency of the snapshot is the mean top hint level of the last items solved
# or closed, over this many (blueprint 05: "trung bình level gần đây").
RECENT_ITEMS = 10


@dataclass(frozen=True)
class LoopEvent:
    """An event of this session; the session service stores it as a ``SessionEvent``."""

    event_type: str
    payload: dict[str, Any]
    session_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class TeachTurn:
    """Everything the tutor does after one student input."""

    messages: tuple[TeachMessage, ...]
    events: tuple[LoopEvent, ...]
    awaiting: Awaiting
    item_id: str | None = None  # the open item when awaiting ANSWER
    item_phase: Phase | None = None
    choice_open: bool = False  # the item loop offered "gợi ý thêm hay tự thử lại?"
    node_id: str | None = None  # the node of the theory or retell being waited for
    prompt: str | None = None  # the question of a THEORY_REPLY or RETELL wait


class TeachingLoop:
    """Call ``start`` once (or ``resume``), then ``on_student`` / ``on_hint_request`` per input."""

    def __init__(
        self,
        chapter: Chapter,
        session_id: str,
        history: Iterable[Any] = (),
        *,
        item_renderer: MessageRenderer | None = None,
        validator: MessageValidator = validate_message,
        config: NodePolicyConfig = DEFAULT_CONFIG,
        mastery: MasteryPolicy = DEFAULT_POLICY,
        speaker: GroundedSpeaker | None = None,
        item_reader: ContextReader | None = None,
        item_chooser: MoveChooser | None = None,
    ) -> None:
        self.chapter, self.session_id = chapter, session_id
        self.speaker = speaker  # live turns only: a replay never calls the RAG or a model again
        self.item_reader = item_reader  # CTX-1: reads an unclear item message in context (live turns only)
        self.item_chooser = item_chooser  # AUTO-1: picks one of the moves the policy allows (live turns only)
        self._restart: str | None = None  # FIX-4: an item whose replay diverged starts again (its id)
        self.history = list(history)  # events of earlier sessions: the projection reads them too
        self.events: list[Any] = []  # events of this session
        self.item_renderer = item_renderer or TemplateRenderer()
        self.validator, self.config, self.mastery = validator, config, mastery
        self.tutor: ItemTutor | None = None
        self.awaiting: Awaiting | None = None
        self._node: str | None = None  # node of the theory or retell being waited for
        self._ref: str | None = None
        self._prompt: str | None = None
        self._for: str | None = None  # DI-52: the node a recall of an earlier node prepares
        self._retry = False  # "Con tự thử lại" closed the micro choice until the next input
        p = chapter.package.persona
        self._persona = {
            "t": p.tutor_self,
            "T": p.tutor_self[:1].upper() + p.tutor_self[1:],
            "s": p.student_address,
            "S": p.student_address[:1].upper() + p.student_address[1:],
        }

    # ------------------------------------------------------------------ public API

    @classmethod
    def resume(
        cls,
        chapter: Chapter,
        session_id: str,
        history: Iterable[Any],
        session_events: Sequence[Any],
        **kw: Any,
    ) -> TeachingLoop:
        """Rebuild the loop from the stored events of this session (templates only, no model call)."""
        loop = cls(chapter, session_id, history, **kw)
        loop.events = list(session_events)
        loop._restore()
        return loop

    def go_live(
        self,
        renderer: MessageRenderer | None = None,
        reader: ContextReader | None = None,
        speaker: GroundedSpeaker | None = None,
        chooser: MoveChooser | None = None,
    ) -> None:
        """What this turn may call (a model, the RAG); the replay before it used templates and records."""
        if renderer is not None:
            self.item_renderer = renderer
        self.item_reader, self.speaker, self.item_chooser = reader, speaker, chooser
        if self.tutor is not None:
            if renderer is not None:
                self.tutor.renderer = renderer
            self.tutor.reader = reader
            self.tutor.chooser = chooser
            self.tutor.explainer = self._explainer(self._item_node(self.tutor.item.id))

    def start(self, now: datetime) -> TeachTurn:
        if self.awaiting is not None:
            raise RuntimeError("the teaching loop has already started")
        return self._advance(now, [], [])

    def on_student(self, text: str, now: datetime, seconds: float = 0.0, modality: str = "TEXT") -> TeachTurn:
        if self.awaiting in (None, Awaiting.NOTHING):
            raise RuntimeError(f"no student input expected (awaiting {self.awaiting})")
        if self.awaiting == Awaiting.ANSWER:
            assert self.tutor is not None
            item_id = self.tutor.item.id
            if signals_distress(text):  # DI-41: care and the teacher first; not an attempt at the item
                # ":SAFETY" keeps the message out of the item's replay (``_restore`` replays the item's id).
                said = StudentMessage(
                    item_id=f"{item_id}:SAFETY", kind="MESSAGE", text=text, seconds=seconds, modality=modality
                )
                events = [self._record(now, EventType.STUDENT_MESSAGE, said)]
                flagged = SafetyFlagged(item_id=item_id, source="RULE")
                events.append(self._record(now, EventType.SAFETY_FLAGGED, flagged))
                messages: list[TeachMessage] = []
                care = TeachMessage(MessageKind.FEEDBACK, self._phrase("distress"), self._item_node(item_id))
                self._say(now, messages, events, care)
                return self._waiting_for_item(messages, events)
            kind = "EXPLANATION" if self.tutor.phase in _WORDS else "ANSWER"
            message = StudentMessage(
                item_id=item_id, kind=kind, text=text, seconds=seconds, modality=modality
            )
            return self._item_input(now, self._record(now, EventType.STUDENT_MESSAGE, message), text, seconds)
        assert self._node is not None
        node_id, kind = self._node, "MESSAGE" if self.awaiting == Awaiting.THEORY_REPLY else "EXPLANATION"
        ref = self._ref if self.awaiting == Awaiting.THEORY_REPLY else (self._ref or "RETELL")
        message = StudentMessage(
            item_id=f"{node_id}:{ref}", kind=kind, text=text, seconds=seconds, modality=modality
        )
        events = [self._record(now, EventType.STUDENT_MESSAGE, message)]
        messages: list[TeachMessage] = []
        said = self._confirmed(text)  # REFORM-5: "ừ" to a guess says what was guessed
        # a bare "không" answers a question that a no can answer ("... có dài hơn không?"), else it
        # is "con không biết"
        verdict = self.awaiting == Awaiting.THEORY_REPLY and _yes_no(self._prompt or "")
        intent = classify_intent(said, verdict=verdict)
        if signals_distress(text):  # DI-41: care and the teacher first, whatever else the message is
            flagged = SafetyFlagged(item_id=f"{node_id}:{self._ref or 'RETELL'}", source="RULE")
            events.append(self._record(now, EventType.SAFETY_FLAGGED, flagged))
            self._say(
                now, messages, events, TeachMessage(MessageKind.FEEDBACK, self._phrase("distress"), node_id)
            )
            return TeachTurn(
                tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=self._prompt
            )
        if intent is None and is_gibberish_or_ambiguous_short(text, known_words(self._prompt or "")):
            # REFORM-5 (3.1): "ki", "ể", "kkk" are neither the reply nor "con không biết". Asked once what
            # they meant (the question still waits, nothing is judged, nothing advances); as unreadable the
            # second time in a row, the child is helped as when they say "con không biết".
            if not self._confirm_open():
                return self._ask_confirm(text, now, node_id, messages, events)
            intent = Outcome.HELP_REQUEST
        if self.speaker is not None and intent not in _OWN_PATH and self.speaker.is_question(text):
            return self._on_question(text, now, node_id, messages, events)
        if intent == Outcome.OFF_TOPIC and self._replies_since_decision() <= MAX_OFF_TOPIC_REDIRECTS:
            # ADR-019: talk outside the lesson is parked and the same question asked again (DI-38).
            assert self._prompt is not None
            back = self._phrase("off_topic", ask=self._prompt)
            self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, back, node_id))
            return TeachTurn(
                tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=self._prompt
            )
        if self.awaiting == Awaiting.THEORY_REPLY:
            assert self._ref is not None
            variant = next(t for t in self.chapter.node(node_id).theory if t.id == self._ref)
            spoken = self._theory_feedback(variant, text, intent)
            self._flag(now, events, spoken, f"{node_id}:{self._ref}")
            feedback = TeachMessage(
                MessageKind.FEEDBACK, spoken.text, node_id, source=spoken.source, rejected=spoken.rejected
            )
            self._say(now, messages, events, feedback)
            return self._advance(now, messages, events)
        node = self.chapter.node(node_id)
        judged = judge_retell(node_id, text, node.explain)
        if self._ref == RECALL:
            return self._on_recall(judged, intent, now, messages, events)
        events.append(self._record(now, EventType.RETELL_JUDGED, judged))
        if intent is not None and not judged.ideas_found:
            # "Con không biết", "là sao ạ?", "chán quá": remind the main idea instead of only saying that
            # it was not heard; the node policy then asks again or moves on, as for any retell.
            key = "retell_affect" if intent == Outcome.NEGATIVE_AFFECT else "retell_help"
            said = self._phrase(key, idea=node.description)
        elif judged.score >= self.config.retell_pass:
            said = self._phrase("retell_good")
        else:
            said = self._phrase("retell_partial" if judged.ideas_found else "retell_none")
        self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, said, node_id))
        return self._advance(now, messages, events)

    def _confirm_open(self) -> bool:
        """REFORM-5: the last thing the tutor said, before the message being read, was the question about
        a few unreadable letters. Read from the events, so a resumed session knows it too."""
        for e in reversed(self.events[:-1]):  # the last event is the message being read
            if e.event_type == EventType.TEACH_MESSAGE_SENT:
                return e.payload.get("ref") == CONFIRM_REF
        return False

    def _confirmed(self, text: str) -> str:
        """REFORM-5: "ừ", "đúng rồi" after "cô đoán con muốn nói là con chưa biết làm, đúng không?" is read
        as the guess it confirms ("con không biết"); anywhere else it is read as typed."""
        if not is_affirmation(text) or not self._confirm_open():
            return text
        guess = next(
            (e.payload for e in reversed(self.events) if e.event_type == EventType.MESSAGE_READ), None
        )
        intent = intent_of_guess((guess or {}).get("guessed_meaning", ""))
        return CONFIRMED_TEXT[intent] if intent is not None else text

    def _ask_confirm(
        self, text: str, now: datetime, node_id: str, messages: list[TeachMessage], events: list[LoopEvent]
    ) -> TeachTurn:
        """REFORM-5 (3.1): ask what a few unreadable letters meant, in the question's own wait. The reading
        (a rule's, or the model's guess and question) is recorded; the question the model proposed is said
        only if ``clarification_problems`` finds nothing wrong with it."""
        ref = f"{node_id}:{self._ref or 'RETELL'}"
        turn = self._replies_since_decision()
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=-1
        )
        spent = sum(
            1
            for e in self.events[last + 1 :]
            if e.event_type == EventType.MESSAGE_READ and e.payload.get("source") == "LLM"
        )
        reading = read_unclear(
            self.item_reader,
            stem=self._prompt or "",
            last_tutor=self._prompt or "",
            said=text,
            turn=turn,
            allow_model=spent < MAX_INTENT_READS_PER_ITEM,
        )
        events.append(
            self._record(
                now,
                EventType.MESSAGE_READ,
                MessageRead(
                    item_id=ref,
                    turn=turn,
                    label=reading.label,  # type: ignore[arg-type]
                    source=reading.source,
                    guessed_meaning=reading.guessed_meaning,
                    clarification=reading.clarification,
                ),
            )
        )
        question, source = reading.clarification, "LLM"
        if not question or clarification_problems(question, self._persona["s"]):
            meaning = without_subject(reading.guessed_meaning)
            if reading.label == "AMBIGUOUS_TYPO" and meaning:
                question = self._phrase("confirm_typo", meaning=meaning)
            else:
                question = self._phrase("confirm_mash")
            source = "TEMPLATE"
        self._say(
            now, messages, events, TeachMessage(MessageKind.FEEDBACK, question, node_id, CONFIRM_REF, source)
        )
        return TeachTurn(tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=self._prompt)

    def _on_recall(
        self,
        judged: RetellJudged,
        intent: Outcome | None,
        now: datetime,
        messages: list[TeachMessage],
        events: list[LoopEvent],
    ) -> TeachTurn:
        """DI-52: the recall of an earlier node is judged like a retell (evidence on that node), then bridged
        to the node being learnt; a recall not good enough gets the earlier node's main idea first."""
        judged = judged.model_copy(update={"purpose": RECALL})
        events.append(self._record(now, EventType.RETELL_JUDGED, judged))
        prior = self.chapter.node(judged.node_id)
        name = self.chapter.node(self._for).name if self._for else prior.name
        if judged.score >= self.config.retell_pass:
            said = self._phrase("recall_good", name=name)
        elif judged.ideas_found and intent is None:
            said = self._phrase("recall_partial", idea=prior.description, name=name)
        else:
            said = self._phrase("recall_help", idea=prior.description, name=name)
        self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, said, prior.id, RECALL))
        return self._advance(now, messages, events)

    def _recall_ask(self, prior_id: str) -> str:
        prior = self.chapter.node(prior_id)
        return recall_question(prior) or self._phrase("recall_ask", prior=prior.name)

    def _theory_feedback(self, variant: TheoryVariant, text: str, intent: Outcome | None) -> Spoken:
        """Right, not quite, or no attempt: the reason (`reply`) in each case. Never graded (ADR-019).

        An attempt that is not right gets, with a speaker, one sentence on what the child said before the
        approved reply (RAG-2): the reply itself stays word for word.
        """
        if not variant.reply:
            return Spoken(self._phrase("theory_ack"), "TEMPLATE")
        if intent == Outcome.NEGATIVE_AFFECT:
            return Spoken(self._phrase("theory_affect", reply=variant.reply), "TEMPLATE")
        if intent is not None or (_bare_no(text) and not _yes_no(variant.ask)):
            # "ko" to "phân số nào?" is "con không biết" (seen live), not a wrong answer; to "có dài hơn
            # không?" it is an answer and goes on to the check below.
            return Spoken(self._phrase("theory_explain", reply=variant.reply), "TEMPLATE")
        accept = phrase_regex(variant.accept) if variant.accept else None
        # "ko" is "không": the short forms children type count as the words they stand for
        right = accept is not None and any(
            accept.search(t) for t in (normalize_text(text), expand_short_forms(text))
        )
        if right:
            return Spoken(self._phrase("theory_right", reply=variant.reply), "TEMPLATE")
        judged, lead = ("chưa đúng", "theory_check_lead") if variant.accept else ("chưa rõ", "theory_ack")
        if self.speaker is None:
            return Spoken(f"{self._phrase(lead)} {variant.reply}", "TEMPLATE")
        return self.speaker.bridge(
            text, asked=variant.ask, explanation=variant.reply, judged=judged, lead=self._phrase(lead)
        )

    def _on_question(
        self, text: str, now: datetime, node_id: str, messages: list[TeachMessage], events: list[LoopEvent]
    ) -> TeachTurn:
        """A question of the child while a theory question or a retell waits (RAG-2, DI-39): answered from the
        retrieved passages, or kept for the teacher; then the question that waits is asked again."""
        assert self.speaker is not None and self._prompt is not None
        ask, ref = self._prompt, f"{node_id}:{self._ref or 'RETELL'}"
        if self._answers_since_decision() >= MAX_QUESTIONS_PER_WAIT:
            parked = QuestionParked(node_id=node_id, text=text, reason="LIMIT")
            events.append(self._record(now, EventType.QUESTION_PARKED, parked))
            said = TeachMessage(MessageKind.ANSWER, self._phrase("question_limit", ask=ask), node_id)
        else:
            hide = []
            if self.awaiting == Awaiting.THEORY_REPLY and self._ref is not None:
                variant = next(t for t in self.chapter.node(node_id).theory if t.id == self._ref)
                hide = [variant.reply]  # the question that waits keeps its answer to itself
            turn = self.speaker.answer(text, node_id=node_id, pending=ask, hide=hide, recent=self._recent(4))
            if turn.retrieval is not None:
                payload = RagRetrieved(**retrieval_payload(turn.retrieval, "QUESTION", node_id))
                events.append(self._record(now, EventType.RAG_RETRIEVED, payload))
            if turn.web is not None:  # WEB-1: what was looked up, and whether the child heard it
                looked = WebLooked(
                    node_id=node_id,
                    query=web_query(text),
                    source=self.speaker.web.name if self.speaker.web else "",
                    title=turn.web.title,
                    url=turn.web.url,
                    answered=turn.kind == "ANSWERED",
                    version=WEB_VERSION,
                )
                events.append(self._record(now, EventType.WEB_LOOKED, looked))
            if turn.kind == "ANSWERED":
                assert turn.spoken is not None
                self._flag(now, events, turn.spoken, ref)
                said = TeachMessage(
                    MessageKind.ANSWER,
                    f"{turn.spoken.text} {self._phrase('question_back', ask=ask)}",
                    node_id,
                    source=turn.spoken.source,
                    sources=turn.spoken.sources,
                    rejected=turn.spoken.rejected,
                )
            else:
                reason = {"PARKED": "NOT_GROUNDED", "SAME_AS_CHECK": "SAME_AS_CHECK", "LATER": "LATER"}[
                    turn.kind
                ]
                parked = QuestionParked(node_id=node_id, text=text, reason=reason, later_node=turn.later_node)
                events.append(self._record(now, EventType.QUESTION_PARKED, parked))
                if turn.kind == "LATER":
                    assert turn.later_node is not None
                    name = self.chapter.node(turn.later_node).name
                    said = TeachMessage(
                        MessageKind.ANSWER, self._phrase("question_later", name=name, ask=ask), node_id
                    )
                else:
                    key = "question_parked" if turn.kind == "PARKED" else "question_same"
                    said = TeachMessage(MessageKind.ANSWER, self._phrase(key, ask=ask), node_id)
        self._say(now, messages, events, said)
        return TeachTurn(tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=ask)

    def _recent(self, n: int) -> list[tuple[str, str]]:
        """The last ``n`` turns before the message being answered: (role, text), oldest first."""
        said = []
        for e in self.events[:-1]:  # the last event is the message being answered
            if e.event_type in (EventType.TEACH_MESSAGE_SENT, EventType.TUTOR_MESSAGE_SENT):
                said.append(("tutor", e.payload.get("text", "")))
            elif e.event_type == EventType.STUDENT_MESSAGE:
                said.append(("student", e.payload.get("text", "")))
        return said[-n:]

    def _answers_since_decision(self) -> int:
        """Replies to the child's questions since the last teaching decision."""
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=-1
        )
        return sum(
            1
            for e in self.events[last + 1 :]
            if e.event_type == EventType.TEACH_MESSAGE_SENT and e.payload.get("kind") == MessageKind.ANSWER
        )

    def _flag(self, now: datetime, events: list[LoopEvent], spoken: Spoken, ref: str) -> None:
        """The model judged the child's words worrying (constitution rule 8): for the teacher to review."""
        if spoken.safety_flag:
            events.append(self._record(now, EventType.SAFETY_FLAGGED, SafetyFlagged(item_id=ref)))

    def _replies_since_decision(self) -> int:
        """Student messages since the last teaching decision, the current one included."""
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=-1
        )
        return sum(1 for e in self.events[last + 1 :] if e.event_type == EventType.STUDENT_MESSAGE)

    def on_hint_request(self, now: datetime, seconds: float = 0.0) -> TeachTurn:
        if self.awaiting != Awaiting.ANSWER or self.tutor is None:
            raise RuntimeError("a hint needs an open item")
        requested = HintRequested(item_id=self.tutor.item.id, seconds=seconds)
        return self._item_input(
            now, self._record(now, EventType.HINT_REQUESTED, requested), HINT_REQUEST_TEXT, seconds
        )

    def on_choice(self, choice_id: str, now: datetime, seconds: float = 0.0) -> TeachTurn:
        """A micro choice after OFFER_CHOICE: HINT asks for the next hint, RETRY only closes the choice
        (the item loop already reads the next message as a normal attempt)."""
        if not self.choice_open or choice_id not in CHOICES:
            raise RuntimeError(f"choice {choice_id!r} is not open")
        assert self.tutor is not None
        made = ChoiceMade(item_id=self.tutor.item.id, choice_id=choice_id, label=CHOICES[choice_id])
        recorded = self._record(now, EventType.CHOICE_MADE, made)
        if choice_id == CHOICE_RETRY:
            self._retry = True
            return self._waiting_for_item([], [*self._restart_mark(now, recorded), recorded])
        return self._item_input(now, recorded, HINT_REQUEST_TEXT, seconds)

    @property
    def choice_open(self) -> bool:
        return self.tutor is not None and self.tutor.phase == Phase.AWAITING_CHOICE and not self._retry

    def projection(self):
        return project_chapter([*self.history, *self.events], self.chapter, self.mastery)

    # ------------------------------------------------------------------ steps

    def _restart_mark(self, now: datetime, recorded: LoopEvent) -> list[LoopEvent]:
        """FIX-4: the ITEM_RESTARTED mark of an item that starts again, put before this input."""
        if self._restart is None:
            return []
        mark = self._event(now, EventType.ITEM_RESTARTED, ItemRestarted(item_id=self._restart))
        self.events.insert(self.events.index(recorded), mark)
        self._restart = None
        return [mark]

    def _item_input(self, now: datetime, recorded: LoopEvent, text: str, seconds: float) -> TeachTurn:
        assert self.tutor is not None
        self._retry = False
        marks = self._restart_mark(now, recorded)
        turn = self.tutor.on_student(text, seconds)
        events = [*marks, recorded, *self._tutor_events(now, turn.events)]
        item_id = self.tutor.item.id
        node_id = self._item_node(item_id)
        messages = [TeachMessage(MessageKind.ITEM, turn.text, node_id, item_id)]
        if not turn.resolved:
            prior = self._hint_from_earlier(item_id, node_id, turn.events)
            if prior is not None:
                idea = self.chapter.node(prior).description
                text = self._phrase("recall_hint", prior=self.chapter.node(prior).name, idea=idea)
                self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, text, prior, RECALL_HINT))
            return self._waiting_for_item(messages, events)
        self.tutor = None
        return self._advance(now, messages, events)

    def _advance(self, now: datetime, messages: list[TeachMessage], events: list[LoopEvent]) -> TeachTurn:
        """Decide and carry out steps until the student has something to do. Every event created here
        is already in ``self.events``; ``events`` collects the ones of this turn."""
        for _ in range(MAX_AUTO_STEPS):
            state = teaching_state(self.events, self.config)
            decision = decide(self.chapter, self.projection(), state, self.config)
            events.append(self._record(now, EventType.NODE_DECISION, decision))
            waiting = self._carry_out(decision, now, messages, events)
            if waiting is not None:
                return waiting
        raise RuntimeError("the node policy took too many steps without a student input")

    def _carry_out(
        self, d: NodeDecisionMade, now: datetime, messages: list[TeachMessage], events: list[LoopEvent]
    ) -> TeachTurn | None:
        a, node_id = d.action, d.node_id
        name = self.chapter.node(node_id).name if node_id else ""

        def say(message: TeachMessage) -> None:
            self._say(now, messages, events, message)

        if a == TeachAction.ENTER_NODE:
            key = "resume" if "RESUME" in d.reason_codes else "enter"
            say(TeachMessage(MessageKind.NODE, self._phrase(key, name=name), node_id))
        elif a == TeachAction.SWITCH_TO_PREREQUISITE:
            say(TeachMessage(MessageKind.NODE, self._phrase("switch", name=name), node_id))
        elif a == TeachAction.TEACH_THEORY:
            variant = next(t for t in self.chapter.node(node_id).theory if t.id == d.ref)
            say(TeachMessage(MessageKind.THEORY, f"{variant.text} {variant.ask}", node_id, d.ref))
            return self._wait(Awaiting.THEORY_REPLY, node_id, d.ref, variant.ask, messages, events)
        elif a == TeachAction.ASK_RETELL:
            prompt = self.chapter.node(node_id).explain.prompt
            if "EXPLANATION_MISSING" in d.reason_codes:
                prompt = f"{self._phrase('retell_again')} {prompt}"
            say(TeachMessage(MessageKind.RETELL_PROMPT, prompt, node_id))
            return self._wait(Awaiting.RETELL, node_id, None, prompt, messages, events)
        elif a == TeachAction.RECALL_PRIOR:
            assert d.ref is not None and node_id is not None
            ask = self._recall_ask(d.ref)
            key = "recall_check" if "CHECK_FAILED" in d.reason_codes else "recall"
            text = self._phrase(key, name=name, prior=self.chapter.node(d.ref).name, ask=ask)
            say(TeachMessage(MessageKind.RETELL_PROMPT, text, d.ref, RECALL))
            self._for = node_id
            return self._wait(Awaiting.RETELL, d.ref, RECALL, ask, messages, events)
        elif a == TeachAction.SHOW_WORKED_EXAMPLE:
            example = next(w for w in self.chapter.node(node_id).worked_examples if w.id == d.ref)
            steps = "\n".join(f"Bước {i}: {step}" for i, step in enumerate(example.steps, 1))
            text = f"{self._phrase('example')}\nBài: {example.problem}\n{steps}\nĐáp số: {example.answer}."
            say(TeachMessage(MessageKind.EXAMPLE, text, node_id, d.ref))
        elif a in ITEM_ACTIONS:
            intro = {TeachAction.WARMUP_ITEM: "warmup", TeachAction.REVIEW_ITEM: "review"}.get(a)
            intro = intro or ("transfer" if a == TeachAction.TRANSFER_ITEM else None)
            if intro:
                say(TeachMessage(MessageKind.NODE, self._phrase(intro), node_id))
            return self._open_item(d, now, messages, events)
        elif a == TeachAction.PASS_NODE:
            say(TeachMessage(MessageKind.PASS, self._phrase("pass", name=name), node_id))
        elif a == TeachAction.STOP_NODE:
            say(TeachMessage(MessageKind.STOP, self._phrase("stop", name=name), node_id))
        elif a == TeachAction.FINISH:
            say(TeachMessage(MessageKind.SUMMARY, self._summary()))
            self.awaiting = Awaiting.NOTHING
            return TeachTurn(tuple(messages), tuple(events), Awaiting.NOTHING)
        return None

    def _open_item(
        self, d: NodeDecisionMade, now: datetime, messages: list[TeachMessage], events: list[LoopEvent]
    ) -> TeachTurn:
        assert d.ref is not None
        self.tutor = self._new_tutor(d)
        turn = self.tutor.start()
        events.extend(self._tutor_events(now, turn.events))
        messages.append(TeachMessage(MessageKind.ITEM, turn.text, self._item_node(d.ref), d.ref))
        return self._waiting_for_item(messages, events)

    def _new_tutor(
        self, d: NodeDecisionMade, reader: ContextReader | None = None, chooser: MoveChooser | None = None
    ) -> ItemTutor:
        assert d.ref is not None
        item, lesson = self.chapter.item(d.ref), self.chapter.lesson_of(d.ref)
        first_on_kc, kc_mastery, snapshot = self._kc_facts(d.ref)
        return ItemTutor(
            item,
            lesson,
            ACTIVITY_FOR[d.action],
            self.item_renderer,
            self.validator,
            reader=reader or self.item_reader,
            explainer=self._explainer(self._item_node(d.ref)),
            chooser=chooser or self.item_chooser,
            first_on_kc=first_on_kc,
            kc_mastery=kc_mastery,
            snapshot=snapshot,
        )

    def _kc_facts(self, item_id: str) -> tuple[bool, float | None, StudentSnapshot]:
        """DI-65: is no item of this session solved yet on one of the item's KCs, and the mastery of its node.
        PRIOR-1 (DI-66): the Student Model snapshot the policy's R-STRONG-PRIOR and R-WEAK-PRIOR read
        (blueprint 25.3: frozen at the start, updated within the session), from the same projection.
        Read from the events up to the item's decision, which is the last one live and on a rebuild alike."""
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=-1
        )
        before = self.events[: last + 1]
        solved = {
            k
            for e in before
            if e.event_type == EventType.ITEM_RESOLVED
            and e.payload.get("resolution") in (ItemResolution.INDEPENDENT, ItemResolution.SUPPORTED)
            for k in e.payload.get("kc_ids", [])
        }
        first = any(k not in solved for k in self.chapter.item(item_id).kc_ids)
        node = self._item_node(item_id)
        nodes = project_chapter([*self.history, *before], self.chapter, self.mastery).nodes
        state = nodes.get(node or "")
        mastery = state.mastery / 100 if state is not None and state.mastery is not None else None
        known = {k: n for k, n in nodes.items() if n.mastery is not None}
        levels = [
            e.payload.get("max_hint_level", 0)
            for e in [*self.history, *before]
            if e.event_type == EventType.ITEM_RESOLVED
        ][-RECENT_ITEMS:]
        snapshot = StudentSnapshot(
            kc_mastery={k: n.mastery / 100 for k, n in known.items()},
            kc_confidence={k: n.confidence / 100 for k, n in known.items()},
            hint_dependency=sum(levels) / len(levels) / 7 if levels else 0.0,
        )
        return first, mastery, snapshot

    def _explainer(self, node_id: str | None) -> Callable[[str, str], Sequence[str]] | None:
        """Approved passages on what the child asks about in an item (CTX-1), from the speaker's index."""
        speaker = self.speaker
        if speaker is None:
            return None
        return lambda focus, last_tutor: speaker.passages(focus, node_id, context=last_tutor)

    def _hint_from_earlier(self, item_id: str, node_id: str | None, new: Iterable[TutorEvent]) -> str | None:
        """DI-53: the first wrong answer to an item of the current node brings back the idea of the earlier
        node it rests on: the home of the misconception the answer showed when that is an earlier node,
        else the closest prerequisite. Once per item; never for a warm-up or review item."""
        state = teaching_state(self.events, self.config)
        if node_id is None or state.current is None or state.current.node_id != node_id:
            return None
        wrong = [
            e.payload
            for e in new
            if e.type == EventType.ANSWER_SUBMITTED and e.payload.get("outcome") == Outcome.WRONG
        ]
        if not wrong or self._recall_hint_given(item_id):
            return None
        earlier = self._earlier(node_id)
        mis_id = wrong[-1].get("misconception_id")
        info = self.chapter.lesson_of(item_id).misconception(mis_id) if mis_id else None
        if info is not None and info.kc_id in earlier:
            return info.kc_id
        prereqs = self.chapter.prerequisites(node_id)
        if not prereqs:
            return None
        order = self.chapter.topological_order()
        return max(prereqs, key=order.index)

    def _recall_hint_given(self, item_id: str) -> bool:
        last = max(
            (
                i
                for i, e in enumerate(self.events)
                if e.event_type == EventType.NODE_DECISION and e.payload.get("ref") == item_id
            ),
            default=-1,
        )
        return any(
            e.event_type == EventType.TEACH_MESSAGE_SENT and e.payload.get("ref") == RECALL_HINT
            for e in self.events[last + 1 :]
        )

    def _earlier(self, node_id: str) -> set[str]:
        found: set[str] = set()
        todo = list(self.chapter.prerequisites(node_id))
        while todo:
            n = todo.pop()
            if n not in found:
                found.add(n)
                todo.extend(self.chapter.prerequisites(n))
        return found

    def _waiting_for_item(self, messages: list[TeachMessage], events: list[LoopEvent]) -> TeachTurn:
        assert self.tutor is not None
        self.awaiting = Awaiting.ANSWER
        return TeachTurn(
            tuple(messages),
            tuple(events),
            Awaiting.ANSWER,
            item_id=self.tutor.item.id,
            item_phase=self.tutor.phase,
            choice_open=self.choice_open,
            node_id=self._item_node(self.tutor.item.id),
        )

    def _wait(
        self,
        awaiting: Awaiting,
        node_id: str | None,
        ref: str | None,
        prompt: str,
        messages: list[TeachMessage],
        events: list[LoopEvent],
    ) -> TeachTurn:
        self.awaiting, self._node, self._ref, self._prompt = awaiting, node_id, ref, prompt
        return TeachTurn(tuple(messages), tuple(events), awaiting, node_id=node_id, prompt=prompt)

    def current_turn(self) -> TeachTurn:
        """What the loop waits for now, without messages or events (for a view after ``resume``)."""
        if self.awaiting == Awaiting.ANSWER:
            return self._waiting_for_item([], [])
        if self.awaiting in (Awaiting.THEORY_REPLY, Awaiting.RETELL):
            return TeachTurn((), (), self.awaiting, node_id=self._node, prompt=self._prompt)
        return TeachTurn((), (), Awaiting.NOTHING)

    # ------------------------------------------------------------------ replay

    def _restore(self) -> None:
        """Find what the stored events wait for, and rebuild the open item from its inputs."""
        state = teaching_state(self.events, self.config)
        if state.finished:
            self.awaiting = Awaiting.NOTHING
            return
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=None
        )
        if last is None:
            raise ValueError("no teaching decision in these events: call start() instead")
        d = NodeDecisionMade.model_validate(self.events[last].payload)
        after = self.events[last + 1 :]
        if d.action in ITEM_ACTIONS:
            mine = [e for e in after if e.payload.get("item_id") == d.ref]
            marks = [i for i, e in enumerate(mine) if e.event_type == EventType.ITEM_RESTARTED]
            if marks:  # FIX-4: the item started again there; what came before is not replayed
                mine = mine[marks[-1] + 1 :]
            readings = [e.payload for e in mine if e.event_type == EventType.MESSAGE_READ]
            picks = [e.payload for e in mine if e.event_type == EventType.MOVE_CHOSEN]
            self.tutor = self._new_tutor(d, reader=recorded(readings), chooser=recorded_choices(picks))
            self.tutor.start()
            for e in mine:
                if self.tutor.phase == Phase.RESOLVED:
                    break  # the replay closed the item before the child's words ran out (FIX-4)
                seconds = e.payload.get("seconds", 0.0)
                if e.event_type == EventType.STUDENT_MESSAGE:
                    self._retry = False
                    self.tutor.on_student(e.payload["text"], seconds)
                elif e.event_type == EventType.HINT_REQUESTED or (
                    e.event_type == EventType.CHOICE_MADE and e.payload.get("choice_id") == CHOICE_HINT
                ):
                    self._retry = False
                    self.tutor.on_student(HINT_REQUEST_TEXT, seconds)
                elif e.event_type == EventType.CHOICE_MADE and e.payload.get("choice_id") == CHOICE_RETRY:
                    self._retry = True
            if self.tutor.phase == Phase.RESOLVED:
                # FIX-4: today's code reads the child's earlier words differently from the code that taught
                # them (a checker or a policy changed since), and no decision follows the item. The item
                # starts again: the next input records ITEM_RESTARTED, and later rebuilds replay from there.
                self.tutor = self._new_tutor(d)
                self.tutor.start()
                self._retry = False
                self._restart = d.ref
            said = [e.payload["text"] for e in mine if e.event_type == EventType.TUTOR_MESSAGE_SENT] or [
                e.payload["text"]
                for e in after
                if e.event_type == EventType.TUTOR_MESSAGE_SENT and e.payload.get("item_id") == d.ref
            ]
            if said:  # the words the child saw (a model's), not the template the replay rendered
                self.tutor.last_tutor = said[-1]
            self.awaiting = Awaiting.ANSWER
        elif d.action in (TeachAction.TEACH_THEORY, TeachAction.ASK_RETELL):
            asked = next((e.payload for e in after if e.event_type == EventType.TEACH_MESSAGE_SENT), None)
            if d.action == TeachAction.TEACH_THEORY:
                variant = next(t for t in self.chapter.node(d.node_id).theory if t.id == d.ref)
                self.awaiting, self._ref, self._prompt = Awaiting.THEORY_REPLY, d.ref, variant.ask
            else:
                prompt = asked["text"] if asked else self.chapter.node(d.node_id).explain.prompt
                self.awaiting, self._ref, self._prompt = Awaiting.RETELL, None, prompt
            self._node = d.node_id
        elif d.action == TeachAction.RECALL_PRIOR:
            assert d.ref is not None
            ask = self._recall_ask(d.ref)
            self.awaiting, self._node, self._ref, self._prompt = Awaiting.RETELL, d.ref, RECALL, ask
            self._for = d.node_id
        else:
            raise ValueError(f"the events end on {d.action}, which waits for nothing")

    # ------------------------------------------------------------------ helpers

    def _say(
        self, now: datetime, messages: list[TeachMessage], events: list[LoopEvent], message: TeachMessage
    ) -> None:
        """Show a teaching message and record it, so the conversation can be rebuilt from the events."""
        messages.append(message)
        sent = TeachMessageSent(
            kind=message.kind.value,
            text=message.text,
            node_id=message.node_id,
            ref=message.ref,
            templates_version=TEMPLATES_VERSION,
            source=message.source,  # type: ignore[arg-type]
            sources=list(message.sources),
            rejected=[list(codes) for codes in message.rejected],
        )
        events.append(self._record(now, EventType.TEACH_MESSAGE_SENT, sent))

    def _record(self, now: datetime, event_type: EventType, payload: Any) -> LoopEvent:
        event = self._event(now, event_type, payload)
        self.events.append(event)
        return event

    def _event(self, now: datetime, event_type: EventType, payload: Any) -> LoopEvent:
        return LoopEvent(event_type.value, payload.model_dump(mode="json"), self.session_id, now)

    def _tutor_events(self, now: datetime, events: Iterable[TutorEvent]) -> list[LoopEvent]:
        out = [LoopEvent(e.type.value, e.payload, self.session_id, now) for e in events]
        self.events.extend(out)
        return out

    def _item_node(self, item_id: str) -> str | None:
        kcs = self.chapter.item(item_id).kc_ids
        return next((k for k in kcs if any(n.id == k for n in self.chapter.nodes)), None)

    def _phrase(self, key: str, **values: str) -> str:
        return PHRASES[key].format(**self._persona, **values)

    def _summary(self) -> str:
        state = teaching_state(self.events, self.config)
        names = lambda ids: ", ".join(self.chapter.node(n).name for n in ids)  # noqa: E731
        parts = [self._phrase("summary_done", names=names(state.passed))] if state.passed else []
        if state.stopped:
            stopped = [n for n in self.chapter.topological_order() if n in state.stopped]
            parts.append(self._phrase("summary_review", names=names(stopped)))
        parts.append(self._phrase("summary_end") if state.passed else self._phrase("summary_none"))
        return " ".join(parts)
