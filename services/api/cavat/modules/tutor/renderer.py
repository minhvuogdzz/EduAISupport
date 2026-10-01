"""Template renderer: turns a policy decision into Vietnamese text without any model call (T03).

Blueprint PART 15.3: approved lesson content comes first. A hint is looked up in this order: the item's
template for (target, level), the item's template for the same target at a lower level, the lesson's
generic hints, then a fixed fallback sentence. The fixed sentences below were approved by the owner
(the supervising teacher) on 2026-10-01; changing them is a template change (CLAUDE.md rule 7).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from cavat.core.pedagogy import HintLevel, HintTarget, Move
from cavat.modules.assessment.vi_numbers import fold
from cavat.modules.content.lesson_package import (
    ChoiceAnswer,
    CompareAnswer,
    HintTemplate,
    Item,
    LessonPackage,
)
from cavat.modules.tutor.contracts import MessageSource, RenderContext, RenderedMessage

TEMPLATE_VERSION = "template-renderer.v2"

# {T}/{t}: how the tutor calls themself, {S}/{s}: how the tutor calls the student (capitalised / not).
PHRASES: dict[str, str] = {
    "probe": "{S} nói cho {t} nghe {s} đã làm thế nào để ra câu trả lời đó được không?",
    "hint": "{S} đọc lại đề bài thật chậm rồi cho {t} biết {s} định bắt đầu từ đâu nhé?",
    "nudge": "{S} đang nghĩ đến đâu rồi, có cần {t} gợi ý thêm không?",
    "redirect": "Mình quay lại câu đang làm nhé.",
    "try_it": "{S} làm thử giúp {t} được không?",
    "offer_choice": "{S} muốn {t} gợi ý thêm hay {s} muốn tự thử lại một lần nữa?",
    "ask_confirm": "{T} chưa chắc đã hiểu đúng ý {s}. {S} viết lại câu trả lời rõ hơn giúp {t} được không?",
    "verify": "Đúng rồi! {S} giải thích cho {t} vì sao {s} làm như vậy được không?",
    "confirm_advance": "Đúng rồi! {S} đã suy nghĩ và kiểm tra rất cẩn thận. Mình sang câu tiếp theo nhé.",
    "worked_next": "Vậy bước cuối cùng là gì, {s} làm tiếp giúp {t} được không?",
    "explain_back": "{S} nói lại cách làm bằng lời của {s} cho {t} nghe được không?",
    "teach_back": "{S} thử giảng lại cho {t} cách làm câu này bằng lời của {s} được không?",
    "close_item": "Mình dừng câu này ở đây nhé. {S} đã cố gắng suy nghĩ rất chăm chỉ.",
}


def _cap(word: str) -> str:
    return word[:1].upper() + word[1:]


def _say(ctx: RenderContext, key: str) -> str:
    t, s = ctx.persona.tutor_self, ctx.persona.student_address
    return PHRASES[key].format(T=_cap(t), t=t, S=_cap(s), s=s)


def _msg(text: str, source: MessageSource, hint_ref: str | None = None) -> RenderedMessage:
    return RenderedMessage(text=" ".join(text.split()), source=source, hint_ref=hint_ref)


def _one_question(text: str) -> bool:
    return len(re.findall(r"\?+", text)) <= 1


# SELF_CHECK and FORMAT say what kind of help is needed, not how much: they are looked up by target.
# The other targets are steps of the hint ladder and are looked up by level.
_KIND_TARGETS = frozenset({HintTarget.SELF_CHECK, HintTarget.FORMAT})


def _pick(
    hints: list[HintTemplate], target: HintTarget | None, level: HintLevel, *, below: bool = False
) -> HintTemplate | None:
    """The template at `level` (with ``below``: the strongest one under it); `target` only breaks a tie.

    A template asking more than one question would fail the validator (one question per turn), so it
    is skipped and the lookup falls through to the next source.
    """
    candidates = [
        h for h in hints if (h.level < level if below else h.level == level) and _one_question(h.text)
    ]
    return max(candidates, key=lambda h: (h.level, h.target == target), default=None)


def select_hint(
    item: Item, package: LessonPackage, target: HintTarget | None, level: HintLevel | None
) -> tuple[HintTemplate, MessageSource, str] | None:
    """Approved hint for the policy's (target, level).

    Order approved by the owner on 2026-10-01. A lesson gives each item one hint per level (its ladder),
    whatever the target, so the level decides:

    1. the hint at that level: the item's, else the generic one;
    2. else the strongest hint below that level: the item's, else the generic one.

    Before, the target came first: a level 1 STEP hint fell through to the fixed fallback sentence although
    the item had a level 1 hint, and a level 3 CONCEPT hint gave the level 2 sentence again.
    SELF_CHECK and FORMAT are the exception: a hint of that kind is used when there is one at or below
    the level.
    """
    level = HintLevel.H1 if level is None else level
    sources: list[tuple[list[HintTemplate], MessageSource, str]] = [
        (item.hints, "TEMPLATE", item.id),
        (package.generic_hints, "GENERIC", "GENERIC"),
    ]

    def found(hint: HintTemplate, source: MessageSource, owner: str):
        return hint, source, f"{owner}:{hint.target.value}:H{int(hint.level)}"

    if target in _KIND_TARGETS:
        for hints, source, owner in sources:
            of_kind = [h for h in hints if h.target == target and h.level <= level and _one_question(h.text)]
            if of_kind:
                return found(max(of_kind, key=lambda h: h.level), source, owner)
    ladders = [
        ([h for h in hints if h.target not in _KIND_TARGETS], src, owner) for hints, src, owner in sources
    ]
    for below in (False, True):
        for hints, source, owner in ladders:
            hit = _pick(hints, target, level, below=below)
            if hit is not None:
                return found(hit, source, owner)
    return None


def counter_example(
    item: Item, package: LessonPackage, misconception_id: str | None
) -> tuple[str, str] | None:
    """First usable counter-example of the misconception; {left}/{right} only fill for compare items."""
    mis = package.misconception(misconception_id) if misconception_id else None
    if mis is None:
        return None
    for i, text in enumerate(mis.counter_examples, start=1):
        if "{" not in text:
            return text, f"{mis.id}:COUNTER:{i}"
        if isinstance(item.answer, CompareAnswer):
            return text.format(left=item.answer.left, right=item.answer.right), f"{mis.id}:COUNTER:{i}"
    return None


def _ask_item(ctx: RenderContext) -> tuple[str, str]:
    """The item restated as one question: the rephrase if any, else the stem plus an invitation."""
    item = ctx.item
    if item.rephrase:
        return item.rephrase, f"{item.id}:REPHRASE"
    if "?" in item.stem:
        return item.stem, f"{item.id}:STEM"
    return f"{item.stem}. {_say(ctx, 'try_it')}", f"{item.id}:STEM"


def _present(ctx: RenderContext) -> RenderedMessage:
    return _msg(ctx.item.stem, "TEMPLATE", f"{ctx.item.id}:STEM")


def _probe(ctx: RenderContext) -> RenderedMessage:
    answer = ctx.item.answer
    if isinstance(answer, ChoiceAnswer) and ctx.student_text:
        said = f" {fold(ctx.student_text)} "
        for opt in answer.options:
            names = [opt.text, *opt.aliases]
            if opt.probe is not None and any(f" {fold(n)} " in said for n in names):
                return _msg(opt.probe.prompt, "TEMPLATE", f"{ctx.item.id}:PROBE:{opt.id}")
    return _msg(_say(ctx, "probe"), "TEMPLATE")


def _hint(ctx: RenderContext) -> RenderedMessage:
    found = select_hint(ctx.item, ctx.package, ctx.decision.target, ctx.decision.level)
    if found is None:
        return _msg(_say(ctx, "hint"), "FALLBACK")
    hint, source, ref = found
    return _msg(hint.text, source, ref)


def _cognitive_conflict(ctx: RenderContext) -> RenderedMessage:
    found = counter_example(ctx.item, ctx.package, ctx.decision.misconception_id)
    if found is None:
        return _hint(ctx)
    text, ref = found
    return _msg(text, "TEMPLATE", ref)


def _redirect(ctx: RenderContext) -> RenderedMessage:
    text, ref = _ask_item(ctx)
    return _msg(f"{_say(ctx, 'redirect')} {text}", "TEMPLATE", ref)


def _verify(ctx: RenderContext) -> RenderedMessage:
    if ctx.item.verify_prompt:
        return _msg(ctx.item.verify_prompt, "TEMPLATE", f"{ctx.item.id}:VERIFY")
    if ctx.package.default_verify_prompt:
        return _msg(ctx.package.default_verify_prompt, "TEMPLATE", f"{ctx.package.lesson_id}:VERIFY")
    return _msg(_say(ctx, "verify"), "FALLBACK")


def _worked_guidance(ctx: RenderContext) -> RenderedMessage:
    steps = ctx.item.worked_solution
    if len(steps) < 2:
        return _hint(ctx)
    shown = " ".join(steps[:-1])
    return _msg(f"{shown} {_say(ctx, 'worked_next')}", "TEMPLATE", f"{ctx.item.id}:WORKED:1-{len(steps) - 1}")


def _full_explanation(ctx: RenderContext) -> RenderedMessage:
    item = ctx.item
    if item.explanation:
        body, ref = item.explanation, f"{item.id}:EXPLANATION"
    elif item.worked_solution:
        body, ref = " ".join(item.worked_solution), f"{item.id}:WORKED:ALL"
    else:
        return _hint(ctx)
    return _msg(f"{body} {_say(ctx, 'explain_back')}", "TEMPLATE", ref)


def _fixed(key: str) -> Callable[[RenderContext], RenderedMessage]:
    return lambda ctx: _msg(_say(ctx, key), "TEMPLATE")


_RENDERERS: dict[Move, Callable[[RenderContext], RenderedMessage]] = {
    Move.PRESENT: _present,
    Move.PROBE: _probe,
    Move.HINT: _hint,
    Move.COGNITIVE_CONFLICT: _cognitive_conflict,
    Move.NUDGE: _fixed("nudge"),
    Move.REDIRECT: _redirect,
    Move.OFFER_CHOICE: _fixed("offer_choice"),
    Move.ASK_CONFIRM: _fixed("ask_confirm"),
    Move.VERIFY: _verify,
    Move.CONFIRM_ADVANCE: _fixed("confirm_advance"),
    Move.WORKED_GUIDANCE: _worked_guidance,
    Move.FULL_EXPLANATION: _full_explanation,
    Move.TEACH_BACK: _fixed("teach_back"),
    Move.CLOSE_ITEM: _fixed("close_item"),
}


class TemplateRenderer:
    """`MessageRenderer` that only uses approved lesson content and fixed sentences (no network)."""

    version = TEMPLATE_VERSION

    def render(self, ctx: RenderContext) -> RenderedMessage:
        return _RENDERERS[ctx.decision.move](ctx)
