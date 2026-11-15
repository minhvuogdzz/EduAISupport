"""What an English session runs with (ENG-5b, ADR-066, DI-140–143): the pieces of ENG-3b…ENG-6 put together.

The teaching loop, the node policy, the item loop and the projector are shared with Mathematics (rule S2).
What differs is configuration of the session's subject, which the backend reads from the unit package the
session runs (rule S1; a client never names it):

- the validator: ``english_validator.validator_for("english", lexicon=…)`` (ADR-065, DI-138);
- the rule that keeps a question of another subject out of the lesson: ``english.english_off_topic``
  (DI-139), run by the loop before any other path (``TeachingLoop(off_topic=…)``);
- the brain that words item moves: ``EnglishRenderer`` sends ``english.build_english_request``
  (``constitution-en`` + ``english_g5``) and never the Math constitution (P1, P2);
- the listener: ``EnglishLiveReader`` reads with ``listener-en`` (``listen_request_en``, label OFF_TOPIC);
- grading (``answer_check``, ADR-063) and the mastery policy (``policy_for``, ``node-mastery-en/0.1.0``) are
  chosen by the shared code from the package's subject already.

Nothing here is imported by a Mathematics session: ``loop_options("math")`` is empty.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from cavat.core.pedagogy import Move
from cavat.core.subjects import check_subject
from cavat.modules.ai_gateway.base import ModelClass
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.tutor.brain import BrainPack, fields_of
from cavat.modules.tutor.contracts import RenderContext, RenderedMessage, ValidationCode, ValidationResult
from cavat.modules.tutor.english import (
    EN_DIALOGUE_LABELS,
    build_english_request,
    english_off_topic,
    listen_request_en,
    task_for_en,
    unit_targets,
)
from cavat.modules.tutor.english_validator import (
    EnglishCode,
    display_text,
    is_say_after_me,
    mark_english,
    unit_lexicon,
    validator_for,
)
from cavat.modules.tutor.llm_renderer import RenderTrace, _template_only
from cavat.modules.tutor.prompt_builder import Turn, clean_text
from cavat.modules.tutor.reader import LiveReader, Reading, rule_reading
from cavat.modules.tutor.renderer import TemplateRenderer

ENGLISH_SESSION_VERSION = "english-session/1.0.0"
RECENT_TURNS_EN = 6
MAX_ATTEMPTS_EN = 2  # one request, then once more with the rejection codes (as the Math brain)
# DI-140: the moves an English turn may spend a model call on. The others keep the approved template words
# (PRESENT, test items, CONFIRM_ADVANCE without words to answer: ``llm_renderer._template_only``).
_REVEAL_MOVES = frozenset({Move.FULL_EXPLANATION})


@dataclass(frozen=True)
class EnglishTools:
    """The unit's own data an English session checks against: its English words and target sentences."""

    lexicon: frozenset[str]
    targets: tuple[str, ...]


_tools: dict[tuple[str, str], EnglishTools] = {}


def english_tools(chapter: Chapter) -> EnglishTools:
    """``unit_lexicon`` and ``unit_targets`` of the unit (approved data only), once per unit version."""
    pkg = chapter.package
    if pkg.subject != "english":
        raise ValueError(f"{pkg.chapter_id} is {pkg.subject}, not an English unit")
    key = (pkg.chapter_id, pkg.version)
    if key not in _tools:
        lessons = list(chapter.lessons.values())
        _tools[key] = EnglishTools(unit_lexicon(lessons), unit_targets(lessons))
    return _tools[key]


def session_validator(lexicon: frozenset[str]) -> Callable[[str, RenderContext], ValidationResult]:
    """DI-141: the validator of an English session's item loop. A model's words (the item loop marks them with
    ``free_numbers``) get the whole English validator (DI-138). Approved words (a template of the unit's own
    data, which the owner reviewed: stems, hints, model sentences) are trusted as the Mathematics templates
    are; only what may never be said in an English lesson is checked on them: a term of the other subject
    (P3) and a broken ``[[en: …]]`` mark. The English checks were written for a model: on the approved data
    of Unit 11 they rejected 259 of its sentences (a name such as "Co To", a question in English, the
    teacher's own H4 hint giving part of the sentence)."""
    full = validator_for("english", lexicon=lexicon)

    def validate(text: str, ctx: RenderContext) -> ValidationResult:
        result = full(text, ctx)
        if ctx.free_numbers:
            return result
        kept = tuple(i for i in result.issues if i.code in _ALWAYS_CHECKED)
        return ValidationResult(kept)

    return validate


_ALWAYS_CHECKED = frozenset({EnglishCode.MATH_TERM, EnglishCode.BROKEN_MARKER, ValidationCode.EMPTY})


def loop_options(chapter: Chapter) -> dict[str, Any]:
    """What the teaching loop of a session of this chapter's subject is built with. Mathematics: nothing,
    the loop's defaults (its validator, no off-topic rule), exactly as before ENG-5b."""
    if check_subject(chapter.package.subject) == "math":
        return {}
    return {
        "validator": session_validator(english_tools(chapter).lexicon),
        "off_topic": english_off_topic,
    }


# ---------------------------------------------------------------------------------------------- listener


def listen_en(model: Any, *, stem: str, last_tutor: str, said: str, recent: Sequence[Turn], phase: str):
    """``conversation.listen`` for an English session: ``listener-en``, the same labels plus OFF_TOPIC. It
    never grades and never receives an answer key. A question of another subject never reaches the model
    (DI-139): the rule reads it first."""
    if english_off_topic(said):
        return Reading("OFF_TOPIC", focus="câu hỏi ngoài bài Tiếng Anh", source="RULE")
    request = listen_request_en(stem=stem, last_tutor=last_tutor, said=said, recent=recent, phase=phase)
    out = model.router.chat(ModelClass.INTENT_AGENT, request, calls_used=model.calls_used + model.calls_made)
    model.calls_made += out.calls_made
    data = out.result.data if out.result is not None else None
    if not data or data.get("label") not in EN_DIALOGUE_LABELS:
        return None
    return Reading(
        data["label"],
        focus=clean_text(str(data.get("focus", "")), 300),
        answer=clean_text(str(data.get("answer", "")), 80),
        source="LLM",
    )


class EnglishLiveReader(LiveReader):
    """The live reader of an English session: the discourse rules, then ``listener-en``. The Math reading
    prompt (``reader.READ_SYSTEM``) is never sent: an unclear message is read by rule only."""

    def read_dialogue(self, *, stem, last_tutor, said, turn, recent=(), phase=""):
        from cavat.modules.tutor.conversation import conversation_signal

        if self.semantic and (signal := conversation_signal(said, last_tutor)) is not None:
            return signal
        if english_off_topic(said):
            return Reading("OFF_TOPIC", focus="câu hỏi ngoài bài Tiếng Anh", source="RULE")
        if self.model is None or not self.semantic:
            return None
        return listen_en(self.model, stem=stem, last_tutor=last_tutor, said=said, recent=recent, phase=phase)

    def read(self, *, stem: str, last_tutor: str, said: str, turn: int) -> Reading | None:
        return rule_reading(said, last_tutor)


# ---------------------------------------------------------------------------------------------- renderer


class EnglishRenderer:
    """``MessageRenderer`` of an English session: the English brain words the move, the template is the
    fallback. Same contract as ``LLMRenderer`` for the session (``calls_used``, ``last_trace``, ``recent``),
    without any of its Math checks: the English validator (DI-138) is the net. The text kept and shown has
    no ``[[en: …]]`` marks (``display_text``); the voice plan finds the English again (ENG-6)."""

    version = ENGLISH_SESSION_VERSION

    def __init__(
        self,
        router: Any,
        template: TemplateRenderer,
        validator: Callable[[str, RenderContext], Any],
        tools: EnglishTools,
        *,
        student_name: str | None = None,
        calls_used: int = 0,
        history: Sequence[Turn] = (),
        history_item: str | None = None,
    ) -> None:
        self._router, self._template, self._validator, self._tools = router, template, validator, tools
        self._student_name = student_name
        self.calls_used = calls_used
        self._history: list[Turn] = list(history)[-RECENT_TURNS_EN:]
        self._history_item = history_item
        self.last_trace: RenderTrace | None = None

    @property
    def recent(self) -> tuple[Turn, ...]:
        return tuple(self._history)

    def render(self, ctx: RenderContext) -> RenderedMessage:
        if ctx.item.id != self._history_item:
            self._history, self._history_item = [], ctx.item.id
        fallback = self._template.render(ctx)
        if _template_only(ctx) or "CONTINUE" in ctx.decision.reason_codes:
            message = fallback
            self.last_trace = RenderTrace(ctx.decision.move, fallback.source)
        else:
            message = self._with_brain(ctx, fallback)
        if ctx.student_text:
            self._history.append(Turn("student", ctx.student_text))
        self._history.append(Turn("tutor", message.text))
        del self._history[:-RECENT_TURNS_EN]
        return message

    def _pack(self, ctx: RenderContext, retry: tuple[str, ...]) -> BrainPack:
        d, item = ctx.decision, ctx.item
        say_after_me = is_say_after_me(item)
        reveal = ctx.solved or ctx.answer_revealed or d.move in _REVEAL_MOVES or say_after_me
        accept = getattr(item.answer, "accept", None) or ()
        persona = ctx.persona
        return BrainPack(
            task=task_for_en(
                d.move,
                level=int(d.level) if d.level is not None else None,
                asks=ctx.focus,
                reasons=d.reason_codes,
                say_after_me=say_after_me,
            ),
            question=item.stem,
            student_text=ctx.student_text or "",
            verdict=_verdict(ctx),
            recent=tuple(self._history),
            grounds=tuple(g for g in (*ctx.evidence[:2],) if g),
            answer=str(accept[0]) if reveal and accept and isinstance(accept[0], str) else "",
            tutor_self=persona.tutor_self,
            student_address=persona.student_address,
            name=self._student_name,
            max_words=ctx.max_words,
            lesson=ctx.package.title,
            retry_codes=retry,
        )

    def _with_brain(self, ctx: RenderContext, fallback: RenderedMessage) -> RenderedMessage:
        move, calls, rejected = ctx.decision.move, 0, []
        level = int(ctx.decision.level) if ctx.decision.level is not None else None
        for _ in range(MAX_ATTEMPTS_EN):
            request = build_english_request(
                self._pack(ctx, tuple(rejected[-1]) if rejected else ()),
                unit_words=self._tools.targets,
                hint_level=level if move == Move.HINT else None,
            )
            outcome = self._router.chat(
                ModelClass.TUTOR_REASONING, request, calls_used=self.calls_used + calls
            )
            calls += outcome.calls_made
            if outcome.result is None:
                reason = outcome.fallback_reason.value if outcome.fallback_reason else None
                self.calls_used += calls
                self.last_trace = RenderTrace(move, fallback.source, calls, reason, tuple(rejected))
                return fallback
            text, flagged, feedback = fields_of(outcome.result.data)
            marked = mark_english(text, self._tools.lexicon)
            codes = tuple(self._validator(marked, ctx).codes)
            if not codes:
                self.calls_used += calls
                self.last_trace = RenderTrace(
                    move, "LLM", calls, None, tuple(rejected), flagged, feedback, outcome.result.model
                )
                return RenderedMessage(text=display_text(marked), source="LLM", hint_ref=fallback.hint_ref)
            rejected.append(codes)
        self.calls_used += calls
        self.last_trace = RenderTrace(move, fallback.source, calls, "validation", tuple(rejected))
        return fallback


def _verdict(ctx: RenderContext) -> str:
    """The checker's conclusion, in words (the English checker graded; the model never does)."""
    check = ctx.check
    if check is None or set(ctx.decision.reason_codes) & {"OFF_TOPIC", "CONVERSATION", "CLARIFY"}:
        return ""
    said = {"CORRECT": "ĐÚNG", "WRONG": "CHƯA ĐÚNG", "PARTIAL": "mới ĐÚNG MỘT PHẦN"}.get(check.outcome.value)
    if said is None:
        return ""
    return f"Câu trả lời của con: {said}. Con đã trả lời {ctx.state.attempt_no} lần."


def english_renderer(chapter: Chapter, router: Any, *, student_name, calls_used, history, history_item):
    """The live renderer of an English session (``session.service.llm_renderer`` for Mathematics)."""
    tools = english_tools(chapter)
    return EnglishRenderer(
        router,
        TemplateRenderer(),
        validator_for("english", lexicon=tools.lexicon),
        tools,
        student_name=student_name,
        calls_used=calls_used,
        history=history,
        history_item=history_item,
    )
