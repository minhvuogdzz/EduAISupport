"""Template renderer: turns a policy decision into Vietnamese text without any model call (T03).

Blueprint PART 15.3: approved lesson content comes first. A hint is looked up in this order: the item's
template for (target, level), the item's template for the same target at a lower level, the lesson's
generic hints, then a fixed fallback sentence. The fixed sentences below were approved by the owner
(the supervising teacher) on 2026-10-01; changing them is a template change (CLAUDE.md rule 7).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from cavat.core.pedagogy import HintLevel, HintTarget, ItemResolution, Move
from cavat.modules.assessment.student_intent import without_subject
from cavat.modules.assessment.vi_numbers import fold
from cavat.modules.content.lesson_package import (
    ChoiceAnswer,
    CompareAnswer,
    HintTemplate,
    Item,
    LessonPackage,
)
from cavat.modules.tutor.contracts import MessageSource, RenderContext, RenderedMessage

# v9: REFORM-5, ASK_CONFIRM asks about a key slip or a likely typo in its own words (DI-77), or says the
#     question the intent agent proposed (checked by the validator)
# v8: REFORM-2, EXPLAIN_AND_ADVANCE says the approved explanation, the rule answers "lý thuyết là gì",
#     punctuation no longer hides a word; v7: FIX-6, the counterexample is tied to the item and varies
TEMPLATE_VERSION = "template-renderer.v9"

# {T}/{t}: how the tutor calls themself, {S}/{s}: how the tutor calls the student (capitalised / not).
PHRASES: dict[str, str] = {
    "probe": "{S} nói cho {t} nghe {s} đã làm thế nào để ra câu trả lời đó được không?",
    "hint": "{S} đọc lại đề bài thật chậm rồi cho {t} biết {s} định bắt đầu từ đâu nhé?",
    "nudge": "{S} đang nghĩ đến đâu rồi, có cần {t} gợi ý thêm không?",
    "redirect": "Mình quay lại câu đang làm nhé.",
    "try_it": "{S} làm thử giúp {t} được không?",
    "offer_choice": "{S} muốn {t} gợi ý thêm hay {s} muốn tự thử lại một lần nữa?",
    "ask_confirm": "{T} chưa chắc đã hiểu đúng ý {s}. {S} viết lại câu trả lời rõ hơn giúp {t} được không?",
    # REFORM-5 (DI-77, drafted for the owner's review): a few letters nothing reads. The tutor says what it
    # guesses and asks (never takes it for an answer), or says the keys slipped and asks again.
    "ask_confirm_typo": "{T} đoán {s} muốn nói là {s} {meaning}, đúng không, hay {s} định gõ ý khác?",
    "ask_confirm_mash": "Hình như bàn phím của {s} vừa gõ ra mấy chữ lạ. {S} gõ lại ý của mình giúp {t} nhé?",
    "verify": "Đúng rồi! {S} giải thích cho {t} vì sao {s} làm như vậy được không?",
    "confirm_advance": "Đúng rồi! {S} đã suy nghĩ và kiểm tra rất cẩn thận. Mình sang câu tiếp theo nhé.",
    "worked_next": "Vậy bước cuối cùng là gì, {s} làm tiếp giúp {t} được không?",
    "explain_back": "{S} nói lại cách làm bằng lời của {s} cho {t} nghe được không?",
    "teach_back": "{S} thử giảng lại cho {t} cách làm câu này bằng lời của {s} được không?",
    "close_item": "Mình dừng câu này ở đây nhé. {S} đã cố gắng suy nghĩ rất chăm chỉ.",
    "move_on": "Mình sang câu tiếp theo nhé.",  # ADR-019: solved, the "vì sao" skipped (draft wording)
    # REFORM-2 (DI-68, drafted for the owner's review): the child could not say why; the tutor says it.
    "explain_and_advance": (
        "{T} giải thích ngắn gọn để {s} nhớ nhé: {explanation} Bây giờ mình sang câu tiếp theo nhé!"
    ),
    "explain_lead": "{T} nói rõ hơn nhé:",  # CTX-1 (draft wording): before a sentence of approved content
    # FIX-6 (drafted, approved on the owner's authority): a counterexample is about other numbers, so the
    # child is told why it comes now ("không liên quan tới đề", the judge said of it on 2026-10-21).
    "example_lead": "{T} lấy một ví dụ để {s} so sánh với bài này nhé.",
}


# ADR-019 (template-renderer.v3, wording drafted for the owner's review): one short sentence before the
# move's own text, for what the student said: a demand for the answer is refused with its reason, a
# feeling is acknowledged, "là sao?" is answered, "không biết" is met with calm, off-topic talk is
# parked. Socratic still: the move's hint and its single question follow.
LEADS: dict[str, tuple[str, ...]] = {
    # REFORM-2 (DI-67, drafted for the owner's review): the child answered the step the hint asked.
    "STEP_PRAISE": ("Đúng rồi, bước này {s} làm đúng!", "Chính xác! {S} đang đi đúng hướng rồi."),
    "ANSWER_DEMAND": (
        "{T} chưa nói đáp án ngay đâu, vì {s} tự tìm ra sẽ nhớ lâu hơn.",
        "Mình cùng làm để {s} tự tìm ra nhé, như vậy {s} sẽ nhớ lâu hơn.",
    ),
    "NEGATIVE_AFFECT": (
        "{T} hiểu, bài này hơi khó một chút. Không sao đâu, mình làm từng bước nhỏ nhé.",
        "{S} đã cố gắng nhiều rồi đấy. Mình đi chậm lại một chút nhé.",
    ),
    "CLARIFY": ("{T} nói rõ hơn nhé.", "{T} nói theo cách khác nhé."),
    # DI-55 (drafted for the owner's review): a "vì sao" that says nothing of this item.
    "VAGUE": (
        "{T} muốn nghe rõ hơn bước {s} đã làm và những số {s} đã dùng.",
        "{S} kể cụ thể hơn một chút nhé, với những số trong bài.",
    ),
    "ASKED_HINT": ("{T} gợi ý nhé.", "{T} gợi ý thêm nhé."),
    "HELP_REQUEST": ("Không sao đâu, mình cùng nghĩ từng bước nhé.", "Mình thử thêm một bước nữa nhé."),
    "OFF_TOPIC": (
        "Chuyện đó để lúc nghỉ mình nói nhé!",
        "{T} rất muốn nghe, nhưng mình làm xong câu này đã nhé!",
    ),
}
# The counter that picks the variant: the same words are not said twice in a row (anti-loop, replayable).
_LEAD_COUNTER = {
    "STEP_PRAISE": "attempt_no",
    "ANSWER_DEMAND": "help_requests",
    "NEGATIVE_AFFECT": "affect_signals",
    "CLARIFY": "clarify_requests",
    "VAGUE": "clarify_requests",
    "ASKED_HINT": "help_requests",
    "HELP_REQUEST": "help_requests",
    "OFF_TOPIC": "off_topic_turns",
}
_LEAD_ORDER = (
    "STEP_PRAISE",
    "ANSWER_DEMAND",
    "NEGATIVE_AFFECT",
    "CLARIFY",
    "VAGUE",
    "ASKED_HINT",
    "HELP_REQUEST",
    "OFF_TOPIC",
)
_LEAD_MOVES = frozenset(
    {
        Move.HINT,
        Move.OFFER_CHOICE,
        Move.WORKED_GUIDANCE,
        Move.FULL_EXPLANATION,
        Move.COGNITIVE_CONFLICT,
        Move.REDIRECT,
        Move.VERIFY,
        Move.TEACH_BACK,
        Move.CLOSE_ITEM,
    }
)


def _cap(word: str) -> str:
    return word[:1].upper() + word[1:]


def _say(ctx: RenderContext, key: str, **extra: str) -> str:
    t, s = ctx.persona.tutor_self, ctx.persona.student_address
    return PHRASES[key].format(T=_cap(t), t=t, S=_cap(s), s=s, **extra)


def _words_of(text: str) -> set[str]:
    """The folded words of a text without its punctuation: "mẫu," and "1000." are "mau" and "1000"."""
    return set(re.findall(r"\w+", fold(text)))


def approved_explanation(item: Item) -> str | None:
    """The item's approved account of why the answer is right, as one passage (REFORM-2)."""
    text = item.explanation or " ".join(item.worked_solution)
    return " ".join(text.split()) or None


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


def fitting_generic_hints(item: Item, package: LessonPackage) -> list[HintTemplate]:
    """The lesson's generic hints that fit this kind of item (DI-37)."""
    kind = item.answer.type
    return [h for h in package.generic_hints if not h.answer_types or kind in h.answer_types]


def ladder_top(item: Item, package: LessonPackage) -> HintLevel:
    """The strongest ladder hint this item can get, its own or a fitting generic one (DI-37)."""
    levels = [
        h.level
        for h in (*item.hints, *fitting_generic_hints(item, package))
        if h.target not in _KIND_TARGETS and _one_question(h.text)
    ]
    return max(levels, default=HintLevel.H1)


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
        (fitting_generic_hints(item, package), "GENERIC", "GENERIC"),
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
    item: Item, package: LessonPackage, misconception_id: str | None, shown: int = 0
) -> tuple[str, str] | None:
    """A usable counter-example of the misconception; {left}/{right} only fill for compare items.

    A counter-example asking two questions would fail the validator (one question per turn) and leave
    the child with the fixed fallback sentence (seen in the live hard-student run, TQ-2): it is skipped.
    ``shown``: counterexamples already given on the item; the next usable one follows (FIX-6), so a child
    who keeps the same mistake does not hear the same words again while the lesson has others.
    """
    mis = package.misconception(misconception_id) if misconception_id else None
    if mis is None:
        return None
    usable: list[tuple[str, str]] = []
    for i, text in enumerate(mis.counter_examples, start=1):
        if "{" not in text:
            found = text
        elif isinstance(item.answer, CompareAnswer):
            found = text.format(left=item.answer.left, right=item.answer.right)
        else:
            continue
        if _one_question(found):
            usable.append((found, f"{mis.id}:COUNTER:{i}"))
    return usable[shown % len(usable)] if usable else None


def _ask_item(ctx: RenderContext) -> tuple[str, str]:
    """The item restated as one question: the rephrase if any, else the stem plus an invitation."""
    item = ctx.item
    if item.rephrase:
        return item.rephrase, f"{item.id}:REPHRASE"
    if "?" in item.stem:
        return item.stem, f"{item.id}:STEM"
    return f"{item.stem.rstrip(' .')}. {_say(ctx, 'try_it')}", f"{item.id}:STEM"


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
    found = counter_example(
        ctx.item, ctx.package, ctx.decision.misconception_id, ctx.state.counter_examples_shown
    )
    if found is None:
        return _hint(ctx)
    text, ref = found
    if "?" not in text:
        # FIX-2: a counterexample of the teacher's documents states the case without asking; the check
        # wanted a question, rejected it twice, and the child lost the counterexample. (One with a question
        # inside is left as it is: a second question would fail the check too.)
        text = f"{text.rstrip()} {_say(ctx, 'try_it')}"
    with_lead = f"{_say(ctx, 'example_lead')} {text}"
    if lead(ctx) is None and len(with_lead.split()) <= ctx.max_words:  # no lead for the child's words yet
        text = with_lead
    return _msg(text, "TEMPLATE", ref)


def _redirect(ctx: RenderContext) -> RenderedMessage:
    text, ref = _ask_item(ctx)
    if lead(ctx) is not None:
        return _msg(text, "TEMPLATE", ref)  # the lead already brings the child back (ADR-019)
    return _msg(f"{_say(ctx, 'redirect')} {text}", "TEMPLATE", ref)


_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def covering_sentence(focus: str | None, evidence: tuple[str, ...]) -> str | None:
    """The sentence of the approved passages that shares the most words with what the child asks about."""
    wanted = {w for w in _words_of(focus or "") if len(w) > 1}
    if not wanted:
        return None
    best, best_score = None, 0
    for passage in evidence:
        for sentence in _SENTENCE_END.split(passage):
            sentence = sentence.strip()
            if len(sentence.split()) < 4 or sentence.endswith("?"):
                continue
            score = len(wanted & _words_of(sentence))
            if score > best_score:
                best, best_score = sentence, score
    return best


def _explain(ctx: RenderContext) -> RenderedMessage:
    """CTX-1 without a model: what the child asked about, then a question to go on.

    The item's own hint of the decided rung when it speaks of what was asked (TP-CC-01: "mẫu như nào" is
    answered by its H2 "Phân số thập phân có mẫu số là 10, 100 hay 1000..."); else the sentence of the
    approved passages that does, with the item asked again; else that hint anyway.
    """
    hint = _hint(ctx)
    wanted = _words_of(ctx.focus or "")
    if wanted & _words_of(hint.text) or not ctx.evidence:
        return _msg(f"{_say(ctx, 'explain_lead')} {hint.text}", hint.source, hint.hint_ref)
    sentence = covering_sentence(ctx.focus, ctx.evidence)
    if sentence is None:
        return _msg(f"{_say(ctx, 'explain_lead')} {hint.text}", hint.source, hint.hint_ref)
    text, ref = _ask_item(ctx)
    return _msg(f"{_say(ctx, 'explain_lead')} {sentence} {text}", "TEMPLATE", ref)


_PRAISE_RE = re.compile(r"^\s*Đúng rồi[!.]\s*")


def _verify(ctx: RenderContext) -> RenderedMessage:
    if "VERIFY_BEFORE_HINT" in ctx.decision.reason_codes:
        # FIX-2: R-STRONG-PRIOR asks "vì sao" in place of a light hint, after a WRONG answer. The "vì sao"
        # prompts open with "Đúng rồi!" (praise of a wrong answer) and an item's own may name the right
        # answer ("vì sao 0,25 bé hơn 0,3"): ask how the child did it instead, the approved probe.
        return _msg(_say(ctx, "probe"), "TEMPLATE")
    if ctx.item.verify_prompt:
        msg = _msg(ctx.item.verify_prompt, "TEMPLATE", f"{ctx.item.id}:VERIFY")
    elif ctx.package.default_verify_prompt:
        msg = _msg(ctx.package.default_verify_prompt, "TEMPLATE", f"{ctx.package.lesson_id}:VERIFY")
    else:
        msg = _msg(_say(ctx, "verify"), "FALLBACK")
    if "ASK_AGAIN" in ctx.decision.reason_codes:
        # Asked once more after "là sao?" or off-topic talk: the answer was already praised (DI-38).
        msg = _msg(_PRAISE_RE.sub("", msg.text), msg.source, msg.hint_ref)
    return _with_rule(ctx, msg)


def _with_rule(ctx: RenderContext, msg: RenderedMessage) -> RenderedMessage:
    """REFORM-2 (2.2): "lý thuyết là gì" in reply to "vì sao" is answered with the approved rule first."""
    if "CLARIFY" not in ctx.decision.reason_codes or ctx.item.explanation is None:
        return msg
    rule = _SENTENCE_END.split(" ".join(ctx.item.explanation.split()))[0]
    if len(rule.split()) + len(msg.text.split()) > ctx.max_words:
        return msg
    return _msg(f"{rule} {msg.text}", "TEMPLATE", msg.hint_ref)


def _teach_back(ctx: RenderContext) -> RenderedMessage:
    return _with_rule(ctx, _msg(_say(ctx, "teach_back"), "TEMPLATE"))


def _ask_confirm(ctx: RenderContext) -> RenderedMessage:
    """REFORM-5: the intent agent's question when it proposed one that the validator passed (said as it is);
    else the template for a likely typo (with the guess) or for a key slip; else the old fixed sentence."""
    if ctx.clarification:
        return _msg(ctx.clarification, "LLM")
    reasons = ctx.decision.reason_codes
    meaning = without_subject(ctx.guessed_meaning or "")
    if "TYPO" in reasons and meaning:
        return _msg(_say(ctx, "ask_confirm_typo", meaning=meaning), "TEMPLATE")
    if "TYPO" in reasons or "GIBBERISH" in reasons:
        return _msg(_say(ctx, "ask_confirm_mash"), "TEMPLATE")
    return _msg(_say(ctx, "ask_confirm"), "TEMPLATE")


def reteach_material(ctx: RenderContext) -> str | None:
    """BRAIN-1 (C2): what the tutor says again to a child who could not say why, when no model can say it:
    the item's approved explanation or worked steps, else the sentences of the approved passages on the item's
    question, else the statements of the lesson's strongest hints, else the answer the child gave (right, or
    they would not be taught again). None only when the lesson has nothing at all on this item."""
    item = ctx.item
    if explanation := approved_explanation(item):
        return explanation
    passages = [s for p in ctx.evidence for s in _SENTENCE_END.split(" ".join(p.split())) if s.strip()]
    if statements := [s for s in passages if not s.endswith("?")][:2]:
        return " ".join(statements)
    hints = sorted((*item.hints, *fitting_generic_hints(item, ctx.package)), key=lambda h: -h.level)
    said = [s for h in hints for s in _SENTENCE_END.split(h.text) if s.strip() and not s.endswith("?")][:2]
    if said:
        return " ".join(said)
    answer = ctx.check.normalized if ctx.check is not None else None
    return f"Đáp án của câu này là {answer}." if answer else None


def _teach_again(ctx: RenderContext) -> RenderedMessage:
    """The child answered right and could not say why: the idea again, then on. Never only "sang câu tiếp"."""
    material = reteach_material(ctx)
    if material is None:
        return _msg(_say(ctx, "move_on"), "TEMPLATE")
    return _msg(_say(ctx, "explain_and_advance", explanation=material), "TEMPLATE")


def _confirm_advance(ctx: RenderContext) -> RenderedMessage:
    if "EXPLAIN_AND_ADVANCE" in ctx.decision.reason_codes:
        return _teach_again(ctx)
    return _msg(_say(ctx, "confirm_advance"), "TEMPLATE")


def _close_item(ctx: RenderContext) -> RenderedMessage:
    d = ctx.decision
    if d.resolution in (None, ItemResolution.UNRESOLVED):
        return _msg(_say(ctx, "close_item"), "TEMPLATE")
    talk = {"OFF_TOPIC", "CLARIFY", "NEGATIVE_AFFECT"}.intersection(d.reason_codes)
    if "NO_EXPLANATION" in d.reason_codes and not talk:
        # The child could not or would not explain ("không biết", silence): the idea is said again (BRAIN-1:
        # whatever the lesson has on the item), then on. Talk outside the lesson keeps its own lead (ADR-019)
        # and the plain move on.
        return _teach_again(ctx)
    return _msg(_say(ctx, "move_on"), "TEMPLATE")


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
    Move.ASK_CONFIRM: _ask_confirm,
    Move.VERIFY: _verify,
    Move.CONFIRM_ADVANCE: _confirm_advance,
    Move.WORKED_GUIDANCE: _worked_guidance,
    Move.FULL_EXPLANATION: _full_explanation,
    Move.TEACH_BACK: _teach_back,
    Move.EXPLAIN: _explain,
    Move.CLOSE_ITEM: _close_item,
}


def lead(ctx: RenderContext) -> str | None:
    """The sentence that answers what the student said (ADR-019), or None."""
    if ctx.decision.move not in _LEAD_MOVES:
        return None
    code = next((c for c in _LEAD_ORDER if c in ctx.decision.reason_codes), None)
    if code is None:
        return None
    variants = LEADS[code]
    said = max(getattr(ctx.state, _LEAD_COUNTER[code]) - 1, 0)
    t, s = ctx.persona.tutor_self, ctx.persona.student_address
    return variants[said % len(variants)].format(T=_cap(t), t=t, S=_cap(s), s=s)


def _with_lead(ctx: RenderContext, msg: RenderedMessage) -> RenderedMessage:
    first = lead(ctx)
    if first is None:
        return msg
    text = f"{first} {msg.text}"
    if len(text.split()) > ctx.max_words:
        return msg  # the move's own content matters more than the warm-up sentence
    return _msg(text, msg.source, msg.hint_ref)


class TemplateRenderer:
    """`MessageRenderer` that only uses approved lesson content and fixed sentences (no network)."""

    version = TEMPLATE_VERSION

    def render(self, ctx: RenderContext) -> RenderedMessage:
        return _with_lead(ctx, _RENDERERS[ctx.decision.move](ctx))
