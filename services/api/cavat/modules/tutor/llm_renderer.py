"""LLM renderer: the conversation brain speaks, the approved templates are the safety net (BRAIN-1,
ADR-034).

Until llm-renderer.v8 the model *phrased a template*: the template of the move was the "anchor", the
model had to keep its idea and its mathematical terms, and the owner saw a tutor that "answers by a
template, not by the context" (measured: 29% of the words at the exercise loop were the model's). v9
hands the turn to ``tutor/brain.py``: the model writes it from a context pack (the question, the
child's words, the checker's verdict, the last turns, the move and level the policy chose, the
approved material as ground) in the voice of ``constitution.v6.md``. The policy still decides the
move, the hint target and level (rule 1); the checker still decides right and wrong (rule 2); an
assessment (EXIT) item is still said with the approved template word for word and its answer never
reaches a prompt.

Which turns the model writes: every move of a practice item except PRESENT (the stem as it is), the
CLOSE_ITEM of an unresolved item (the fixed words of calm), the question the intent agent already
proposed (ASK_CONFIRM for a key slip) and the move on when the child said nothing to answer. VERIFY
is now the model's: the first "vì sao" is written from the question and the child's answer, and must
name what the child wrote (``OFF_TARGET``, the 9/10 child asked about the comma). CLOSE_ITEM after a
child who answered right and could not say why, and the CONFIRM_ADVANCE that explains for them, are
the model teaching again with the numbers of the question; the fallback is the approved explanation
or worked steps, and never only "Mình sang câu tiếp theo nhé".

What the net checks (the validator, then ``brain.speech_codes``): no answer of an unsolved item, no
praise of a wrong answer, no echo of the child, address, one question, length, safety, wrong
arithmetic (``WRONG_MATH``), a repeated turn, a ground read out as it stands (``COPIES_GROUND``).
The keyword checks of v8 (``BEYOND_ANCHOR``, ``KEY_IDEA_MISSING``, ``OFF_ANCHOR``) are gone. A
refused turn is tried once more with the reasons, then the caller says the approved material, then
the template. When the router answers ``use_template`` (429, session cap, no API key, prompt too
long) the template is used at once: a lesson never stops because of a provider. One instance serves
one session: it counts the LLM calls of that session and keeps the last turns of the current item
for the prompt.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace

from cavat.core.pedagogy import Move
from cavat.modules.ai_gateway.base import ChatMessage, ModelClass
from cavat.modules.ai_gateway.router import DEFAULT_MAX_LLM_CALLS_PER_SESSION, AIRouter
from cavat.modules.assessment.vi_numbers import normalize_text
from cavat.modules.content.lesson_package import BooleanAnswer
from cavat.modules.teaching.answer_support import support_request, supported
from cavat.modules.tutor import brain
from cavat.modules.tutor.brain import BRAIN_MAX_WORDS, BrainPack
from cavat.modules.tutor.contracts import (
    MessageSource,
    MessageValidator,
    PolicyDecision,
    RenderContext,
    RenderedMessage,
    ValidationCode,
)
from cavat.modules.tutor.policy import UNCLEAR_REASONS
from cavat.modules.tutor.prompt_builder import RECENT_TURNS, Turn, given_name
from cavat.modules.tutor.renderer import TemplateRenderer, fitting_generic_hints
from cavat.modules.tutor.validator import singles_out_choice

# v9: BRAIN-1 (DI-84), see the module docstring
# v8: REFORM-1b (DI-81), OFFER_CHOICE, CONFIRM_ADVANCE and a lead before the approved explanation
# v7: REFORM-5, ASK_CONFIRM about a key slip or a typo is said by the intent agent's question or the
# template: no second call for the same message
LLM_RENDERER_VERSION = "llm-renderer.v10"
# PRESENT is the stem as it is; CLOSE_ITEM is the model's only when it teaches (``teaches``)
TEMPLATE_ONLY_MOVES = frozenset({Move.PRESENT, Move.CLOSE_ITEM})
LLM_MOVES = frozenset(Move) - TEMPLATE_ONLY_MOVES
# DI-61 (LLM-2), DI-71, DI-84: the session's model calls go where the wording matters most. These
# moves may use every call; every other move leaves them the last fifth of the cap.
TOP_MOVES = frozenset({Move.EXPLAIN, Move.REDIRECT, Move.CLOSE_ITEM, Move.FULL_EXPLANATION})
CHOICE_MISSING = "CHOICE_MISSING"
ASKS_ON_ADVANCE = "ASKS_ON_ADVANCE"
# DI-60: words a model message may add to its anchor when the anchor is already near the cap (final check)
ANCHOR_SLACK = 15
ALTITUDE_RULE = (
    "Trong tam giác tù, đường cao từ đỉnh có góc tù nằm trong tam giác; "
    "hai đường cao từ hai đỉnh còn lại nằm ngoài tam giác. "
    "Đường cao vuông góc với đường thẳng chứa cạnh đối diện."
)
_TALK = frozenset({"OFF_TOPIC", "CLARIFY", "NEGATIVE_AFFECT"})
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def word_cap(ctx: RenderContext, anchor: str) -> int:
    """DI-60: the cap of the approved text: never under the turn's cap, room for the anchor plus a little."""
    return max(ctx.max_words, len(anchor.split()) + ANCHOR_SLACK)


def teaches(ctx: RenderContext) -> bool:
    """The turn explains again what the child could not say: the child answered right and could not (or would
    not) say why. The numbers of the question are the model's example."""
    return teaches_again(ctx.decision)


def teaches_again(d: PolicyDecision) -> bool:
    if d.move == Move.CONFIRM_ADVANCE:
        return "EXPLAIN_AND_ADVANCE" in d.reason_codes
    return (
        d.move == Move.CLOSE_ITEM
        and "NO_EXPLANATION" in d.reason_codes
        and not _TALK.intersection(d.reason_codes)
        and d.resolution is not None
        and d.resolution.value != "UNRESOLVED"
    )


def _template_only(ctx: RenderContext) -> bool:
    """Said with the approved template: a test item, PRESENT, the fixed words of an unresolved CLOSE_ITEM, a
    question the intent agent or the template already has for a typo, and a move on when the child said
    nothing to answer."""
    move = ctx.decision.move
    if ctx.item.is_assessment:
        return True
    if move in TEMPLATE_ONLY_MOVES and not teaches(ctx):
        return True
    if move == Move.ASK_CONFIRM and UNCLEAR_REASONS.intersection(ctx.decision.reason_codes):
        return True  # REFORM-5: the reader already wrote (or the template has) the question for this slip
    return move == Move.CONFIRM_ADVANCE and not teaches(ctx) and not (ctx.student_text or "").strip()


def move_codes(text: str, ctx: RenderContext) -> tuple[str, ...]:
    """DI-81: what a whole message of OFFER_CHOICE or CONFIRM_ADVANCE must (not) say."""
    move, lowered = ctx.decision.move, normalize_text(text)
    if move == Move.OFFER_CHOICE and not ("gợi ý" in lowered and "thử" in lowered):
        return (CHOICE_MISSING,)  # the screen shows both buttons: the words must offer both
    if move == Move.CONFIRM_ADVANCE and "?" in text:
        return (ASKS_ON_ADVANCE,)  # the item is closed; the next one opens at once
    return ()


def verdict_line(ctx: RenderContext) -> str:
    """The checker's conclusion on the child's graded answer, in words for the pack."""
    check = ctx.check
    if check is None:
        return ""
    if set(ctx.decision.reason_codes) & {"OFF_TOPIC", "ASKS_ABOUT", "CLARIFY", "NEGATIVE_AFFECT"}:
        return "Lượt hiện tại chưa chấm đáp án; không dùng kết luận cũ để phủ nhận điều con vừa nói."
    normalized = {"true": "Đúng", "false": "Sai"}.get(check.normalized, check.normalized)
    shown = f' (con viết "{normalized}")' if normalized else ""
    outcome = check.outcome.value
    if outcome == "CORRECT":
        said = "ĐÚNG"
    elif outcome == "WRONG":
        error = f", kiểu lỗi {check.error_class.value}" if check.error_class else ""
        said = f"CHƯA ĐÚNG{error}"
    elif outcome == "PARTIAL":
        said = "mới ĐÚNG MỘT PHẦN"
    else:
        return ""
    state = ctx.state
    tries = f" Con đã trả lời {state.attempt_no} lần, cô đã gợi ý {len(state.hint_levels)} lần."
    return f"Câu trả lời của con{shown}: {said}.{tries}"


def _sentences(text: str) -> list[str]:
    return [x for x in _SENTENCE_END.split(" ".join(text.split())) if x]


def grounds_for(ctx: RenderContext, anchor: str, reveal: bool) -> tuple[str, ...]:
    """The approved material the turn may rest on. The explanation and the worked steps of an item whose
    answer the tutor may not say yet are left out of the prompt; the anchor (the hint of the level the
    policy chose, the counter-example) says what this turn may do about it."""
    item = ctx.item
    out: list[str] = []
    if anchor and ctx.decision.move in _CONTENT_MOVES:
        out.append(anchor)
    if reveal:
        if item.explanation:
            out.append(item.explanation)
        if item.worked_solution:
            out.append("Các bước: " + " ".join(item.worked_solution))
    out += list(ctx.evidence)
    if any("đường cao" in s.lower() and "tam giác" in s.lower() for s in ctx.evidence):
        out.append(ALTITUDE_RULE)
    if ctx.decision.move == Move.VERIFY and (item.verify_prompt or ctx.package.default_verify_prompt):
        out.append(
            "Ý câu hỏi vì sao của giáo viên: "
            + (item.verify_prompt or ctx.package.default_verify_prompt or "")
        )
    if reveal and not out:
        # nothing approved on this item: the strongest hints the lesson has say the method
        hints = sorted((*item.hints, *fitting_generic_hints(item, ctx.package)), key=lambda h: -h.level)
        out += [h.text for h in hints[:2]]
    return tuple(dict.fromkeys(g for g in out if g.strip()))


_CONTENT_MOVES = frozenset(
    {
        Move.HINT,
        Move.COGNITIVE_CONFLICT,
        Move.EXPLAIN,
        Move.WORKED_GUIDANCE,
        Move.FULL_EXPLANATION,
        Move.ASK_CONFIRM,
    }
)


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
    model: str | None = None  # the model that wrote an LLM message


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
        self._support_calls = 0

    def render(self, ctx: RenderContext) -> RenderedMessage:
        if ctx.item.id != self._history_item:
            self._history, self._history_item = [], ctx.item.id
        fallback = self._template.render(ctx)
        if _template_only(ctx):
            message = fallback
            self.last_trace = RenderTrace(ctx.decision.move, fallback.source)
        elif not self._may_call(ctx.decision.move):
            message = fallback  # DI-61: this move leaves the remaining calls to the moves that need them
            self.last_trace = RenderTrace(ctx.decision.move, fallback.source, 0, "call_budget")
        else:
            message = self._render_with_brain(ctx, fallback)
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
        return self.calls_used < cap - cap // 5

    def _pack(self, ctx: RenderContext, fallback: RenderedMessage) -> BrainPack:
        d, item = ctx.decision, ctx.item
        reveal = ctx.solved or d.move == Move.FULL_EXPLANATION or teaches(ctx)
        task = brain.task_for(
            Move.CLOSE_ITEM if teaches(ctx) else d.move,
            level=int(d.level) if d.level is not None else None,
            asks=ctx.focus,
            reasons=d.reason_codes,
        )
        if ctx.follow_up:
            task = (
                "Con đã làm ĐÚNG một phần. Công nhận ngắn phần con vừa trả lời, không chấm nó sai. "
                f"Chỉ hỏi phần còn thiếu: {ctx.follow_up} Không đổi sang câu hỏi lý thuyết khác."
            )
        answer = ""
        if reveal and ctx.check is not None and ctx.check.normalized:
            answer = {"true": "Đúng", "false": "Sai"}.get(ctx.check.normalized, ctx.check.normalized)
        return BrainPack(
            task=task,
            question=item.rephrase or item.stem,
            student_text=ctx.student_text or "",
            verdict=verdict_line(ctx),
            recent=tuple(self._history),
            grounds=grounds_for(ctx, fallback.text, reveal),
            answer=answer,
            tutor_self=ctx.persona.tutor_self,
            student_address=ctx.persona.student_address,
            name=given_name(self._student_name),
            lesson=f"{ctx.package.title} (lớp {ctx.package.grade})",
            question_kind="TRUE_FALSE" if isinstance(item.answer, BooleanAnswer) else "TASK",
            max_words=60
            if d.move
            in (Move.EXPLAIN, Move.HINT, Move.WORKED_GUIDANCE, Move.FULL_EXPLANATION, Move.CLOSE_ITEM)
            else 45,
        )

    def _codes(self, text: str, ctx: RenderContext, pack: BrainPack) -> tuple[str, ...]:
        """Every rejection code of a model message: the validator, then the brain's net."""
        d = ctx.decision
        vctx = replace(ctx, max_words=BRAIN_MAX_WORDS, free_numbers=True)
        codes = list(self._validator(text, vctx).codes)
        if text:  # an empty message is already rejected; the other checks need words to look at
            asks = d.move == Move.VERIFY and "VERIFY_BEFORE_HINT" not in d.reason_codes
            codes += brain.speech_codes(
                text,
                pack,
                ask_target=asks,
                rephrase=(
                    (d.move == Move.EXPLAIN and not ctx.follow_up)
                    or teaches(ctx)
                    or "CLARIFY" in d.reason_codes
                ),
            )
            codes += move_codes(text, ctx)
            if not pack.answer and singles_out_choice(text, ctx.item):
                codes.append(ValidationCode.ANSWER_LEAK)
            teaching = ctx.decision.move in (
                Move.EXPLAIN,
                Move.HINT,
                Move.WORKED_GUIDANCE,
                Move.FULL_EXPLANATION,
                Move.CLOSE_ITEM,
            )
            if (
                not codes
                and not ctx.item.is_assessment
                and (isinstance(ctx.item.answer, BooleanAnswer) or (ctx.evidence and teaching))
            ):
                # The statement is a test proposition, not a source of truth. Only the verifier sees
                # the practice key; it cannot change the grade or write any student state.
                premises = tuple(ctx.evidence)
                if ALTITUDE_RULE in pack.grounds:
                    premises += (ALTITUDE_RULE,)
                if isinstance(ctx.item.answer, BooleanAnswer):
                    truth = "đúng" if ctx.item.answer.value else "sai"
                    premises += (f"Giáo viên đã xác nhận nhận định “{ctx.item.stem}” là {truth}.",)
                else:
                    premises += (f"Đề bài để tham chiếu: {ctx.item.stem}",)
                if ctx.check is not None:
                    premises += (f"Kết quả câu trả lời đã chấm của học sinh: {verdict_line(ctx)}",)
                request = support_request(text, premises, ctx.student_text or ctx.item.stem)
                request = replace(
                    request,
                    messages=(
                        ChatMessage(
                            "system",
                            request.messages[0].content
                            + " Đây là lời gia sư: động viên, câu hỏi gợi mở và chuyển bước "
                            "không phải kiến thức Toán mới. Nhận xét học sinh phải khớp kết quả "
                            "đã chấm. Nhận định trong đề có thể SAI, tuyệt đối không lấy nó làm định lý. "
                            "Nếu lời cô có mệnh đề sai hoặc tự mâu thuẫn, dù sửa ở câu sau, supported=false. "
                            "Vẫn trích đoạn NGUỒN làm căn cứ cho bước dạy, không trích lời học sinh.",
                        ),
                        request.messages[1],
                    ),
                    schema_name="classroom_support_v1",
                )
                result = self._router.chat(
                    ModelClass.TUTOR_REASONING,
                    request,
                    calls_used=self.calls_used + self._support_calls + 1,
                )
                self._support_calls += result.calls_made
                if result.result is None or not supported(result.result.data, premises):
                    codes.append("UNSUPPORTED_MEANING")
        return tuple(dict.fromkeys(codes))

    def _render_with_brain(self, ctx: RenderContext, fallback: RenderedMessage) -> RenderedMessage:
        move = ctx.decision.move
        pack = self._pack(ctx, fallback)
        self._support_calls = 0
        out = brain.speak(
            self._router,
            pack,
            lambda text: self._codes(text, ctx, pack),
            calls_used=self.calls_used,
        )
        total_calls = out.calls + self._support_calls
        self.calls_used += total_calls
        if out.text is None:
            self.last_trace = RenderTrace(
                move, fallback.source, total_calls, out.fallback_reason, out.rejected, out.flagged
            )
            return fallback
        self.last_trace = RenderTrace(
            move, "LLM", total_calls, None, out.rejected, out.flagged, out.feedback, out.model
        )
        return RenderedMessage(text=out.text, source="LLM", hint_ref=fallback.hint_ref)
