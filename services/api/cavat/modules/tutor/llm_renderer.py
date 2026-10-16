"""LLM renderer (T06b): Qwen phrases the policy's move, approved templates stay the safety net (ADR-017).

The model only words PROBE, HINT, COGNITIVE_CONFLICT, NUDGE and REDIRECT (``LLM_MOVES``). Every other move
is said with the approved template, word for word, and so is every move on an assessment (EXIT) item: the
model must not add help to a test, and the reply to a correct answer, the worked steps and the full
explanation are lesson content.

For an LLM move the renderer calls the gateway (``ModelClass.TUTOR_REASONING``, strict JSON), runs the
output validator, retries once with the rejection codes, then falls back to the template. The template for
the move is the *anchor*: the idea the teacher approved for this turn (CTX-1, llm-renderer.v3: the model
answers what the child just said in its own words; v2 made it keep 60% of the anchor's words, and the owner
saw a tutor that "answers by a template, not by the context"). Checks beyond the validator, each one from a
real Qwen output:

- ``BEYOND_ANCHOR``: a number that is not in the stem, the anchor, the tutor's last message, the passages
  or what the student said (an H2 question came back as the H4 step "0,3 viết thành 0,30");
- ``REPEATS_PREVIOUS``: an earlier tutor turn of the item copied word for word;
- ``KEY_IDEA_MISSING``: fewer than ``KEY_TERMS`` of the anchor's mathematical terms kept (all of them when it
  has one or two): the idea and the level of the hint live in its terms (asked for the H3 concept hint,
  the model reworded the earlier counter-example instead);
- ``NEW_MATH_TERM``: a mathematical term none of those sources uses (a step or a rule of another level);
- ``OFF_ANCHOR``: for an anchor with no mathematical term, fewer than ``MIN_ANCHOR_COVERAGE`` of its words.

LLM-1 (llm-renderer.v4, DI-60), from the S1 sessions where 16 of 20 drafts were rejected, all for form:

- the word cap follows the anchor: ``max(max_words, anchor words + ANCHOR_SLACK)``. A geometry anchor
  that restates a long stem already has about 40 words, and every rewording of it went over 60;
- two form slips are repaired in place, then the repaired text goes through every check again: a missing
  final question gets the anchor's own last question (approved text), and the child called "em" in a
  lesson that says "con" gets the lesson's word. Nothing else is ever repaired.

The policy picks the move, the target and the level; the model may not change them. When the router answers
``use_template`` (429, session cap, no API key, prompt too long) the template is used at once: a lesson
never stops because of a provider. One instance serves one session: it counts the LLM calls of that session
and keeps the last turns of the current item for the prompt.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any

from cavat.core.pedagogy import Move
from cavat.modules.ai_gateway.base import ModelClass
from cavat.modules.ai_gateway.router import DEFAULT_MAX_LLM_CALLS_PER_SESSION, AIRouter
from cavat.modules.assessment.math_terms import terms_in, terms_missing
from cavat.modules.assessment.vi_numbers import extract_numbers, normalize_text
from cavat.modules.tutor.contracts import (
    MessageSource,
    MessageValidator,
    RenderContext,
    RenderedMessage,
    ValidationCode,
)
from cavat.modules.tutor.prompt_builder import RECENT_TURNS, Turn, build_request, prompt_view
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import singles_out_choice

LLM_RENDERER_VERSION = "llm-renderer.v5"
LLM_MOVES = frozenset(
    {Move.PROBE, Move.HINT, Move.COGNITIVE_CONFLICT, Move.NUDGE, Move.REDIRECT, Move.EXPLAIN}
)
TEMPLATE_ONLY_MOVES = frozenset(Move) - LLM_MOVES
# DI-61 (LLM-2): the session's model calls go where the wording matters most. The owner chose (2026-10-16)
# to keep the cap of 15 and spend it on explanations, hints after a wrong answer and pulling back to the
# lesson. EXPLAIN and REDIRECT may use every call; HINT and COGNITIVE_CONFLICT leave the last fifth of the
# cap to them; PROBE and NUDGE (the approved "con làm thế nào" says it well) only use the first third.
TOP_MOVES = frozenset({Move.EXPLAIN, Move.REDIRECT})
HINT_MOVES_LLM = frozenset({Move.HINT, Move.COGNITIVE_CONFLICT})
MAX_ATTEMPTS = 2  # the first call and one retry carrying the rejection codes
BEYOND_ANCHOR = "BEYOND_ANCHOR"
REPEATS_PREVIOUS = "REPEATS_PREVIOUS"
OFF_ANCHOR = "OFF_ANCHOR"
KEY_IDEA_MISSING = "KEY_IDEA_MISSING"
NEW_MATH_TERM = "NEW_MATH_TERM"
# DI-42: for an anchor without a mathematical term ("Con đang nghĩ đến đâu rồi?"), the share of its words a
# message must keep. A message about something else keeps under 0,3 (v2 asked 0,6 of every anchor).
MIN_ANCHOR_COVERAGE = 0.3
# DI-42: share of the anchor's mathematical terms a message must keep ("mẫu số đặc biệt là 10, 100 hay 1000"
# answers "mẫu như nào" without saying "phân số thập phân" again).
KEY_TERMS = 0.6
# DI-60: words a model message may add to its anchor when the anchor is already near the cap.
ANCHOR_SLACK = 15
_REPAIRABLE = frozenset({ValidationCode.MISSING_QUESTION, ValidationCode.WRONG_ADDRESS})
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")

_WORD = re.compile(r"[^\W_]+(?:[,.\-][^\W_]+)*")  # words, decimals ("0,25") and "xăng-ti-mét"


def anchor_coverage(text: str, anchor: str) -> float:
    """Share of the anchor's distinct words (Vietnamese syllables, numbers) that also occur in ``text``."""
    wanted = set(_WORD.findall(normalize_text(anchor)))
    if not wanted:
        return 1.0
    return len(wanted & set(_WORD.findall(normalize_text(text)))) / len(wanted)


def beyond_anchor(text: str, ctx: RenderContext, anchor: str) -> list[str]:
    """Numbers of a model message that the stem, the anchor and the student did not use.

    Decimals are compared as written ("0,30" is new next to "0,3": rewriting it is a hint step);
    other numbers by value.
    """
    allowed = [n for s in _sources(ctx, anchor) for n in extract_numbers(s)]
    written = {n.text for n in allowed}
    values = {n.value for n in allowed}
    return [
        n.text
        for n in extract_numbers(text)
        if (n.text not in written if n.form == "decimal" else n.value not in values)
    ]


def _sources(ctx: RenderContext, anchor: str) -> list[str]:
    """What a model message may rest on: the item, the anchor, the tutor's last words, passages, the child."""
    return [
        ctx.item.stem,
        ctx.item.rephrase or "",
        anchor,
        ctx.last_tutor or "",
        *ctx.evidence,
        ctx.student_text or "",
    ]


def idea_codes(text: str, ctx: RenderContext, anchor: str) -> tuple[str, ...]:
    """CTX-1: the anchor's idea kept (its mathematical terms), nothing mathematical added."""
    codes: list[str] = []
    key = terms_in(anchor)
    if key:
        kept = len(key) - len(terms_missing(key, [text]))
        if kept < len(key) and (len(key) <= 2 or kept / len(key) < KEY_TERMS):
            codes.append(KEY_IDEA_MISSING)
    elif anchor_coverage(text, anchor) < MIN_ANCHOR_COVERAGE:
        codes.append(OFF_ANCHOR)
    if terms_missing(terms_in(text), _sources(ctx, anchor)):
        codes.append(NEW_MATH_TERM)
    return tuple(codes)


def word_cap(ctx: RenderContext, anchor: str) -> int:
    """DI-60: a model message's cap: never under the turn's cap, room for the anchor plus a little."""
    return max(ctx.max_words, len(anchor.split()) + ANCHOR_SLACK)


def repair(text: str, codes: Sequence[str], ctx: RenderContext, anchor: str) -> str | None:
    """DI-60: fix the two form slips in place, or None. Only when they are the only codes; the caller checks
    the repaired text again in full."""
    if not codes or not set(codes) <= _REPAIRABLE:
        return None
    out = text
    if ValidationCode.WRONG_ADDRESS in codes:
        want = ctx.persona.student_address
        for word in ("em", "cháu", "cậu"):
            if word != want:
                out = re.sub(
                    rf"(?<!\w)({word})(?!\w)(?! bé)",
                    lambda m: want.capitalize() if m.group(1)[0].isupper() else want,
                    out,
                    flags=re.IGNORECASE,
                )
    if ValidationCode.MISSING_QUESTION in codes:
        if "?" in out:  # a question that is not last: reordering would change what the model said
            return None
        if not out.rstrip().endswith((".", "!", "…")):  # cut short (max output tokens): never patch it
            return None
        sentences = [x for x in _SENTENCE_END.split(anchor.strip()) if x]
        if not sentences or not sentences[-1].rstrip(" \"'”»)").endswith("?"):
            return None
        out = f"{out.rstrip()} {sentences[-1]}"
    return out if out != text else None


@dataclass(frozen=True)
class RenderTrace:
    """How the last message was produced, for logs and (once wired) the session event."""

    move: Move
    source: MessageSource
    calls_made: int = 0
    fallback_reason: str | None = None  # a router FallbackReason, or "validation"
    rejected: tuple[tuple[str, ...], ...] = ()  # validator codes of each rejected model output
    safety_flag: bool = False
    policy_feedback: str = ""


def _fields(data: dict[str, Any] | None) -> tuple[str, bool, str]:
    data = data or {}
    message, feedback = data.get("message"), data.get("policy_feedback")
    text = " ".join(message.split()) if isinstance(message, str) else ""
    return text, data.get("safety_flag") is True, feedback if isinstance(feedback, str) else ""


class LLMRenderer:
    """`MessageRenderer` backed by the AI gateway, with the template renderer as fallback."""

    version = LLM_RENDERER_VERSION

    def __init__(
        self,
        router: AIRouter,
        template: TemplateRenderer,
        validator: MessageValidator,
        *,
        student_name: str | None = None,
        calls_used: int = 0,
        history: Sequence[Turn] = (),
        history_item: str | None = None,
    ) -> None:
        self._router = router
        self._template = template
        self._validator = validator
        self._student_name = student_name
        self.calls_used = calls_used  # LLM requests already sent in this session (from SessionContext)
        # A session that rebuilds the renderer for each request passes the turns of the current item.
        self._history: list[Turn] = list(history)[-RECENT_TURNS:]
        self._history_item: str | None = history_item
        self.last_trace: RenderTrace | None = None

    def render(self, ctx: RenderContext) -> RenderedMessage:
        if ctx.item.id != self._history_item:
            self._history, self._history_item = [], ctx.item.id
        fallback = self._template.render(ctx)
        if ctx.decision.move in TEMPLATE_ONLY_MOVES or ctx.item.is_assessment:
            message = fallback
            self.last_trace = RenderTrace(ctx.decision.move, fallback.source)
        elif not self._may_call(ctx.decision.move):
            message = fallback  # DI-61: this move leaves the remaining calls to the moves that need them
            self.last_trace = RenderTrace(ctx.decision.move, fallback.source, 0, "call_budget")
        else:
            message = self._render_with_llm(ctx, fallback)
        if ctx.student_text:
            self._history.append(Turn("student", ctx.student_text))
        self._history.append(Turn("tutor", message.text))
        del self._history[:-RECENT_TURNS]
        return message

    def _may_call(self, move: Move) -> bool:
        """DI-61: whether this move may still spend one of the session's model calls."""
        cap = getattr(self._router, "max_calls_per_session", DEFAULT_MAX_LLM_CALLS_PER_SESSION)
        if move in TOP_MOVES or self.calls_used >= cap:
            return True  # the router enforces the cap itself and says so ("session_cap")
        if move in HINT_MOVES_LLM:
            return self.calls_used < cap - cap // 5
        return self.calls_used < max(1, cap // 3)

    def _repeats(self, text: str) -> bool:
        """The model copied a tutor turn of this item word for word (seen with real Qwen output: a level 3
        hint came back as the level 2 sentence it had just said). The student gets nothing new from it."""
        said = normalize_text(text)
        return any(t.role == "tutor" and normalize_text(t.text) == said for t in self._history)

    def _codes(self, text: str, ctx: RenderContext, anchor: str) -> tuple[str, ...]:
        """Every rejection code of a model message: the validator, then the anchor checks."""
        codes = self._validator(text, ctx).codes  # the full item: leak checks need the answer
        if text:  # an empty message is already rejected; the anchor checks need words to look at
            if beyond_anchor(text, ctx, anchor):
                codes = (*codes, BEYOND_ANCHOR)
            if self._repeats(text):
                codes = (*codes, REPEATS_PREVIOUS)
            codes = (*codes, *idea_codes(text, ctx, anchor))
            if singles_out_choice(text, ctx.item) and not singles_out_choice(anchor, ctx.item):
                codes = (*codes, ValidationCode.ANSWER_LEAK)
        return tuple(codes)

    def _render_with_llm(self, ctx: RenderContext, fallback: RenderedMessage) -> RenderedMessage:
        move = ctx.decision.move
        view = prompt_view(ctx)
        anchor = fallback.text if view is ctx else self._template.render(view).text
        ctx = replace(ctx, max_words=word_cap(ctx, anchor))  # DI-60: the prompt and the checks use it
        rejected: list[tuple[str, ...]] = []
        calls, flagged = 0, False  # a safety flag survives even when its message is rejected
        for _ in range(MAX_ATTEMPTS):
            request = build_request(
                ctx,
                anchor=anchor,
                history=self._history,
                student_name=self._student_name,
                retry_codes=rejected[-1] if rejected else (),
            )
            outcome = self._router.chat(ModelClass.TUTOR_REASONING, request, calls_used=self.calls_used)
            self.calls_used += outcome.calls_made
            calls += outcome.calls_made
            if outcome.result is None:
                reason = outcome.fallback_reason.value if outcome.fallback_reason else None
                self.last_trace = RenderTrace(move, fallback.source, calls, reason, tuple(rejected), flagged)
                return fallback
            text, safety_flag, feedback = _fields(outcome.result.data)
            flagged = flagged or safety_flag
            codes = self._codes(text, ctx, anchor)
            fixed = repair(text, codes, ctx, anchor)
            if fixed is not None and not self._codes(fixed, ctx, anchor):
                text, codes = fixed, ()
            if not codes:
                self.last_trace = RenderTrace(move, "LLM", calls, None, tuple(rejected), flagged, feedback)
                return RenderedMessage(text=text, source="LLM", hint_ref=fallback.hint_ref)
            rejected.append(codes)
        self.last_trace = RenderTrace(move, fallback.source, calls, "validation", tuple(rejected), flagged)
        return fallback
