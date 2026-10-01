"""LLM renderer (T06b): Qwen phrases the policy's move, approved templates stay the safety net (ADR-017).

PRESENT, CONFIRM_ADVANCE, CLOSE_ITEM, OFFER_CHOICE and ASK_CONFIRM always use the template, and so does
every move on an assessment (EXIT) item: the model must not add help to a test. Any other move
calls the gateway (``ModelClass.TUTOR_REASONING``, strict JSON), runs the output validator, retries once
with the validator's codes, then falls back to the template. A message that passes the validator is
still rejected (``BEYOND_ANCHOR``) when it uses a number that is neither in the item stem, in the anchor
nor in what the student said: seen with real Qwen output, which turned an H2 question into the H4 step
"0,3 viết thành 0,30". The policy picks the hint level, the model may not raise it. When the router
answers ``use_template``
(429, session cap, no API key, prompt too long) the template is used at once: a lesson never stops because
of a provider. One instance serves one session: it counts the LLM calls of that session and keeps the last
turns of the current item for the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cavat.core.pedagogy import Move
from cavat.modules.ai_gateway.base import ModelClass
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.assessment.vi_numbers import extract_numbers
from cavat.modules.tutor.contracts import (
    MessageSource,
    MessageValidator,
    RenderContext,
    RenderedMessage,
)
from cavat.modules.tutor.prompt_builder import RECENT_TURNS, Turn, build_request, prompt_view
from cavat.modules.tutor.renderer import TemplateRenderer

LLM_RENDERER_VERSION = "llm-renderer.v1"
TEMPLATE_ONLY_MOVES = frozenset(
    {Move.PRESENT, Move.CONFIRM_ADVANCE, Move.CLOSE_ITEM, Move.OFFER_CHOICE, Move.ASK_CONFIRM}
)
MAX_ATTEMPTS = 2  # the first call and one retry carrying the validator's codes
BEYOND_ANCHOR = "BEYOND_ANCHOR"


def beyond_anchor(text: str, ctx: RenderContext, anchor: str) -> list[str]:
    """Numbers of a model message that the stem, the anchor and the student did not use.

    Decimals are compared as written ("0,30" is new next to "0,3": rewriting it is a hint step);
    other numbers by value.
    """
    sources = [ctx.item.stem, ctx.item.rephrase or "", anchor, ctx.student_text or ""]
    allowed = [n for s in sources for n in extract_numbers(s)]
    written = {n.text for n in allowed}
    values = {n.value for n in allowed}
    return [
        n.text
        for n in extract_numbers(text)
        if (n.text not in written if n.form == "decimal" else n.value not in values)
    ]


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
    ) -> None:
        self._router = router
        self._template = template
        self._validator = validator
        self._student_name = student_name
        self.calls_used = calls_used  # LLM requests already sent in this session (from SessionContext)
        self._history: list[Turn] = []
        self._history_item: str | None = None
        self.last_trace: RenderTrace | None = None

    def render(self, ctx: RenderContext) -> RenderedMessage:
        if ctx.item.id != self._history_item:
            self._history, self._history_item = [], ctx.item.id
        fallback = self._template.render(ctx)
        if ctx.decision.move in TEMPLATE_ONLY_MOVES or ctx.item.is_assessment:
            message = fallback
            self.last_trace = RenderTrace(ctx.decision.move, fallback.source)
        else:
            message = self._render_with_llm(ctx, fallback)
        if ctx.student_text:
            self._history.append(Turn("student", ctx.student_text))
        self._history.append(Turn("tutor", message.text))
        del self._history[:-RECENT_TURNS]
        return message

    def _render_with_llm(self, ctx: RenderContext, fallback: RenderedMessage) -> RenderedMessage:
        move = ctx.decision.move
        view = prompt_view(ctx)
        anchor = fallback.text if view is ctx else self._template.render(view).text
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
            codes = self._validator(text, ctx).codes  # the full item: leak checks need the answer
            if beyond_anchor(text, ctx, anchor):
                codes = (*codes, BEYOND_ANCHOR)
            if not codes:
                self.last_trace = RenderTrace(move, "LLM", calls, None, tuple(rejected), flagged, feedback)
                return RenderedMessage(text=text, source="LLM", hint_ref=fallback.hint_ref)
            rejected.append(codes)
        self.last_trace = RenderTrace(move, fallback.source, calls, "validation", tuple(rejected), flagged)
        return fallback
