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

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from cavat.config import get_settings
from cavat.core.en_text import IRREGULAR_PAST
from cavat.core.pedagogy import Move
from cavat.core.subjects import check_subject
from cavat.core.vi_text import fold
from cavat.modules.ai_gateway.base import ModelClass
from cavat.modules.content.chapter_package import Chapter
from cavat.modules.tutor.brain import BrainPack, fields_of
from cavat.modules.tutor.contracts import RenderContext, RenderedMessage, ValidationCode, ValidationResult
from cavat.modules.tutor.english import (
    EN_DIALOGUE_LABELS,
    RETEACH_TASK_EN,
    build_english_request,
    english_off_topic,
    listen_request_en,
    task_for_en,
    unit_targets,
)
from cavat.modules.tutor.english_validator import (
    STANDARD_WORDS,
    EnglishCode,
    display_text,
    english_spans,
    is_say_after_me,
    mark_english,
    normalize_en,
    unit_lexicon,
    validator_for,
)
from cavat.modules.tutor.llm_renderer import RenderTrace, _template_only
from cavat.modules.tutor.prompt_builder import Turn, clean_text
from cavat.modules.tutor.reader import LiveReader, Reading, rule_reading
from cavat.modules.tutor.renderer import TemplateRenderer

ENGLISH_SESSION_VERSION = "english-session/1.2.0"  # 1.2.0 (ENG-5g): DI-156–163; 1.1.0 (ENG-5c): DI-148–151
RECENT_TURNS_EN = 6
# DI-164: the model is the way a turn is worded; a refused output is asked again twice with the refusal codes
# (ENG-5g) before the approved words are said, so the fallback is the last resort, not the usual turn.
MAX_ATTEMPTS_EN = 3
# DI-140: the moves an English turn may spend a model call on. The others keep the approved template words
# (PRESENT, test items, CONFIRM_ADVANCE without words to answer: ``llm_renderer._template_only``).
_REVEAL_MOVES = frozenset({Move.FULL_EXPLANATION})
# DI-151 (ENG-5c, L-4): messages in a row that only repeat the tutor before the period stops (N-ECHO).
ECHO_STOP_EN = 4
RETEACH_MAX_WORDS = 55  # DI-162: a short teaching again, then the question that waits
# DI-163: what a model's turn says the child said, in English ("Con nói: [[en: Yes, I did.]]").
_QUOTE = re.compile(r"(?i)\bcon\s+(?:vừa\s+|đã\s+)?nói(?:\s+là)?\s*:?\s*\[\[en:\s*([^\]]+?)\s*\]\]")


@dataclass(frozen=True)
class EnglishTools:
    """The unit's own data an English session checks against: its English words and target sentences."""

    lexicon: frozenset[str]
    targets: tuple[str, ...]
    # ENG-5g (DI-163): the English words of each node's approved teaching (theory, rule, worked examples). A
    # hint on an item may use them and the item's own; other English is teaching off the item.
    node_words: Mapping[str, frozenset[str]] = field(default_factory=dict)


_tools: dict[tuple[str, str], EnglishTools] = {}


def english_tools(chapter: Chapter) -> EnglishTools:
    """``unit_lexicon`` and ``unit_targets`` of the unit (approved data only), once per unit version."""
    pkg = chapter.package
    if pkg.subject != "english":
        raise ValueError(f"{pkg.chapter_id} is {pkg.subject}, not an English unit")
    key = (pkg.chapter_id, pkg.version)
    if key not in _tools:
        lessons = list(chapter.lessons.values())
        _tools[key] = EnglishTools(unit_lexicon(lessons), unit_targets(lessons), _node_words(chapter))
    return _tools[key]


_EN_TOKEN = re.compile(r"(?<![^\W\d_])[A-Za-z][A-Za-z']*(?![^\W\d_])")
# Words any sentence of the unit may hold: grammar words, the names of the people of the book.
_COMMON_EN = frozenset(
    "a an the and or to of in on at with for is are was were it i we you he she they my your his her our "
    "their this that there yes no not do does did ok".split()
)


def english_words(text: str) -> set[str]:
    """The English words of a text: ASCII words that are not a Vietnamese syllable typed without marks are
    not told apart here, so only the words of the unit's English count (callers intersect with a lexicon)."""
    return {w.lower() for w in _EN_TOKEN.findall(text)}


def _node_words(chapter: Chapter) -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for node in chapter.nodes:
        texts = [
            node.name,
            node.method.rule,
            *(t.text for t in node.theory),
            *(t.reply or "" for t in node.theory),
        ]
        texts += [x for w in node.worked_examples for x in (w.problem, *w.steps, w.answer)]
        out[node.id] = frozenset(w for t in texts for w in english_words(t or ""))
    return out


def _item_texts(item: Any) -> list[str]:
    answer = item.answer
    texts = [item.stem, item.explanation or "", item.rephrase or "", *item.worked_solution]
    texts += [h.text for h in item.hints]
    texts += [str(a) for a in getattr(answer, "accept", ()) or ()]
    texts += [o.text for o in getattr(answer, "options", ()) or ()]
    return texts


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
        "validator": session_validator(
            knowledge_tools(english_tools(chapter), get_settings().english_allow_tutor_knowledge).lexicon
        ),
        "off_topic": english_off_topic,
        "echo_stop": ECHO_STOP_EN,
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
        knowledge: bool = True,
    ) -> None:
        self._knowledge = knowledge
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

    def _pack(self, ctx: RenderContext, retry: tuple[str, ...], approved: str = "") -> BrainPack:
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
            # DI-163 (L-7): a hint rests on the item's own approved hint first, so it stays on the item
            grounds=tuple(
                dict.fromkeys(g for g in ((approved if d.move == Move.HINT else ""), *ctx.evidence[:2]) if g)
            ),
            answer=str(accept[0]) if reveal and accept and isinstance(accept[0], str) else "",
            tutor_self=persona.tutor_self,
            student_address=persona.student_address,
            name=self._student_name,
            max_words=ctx.max_words,
            lesson=ctx.package.title,
            retry_codes=retry,
        )

    def _named(self, text: str) -> str:
        """DI-163 (L-9): the child's name exactly as it is written ("Vuong", never "Vuông"): a word that is
        the name with other diacritics is put back to the name. Deterministic, never a model's call."""
        name = (self._student_name or "").strip()
        if not name or " " in name:
            return text
        folded = fold(name.lower())

        def fix(m: re.Match[str]) -> str:
            word = m.group(0)
            return name if word != name and fold(word.lower()) == folded else word

        return re.sub(r"\w+", fix, text)

    def _own_checks(self, marked: str, ctx: RenderContext) -> tuple[str, ...]:
        """DI-163: two checks of a model's English turn the shared validator cannot make. INVENTED_QUOTE: it
        quotes the child ("Con nói: Yes, I did…") with English the child did not say. OFF_ITEM_ENGLISH: a hint
        or an explanation teaches English of another node than the item's (the "Did you…?" hints on a
        comprehension item of VOCAB)."""
        codes: list[str] = []
        said = normalize_en(ctx.student_text or "")
        for quoted in _QUOTE.findall(marked):
            if normalize_en(quoted) and f" {normalize_en(quoted)} " not in f" {said} ":
                codes.append("INVENTED_QUOTE")
                break
        if ctx.decision.move in (Move.HINT, Move.EXPLAIN) and self._tools.node_words:
            allowed = set().union(*(self._tools.node_words.get(k, frozenset()) for k in ctx.item.kc_ids))
            allowed |= {w for t in _item_texts(ctx.item) for w in english_words(t)}
            if self._knowledge:
                allowed |= STANDARD_WORDS
            spoken = {w for span in english_spans(marked) for w in english_words(span)}
            if len(spoken - allowed - _COMMON_EN) >= 1 or ("did" in spoken and "did" not in allowed):
                codes.append("OFF_ITEM_ENGLISH")
        return tuple(codes)

    def explain_again(
        self,
        *,
        student_text: str,
        asked: str,
        grounds: Sequence[str],
        recent: Sequence[tuple[str, str]],
        item: Any,
        package: Any,
    ) -> Any:
        """DI-162 (L-8): the teaching loop asks the English brain to teach again, short, what the child asked
        in a theory or retell wait. Checked by the English validator (the node's check item for the leak
        check) and by ``_own_checks``; the question that waits ends the turn. None: no model may speak."""
        from cavat.core.pedagogy import ActivityType
        from cavat.modules.teaching.grounded import Spoken
        from cavat.modules.tutor.contracts import ItemState, Persona, PolicyDecision

        persona = package.persona
        ctx = RenderContext(
            decision=PolicyDecision(move=Move.EXPLAIN, reason_codes=("RETEACH",)),
            item=item,
            package=package,
            state=ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE),
            student_text=student_text,
            persona=Persona(tutor_self=persona.tutor_self, student_address=persona.student_address),
            max_words=RETEACH_MAX_WORDS,
        )
        history = tuple(Turn(role, text) for role, text in recent)[-RECENT_TURNS_EN:]
        calls, rejected = 0, []
        for _ in range(MAX_ATTEMPTS_EN):
            pack = BrainPack(
                task=RETEACH_TASK_EN,
                question=asked,
                student_text=student_text,
                recent=history,
                grounds=tuple(grounds),
                tutor_self=persona.tutor_self,
                student_address=persona.student_address,
                name=self._student_name,
                max_words=RETEACH_MAX_WORDS,
                lesson=package.title,
                retry_codes=tuple(rejected[-1]) if rejected else (),
            )
            request = build_english_request(pack, unit_words=self._tools.targets, knowledge=self._knowledge)
            outcome = self._router.chat(
                ModelClass.TUTOR_REASONING, request, calls_used=self.calls_used + calls
            )
            calls += outcome.calls_made
            if outcome.result is None:
                break
            text, _, _ = fields_of(outcome.result.data)
            marked = mark_english(self._named(text), self._tools.lexicon)
            codes = tuple(self._validator(marked, ctx).codes) + self._own_checks(marked, ctx)
            if not codes and asked and not display_text(marked).rstrip().endswith("?"):
                codes = ("MISSING_QUESTION",)
            if not codes:
                self.calls_used += calls
                return Spoken(display_text(marked), "LLM", (), tuple(rejected))
            rejected.append(codes)
        self.calls_used += calls
        return Spoken("", "TEMPLATE", (), tuple(rejected))

    def _with_brain(self, ctx: RenderContext, fallback: RenderedMessage) -> RenderedMessage:
        move, calls, rejected = ctx.decision.move, 0, []
        level = int(ctx.decision.level) if ctx.decision.level is not None else None
        for _ in range(MAX_ATTEMPTS_EN):
            request = build_english_request(
                self._pack(ctx, tuple(rejected[-1]) if rejected else (), fallback.text),
                unit_words=self._tools.targets,
                hint_level=level if move == Move.HINT else None,
                knowledge=self._knowledge,
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
            text = self._named(text)
            marked = mark_english(text, self._tools.lexicon)
            codes = tuple(self._validator(marked, ctx).codes) + self._own_checks(marked, ctx)
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
    verdict = f"Câu trả lời của con: {said}. Con đã trả lời {ctx.state.attempt_no} lần."
    if check.detail.get("whole_sentence"):  # DI-159: the right word, said alone
        verdict += " Con mới nói đúng một từ cần điền; câu này cần nói cả câu."
    return verdict


def knowledge_tools(tools: EnglishTools, knowledge: bool) -> EnglishTools:
    """DI-164 (BRAIN-4 for English): with ``ENGLISH_ALLOW_TUTOR_KNOWLEDGE`` the lexicon of the checks holds
    the everyday English of grade 5 and the past forms the checker knows; the targets of the prompt are the
    unit's own, unchanged."""
    if not knowledge:
        return tools
    extra = STANDARD_WORDS | set(IRREGULAR_PAST) | set(IRREGULAR_PAST.values())
    return replace(tools, lexicon=tools.lexicon | extra)


def english_renderer(
    chapter: Chapter, router: Any, *, student_name, calls_used, history, history_item, knowledge: bool = True
):
    """The live renderer of an English session (``session.service.llm_renderer`` for Mathematics)."""
    tools = knowledge_tools(english_tools(chapter), knowledge)
    return EnglishRenderer(
        router,
        TemplateRenderer(),
        validator_for("english", lexicon=tools.lexicon),
        tools,
        knowledge=knowledge,
        student_name=student_name,
        calls_used=calls_used,
        history=history,
        history_item=history_item,
    )
