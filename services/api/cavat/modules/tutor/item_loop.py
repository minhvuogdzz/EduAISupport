"""Item tutoring loop: state machine tier 3 of blueprint PART 16.2 (T04).

``ItemTutor`` runs one item from PRESENT to ``ITEM_RESOLVED``. Each student message is read by the
deterministic checker, folded into ``ItemState``, handed to ``policy.decide`` (which picks the move),
rendered by the injected ``MessageRenderer`` and checked by the injected ``MessageValidator``: a rejected
message is rendered once more, then replaced by a fixed fallback sentence (``OUTPUT_REJECTED`` is logged
for every rejection). Every event payload is a model of ``cavat.core.events`` dumped to JSON.

The loop never calls a model and never writes mastery; it only produces events for the projector.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from cavat.core.events import (
    AnswerSubmitted,
    EventType,
    ExplanationSubmitted,
    HintDelivered,
    ItemResolved,
    MessageRead,
    MisconceptionDetected,
    MoveChosen,
    OutputRejected,
    PolicyDecisionMade,
    QuestionShown,
    TutorMessageSent,
)
from cavat.core.pedagogy import (
    GRADED_OUTCOMES,
    HINT_MOVES,
    ActivityType,
    ErrorClass,
    ItemResolution,
    Move,
    Outcome,
    resolution_for,
)
from cavat.modules.assessment.math_checker import (
    CheckResult,
    check_answer,
    classify_intent,
    no_is_an_answer,
    parse_relation,
)
from cavat.modules.assessment.reason import judge_reason
from cavat.modules.assessment.student_intent import (
    asks_for_hint,
    asks_question,
    intent_of_guess,
    is_affirmation,
    is_bare_negation,
    is_gibberish_or_ambiguous_short,
    known_words,
)
from cavat.modules.assessment.vi_numbers import parse_literal
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    ChoiceOption,
    CompareAnswer,
    Item,
    LessonPackage,
    NumericAnswer,
    OpenAnswer,
    OrderAnswer,
)
from cavat.modules.rag.bm25 import content_words
from cavat.modules.tutor.brain import BRAIN_MAX_WORDS, math_errors
from cavat.modules.tutor.chooser import MoveChooser, situation
from cavat.modules.tutor.contracts import (
    ItemState,
    MessageRenderer,
    MessageValidator,
    PolicyDecision,
    PolicyInput,
    RenderContext,
    RenderedMessage,
    StudentSnapshot,
    TurnTrigger,
    ValidationCode,
    ValidationIssue,
    ValidationResult,
)
from cavat.modules.tutor.dialogue import (
    CURRENT_DIALOGUE_VERSION,
    DIALOGUE_VERSION,
    boolean_read,
    numeric_helper,
    parts_read,
    relation_step,
)
from cavat.modules.tutor.llm_renderer import teaches_again, word_cap
from cavat.modules.tutor.policy import (
    DEFAULT_CONFIG,
    ItemFacts,
    PolicyConfig,
    accept,
    decide,
    options,
    unclear_twice,
)
from cavat.modules.tutor.reader import (
    MAX_INTENT_READS_PER_ITEM,
    ContextReader,
    clarification_problems,
    read_unclear,
    rule_step_reading,
    rule_unclear_reading,
)
from cavat.modules.tutor.renderer import PHRASES, TemplateRenderer, counter_example, ladder_top
from cavat.modules.tutor.social import social_reply

# DI, approved by the owner on 2026-10-01: hard stop for one item. Every policy path ends well before
# this (frustration -> worked -> full -> teach-back); the guard only makes sure that no sequence of
# replies can keep an item open forever.
MAX_STUDENT_TURNS = 12

# What the loop reads when the student presses "gợi ý" (classified as HELP_REQUEST).
HINT_REQUEST_TEXT = "con cần gợi ý"

# Micro choices after OFFER_CHOICE (PART 24.3). Wording approved by the owner on 2026-10-01.
CHOICE_HINT = "HINT"
CHOICE_RETRY = "RETRY"
CHOICES: dict[str, str] = {CHOICE_HINT: "Cho con gợi ý", CHOICE_RETRY: "Con tự thử lại"}

# DI: confidence of a misconception attributed by a probe answer (same as one bug-rule match in the
# checker): a targeted comparison is strong evidence, so the policy may answer with R-MISC-HIGH.
PROBE_CONFIDENCE = 0.8

# DI: error class of the probe's "other cause" (the numbers were compared correctly).
PROBE_CORRECT_ERROR = ErrorClass.REASONING

# Outcomes that show no progress on the item (R-FRUSTRATION counts them; silence too, DI).
# DI, approved by the owner on 2026-10-01: asking for help is not one of them. In the owner's trial two
# wrong answers followed by "Xin gợi ý" jumped straight to the worked solution; the request must get the
# next hint instead. (Help requests still feed the negative-affect signal of R-ESCALATE.)
_UNPRODUCTIVE = frozenset({Outcome.WRONG, Outcome.UNPARSEABLE, Outcome.NO_RESPONSE})
# CTX-1: what a reading in context turns a message into (an ANSWER is graded by the checker instead).
_READ_OUTCOME = {
    "ASKS_ABOUT": Outcome.ASKS_ABOUT,
    "STEP_ANSWER": Outcome.PARTIAL,
    "ASK_TASK": Outcome.CLARIFY_REQUEST,
    "DONT_KNOW": Outcome.HELP_REQUEST,
    "OFF_TOPIC": Outcome.OFF_TOPIC,
    "AFFECT": Outcome.NEGATIVE_AFFECT,
}
_HELP = frozenset({Outcome.HELP_REQUEST, Outcome.ANSWER_DEMAND})
# REFORM-5: "ừ" to "cô đoán con muốn nói là con chưa biết làm, đúng không?" is read as the guess it confirms.
CONFIRMED_TEXT = {
    Outcome.HELP_REQUEST: "con không biết",
    Outcome.NEGATIVE_AFFECT: "con thấy chán",
    Outcome.CLARIFY_REQUEST: "con chưa hiểu",
}

# Fixed fallback sentence (renderer.PHRASES key) used when a message fails the validator twice.
_FALLBACK_KEY: dict[Move, str] = {
    Move.NUDGE: "nudge",
    Move.OFFER_CHOICE: "offer_choice",
    Move.ASK_CONFIRM: "ask_confirm",
    Move.VERIFY: "verify",
    Move.CONFIRM_ADVANCE: "confirm_advance",
    Move.FULL_EXPLANATION: "explain_back",
    Move.TEACH_BACK: "teach_back",
    Move.CLOSE_ITEM: "close_item",
}


class Phase(StrEnum):
    """What the loop is waiting for (blueprint PART 16.2, tier 3)."""

    AWAITING = "AWAITING"  # an answer to the item
    AWAITING_CHOICE = "AWAITING_CHOICE"  # "gợi ý thêm hay tự thử lại?" after OFFER_CHOICE
    AWAITING_CONFIRM = "AWAITING_CONFIRM"  # a clearer answer after ASK_CONFIRM
    AWAITING_PROBE = "AWAITING_PROBE"  # the comparison that separates two causes (lesson.yaml `probe`)
    AWAITING_REASON = "AWAITING_REASON"  # the student's account of the method after "con làm thế nào?"
    VERIFYING = "VERIFYING"  # the "vì sao" after a correct answer (R-VERIFY)
    TEACH_BACK = "TEACH_BACK"  # the student retells the method after H6/H7 (R-TEACH-BACK)
    RESOLVED = "RESOLVED"


# Phases in which the child answers in words: asking what a few letters meant leaves the phase as it is.
_WORDS_PHASES = frozenset({Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON, Phase.AWAITING_PROBE})


@dataclass(frozen=True)
class TutorEvent:
    type: EventType
    payload: dict[str, Any]


@dataclass(frozen=True)
class TutorTurn:
    """One tutor message and the events produced since the previous one."""

    text: str
    move: Move
    phase: Phase
    events: tuple[TutorEvent, ...] = field(default=())

    @property
    def resolved(self) -> bool:
        return self.phase == Phase.RESOLVED


class ItemTutor:
    """Runs one item. Call ``start()`` once, then ``on_student()`` for each reply until resolved."""

    def __init__(
        self,
        item: Item,
        package: LessonPackage,
        activity: ActivityType,
        renderer: MessageRenderer,
        validator: MessageValidator,
        cfg: PolicyConfig = DEFAULT_CONFIG,
        snapshot: StudentSnapshot | None = None,
        reader: ContextReader | None = None,
        explainer: Callable[[str, str], Sequence[str]] | None = None,
        chooser: MoveChooser | None = None,
        first_on_kc: bool = False,
        kc_mastery: float | None = None,
        reason_seen: bool = False,
        knowledge: Sequence[str] = (),
    ) -> None:
        """``reader``: reads an unclear message in context (CTX-1; a ``RecordedReader`` on replay).
        ``explainer``: approved passages on what the child asks about (the Hybrid RAG of the chapter).
        ``chooser``: picks one of the moves the policy allows (AUTO-1; a ``RecordedChooser`` on replay).
        ``first_on_kc``, ``kc_mastery``: what the session knows of the item's KCs when it opens (DI-65)."""
        self.item = item
        self.reader = reader
        self.chooser = chooser
        self._said = ""  # the child's message of this turn: what the chooser reads
        self.explainer = explainer
        self.knowledge = tuple(knowledge)
        self._dialogue_version = DIALOGUE_VERSION
        self._heard = []
        self._dialogue_focus = ""
        self._helper_context = False
        self._parts: dict[str, str] = {}
        self._follow_up = ""
        self.last_tutor = ""  # what the tutor said last on this item: what "mẫu như nào" asks about
        self._focus: str | None = None  # what the child asks about (EXPLAIN)
        self.package = package
        self.renderer = renderer
        self.validator = validator
        self.cfg = cfg
        self.snapshot = snapshot or StudentSnapshot()
        self.state = ItemState(item_id=item.id, activity=activity)
        self.facts = ItemFacts(
            kc_ids=tuple(item.kc_ids),
            counterexamples=frozenset(
                m.id for m in package.misconceptions if counter_example(item, package, m.id) is not None
            ),
            expected_item_s=float(item.expected_time_s),
            requires_explanation=item.requires_explanation,
            top_hint_level=ladder_top(item, package),
            first_on_kc=first_on_kc,
            kc_mastery=kc_mastery,
            reason_seen=reason_seen,
        )
        self.phase: Phase | None = None
        self.events: list[TutorEvent] = []
        self._pending: list[TutorEvent] = []
        self._turns = 0
        self._offer: PolicyDecision | None = None  # the hint offered by OFFER_CHOICE
        self._probe_option: ChoiceOption | None = None
        self._probe_asked = False
        self._last_check: CheckResult | None = None
        self._last_graded: CheckResult | None = None
        self._why_pending = False  # a "vì sao" before a hint (R-STRONG-PRIOR) waits for its reply
        self._explanation_asked = False
        self._explained: bool | None = None
        self._misconceptions: list[str] = []
        # REFORM-5: words of the task a child may quote (a name, an option), which are not a key slip; the
        # model readings spent on this item; the question the reader proposed and the guess it made for the
        # message being answered, and what the guess asks of the tutor if the child says yes.
        self._known = known_words(item.stem, item.rephrase or "", *_option_words(item))
        self._intent_reads = 0
        self._clarification: str | None = None
        self._guess: str | None = None
        self._guess_intent: Outcome | None = None

    # ------------------------------------------------------------------ public API

    def start(self) -> TutorTurn:
        if self.phase is not None:
            raise RuntimeError("item already started")
        it = self.item
        self._emit(
            EventType.QUESTION_SHOWN,
            QuestionShown(
                item_id=it.id,
                activity_type=self.state.activity,
                purpose=it.purpose,
                kc_ids=list(it.kc_ids),
                cognitive_level=it.cognitive_level,
                difficulty=it.difficulty,
                transfer=it.transfer,
                isomorphic_group=it.isomorphic_group,
            ),
        )
        return self._act(self._decide("START", None), None)

    def on_student(
        self,
        text: str,
        seconds: float = 0.0,
        *,
        allow_social: bool = True,
        dialogue_version: int = CURRENT_DIALOGUE_VERSION,
    ) -> TutorTurn:
        """Handle one student message. ``seconds``: time since the previous tutor message."""
        if self.phase is None:
            raise RuntimeError("call start() first")
        if self.phase == Phase.RESOLVED:
            raise RuntimeError("item already resolved")
        self._dialogue_version = dialogue_version
        reply = social_reply(text, self.package.persona.tutor_self, self.package.persona.student_address)
        if allow_social and reply is not None:
            # R-SOCIAL: preserve phase, pending confirmation, timing, turn/hint counters and mastery.
            self._emit(
                EventType.POLICY_DECISION,
                PolicyDecisionMade(
                    item_id=self.item.id, move=Move.REDIRECT, reason_codes=["SOCIAL"], rule_ids=["R-SOCIAL"]
                ),
            )
            self._emit(
                EventType.TUTOR_MESSAGE_SENT,
                TutorMessageSent(
                    item_id=self.item.id,
                    move=Move.REDIRECT,
                    text=reply,
                    source="TEMPLATE",
                    words=len(reply.split()),
                    attempts_to_pass_validator=1,
                ),
            )
            events, self._pending = tuple(self._pending), []
            return TutorTurn(text=reply, move=Move.REDIRECT, phase=self.phase, events=events)
        st = self.state
        st.dialogue_version = dialogue_version
        self._turns += 1
        self._said = text
        if dialogue_version >= 3 and getattr(self.reader, "semantic", False) and not self.item.is_assessment:
            dialogue = self._conversation(text, seconds)
            if dialogue is not None:
                return dialogue
        if st.confirm_open and self._guess_intent is not None and is_affirmation(text):
            text = CONFIRMED_TEXT[self._guess_intent]  # the child confirmed what the tutor guessed
        elif (
            (dialogue_version < 3 or not getattr(self.reader, "semantic", False))
            and is_bare_negation(text)
            and not no_is_an_answer(self.item)
        ):
            # "chưa", "ko", "k" are "con không biết" (student-intent/0.3.0), and the tutor answers that.
            # Given as typed, the model once greeted "chưa" with "Chưa sao" (live, 2026-10-26).
            text = CONFIRMED_TEXT[Outcome.HELP_REQUEST]
        self._said = text
        st.seconds_since_shown += seconds
        st.seconds_since_last_message = seconds
        if self._why_pending:
            st.verified = True
            self._why_pending = False

        if self.phase in (Phase.VERIFYING, Phase.TEACH_BACK):
            return self._on_explanation(text)
        if self.phase == Phase.AWAITING_PROBE:
            return self._on_probe(text, seconds)
        if self.phase == Phase.AWAITING_REASON:
            return self._on_reason(text, seconds)

        check = self._check(text)
        if self._ambiguous(text, check):
            return self._on_unclear(text, "ANSWER")
        if self._step_candidate(check):
            check = self._read_step(check, text)
        elif self.reader is not None and self._unclear(check, text):
            check = self._read(check, text)
        if self.phase == Phase.AWAITING_CHOICE and check.outcome in _HELP and self._offer is not None:
            # The student took the offered hint: deliver what the policy offered (level and target).
            offer = self._offer
            accepted = replace(offer, move=Move.HINT, reason_codes=(*offer.reason_codes, "HINT_ACCEPTED"))
            return self._act(accepted, text)
        self._record_answer(check, text, seconds)
        trigger: TurnTrigger = "HINT_REQUEST" if check.outcome in _HELP else "ANSWER"
        return self._act(self._decide(trigger, check), text)

    def _conversation(self, text: str, seconds: float) -> TutorTurn | None:
        """Hear raw conversational language before it is collapsed into a wrong/help answer."""
        from cavat.core.vi_text import fold, normalize
        from cavat.modules.tutor.reader import Reading, rule_unclear_reading

        acknowledgment = fold(normalize(text)).strip(" .!?") in {
            "ok",
            "okay",
            "uh",
            "u",
            "vang",
        }
        if not acknowledgment and rule_unclear_reading(text) is not None:
            return self._on_unclear(text, "EXPLANATION" if self.phase in _WORDS_PHASES else "ANSWER")
        if not text.strip() or text == HINT_REQUEST_TEXT:
            return None
        if no_is_an_answer(self.item) and is_bare_negation(text):
            return None
        plain = check_answer(self.item, text, self.package)
        natural_numeric = (
            isinstance(self.item.answer, NumericAnswer)
            and plain.outcome == Outcome.WRONG
            and len(text.split()) >= 4
        )
        if plain.outcome in GRADED_OUTCOMES and not asks_question(text) and not natural_numeric:
            return None
        if classify_intent(text) == Outcome.ANSWER_DEMAND:
            return None
        read = getattr(self.reader, "read_dialogue", None)
        recent = getattr(self.renderer, "recent", ()) or self._heard[-6:]
        reading = (
            read(
                stem=self.item.stem,
                last_tutor=self.last_tutor,
                said=text,
                turn=self._turns,
                recent=recent,
                phase=str(self.phase),
            )
            if read
            else None
        )
        if acknowledgment and (reading is None or reading.label == "PASS"):
            reading = Reading(
                "REPAIR", focus="con tiếp nhận lời hướng dẫn; nối tiếp bước đang chờ, chưa chấm hiểu"
            )
        if (reading is None or reading.label == "PASS") and (
            is_bare_negation(text) or is_gibberish_or_ambiguous_short(text)
        ):
            prior = next((e for e in reversed(self.events) if e.type == EventType.POLICY_DECISION), None)
            repeated = prior is not None and "AMBIGUOUS_REPLY" in prior.payload.get("reason_codes", ())
            reading = Reading(
                "REPAIR" if repeated else "AMBIGUOUS_REPLY",
                focus="giảng một bước dễ hơn" if repeated else "chưa hiểu hay chưa muốn làm tiếp",
            )
        if (
            reading is not None
            and reading.label == "PASS"
            and reading.answer
            and isinstance(self.item.answer, NumericAnswer)
            and not asks_question(text)
        ):
            from cavat.modules.assessment.vi_numbers import extract_numbers

            proposed = extract_numbers(reading.answer)
            observed = {(n.value, n.form) for n in extract_numbers(text)}
            if (
                len(proposed) == 1
                and (proposed[0].value, proposed[0].form) in observed
                and not re.search(r"\b(?:hay|hoặc)\b", text.lower())
            ):
                checked = self._check(reading.answer)
                if checked.outcome in GRADED_OUTCOMES:
                    self._emit(
                        EventType.MESSAGE_READ,
                        MessageRead(
                            item_id=self.item.id,
                            turn=self._turns,
                            label="PASS",
                            answer=reading.answer,
                            focus=reading.focus,
                            source=reading.source,
                        ),
                    )
                    judged = judge_reason(self.item, text, self.package)
                    if (
                        checked.outcome == Outcome.CORRECT
                        and {"TERM", "SOLUTION"}.intersection(judged.cues)
                        and re.search(r"\b(?:vì|nên|chữ số)\b", text.lower())
                        and not math_errors(text)
                    ):
                        checked = replace(checked, detail={**checked.detail, "reason_supplied": True})
                    self.state.seconds_since_shown += seconds
                    self.state.seconds_since_last_message = seconds
                    self._record_answer(checked, text, seconds)
                    return self._act(self._decide("ANSWER", checked), text)
        if reading is None or reading.label not in ("AMBIGUOUS_REPLY", "REPAIR", "DECLINE"):
            return None
        self._emit(
            EventType.MESSAGE_READ,
            MessageRead(
                item_id=self.item.id,
                turn=self._turns,
                label=reading.label,
                focus=reading.focus,
                source=reading.source,
            ),
        )
        self._dialogue_focus = reading.focus
        self._focus = reading.focus
        check = CheckResult(Outcome.ASKS_ABOUT, detail={"dialogue": reading.label})
        return self._act(self._decide("ANSWER", check), text)

    # ------------------------------------------------------------------ student side

    def _check(self, text: str) -> CheckResult:
        checked_item = self.item
        if (
            self._dialogue_version >= 3
            and isinstance(self.item.answer, NumericAnswer)
            and not self.item.answer.form
        ):
            form = (
                "fraction"
                if "phân số thập phân" in self.item.stem.lower()
                else "decimal"
                if "thành số thập phân" in self.item.stem.lower()
                else None
            )
            if form:
                checked_item = self.item.model_copy(
                    update={"answer": self.item.answer.model_copy(update={"form": form})}
                )
        check = check_answer(checked_item, text, self.package)
        if self._dialogue_version >= DIALOGUE_VERSION and not self.item.is_assessment:
            contextual = boolean_read(self.item, text, self.package, self.last_tutor)
            if contextual is None and self._helper_context:
                contextual = numeric_helper(self.item, text, self.last_tutor, self.package)
            if contextual is None and check.outcome != Outcome.CORRECT:
                contextual = parts_read(self.item, text, self.last_tutor, self._parts)
            if contextual is None and check.outcome not in (Outcome.CORRECT, Outcome.PARTIAL):
                contextual = relation_step(self.item, text, self.last_tutor, self.knowledge)
            if contextual is not None:
                check = contextual
                self._follow_up = check.detail.get("follow_up", "")
        if check.outcome == Outcome.HELP_REQUEST and (text == HINT_REQUEST_TEXT or asks_for_hint(text)):
            check = replace(check, detail={**check.detail, "asked_hint": True})
        if self._probe_asked and check.detail.get("probe_option"):
            # The cause is already known (or the probe was skipped): do not ask the probe twice.
            check = replace(check, detail={k: v for k, v in check.detail.items() if k != "probe_option"})
        if check.detail.get("ambiguous_misconceptions") and check.misconception_id:
            # Several misconceptions predict this answer: attribute none (no COGNITIVE_CONFLICT).
            check = replace(check, misconception_id=None, misconception_confidence=0.0)
        return check

    def _step_candidate(self, check: CheckResult) -> bool:
        """A wrong answer, undiagnosed, to an item the tutor already gave a hint on (DI-67)."""
        return (
            check.outcome == Outcome.WRONG
            and check.misconception_id is None
            and bool(self.state.hint_levels)
            and isinstance(self.item.answer, NumericAnswer)
        )

    def _read_step(self, check: CheckResult, text: str) -> CheckResult:
        """REFORM-2 (2.1): the answer to the small question of the hint is a step, not a wrong answer. The
        reading is recorded (MESSAGE_READ) like the model's, so the session replays the same."""
        reading = rule_step_reading(text, self.item.stem, self.last_tutor)
        if reading is None:
            return check
        self._emit(
            EventType.MESSAGE_READ,
            MessageRead(
                item_id=self.item.id,
                turn=self._turns,
                label="STEP_ANSWER",
                answer=reading.answer,
                source="RULE",
            ),
        )
        return self._step(check, text)

    @staticmethod
    def _step(check: CheckResult, text: str) -> CheckResult:
        return CheckResult(
            Outcome.PARTIAL,
            normalized=text.strip(),
            correct_answer=check.correct_answer,
            detail={"partial_reason": "STEP_CORRECT", "read": "STEP_ANSWER"},
        )

    @staticmethod
    def _unclear(check: CheckResult, text: str) -> bool:
        """Messages the checker and the phrase lists cannot settle: unparsed words, a "là gì" about a word."""
        if check.outcome in (Outcome.UNPARSEABLE, Outcome.NEEDS_LLM):
            return True
        return check.outcome == Outcome.CLARIFY_REQUEST and bool(content_words(text))

    def _read(self, check: CheckResult, text: str) -> CheckResult:
        """CTX-1: the reader's proposal, recorded; an answer it finds is graded by the checker (rule 2)."""
        assert self.reader is not None
        reading = self.reader.read(
            stem=self.item.stem, last_tutor=self.last_tutor, said=text, turn=self._turns
        )
        if reading is None:
            return check
        self._emit(
            EventType.MESSAGE_READ,
            MessageRead(
                item_id=self.item.id,
                turn=self._turns,
                label=reading.label,  # type: ignore[arg-type]
                focus=reading.focus,
                answer=reading.answer,
                source=reading.source,
            ),
        )
        if reading.label == "ANSWER" and reading.answer:
            graded = self._check(reading.answer)
            return graded if graded.outcome in GRADED_OUTCOMES else check
        if reading.label == "STEP_ANSWER":
            numeric = isinstance(self.item.answer, NumericAnswer)
            return self._step(check, text) if numeric and self.state.hint_levels else check
        outcome = _READ_OUTCOME.get(reading.label)
        if outcome is None:
            return check
        if outcome == Outcome.ASKS_ABOUT:
            self._focus = reading.focus or text
        return CheckResult(outcome, normalized=text.strip(), detail={"read": reading.label})

    def _record_answer(self, check: CheckResult, text: str, seconds: float) -> None:
        if self._dialogue_version >= 3 and check.outcome == Outcome.CORRECT and not self.item.is_assessment:
            judged = judge_reason(self.item, text, self.package)
            if (
                {"TERM", "SOLUTION"}.intersection(judged.cues)
                and re.search(r"\b(?:vì|nên)\b", text.lower())
                and not math_errors(text)
            ):
                check = replace(check, detail={**check.detail, "reason_supplied": True})
        st = self.state
        self._last_check = check
        if check.outcome in _UNPRODUCTIVE:
            st.unproductive_turns += 1
        if check.outcome in _HELP:
            st.help_requests += 1
        if check.outcome == Outcome.CLARIFY_REQUEST:
            st.clarify_requests += 1
        elif check.outcome == Outcome.OFF_TOPIC:
            st.off_topic_turns += 1
        elif check.outcome == Outcome.NEGATIVE_AFFECT:
            st.affect_signals += 1
        if check.outcome not in GRADED_OUTCOMES:
            return
        st.attempt_no += 1
        previous = self._last_graded
        if previous is not None and previous.normalized != check.normalized:
            st.answer_changes += 1
        self._last_graded = check
        self._emit(
            EventType.ANSWER_SUBMITTED,
            AnswerSubmitted(
                item_id=self.item.id,
                attempt_no=st.attempt_no,
                raw_text=text,
                latency_ms=int(seconds * 1000),
                outcome=check.outcome,
                normalized=check.normalized,
                error_class=check.error_class,
                misconception_id=check.misconception_id,
                misconception_confidence=check.misconception_confidence,
                answer_changes=st.answer_changes,
            ),
        )
        if (
            self._dialogue_version >= DIALOGUE_VERSION
            and check.outcome == Outcome.CORRECT
            and check.detail.get("reason_supplied")
        ):
            quality = max(0.6, judge_reason(self.item, text, self.package).quality)
            self._emit(
                EventType.EXPLANATION_SUBMITTED,
                ExplanationSubmitted(
                    item_id=self.item.id,
                    text=text,
                    reasoning_quality=quality,
                    label_source="RUBRIC_RULE",
                    label_confidence=1.0,
                ),
            )
            self.state.verified = True
            self.facts = replace(self.facts, reason_seen=True)
        if check.misconception_id:
            self._misconception(check.misconception_id, check.misconception_confidence, self._source())

    def _source(self) -> str:
        ans = self.item.answer
        if isinstance(ans, ChoiceAnswer):
            return "CHOICE"
        if isinstance(ans, NumericAnswer):
            return "NUMERIC"
        if isinstance(ans, BooleanAnswer):
            return "BOOLEAN"
        if isinstance(ans, CompareAnswer | OrderAnswer):
            return "BUG_RULE"
        return "LLM"

    def _misconception(self, mis_id: str, confidence: float, source: str) -> None:
        st = self.state
        st.misconception_counts[mis_id] = st.misconception_counts.get(mis_id, 0) + 1
        if mis_id not in self._misconceptions:
            self._misconceptions.append(mis_id)
        self._emit(
            EventType.MISCONCEPTION_DETECTED,
            MisconceptionDetected(
                item_id=self.item.id,
                misconception_id=mis_id,
                confidence=confidence,
                source=source,  # type: ignore[arg-type]
            ),
        )

    def _on_explanation(self, text: str) -> TutorTurn:
        contextual = (
            boolean_read(self.item, text, self.package, self.last_tutor)
            if self._dialogue_version >= DIALOGUE_VERSION and not self.item.is_assessment
            else None
        )
        if contextual is None and self._ambiguous(text):
            return self._on_unclear(text, "EXPLANATION")
        intent = None if contextual is not None else classify_intent(text)
        self._explained = intent is None
        self.state.last_explanation_vague = False
        if intent is None:
            # DI-55: judged by the rubric (numbers, terms, the item's own solution); a vague reply is asked
            # once more, and whatever comes is recorded with its quality as evidence on R.
            judged = judge_reason(self.item, text, self.package)
            if contextual is not None and contextual.outcome == Outcome.CORRECT:
                judged = replace(judged, quality=max(0.6, judged.quality), cues=(*judged.cues, "CONTEXT"))
            elif contextual is not None and contextual.outcome == Outcome.WRONG:
                judged = replace(judged, quality=0.2, cues=())
            self.state.last_explanation_vague = judged.vague
            self._emit(
                EventType.EXPLANATION_SUBMITTED,
                ExplanationSubmitted(
                    item_id=self.item.id,
                    text=text,
                    reasoning_quality=judged.quality,
                    label_source="RUBRIC_RULE",
                    label_confidence=1.0,
                ),
            )
        self.state.verified = True
        check = CheckResult(intent) if intent is not None else None
        if contextual is not None and contextual.outcome == Outcome.WRONG:
            check = replace(contextual, detail={**contextual.detail, "reason_error": True})
        decision = self._decide("EXPLANATION", check)
        if decision is not None and "ASK_AGAIN" in decision.reason_codes:
            self.state.explanation_asked_again = True  # once (DI-38)
        return self._act(decision, text)

    def _on_reason(self, text: str, seconds: float) -> TutorTurn:
        """The reply to "con đã làm thế nào?" (R-FIRST-WRONG).

        It is the student's account of the method, not a new attempt (DI, approved by the owner on
        2026-10-01). Restating the same wrong answer ("thì nó bằng thật mà"), or words the checker cannot
        read as an answer, are recorded as an explanation and the tutor goes on to the first hint: no
        second wrong attempt, no unproductive turn. A correct answer, a different answer, silence and a
        request for help are handled as on any other turn.
        """
        if self._ambiguous(text):
            return self._on_unclear(text, "ANSWER")
        check = self._check(text)
        last = self._last_graded
        restated = (
            last is not None
            and check.outcome in (Outcome.WRONG, Outcome.PARTIAL)
            and check.normalized == last.normalized
        )
        if last is None or not (restated or check.outcome == Outcome.UNPARSEABLE):
            self._record_answer(check, text, seconds)
            trigger: TurnTrigger = "HINT_REQUEST" if check.outcome in _HELP else "ANSWER"
            return self._act(self._decide(trigger, check), text)
        self._emit(EventType.EXPLANATION_SUBMITTED, ExplanationSubmitted(item_id=self.item.id, text=text))
        self._last_check = last
        return self._act(self._decide("ANSWER", last), text)

    def _on_probe(self, text: str, seconds: float) -> TutorTurn:
        """Read the probe comparison and attribute ``if_wrong`` or ``if_correct`` (GP-08, GP-08b)."""
        if self._ambiguous(text):  # before the probe is used up: asked about, the child may still answer it
            return self._on_unclear(text, "ANSWER")
        option = self._probe_option
        assert option is not None and option.probe is not None
        probe = option.probe
        self._probe_option = None
        intent = classify_intent(text)
        if intent is not None:
            check = CheckResult(intent)  # no answer to the probe: attribute nothing
        else:
            left, right = parse_literal(probe.left), parse_literal(probe.right)
            rel = parse_relation(text, left, right, ask="larger")
            if rel is None:
                check = CheckResult(Outcome.UNPARSEABLE)
            else:
                truth = "<" if left.value < right.value else ">" if left.value > right.value else "="
                correct = rel == truth
                mis = probe.if_correct if correct else probe.if_wrong
                self._misconception(mis, PROBE_CONFIDENCE, "CHOICE")
                # The item answer is still the wrong option: decide again with the cause now known.
                base = self._last_graded or CheckResult(Outcome.WRONG)
                check = replace(
                    base,
                    detail={k: v for k, v in base.detail.items() if k != "probe_option"},
                    misconception_id=mis,
                    misconception_confidence=PROBE_CONFIDENCE,
                    error_class=PROBE_CORRECT_ERROR if correct else ErrorClass.CONCEPTUAL,
                )
                self._last_check = check
                return self._act(self._decide("ANSWER", check), text)
        self._record_answer(check, text, seconds)
        trigger: TurnTrigger = "HINT_REQUEST" if check.outcome in _HELP else "ANSWER"
        return self._act(self._decide(trigger, check), text)

    # ------------------------------------------------------------------ a few letters nothing reads

    def _ambiguous(self, text: str, check: CheckResult | None = None) -> bool:
        """REFORM-5 (3.1): nothing reads the message and it is a few letters ("ki", "kk", "ể"): a key slip
        or a typo, not an answer, an explanation or a request. ``check``: what the checker made of it in a
        phase that grades (None in a phase that waits for words); a graded outcome is never a slip."""
        if check is None:
            if classify_intent(text) is not None:
                return False
        elif check.outcome not in (Outcome.UNPARSEABLE, Outcome.NEEDS_LLM):
            # an open answer the facts could not match is graded WRONG even when nothing in it was readable
            if not (
                check.outcome == Outcome.WRONG
                and check.misconception_id is None
                and isinstance(self.item.answer, OpenAnswer)
            ):
                return False
        return is_gibberish_or_ambiguous_short(text, self._known)

    def _on_unclear(self, text: str, trigger: TurnTrigger) -> TutorTurn:
        """REFORM-5 (3.1, DI-77): the tutor asks what the letters meant (ASK_CONFIRM), once; if the next
        message is as unreadable the policy helps instead (R-ASK-CONFIRM, UNCLEAR_TWICE). Nothing is graded,
        counted as unproductive or praised, and the phase stays what it was. The reading (the rule's, or
        the model's guess and the question it proposes) is recorded, so a replay asks the same without a
        model."""
        st = self.state
        twice = st.confirm_open
        asks_model = (
            not twice
            and self.reader is not None
            and rule_unclear_reading(text) is None
            and self._intent_reads < MAX_INTENT_READS_PER_ITEM
        )
        self._intent_reads += int(asks_model)
        reading = read_unclear(
            self.reader,
            stem=self.item.stem,
            last_tutor=self.last_tutor,
            said=text,
            turn=self._turns,
            allow_model=asks_model,
        )
        self._emit(
            EventType.MESSAGE_READ,
            MessageRead(
                item_id=self.item.id,
                turn=self._turns,
                label=reading.label,  # type: ignore[arg-type]
                source=reading.source,
                guessed_meaning=reading.guessed_meaning,
                clarification=reading.clarification,
            ),
        )
        self._clarification = reading.clarification or None
        self._guess = reading.guessed_meaning or None
        self._guess_intent = intent_of_guess(reading.guessed_meaning)
        check = CheckResult(
            Outcome.NEEDS_CONFIRMATION, normalized=text.strip(), detail={"read": reading.label}
        )
        if unclear_twice(st, check):
            st.help_requests += 1  # the policy turns it into a request for help
        decision = self._decide(trigger, check)
        if decision.move != Move.ASK_CONFIRM:
            if self.phase == Phase.AWAITING_PROBE:
                self._probe_option = None  # the comparison is dropped: the child is helped instead
            if self.phase in (Phase.VERIFYING, Phase.TEACH_BACK):
                self._explained = False
                st.last_explanation_vague = False
        return self._act(decision, text)

    # ------------------------------------------------------------------ tutor side

    def _decide(self, trigger: TurnTrigger, check: CheckResult | None) -> PolicyDecision:
        inp = PolicyInput(
            item=self.item, state=self.state, check=check, trigger=trigger, snapshot=self.snapshot
        )
        decision = decide(inp, self.facts, self.cfg)
        if decision is None:  # only SILENCE/TICK may wait, and the loop never sends them
            raise RuntimeError(f"policy returned no move for {trigger}")
        return self._chosen(inp, decision)

    def _chosen(self, inp: PolicyInput, decision: PolicyDecision) -> PolicyDecision:
        """AUTO-1: the policy offers the moves allowed this turn, the chooser picks one, the policy checks
        the pick. Without a chooser, or with one move only, the policy's own move."""
        if self.chooser is None:
            return decision
        menu = options(inp, decision, self.facts, self.cfg)
        if len(menu) < 2:
            return decision
        pick = self.chooser.choose(
            menu=menu,
            stem=self.item.stem,
            last_tutor=self.last_tutor,
            said=self._said,
            turn=self._turns,
            situation=situation(self.state),
        )
        if pick is None:
            return decision
        played = accept(menu, pick.option_id)
        self._emit(
            EventType.MOVE_CHOSEN,
            MoveChosen(
                item_id=self.item.id,
                turn=self._turns,
                option_id=pick.option_id,
                options=[o.decision.move.value for o in menu],
                move=(played or decision).move.value,
                reason=pick.reason,
                accepted=played is not None,
            ),
        )
        return played or decision

    def _act(self, d: PolicyDecision, student_text: str | None) -> TutorTurn:
        st = self.state
        if self._turns >= MAX_STUDENT_TURNS and d.move not in (Move.CONFIRM_ADVANCE, Move.CLOSE_ITEM):
            solved = self._last_graded is not None and self._last_graded.outcome == Outcome.CORRECT
            d = PolicyDecision(
                move=Move.CLOSE_ITEM,
                resolution=d.resolution
                or (self._solved_resolution() if solved else ItemResolution.UNRESOLVED),
                reason_codes=(*d.reason_codes, "TURN_LIMIT"),
                rule_ids=(*d.rule_ids, "R-TURN-LIMIT"),
            )
        self._emit(
            EventType.POLICY_DECISION,
            PolicyDecisionMade(
                item_id=self.item.id,
                move=d.move,
                hint_level=int(d.level) if d.level is not None else None,
                hint_target=d.target.value if d.target is not None else None,
                misconception_id=d.misconception_id,
                reason_codes=list(d.reason_codes),
                rule_ids=list(d.rule_ids),
            ),
        )
        st.confirm_open = d.move == Move.ASK_CONFIRM
        if d.move == Move.NUDGE:
            st.nudges_sent += 1
        if d.move == Move.EXPLAIN and not {"ASK_REMAINING", "CONVERSATION"}.intersection(d.reason_codes):
            st.explanations += 1
        if d.move in HINT_MOVES and d.level is not None and d.target is not None:
            st.hint_levels.append(d.level)
            st.hint_targets.append(d.target)
        if d.move in (Move.WORKED_GUIDANCE, Move.FULL_EXPLANATION):
            st.worked_shown = True
        if d.move == Move.PROBE and "R-PROBE-CAUSE" in d.rule_ids:
            self._probe_option = self._chosen_option()
            self._probe_asked = True
            if self._probe_option is not None:
                # The renderer finds the probe from the option named in the student text.
                student_text = self._probe_option.text
        if d.move == Move.PROBE and self._probe_option is None:
            st.probes_sent += 1  # R-FIRST-WRONG asks "con làm thế nào?" once per item

        msg, attempts = self._render(d, student_text)
        self._clarification = self._guess = None
        if d.move != Move.ASK_CONFIRM:
            self._guess_intent = None
        self.last_tutor = msg.text
        self._helper_context = "CONVERSATION" in d.reason_codes
        from cavat.modules.tutor.prompt_builder import Turn

        if self._said:
            self._heard.append(Turn("student", self._said))
        self._heard.append(Turn("tutor", msg.text))
        self._heard = self._heard[-6:]
        if d.move == Move.COGNITIVE_CONFLICT:
            st.counter_examples_shown += 1
        if d.move in HINT_MOVES and d.level is not None and msg.source != "FALLBACK":
            self._emit(
                EventType.HINT_DELIVERED,
                HintDelivered(
                    item_id=self.item.id,
                    hint_level=int(d.level),
                    hint_target=(d.target.value if d.target is not None else "STEP"),
                    source=msg.source,  # type: ignore[arg-type]
                    template_ref=msg.hint_ref,
                ),
            )
        self._emit(
            EventType.TUTOR_MESSAGE_SENT,
            TutorMessageSent(
                item_id=self.item.id,
                move=d.move,
                text=msg.text,
                source=msg.source,
                words=len(msg.text.split()),
                attempts_to_pass_validator=attempts,
                model=(getattr(self.renderer, "last_trace", None) and self.renderer.last_trace.model)
                if msg.source == "LLM"
                else None,
            ),
        )
        self.phase = self._next_phase(d)
        if self.phase == Phase.RESOLVED:
            self._resolve(d)
        events, self._pending = tuple(self._pending), []
        return TutorTurn(text=msg.text, move=d.move, phase=self.phase, events=events)

    def _solved_resolution(self) -> ItemResolution:
        return resolution_for(self.state.max_hint_level)

    def _chosen_option(self) -> ChoiceOption | None:
        ans = self.item.answer
        chosen = self._last_graded.detail.get("probe_option") if self._last_graded else None
        if not isinstance(ans, ChoiceAnswer) or chosen is None:
            return None
        return next((o for o in ans.options if o.id == chosen and o.probe is not None), None)

    def _next_phase(self, d: PolicyDecision) -> Phase:
        if "CONVERSATION" in d.reason_codes:
            return self.phase
        if d.move in (Move.CONFIRM_ADVANCE, Move.CLOSE_ITEM) or d.resolution is not None:
            return Phase.RESOLVED
        self._offer = d if d.move == Move.OFFER_CHOICE else None
        if d.move == Move.OFFER_CHOICE:
            self.state.choice_offered = True
            return Phase.AWAITING_CHOICE
        if d.move == Move.ASK_CONFIRM:
            # REFORM-5: the child still owes the explanation (or the probe, or the account of the method)
            return self.phase if self.phase in _WORDS_PHASES else Phase.AWAITING_CONFIRM
        if d.move == Move.PROBE:
            return Phase.AWAITING_PROBE if self._probe_option is not None else Phase.AWAITING_REASON
        if d.move in (Move.TEACH_BACK, Move.FULL_EXPLANATION):
            # H7 already ends with "nói lại cách làm": its reply is the teach-back (PART 16.2 WORKED).
            self._explanation_asked = True
            return Phase.TEACH_BACK
        if d.move == Move.VERIFY:
            if self._last_check is not None and self._last_check.outcome == Outcome.CORRECT:
                self._explanation_asked = True
                return Phase.VERIFYING
            self._why_pending = True  # R-STRONG-PRIOR: "vì sao" before a hint; the reply is an answer
        return Phase.AWAITING

    def _render(self, d: PolicyDecision, student_text: str | None) -> tuple[RenderedMessage, int]:
        explaining = d.move == Move.EXPLAIN
        # BRAIN-1 (C2): a child who answered right and could not say why is taught again, with the approved
        # passages on the item's own question as one more ground
        reteaching = teaches_again(d)
        focus = self._focus if explaining else (self.item.stem if reteaching else None)
        evidence = self.knowledge + (
            tuple(self.explainer(focus or "", self.last_tutor))
            if (explaining or reteaching) and self.explainer
            else ()
        )
        if self._dialogue_version >= 3 and "REPAIR" in d.reason_codes and not self.item.is_assessment:
            from cavat.modules.tutor.dialogue import conversion_ground

            if scaffold := conversion_ground(self.item):
                evidence = (scaffold, *evidence)
        graded = self._last_graded
        asking = d.move == Move.ASK_CONFIRM
        ctx = RenderContext(
            decision=d,
            item=self.item,
            package=self.package,
            state=self.state,
            student_text=student_text,
            persona=self.package.persona,
            focus=self._focus if explaining else None,
            last_tutor=self.last_tutor or None,
            evidence=evidence,
            guessed_meaning=self._guess if asking else None,
            clarification=self._clarification if asking else None,
            check=graded,
            solved=graded is not None and graded.outcome == Outcome.CORRECT,
            answer_revealed=self.state.max_hint_level >= 7 and not self.item.is_assessment,
            follow_up=self._follow_up if "ASK_REMAINING" in d.reason_codes else "",
        )
        if ctx.clarification and (codes := self._refused(ctx.clarification, ctx)):
            # REFORM-5: the reader's question did not pass; the template asks (DI-77). The record keeps it.
            self._emit(
                EventType.OUTPUT_REJECTED,
                OutputRejected(item_id=self.item.id, move=d.move, issue_codes=codes, source="LLM"),
            )
            ctx = replace(ctx, clarification=None)
        # DI-60: the word cap of the final check follows the approved text, as in the LLM renderer. With the
        # fixed 60 an approved explanation of a geometry period (158 words with its stem) failed twice and the
        # child got a generic phrase, and a model message the renderer had accepted was rejected here.
        anchor = TemplateRenderer().render(ctx).text
        for attempt in (1, 2):
            msg = self.renderer.render(ctx)
            if msg.source == "LLM":
                # the model's words were checked by the brain (its arithmetic, its length): here the validator
                # runs again, with the numbers left to the arithmetic check and the cap of a spoken turn
                cap = max(word_cap(ctx, anchor), BRAIN_MAX_WORDS)
                final = replace(ctx, max_words=cap, free_numbers=True)
            else:
                final = replace(ctx, max_words=max(ctx.max_words, len(msg.text.split())))
            result = self.validator(msg.text, final)
            if result.ok and msg.source == "LLM" and math_errors(msg.text):
                result = ValidationResult((ValidationIssue(ValidationCode.UNGROUNDED_NUMBER, "WRONG_MATH"),))
            if result.ok:
                return msg, attempt
            self._emit(
                EventType.OUTPUT_REJECTED,
                OutputRejected(
                    item_id=self.item.id, move=d.move, issue_codes=list(result.codes), source=msg.source
                ),
            )
        return RenderedMessage(text=self._fallback(d.move), source="FALLBACK"), 3

    def _refused(self, question: str, ctx: RenderContext) -> list[str]:
        """Why the question a reader proposed may not be said: its own checks, then the validator's."""
        problems = clarification_problems(question, ctx.persona.student_address)
        return problems + list(self.validator(question, ctx).codes)

    def _fallback(self, move: Move) -> str:
        if move == Move.PRESENT:
            return self.item.stem
        p = self.package.persona
        t, s = p.tutor_self, p.student_address
        phrase = PHRASES[_FALLBACK_KEY.get(move, "hint")]
        return phrase.format(T=t[:1].upper() + t[1:], t=t, S=s[:1].upper() + s[1:], s=s)

    def _resolve(self, d: PolicyDecision) -> None:
        st, it = self.state, self.item
        st.resolution = d.resolution or ItemResolution.UNRESOLVED
        last = self._last_graded
        final_error = last.error_class if last is not None and last.outcome != Outcome.CORRECT else None
        self._emit(
            EventType.ITEM_RESOLVED,
            ItemResolved(
                item_id=it.id,
                purpose=it.purpose,
                kc_ids=list(it.kc_ids),
                cognitive_level=it.cognitive_level,
                difficulty=it.difficulty,
                transfer=it.transfer,
                resolution=st.resolution,
                max_hint_level=int(st.max_hint_level),
                attempts=st.attempt_no,
                hints_count=len(st.hint_levels),
                misconception_ids=list(self._misconceptions),
                final_error_class=final_error,
                explained=self._explained if self._explanation_asked else None,
                time_s=st.seconds_since_shown,
            ),
        )

    def _emit(self, event_type: EventType, payload: BaseModel) -> None:
        event = TutorEvent(type=event_type, payload=payload.model_dump(mode="json"))
        self.events.append(event)
        self._pending.append(event)


def _option_words(item: Item) -> list[str]:
    """What a child may quote of a choice item: the options, their aliases and their letters."""
    if not isinstance(item.answer, ChoiceAnswer):
        return []
    return [w for o in item.answer.options for w in (o.text, *o.aliases, o.id)]
