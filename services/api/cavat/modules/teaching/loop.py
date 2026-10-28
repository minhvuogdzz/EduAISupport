"""Teaching loop (M1-6): runs the teaching cycle on the chapter graph, one student input at a time.

The node policy decides every step; this loop carries it out. It phrases theory, worked examples, the
retell prompt and the transitions with templates, runs the item loop (``ItemTutor``) for every item, judges
retells with the rubric, and records the session's events. After each input it advances on its own until the
student has something to do.

Grounded speech (RAG-2, ``grounded.py``), when a ``speaker`` is given for the live turn: a question the child
asks while a theory question or a retell waits is answered from the passages the Hybrid RAG retrieves (or
kept for the teacher when nothing grounds it), and the reply to a theory answer starts with one sentence on
what the child said, before the approved explanation. Both are checked against their sources. REFORM-1b
(DI-81): every fixed lead before approved text is such a bridge too ("Đúng rồi!", "Không sao đâu, cô giải
thích nhé:", the reminder of the main idea after a retell the child cannot give, talk outside the lesson,
the reminder of an earlier lesson); the approved text after it never changes, and the template lead is said
when the model cannot be.

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
from cavat.core.pedagogy import ITEM_ACTIONS, ActivityType, ItemResolution, Move, Outcome, TeachAction
from cavat.core.vi_text import contains_phrase
from cavat.modules.assessment.math_checker import classify_intent
from cavat.modules.assessment.projector import DEFAULT_POLICY, MasteryPolicy, project_chapter
from cavat.modules.assessment.retell import judge_retell, with_meaning
from cavat.modules.assessment.student_intent import (
    asks_question,
    expand_short_forms,
    intent_of_guess,
    is_affirmation,
    is_gibberish_or_ambiguous_short,
    known_words,
    signals_distress,
    wants_other_question,
    without_subject,
)
from cavat.modules.assessment.vi_numbers import normalize_text, phrase_regex
from cavat.modules.content.chapter_package import Chapter, Node, TheoryVariant
from cavat.modules.teaching.grounded import GroundedSpeaker, Spoken, retrieval_payload
from cavat.modules.teaching.meaning import MEANING_CONFIDENCE
from cavat.modules.teaching.node_policy import decide
from cavat.modules.teaching.official_web import scoped_query
from cavat.modules.teaching.state import DEFAULT_CONFIG, NodePolicyConfig, teaching_state
from cavat.modules.teaching.web import WEB_VERSION, web_query
from cavat.modules.tutor.chooser import MoveChooser, recorded_choices
from cavat.modules.tutor.contracts import (
    MessageRenderer,
    MessageValidator,
    PolicyDecision,
    RenderContext,
    StudentSnapshot,
)
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
from cavat.modules.tutor.social import social_reply
from cavat.modules.tutor.validator import singles_out_choice, validate_message

# 0.8.0: REFORM-6 (DI-82), a child who has not understood is taught again once before the step goes on
# 0.7.0: REFORM-1b (DI-81), the leads before approved text are bridges when a speaker is live
# 0.6.0: REFORM-5 (DI-77), a few unreadable letters at a theory question or a retell are asked about once
# 0.5.0: DI-53 hint from the earlier node; 0.4.0: DI-52
TEMPLATES_VERSION = "teaching-templates/0.11.0"  # DI-89: explain the rule, acknowledge a correct part

RECALL = "RECALL"  # the ref of a recall wait (DI-52)
RECALL_HINT = "RECALL_HINT"  # the ref of the reminder of an earlier node after a wrong answer (DI-53)
# REFORM-5: the ref of the question "con muốn nói gì?" asked about a few unreadable letters
CONFIRM_REF = "ASK_CONFIRM"
# REFORM-6 (3.3): the ref of the message that teaches again a child who has not understood. One per wait: the
# next time the approved reply is said and the step goes on.
HOLD_REF = "RETEACH"
# What says "I have not understood" ("ko", "không biết", "hả", "là sao má", "???"). Feeling, a demand for the
# answer and talk outside the lesson keep their own paths.
_NOT_UNDERSTOOD = frozenset({Outcome.HELP_REQUEST, Outcome.CLARIFY_REQUEST, Outcome.NO_RESPONSE})
MIN_MEANING_WORDS = 3  # DI-83: fewer words are not an answer worth reading for meaning

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
    # FLOW-2 (DI-80, drafted for the owner's review): the second pass of a period stopped earlier today.
    "second_pass": "Mình quay lại bài {name} một lần nữa nhé, {t} giảng lại bằng ví dụ khác.",
    "second_pass_same": "Mình quay lại bài {name} một lần nữa nhé, {t} giải lại chậm hơn từng bước.",
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
    # REFORM-5 (DI-77, drafted for the owner's review): the same two questions as the item loop's, for a
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
    "retell_close": "{T} nhắc lại ý đúng nhé: {idea}",
    # REFORM-6 (DI-82, drafted for the owner's review): the teaching again of a child who has not understood
    # (the lead is the model's words when it can speak, else the approved material).
    "hold_lead": "Không sao đâu, {t} nói lại theo cách khác nhé.",
    "hold_theory_ask": "{S} thử trả lời lại giúp {t} nhé: {ask}",
    # BRAIN-1 (DI-84, drafted for the owner's review): the child asked for another question; said when no
    # model can ask it in another way
    "another_way": "Được {s}, {t} hỏi lại nhé: {ask}",
    "hold_retell": "Không sao đâu, mình nói từng ý một nhé. {T} nhắc ý này: {part}",
    "hold_retell_ask": "{S} nói lại ý đó bằng lời của mình giúp {t} nhé?",
    "example": "{T} làm mẫu cho {s} xem nhé.",
    "pass": "{S} đã hiểu bài {name} rồi. Giỏi lắm!",
    "stop": "Bài {name} {s} chưa vững hẳn. {T} nhắc lại cách làm để {s} nhớ: {rule} "
    "{T} sẽ ôn lại với {s} sau nhé.",
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
            actual = next(
                (
                    e.payload.get("text")
                    for e in reversed(self.events)
                    if e.event_type == EventType.TUTOR_MESSAGE_SENT
                    and e.payload.get("item_id") == self.tutor.item.id
                ),
                None,
            )
            if actual:
                self.tutor.last_tutor = actual  # replay templates are not the words the child heard

    def start(self, now: datetime) -> TeachTurn:
        if self.awaiting is not None:
            raise RuntimeError("the teaching loop has already started")
        return self._advance(now, [], [])

    def on_student(self, text: str, now: datetime, seconds: float = 0.0, modality: str = "TEXT") -> TeachTurn:
        if self.awaiting in (None, Awaiting.NOTHING):
            raise RuntimeError(f"no student input expected (awaiting {self.awaiting})")
        # ItemTutor owns its social path and replay. Theory/retell social turns are kept outside the
        # assessment reference, so they cannot count as failed theory replies or retells after resume.
        persona = self.chapter.package.persona
        reply = social_reply(text, persona.tutor_self, persona.student_address)
        if reply is not None:
            ref = self.tutor.item.id if self.awaiting == Awaiting.ANSWER and self.tutor else self._node
            message = StudentMessage(
                item_id=f"{ref}:SOCIAL", kind="MESSAGE", text=text, seconds=seconds, modality=modality
            )
            events = [self._record(now, EventType.STUDENT_MESSAGE, message)]
            messages: list[TeachMessage] = []
            self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, reply, self._node))
            if self.awaiting == Awaiting.ANSWER:
                return self._waiting_for_item(messages, events)
            return TeachTurn(
                tuple(messages), tuple(events), self.awaiting, node_id=self._node, prompt=self._prompt
            )
        if self.awaiting != Awaiting.ANSWER:
            conversational = self._conversational_input(text, now, seconds, modality)
            if conversational is not None:
                return conversational
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
            node_id = self._item_node(item_id)
            if (
                self.speaker is not None
                and node_id is not None
                and self.tutor.state.activity
                in (ActivityType.GUIDED_PRACTICE, ActivityType.INDEPENDENT_PRACTICE)
                and self.speaker.is_question(text)
                and scoped_query(text, self.speaker.index, node_id)
            ):
                # A pure concept question in practice is not a failed numerical attempt. Assessment
                # retains its existing policy path. :QUESTION keeps this outside the item's replay.
                said = StudentMessage(
                    item_id=f"{item_id}:QUESTION",
                    kind="MESSAGE",
                    text=text,
                    seconds=seconds,
                    modality=modality,
                )
                events = [self._record(now, EventType.STUDENT_MESSAGE, said)]
                return self._on_question(text, now, node_id, [], events)
            kind = "EXPLANATION" if self.tutor.phase in _WORDS else "ANSWER"
            message = StudentMessage(
                item_id=item_id,
                kind=kind,
                text=text,
                seconds=seconds,
                modality=modality,
                dialogue_version=3,
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
        if wants_other_question(text) and self._prompt:
            return self._another_way(text, now, node_id, messages, events)
        if self.speaker is not None and intent not in _OWN_PATH and self.speaker.is_question(text):
            return self._on_question(text, now, node_id, messages, events)
        if intent == Outcome.OFF_TOPIC and self._replies_since_decision() <= MAX_OFF_TOPIC_REDIRECTS:
            # ADR-019: talk outside the lesson is parked and the same question asked again (DI-38). BRAIN-1:
            # a short human answer first (the model's), the approved question word for word after it.
            assert self._prompt is not None
            back = self._chat_back(text)
            self._flag(now, events, back, f"{node_id}:{self._ref or 'RETELL'}")
            self._say(now, messages, events, self._feedback(back, node_id))
            return TeachTurn(
                tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=self._prompt
            )
        if self.awaiting == Awaiting.THEORY_REPLY:
            assert self._ref is not None
            variant = next(t for t in self.chapter.node(node_id).theory if t.id == self._ref)
            by_meaning = False
            if not self._held() and (intent is None or intent in _NOT_UNDERSTOOD):
                by_meaning = self._theory_by_meaning(variant, text, intent)
                if not by_meaning and not self._theory_understood(variant, text, intent):
                    return self._hold_theory(variant, text, now, messages, events)
            spoken = self._theory_feedback(variant, text, intent, by_meaning)
            self._flag(now, events, spoken, f"{node_id}:{self._ref}")
            feedback = TeachMessage(
                MessageKind.FEEDBACK, spoken.text, node_id, source=spoken.source, rejected=spoken.rejected
            )
            self._say(now, messages, events, feedback)
            return self._advance(now, messages, events)
        node = self.chapter.node(node_id)
        if self._ref == RECALL:
            return self._on_recall(
                judge_retell(node_id, text, node.explain), intent, now, messages, events, text
            )
        words = self._retell_words(node_id)  # REFORM-6: what the child said in this wait, read together
        judged = self._judge_meaning(judge_retell(node_id, words, node.explain), node, intent)
        closing = self._held()
        if (
            not closing
            and judged.score < self.config.retell_pass
            and (intent is None or intent in _NOT_UNDERSTOOD)
        ):
            return self._hold_retell(judged, node, text, now, messages, events)
        events.append(self._record(now, EventType.RETELL_JUDGED, judged))
        if intent is not None and not judged.ideas_found:
            # "Con không biết", "là sao ạ?", "chán quá": remind the main idea instead of only saying that
            # it was not heard; the node policy then asks again or moves on, as for any retell.
            key = "retell_affect" if intent == Outcome.NEGATIVE_AFFECT else "retell_help"
            spoken = self._bridged(
                key, "idea", self._idea(node), text, asked=node.explain.prompt, judged="chưa rõ"
            )
            self._flag(now, events, spoken, f"{node_id}:{self._ref or 'RETELL'}")
            self._say(now, messages, events, self._feedback(spoken, node_id))
            return self._advance(now, messages, events)
        if judged.score >= self.config.retell_pass:
            said = self._phrase("retell_good")
        else:
            said = self._phrase("retell_partial" if judged.ideas_found else "retell_none")
            if closing:  # taught again once already: the right idea is said, then the step goes on
                said = f"{said} {self._phrase('retell_close', idea=self._idea(node))}"
        self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, said, node_id))
        return self._advance(now, messages, events)

    # ------------------------------------------------------------------ REFORM-6: taught again, meaning

    def _held(self) -> bool:
        """The child was already taught again in this wait (read from the events: a resumed session knows)."""
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=-1
        )
        return any(
            e.event_type == EventType.TEACH_MESSAGE_SENT and e.payload.get("ref") == HOLD_REF
            for e in self.events[last + 1 :]
        )

    def _has_content(self, text: str) -> bool:
        """Words worth reading for meaning: not a question and not a few words."""
        n = len(re.findall(r"[^\W\d_]+", text))  # words: a number alone is no sentence
        return n >= MIN_MEANING_WORDS and not (asks_question(text) and n <= MIN_MEANING_WORDS + 1)

    def _accepts(self, variant: TheoryVariant, text: str) -> bool:
        accept = phrase_regex(variant.accept) if variant.accept else None
        # "ko" is "không": the short forms children type count as the words they stand for
        return accept is not None and any(
            accept.search(t) for t in (normalize_text(text), expand_short_forms(text))
        )

    def _theory_understood(self, variant: TheoryVariant, text: str, intent: Outcome | None) -> bool:
        """3.3: the child showed the idea (or the answer is not graded and not a question). The rest is taught
        again once."""
        if intent in _NOT_UNDERSTOOD:
            return False
        if variant.accept:
            return self._accepts(variant, text)
        return not asks_question(text)  # ADR-019: no list of right answers, so a reply is not judged

    def _theory_by_meaning(self, variant: TheoryVariant, text: str, intent: Outcome | None) -> bool:
        """4.1: an answer in other words than the teacher's phrasings, shown right by a quote of the child."""
        if self.speaker is None or intent is not None or not variant.accept or not variant.reply:
            return False
        if self._accepts(variant, text) or not self._has_content(text):
            return False
        assert self._node is not None
        node = self.chapter.node(self._node)
        ideas, _ = self.speaker.judge_meaning(
            text,
            asked=variant.ask,
            rule=node.method.rule,
            reference=[variant.reply],
            ideas=[[variant.reply]],
            found=[],
        )
        return bool(ideas)

    def _retell_words(self, node_id: str) -> str:
        """Everything the child said to the retell in this wait: the second try completes the first."""
        last = max(
            (i for i, e in enumerate(self.events) if e.event_type == EventType.NODE_DECISION), default=-1
        )
        mine = f"{node_id}:{self._ref or 'RETELL'}"
        return " ".join(
            e.payload["text"]
            for e in self.events[last + 1 :]
            if e.event_type == EventType.STUDENT_MESSAGE and e.payload.get("item_id") == mine
        )

    def _judge_meaning(self, judged: RetellJudged, node: Node, intent: Outcome | None) -> RetellJudged:
        """4.1: the model reads what the keywords did not find, once, only for a reply with content that
        is not yet enough. It adds ideas that carry a quote of the child, never takes one away."""
        if (
            self.speaker is None
            or intent is not None
            or judged.score >= self.config.retell_pass
            or not self._has_content(judged.text)
        ):
            return judged
        ideas, quotes = self.speaker.judge_meaning(
            judged.text,
            asked=node.explain.prompt,
            rule=node.method.rule,
            reference=[node.description, *[t.reply for t in node.theory if t.reply][:2]],
            ideas=node.explain.key_ideas,
            found=judged.ideas_found,
        )
        return with_meaning(judged, ideas, quotes, MEANING_CONFIDENCE)

    def _reteach_words(
        self,
        text: str,
        asked: str,
        node: Node,
        material: str,
        hide: re.Pattern[str] | None,
        forbid: Sequence[str],
    ) -> Spoken | None:
        if self.speaker is None:
            return None
        return self.speaker.reteach(
            text, asked=asked, rule=node.method.rule, material=material, forbid=forbid, answer=hide
        )

    def _hold_theory(
        self,
        variant: TheoryVariant,
        text: str,
        now: datetime,
        messages: list[TeachMessage],
        events: list[LoopEvent],
    ) -> TeachTurn:
        """3.3: the question stays; the idea is said again another way (the model's words, else another
        approved variant or the rule, one that does not give the answer), then asked again. Nothing is
        judged."""
        assert self._node is not None
        node = self.chapter.node(self._node)
        accept = phrase_regex(variant.accept) if variant.accept else None

        def reveals(t: str) -> bool:
            return accept is not None and any(
                accept.search(x) for x in (normalize_text(t), expand_short_forms(t))
            )

        others = [t.text.strip() for t in node.theory if t.id != variant.id]
        pieces = [p for p in (*others, node.method.rule.strip()) if p and not reveals(p)]
        material = pieces[0] if pieces else variant.text.strip()
        spoken = self._reteach_words(text, variant.ask, node, material, accept, (variant.reply,))
        lead = spoken.text if spoken else f"{self._phrase('hold_lead')} {material}"
        asked = self._phrase("hold_theory_ask", ask=variant.ask)
        source = spoken.source if spoken else "TEMPLATE"
        if spoken is not None:
            self._flag(now, events, spoken, f"{self._node}:{self._ref}")
        return self._hold(now, f"{lead} {asked}", source, spoken, messages, events)

    def _idea(self, node: Node) -> str:
        """An actual explanation, never a goal such as 'Con xác định đúng…' read out as teaching."""
        return node.method.rule or next((t.reply for t in node.theory if t.reply), "")

    def _chat_back(self, text: str) -> Spoken:
        """Talk outside the lesson: the model answers like a person and rejoins the step, else the approved
        sentence; the question that waits is said after either."""
        assert self._prompt is not None
        if self.speaker is not None:
            said = self.speaker.chat(text, asked=self._prompt, recent=self._recent(4))
            if said.text:
                return Spoken(f"{said.text} {self._prompt}", "LLM", (), said.rejected, said.safety_flag)
            if said.rejected:
                back = self._bridged(
                    "off_topic", "ask", self._prompt, text, asked=self._prompt, judged="chưa rõ"
                )
                return Spoken(
                    back.text, back.source, back.sources, said.rejected, said.safety_flag, back.refused
                )
        return self._bridged("off_topic", "ask", self._prompt, text, asked=self._prompt, judged="chưa rõ")

    def _another_way(
        self, text: str, now: datetime, node_id: str, messages: list[TeachMessage], events: list[LoopEvent]
    ) -> TeachTurn:
        """BRAIN-1: "hỏi cái khác mà": the same idea asked in another way (the model's), else the approved
        question after a sentence that agrees. Nothing is judged; the wait stays."""
        assert self._prompt is not None
        spoken = (
            self.speaker.ask_another_way(
                text, asked=self._prompt, node_name=self.chapter.node(node_id).name, recent=self._recent(4)
            )
            if self.speaker is not None
            else Spoken("", "TEMPLATE")
        )
        said = spoken.text or self._phrase("another_way", ask=self._prompt)
        self._flag(now, events, spoken, f"{node_id}:{self._ref or 'RETELL'}")
        feedback = TeachMessage(
            MessageKind.FEEDBACK,
            said,
            node_id,
            source="LLM" if spoken.text else "TEMPLATE",
            rejected=spoken.rejected,
        )
        self._say(now, messages, events, feedback)
        return TeachTurn(tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=self._prompt)

    def _hold_retell(
        self,
        judged: RetellJudged,
        node: Node,
        text: str,
        now: datetime,
        messages: list[TeachMessage],
        events: list[LoopEvent],
    ) -> TeachTurn:
        """3.3: the retell stays; the part of the rule the child has not said is given and asked back in the
        child's own words (a small question instead of the sample said twice)."""
        part = self._rule_part(node, judged.ideas_found)
        spoken = self._reteach_words(text, node.explain.prompt, node, part, None, ())
        lead = spoken.text if spoken else self._phrase("hold_retell", part=part)
        if judged.ideas_found and spoken is None:
            lead = f"Ý đó con nói đúng rồi. {lead}"
        source = spoken.source if spoken else "TEMPLATE"
        if spoken is not None:
            self._flag(now, events, spoken, f"{self._node}:RETELL")
        return self._hold(now, f"{lead} {self._phrase('hold_retell_ask')}", source, spoken, messages, events)

    def _rule_part(self, node: Node, found: Sequence[int]) -> str:
        """The sentence of the rule that says the first idea not said yet (else the first sentence)."""
        source = " ".join([node.method.rule, *(t.reply for t in node.theory if t.reply)])
        sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", source.strip()) if x.strip()]
        for i, phrasings in enumerate(node.explain.key_ideas):
            if i in found:
                continue
            for sentence in sentences:
                if any(contains_phrase(sentence, p) for p in phrasings):
                    return sentence
            break
        return sentences[0] if sentences else self._idea(node)

    def _hold(
        self,
        now: datetime,
        text: str,
        source: str,
        spoken: Spoken | None,
        messages: list[TeachMessage],
        events: list[LoopEvent],
    ) -> TeachTurn:
        assert self._node is not None
        rejected = spoken.rejected if spoken else ()
        self._say(
            now,
            messages,
            events,
            TeachMessage(MessageKind.FEEDBACK, text, self._node, HOLD_REF, source, rejected=rejected),
        )
        return TeachTurn(
            tuple(messages), tuple(events), self.awaiting, node_id=self._node, prompt=self._prompt
        )

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
        text: str = "",
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
            said = self._phrase("recall_partial", idea=self._idea(prior), name=name)
        else:
            asked = self._recall_ask(prior.id)
            spoken = self._bridged(
                "recall_help", "idea", self._idea(prior), text, asked=asked, judged="chưa rõ", name=name
            )
            self._flag(now, events, spoken, f"{prior.id}:{RECALL}")
            self._say(now, messages, events, self._feedback(spoken, prior.id, RECALL))
            return self._advance(now, messages, events)
        self._say(now, messages, events, TeachMessage(MessageKind.FEEDBACK, said, prior.id, RECALL))
        return self._advance(now, messages, events)

    def _recall_ask(self, prior_id: str) -> str:
        prior = self.chapter.node(prior_id)
        return recall_question(prior) or self._phrase("recall_ask", prior=prior.name)

    def _theory_feedback(
        self, variant: TheoryVariant, text: str, intent: Outcome | None, by_meaning: bool = False
    ) -> Spoken:
        """Right, not quite, or no attempt: the reason (`reply`) in each case. Never graded (ADR-019).

        An attempt that is not right gets, with a speaker, one sentence on what the child said before the
        approved reply (RAG-2): the reply itself stays word for word.
        """
        if not variant.reply:
            return Spoken(self._phrase("theory_ack"), "TEMPLATE")
        reply = variant.reply
        if intent == Outcome.NEGATIVE_AFFECT:
            return self._bridged("theory_affect", "reply", reply, text, asked=variant.ask, judged="chưa rõ")
        if intent is not None or (_bare_no(text) and not _yes_no(variant.ask)):
            # "ko" to "phân số nào?" is "con không biết" (seen live), not a wrong answer; to "có dài hơn
            # không?" it is an answer and goes on to the check below.
            return self._bridged("theory_explain", "reply", reply, text, asked=variant.ask, judged="chưa rõ")
        # REFORM-6 (4.1): right by the keywords, or by words a quote of the child shows carry the idea
        if by_meaning or self._accepts(variant, text):
            return self._bridged("theory_right", "reply", reply, text, asked=variant.ask, judged="đúng")
        judged, lead = ("chưa đúng", "theory_check_lead") if variant.accept else ("chưa rõ", "theory_ack")
        if self.speaker is None:
            return Spoken(f"{self._phrase(lead)} {variant.reply}", "TEMPLATE")
        return self.speaker.bridge(
            text,
            asked=variant.ask,
            explanation=variant.reply,
            judged=judged,
            lead=self._phrase(lead),
            recent=self._recent(4),
        )

    def _conversational_input(self, text, now, seconds, modality):
        if (
            not self.speaker
            or not self.speaker.knowledge_active
            or not getattr(self.item_reader, "semantic", False)
            or not self._node
            or signals_distress(text)
            or not text.strip()
        ):
            return None
        from cavat.modules.assessment.student_intent import is_bare_negation
        from cavat.modules.tutor.prompt_builder import Turn
        from cavat.modules.tutor.reader import Reading

        # Named theory questions keep the RAG/internet path and its source log.
        if self.speaker.is_question(text) and scoped_query(text, self.speaker.index, self._node):
            return None
        recent = self._recent(6, include_last=True)
        reading = self.item_reader.read_dialogue(
            stem=self._prompt or "",
            last_tutor=next((said for role, said in reversed(recent) if role == "tutor"), self._prompt or ""),
            said=text,
            turn=self._replies_since_decision() + 1,
            recent=[Turn(role, said) for role, said in recent],
            phase=str(self.awaiting),
        )
        if reading is None and is_bare_negation(text):
            reading = Reading("AMBIGUOUS_REPLY")
        if not reading or reading.label not in ("AMBIGUOUS_REPLY", "REPAIR", "DECLINE"):
            return None
        ref = f"{self._node}:DIALOGUE"
        message = StudentMessage(
            item_id=ref, kind="MESSAGE", text=text, seconds=seconds, modality=modality, dialogue_version=3
        )
        events = [self._record(now, EventType.STUDENT_MESSAGE, message)]
        spoken = self.speaker.conversation_reply(
            text,
            asked=self._prompt or "",
            node=self.chapter.node(self._node),
            focus=reading.focus,
            label=reading.label,
            recent=recent,
        )
        messages = []
        self._flag(now, events, spoken, ref)
        self._say(
            now,
            messages,
            events,
            TeachMessage(
                MessageKind.FEEDBACK, spoken.text, self._node, ref, spoken.source, rejected=spoken.rejected
            ),
        )
        return TeachTurn(
            tuple(messages), tuple(events), self.awaiting, node_id=self._node, prompt=self._prompt
        )

    def _on_question(
        self, text: str, now: datetime, node_id: str, messages: list[TeachMessage], events: list[LoopEvent]
    ) -> TeachTurn:
        """A question of the child while a theory question or a retell waits (RAG-2, DI-39): answered from the
        retrieved passages, or kept for the teacher; then the question that waits is asked again."""
        assert self.speaker is not None
        if self.awaiting == Awaiting.ANSWER:
            assert self.tutor is not None
            ask, ref = self.tutor.last_tutor, f"{self.tutor.item.id}:QUESTION"
        else:
            assert self._prompt is not None
            ask, ref = self._prompt, f"{node_id}:{self._ref or 'RETELL'}"
        if not self.speaker.knowledge_active and self._answers_since_decision() >= MAX_QUESTIONS_PER_WAIT:
            parked = QuestionParked(node_id=node_id, text=text, reason="LIMIT")
            events.append(self._record(now, EventType.QUESTION_PARKED, parked))
            said = TeachMessage(MessageKind.ANSWER, self._phrase("question_limit", ask=ask), node_id)
        else:
            hide = []
            if self.awaiting == Awaiting.THEORY_REPLY and self._ref is not None:
                variant = next(t for t in self.chapter.node(node_id).theory if t.id == self._ref)
                hide = [variant.reply]  # the question that waits keeps its answer to itself
            guard = None
            if self.awaiting == Awaiting.ANSWER:
                assert self.tutor is not None
                graded = self.tutor._last_graded
                ctx = RenderContext(
                    decision=PolicyDecision(Move.EXPLAIN),
                    item=self.tutor.item,
                    package=self.tutor.package,
                    state=self.tutor.state,
                    persona=self.tutor.package.persona,
                    free_numbers=True,
                    solved=graded is not None and graded.outcome == Outcome.CORRECT,
                )

                def guard(message: str) -> Sequence[str]:
                    if ctx.solved:
                        return ()
                    codes = tuple(
                        c
                        for c in validate_message(message, ctx).codes
                        if c in ("ANSWER_LEAK", "WRONG_PRAISE")
                    )
                    return (*codes, "ANSWER_LEAK") if singles_out_choice(message, ctx.item) else codes

            turn = self.speaker.answer(
                text, node_id=node_id, pending=ask, hide=hide, recent=self._recent(4), output_guard=guard
            )
            if turn.retrieval is not None:
                payload = RagRetrieved(**retrieval_payload(turn.retrieval, "QUESTION", node_id))
                events.append(self._record(now, EventType.RAG_RETRIEVED, payload))
            if turn.web is not None:  # WEB-1: what was looked up, and whether the child heard it
                looked = WebLooked(
                    node_id=node_id,
                    query=turn.web.asked or web_query(text),
                    source=turn.web.publisher or (self.speaker.web.name if self.speaker.web else ""),
                    title=turn.web.title,
                    url=turn.web.url,
                    answered=turn.kind == "ANSWERED",
                    version=WEB_VERSION,
                    excerpt=turn.web.text,
                    excerpt_hash=turn.web.excerpt_hash,
                )
                events.append(self._record(now, EventType.WEB_LOOKED, looked))
            if turn.kind == "ANSWERED":
                assert turn.spoken is not None
                self._flag(now, events, turn.spoken, ref)
                said = TeachMessage(
                    MessageKind.ANSWER,
                    (
                        turn.spoken.text
                        if self.speaker.knowledge_active
                        else f"{turn.spoken.text} {self._phrase('question_back', ask=ask)}"
                    ),
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
        if self.awaiting == Awaiting.ANSWER:
            return self._waiting_for_item(messages, events)
        return TeachTurn(tuple(messages), tuple(events), self.awaiting, node_id=node_id, prompt=ask)

    def _recent(self, n: int, *, include_last: bool = False) -> list[tuple[str, str]]:
        """The last ``n`` turns before the message being answered: (role, text), oldest first."""
        said = []
        for e in self.events if include_last else self.events[:-1]:
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
        return sum(
            1
            for e in self.events[last + 1 :]
            if e.event_type == EventType.STUDENT_MESSAGE
            and not str(e.payload.get("item_id", "")).endswith(":SOCIAL")
        )

    def on_hint_request(self, now: datetime, seconds: float = 0.0, *, source="BUTTON") -> TeachTurn:
        if self.awaiting != Awaiting.ANSWER or self.tutor is None:
            raise RuntimeError("a hint needs an open item")
        requested = HintRequested(item_id=self.tutor.item.id, seconds=seconds, source=source)
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
                idea = self._idea(self.chapter.node(prior))
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
            if "SECOND_PASS" in d.reason_codes:
                key = (
                    "second_pass_same"
                    if {"SAME_EXAMPLE", "SAME_VARIANT"} & set(d.reason_codes)
                    else "second_pass"
                )
            say(TeachMessage(MessageKind.NODE, self._phrase(key, name=name), node_id))
        elif a == TeachAction.SWITCH_TO_PREREQUISITE:
            say(TeachMessage(MessageKind.NODE, self._phrase("switch", name=name), node_id))
        elif a == TeachAction.TEACH_THEORY:
            node = self.chapter.node(node_id)
            variant = next(t for t in node.theory if t.id == d.ref)
            # BRAIN-1: the theory in the tutor's own words (the approved text is its ground); the approved
            # question follows word for word, so what the child answers is judged against it
            lecture = (
                self.speaker.lecture(
                    variant.text,
                    ask=variant.ask,
                    node_name=node.name,
                    rule=node.method.rule,
                    recent=self._recent(4),
                )
                if self.speaker is not None
                else Spoken("", "TEMPLATE")
            )
            self._flag(now, events, lecture, f"{node_id}:{d.ref}")
            body = lecture.text or variant.text
            say(
                TeachMessage(
                    MessageKind.THEORY,
                    f"{body} {variant.ask}",
                    node_id,
                    d.ref,
                    source="LLM" if lecture.text else "TEMPLATE",
                    rejected=lecture.rejected,
                )
            )
            return self._wait(Awaiting.THEORY_REPLY, node_id, d.ref, variant.ask, messages, events)
        elif a == TeachAction.ASK_RETELL:
            node = self.chapter.node(node_id)
            prompt = node.explain.prompt
            invite = (
                self.speaker.invite_retell(node, prompt=prompt, recent=self._recent(4))
                if self.speaker is not None
                else Spoken("", "TEMPLATE")
            )
            self._flag(now, events, invite, f"{node_id}:RETELL")
            if invite.text:
                prompt = invite.text  # BRAIN-1: said for what the child has just done; this is what waits
            elif "EXPLANATION_MISSING" in d.reason_codes:
                prompt = f"{self._phrase('retell_again')} {prompt}"
            say(
                TeachMessage(
                    MessageKind.RETELL_PROMPT,
                    prompt,
                    node_id,
                    source="LLM" if invite.text else "TEMPLATE",
                    rejected=invite.rejected,
                )
            )
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
            rule = self.chapter.node(node_id).method.rule.strip()
            rule += "" if rule.endswith((".", "!", "?")) else "."
            say(TeachMessage(MessageKind.STOP, self._phrase("stop", name=name, rule=rule), node_id))
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
        visit_start = max(
            (
                i
                for i, e in enumerate(self.events)
                if e.event_type == EventType.NODE_DECISION
                and e.payload.get("action") == TeachAction.TEACH_THEORY
            ),
            default=-1,
        )
        prior_items = {
            e.payload.get("item_id")
            for e in self.events[visit_start + 1 :]
            if e.event_type == EventType.EXPLANATION_SUBMITTED
            and (e.payload.get("reasoning_quality") or 0) >= 0.6
        }
        previous = next((e for e in reversed(self.events) if e.event_type == EventType.ITEM_RESOLVED), None)
        reason_seen = bool(
            previous
            and previous.payload.get("item_id") in prior_items
            and previous.payload.get("resolution") in (ItemResolution.INDEPENDENT, ItemResolution.SUPPORTED)
            and set(previous.payload.get("kc_ids", ())) & set(item.kc_ids)
            and item.transfer == "none"
            and self.chapter.item(previous.payload["item_id"]).answer.type == item.answer.type
            and self.chapter.item(previous.payload["item_id"]).cognitive_level == item.cognitive_level
        )
        node_id = self._item_node(d.ref)
        node = self.chapter.node(node_id) if node_id else None
        knowledge = (
            (node.method.rule, *(t.text for t in node.theory), *(t.reply for t in node.theory))
            if node
            else ()
        )
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
            reason_seen=reason_seen,
            knowledge=knowledge if not item.is_assessment else (),
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
            replay_dialogue_version = 1
            for e in mine:
                if self.tutor.phase == Phase.RESOLVED:
                    break  # the replay closed the item before the child's words ran out (FIX-4)
                seconds = e.payload.get("seconds", 0.0)
                if e.event_type == EventType.STUDENT_MESSAGE:
                    replay_dialogue_version = e.payload.get("dialogue_version", 1)
                    self._retry = False
                    # New social events have :SOCIAL and are outside `mine`. Old, already graded 'hi'
                    # messages must keep the old routing on replay rather than rewriting past attempts.
                    self.tutor.on_student(
                        e.payload["text"],
                        seconds,
                        allow_social=False,
                        dialogue_version=e.payload.get("dialogue_version", 1),
                    )
                elif e.event_type == EventType.TUTOR_MESSAGE_SENT and replay_dialogue_version >= 3:
                    self.tutor.last_tutor = e.payload["text"]
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

    def _bridged(
        self, key: str, slot: str, body: str, said: str, *, asked: str, judged: str, **values: str
    ) -> Spoken:
        """REFORM-1b (DI-81): the phrase ``key`` is a lead, then ``slot`` (approved text) and what follows it.
        With a live speaker the lead is a checked sentence on what the child ``said`` (``bridge``); the
        approved part is said word for word either way."""
        mark = "\x00"
        lead, _, after = self._phrase(key, **{slot: mark}, **values).partition(mark)
        approved = f"{body}{after}"
        if self.speaker is None:
            return Spoken(f"{lead}{approved}", "TEMPLATE")
        return self.speaker.bridge(
            said,
            asked=asked,
            explanation=approved,
            judged=judged,
            lead=lead.strip(),
            recent=self._recent(4),
            teaching=slot != "ask",  # "ask": the same question again after talk outside the lesson
        )

    @staticmethod
    def _feedback(spoken: Spoken, node_id: str | None, ref: str | None = None) -> TeachMessage:
        return TeachMessage(
            MessageKind.FEEDBACK, spoken.text, node_id, ref, source=spoken.source, rejected=spoken.rejected
        )

    def _summary(self) -> str:
        state = teaching_state(self.events, self.config)
        names = lambda ids: ", ".join(self.chapter.node(n).name for n in ids)  # noqa: E731
        parts = [self._phrase("summary_done", names=names(state.passed))] if state.passed else []
        if state.stopped:
            stopped = [n for n in self.chapter.topological_order() if n in state.stopped]
            parts.append(self._phrase("summary_review", names=names(stopped)))
        parts.append(self._phrase("summary_end") if state.passed else self._phrase("summary_none"))
        return " ".join(parts)
