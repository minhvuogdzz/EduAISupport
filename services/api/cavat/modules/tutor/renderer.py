"""Template renderer: turns a policy decision into Vietnamese text without any model call (T03).

Blueprint PART 15.3: approved lesson content comes first. A hint is looked up in this order: the item's
template for (target, level), the item's template for the same target at a lower level, the lesson's
generic hints, then a fixed fallback sentence. The fixed sentences below were approved by the owner
(the supervising teacher) on 2026-10-01; changing them is a template change (CLAUDE.md rule 7).
"""

from __future__ import annotations

import re
from collections.abc import Callable

from cavat.core.pedagogy import HintLevel, HintTarget, ItemResolution, Move, Outcome
from cavat.modules.assessment.math_checker import classify_intent
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
TEMPLATE_VERSION = "template-renderer.v14"
# ENG-5g (DI-157): the words an English session says in place of the Mathematics ones ("những số con đã
# dùng", "kết quả bài trên thẻ"). Mathematics never reads them: ``_phrase_of`` picks them by the package's
# subject.
# v2 (ENG-5h, DI-165–168): a feeling answered first, a spelling slip named, the word order of a correction
# named, a counterexample only when the item has its cue, "nói lại cả câu" after the model sentence
TEMPLATE_VERSION_EN = "template-renderer-en.v2"

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
    # ENG-5c (DI-149, drafted for the owner's review): an English item answered in Vietnamese. Only the
    # English checker sets L1, so a Mathematics turn never says these.
    "L1_ASK_ENGLISH": (
        "{T} nghe {s} nói bằng tiếng Việt rồi. Câu này {s} nói bằng tiếng Anh giúp {t} nhé.",
        "Mình đang luyện nói tiếng Anh, {s} trả lời bằng tiếng Anh nhé.",
    ),
    "OFF_TOPIC": (
        "Chuyện đó để lúc nghỉ mình nói nhé!",
        "{T} rất muốn nghe, nhưng mình làm xong câu này đã nhé!",
    ),
}
# ENG-5g (DI-157, drafted for the owner's review): an English session's own words for the templates whose
# shared wording speaks of Mathematics (numbers, "bài trên thẻ", "bước") or is said the same way each time.
PHRASES_EN: dict[str, tuple[str, ...]] = {
    "probe": (
        "{S} đọc lại câu của mình rồi cho {t} biết {s} đã nghĩ thế nào khi nói như vậy nhé?",
        "{S} kể cho {t} nghe vì sao {s} chọn cách nói đó được không?",
    ),
    "verify": ("Đúng rồi! {S} nói cho {t} biết chữ nào trong câu giúp {s} chọn cách nói đó được không?",),
    "confirm_advance": (
        "Đúng rồi! Mình sang câu tiếp theo nhé.",
        "{S} nói đúng rồi, giỏi lắm! Mình sang câu tiếp theo nhé.",
        "Chính xác! {T} chuyển sang câu sau nhé.",
        "Đúng rồi, {s} nhớ bài tốt lắm! Mình làm câu tiếp theo nhé.",
    ),
    "explain_back": ("{S} nói lại câu đó và vì sao nói như vậy cho {t} nghe được không?",),
    "teach_back": ("{S} thử giảng lại cho {t} vì sao câu này nói như vậy, bằng lời của {s} nhé?",),
    "worked_next": ("{S} nói tiếp phần còn lại của câu giúp {t} được không?",),
    "close_item": (
        "Mình dừng câu này ở đây nhé, {s} đã cố gắng nhiều rồi.",
        "Câu này mình tạm dừng nhé. {S} đã thử rất chăm chỉ.",
    ),
}
LEADS_EN: dict[str, tuple[str, ...]] = {
    "NEGATIVE_AFFECT": (
        "{T} nghe {s} nói rồi. Không sao đâu, mình đi chậm thôi nhé.",
        "{T} ở đây cùng {s}. Mình thử từng chút một nhé.",
    ),
    "VAGUE": (
        "{T} muốn nghe rõ hơn: chữ nào trong câu cho {s} biết phải nói như vậy?",
        "{S} chỉ cho {t} chữ hoặc cụm từ trong câu đã giúp {s} nhé.",
    ),
    "HELP_REQUEST": ("Không sao đâu, mình cùng nghĩ từng chút nhé.", "Mình thử thêm một chút nữa nhé."),
}
# ENG-5g (DI-159): a right word said alone where the item wants the whole sentence ("ate" for "Yesterday we …
# seafood"). The English checker marks it (``whole_sentence``); the tutor says so before the move's text.
WHOLE_SENTENCE_LEAD = "Từ đó {s} chọn đúng rồi! {S} nói cả câu giúp {t} nhé."
# ENG-5h (DI-165, drafted for the owner's review): what the child says of how they feel ("con đói quá cô
# ơi", "hôm nay con buồn") is answered first, in its own words, before the lesson goes on; the model sentence
# is not read again in the same turn. Matched on the words with or without diacritics.
FEELINGS_EN: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "đói",
        r"\b(?:đói|khát|doi (?:qua|bung|roi)|khat (?:qua|nuoc))",
        (
            "{S} đói bụng rồi à, {t} hiểu mà. Mình làm nốt câu này thật nhẹ nhàng rồi {s} đi ăn nhé, "
            "được không {s}?",
            "Đói thì khó học lắm, {t} biết. {S} uống chút nước rồi mình làm nốt câu này nhé, được không?",
        ),
    ),
    (
        "buồn",
        r"\b(?:buồn(?! ngủ)|buon (?:qua|lam|roi)|hom nay con buon)",
        (
            "{T} nghe {s} nói hôm nay {s} buồn, {t} thương {s} lắm. {T} vẫn ở đây với {s}; {s} muốn kể "
            "{t} nghe một chút, hay mình học tiếp thật nhẹ nhàng nhé?",
            "{S} đang buồn à, không sao đâu, {t} ở đây cùng {s}. Mình học chậm thôi nhé, {s} sẵn sàng chưa?",
        ),
    ),
    (
        "mệt",
        r"\b(?:mệt|buồn ngủ|met (?:qua|lam|roi)|buon ngu)",
        (
            "{S} mệt rồi à, {t} hiểu. Mình đi chậm lại, làm nốt câu này rồi nghỉ một chút nhé, được không?",
            "Học lâu cũng mệt thật, {t} biết. {S} hít thở sâu một cái rồi mình thử tiếp nhé?",
        ),
    ),
    (
        "chán",
        r"\b(?:chán|chan (?:qua|lam|roi))",
        (
            "{T} biết học mãi cũng có lúc chán. Mình thử câu này thật nhanh, như một trò chơi nhé, "
            "{s} sẵn sàng chưa?",
            "{S} thấy chán à, {t} hiểu. Câu này ngắn thôi, mình làm cùng nhau nhé?",
        ),
    ),
)


def feeling_of(text: str | None) -> str | None:
    """ENG-5h (DI-165): the feeling the child's words name ("đói", "buồn", "mệt", "chán"), else None."""
    import unicodedata

    low = unicodedata.normalize("NFC", text or "").lower()
    for name, pattern, _ in FEELINGS_EN:
        if re.search(pattern, low):
            return name
    return None


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
    "L1_ASK_ENGLISH": "unproductive_turns",
}
_LEAD_ORDER = (
    "L1_ASK_ENGLISH",
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


def _english(ctx: RenderContext) -> bool:
    return getattr(ctx.package, "subject", "math") == "english"


def _phrase_of(ctx: RenderContext, key: str) -> str:
    """The template of ``key`` in the session's subject: an English session's own words when it has them
    (DI-157), else the shared ones. A Mathematics package always gets ``PHRASES``."""
    if _english(ctx):
        variants = PHRASES_EN.get(key)
        if variants:
            # several wordings, picked by the item and the attempt: the same praise is not said each time
            pick = (sum(map(ord, ctx.item.id)) + ctx.state.attempt_no) % len(variants)
            return variants[pick]
    return PHRASES[key]


def _say(ctx: RenderContext, key: str, **extra: str) -> str:
    t, s = ctx.persona.tutor_self, ctx.persona.student_address
    return _phrase_of(ctx, key).format(T=_cap(t), t=t, S=_cap(s), s=s, **extra)


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
    """The lesson's generic hints that fit this kind of item (DI-37). ENG-5i (DI-187): in an English lesson a
    generic hint whose English belongs to other items ("Did you swim? – Yes, I did." on "We took a boat trip
    around the bay.") does not fit; Mathematics is unchanged."""
    kind = item.answer.type
    fitting = [h for h in package.generic_hints if not h.answer_types or kind in h.answer_types]
    if package.subject != "english":
        return fitting
    return [h for h in fitting if not _off_item_en(h.text, item, package)]


def _english_words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"(?<![^\W\d_])[A-Za-z]+(?![^\W\d_])", text)}


def _off_item_en(text: str, item: Item, package: LessonPackage) -> bool:
    """DI-187: the English of ``text`` holds a word of the lesson's answers that this item never says."""
    lesson = {
        w
        for other in package.items
        for a in (getattr(other.answer, "accept", None) or ())
        for w in _english_words(str(a))
    }
    own = " ".join(
        [item.stem, item.explanation or "", *item.worked_solution, *(h.text for h in item.hints)]
        + [str(a) for a in (getattr(item.answer, "accept", None) or ())]
    )
    return bool(
        (_english_words(text) & lesson) - _english_words(own) - {"a", "the", "we", "i", "in", "on", "to"}
    )


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
        if not _cue_present(text, item, package):
            continue
        if "{" not in text:
            found = text
        elif isinstance(item.answer, CompareAnswer):
            found = text.format(left=item.answer.left, right=item.answer.right)
        else:
            continue
        if _one_question(found):
            usable.append((found, f"{mis.id}:COUNTER:{i}"))
    return usable[shown % len(usable)] if usable else None


# ENG-5h (DI-168): "Câu có 'yesterday' (hôm qua)…" speaks of a word of the item's own sentence; said on an
# item without that word ("Con nói câu kể việc cả nhà làm… We ate …") it compares the child with nothing.
_CUE = re.compile(r"\bcó (?:chữ |từ )?['‘\"“]([^'’\"”]+)['’\"”]", re.IGNORECASE)


def _cue_present(text: str, item: Item, package: LessonPackage) -> bool:
    """An English counterexample that names a word the item has ("câu có 'yesterday'") is usable only when
    the item's words hold it. Mathematics: always (its counterexamples are not read this way)."""
    if getattr(package, "subject", "math") != "english":
        return True
    said = fold(" ".join((item.stem, item.rephrase or ""))).lower()
    return all(fold(cue).lower() in said for cue in _CUE.findall(text))


_FIGURE = re.compile(r"\[Hình[^\]]*\]\s*", re.IGNORECASE)
LONG_STEM_WORDS = 60


def visible_stem(stem: str) -> str:
    """BRAIN-1: what a child is shown when the tutor asks the item again. The text description of a figure
    ("[Hình: Tam giác ABC nhọn, đường cao AH…]") is for the reader of the plan, not for the child, and a long
    stem is not printed again whole: only its last sentence, the question."""
    text = " ".join(_FIGURE.sub("", stem).split())
    if len(text.split()) <= LONG_STEM_WORDS:
        return text
    sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
    asked = [s for s in sentences if s.rstrip().endswith("?")]
    return (asked or sentences)[-1]


def _ask_item(ctx: RenderContext) -> tuple[str, str]:
    """The item restated as one question: the rephrase if any, else the stem plus an invitation."""
    item = ctx.item
    if item.rephrase:
        return item.rephrase, f"{item.id}:REPHRASE"
    stem = visible_stem(item.stem)
    if "?" in stem:
        return stem, f"{item.id}:STEM"
    return f"{stem.rstrip(' .')}. {_say(ctx, 'try_it')}", f"{item.id}:STEM"


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
    from cavat.modules.tutor.brain import explanation_only

    if ctx.state.dialogue_version >= 3 and explanation_only(ctx.student_text or ""):
        sentence = covering_sentence(ctx.focus, ctx.evidence)
        if sentence is None:
            sentence = next(
                (
                    part.strip()
                    for part in re.split(r"(?<=[.!?])\s+", hint.text)
                    if part.strip() and "?" not in part
                ),
                None,
            )
        if sentence:
            return _msg(sentence, "TEMPLATE")
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
    question, else the statements of the item's strongest hints, else the answer the child gave (right, or
    they would not be taught again). None only when the lesson has nothing at all on this item."""
    item = ctx.item
    if explanation := approved_explanation(item):
        return explanation
    passages = [s for p in ctx.evidence for s in _SENTENCE_END.split(" ".join(p.split())) if s.strip()]
    if statements := [s for s in passages if not s.endswith("?")][:2]:
        return " ".join(statements)
    hints = sorted(item.hints, key=lambda h: -h.level)  # the generic ones say nothing of this item
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
    variants = (LEADS_EN.get(code) if _english(ctx) else None) or LEADS[code]
    said = max(getattr(ctx.state, _LEAD_COUNTER[code]) - 1, 0)
    t, s = ctx.persona.tutor_self, ctx.persona.student_address
    return variants[said % len(variants)].format(T=_cap(t), t=t, S=_cap(s), s=s)


def _whole_sentence(ctx: RenderContext) -> bool:
    return (
        _english(ctx)
        and ctx.check is not None
        and bool(ctx.check.detail.get("whole_sentence"))
        and ctx.decision.move
        in (Move.HINT, Move.PROBE, Move.VERIFY, Move.COGNITIVE_CONFLICT, Move.OFFER_CHOICE)
    )


def _with_lead(ctx: RenderContext, msg: RenderedMessage) -> RenderedMessage:
    if _whole_sentence(ctx):
        t, s = ctx.persona.tutor_self, ctx.persona.student_address
        said = WHOLE_SENTENCE_LEAD.format(T=_cap(t), t=t, S=_cap(s), s=s)
        return _msg(f"{said} {msg.text}", msg.source, msg.hint_ref)
    first = lead(ctx)
    if first is None:
        return msg
    text = f"{first} {msg.text}"
    if len(text.split()) > ctx.max_words:
        return msg  # the move's own content matters more than the warm-up sentence
    return _msg(text, msg.source, msg.hint_ref)


# ENG-5h (drafted for the owner's review). DI-166: a sentence right but for the spelling of a word.
SLIP_EN = (
    "Câu của {s} đủ ý rồi, chỉ có chữ «{word}» viết chưa đúng chính tả thôi. {S} xem lại chữ đó rồi viết "
    "lại cả câu giúp {t} nhé?",
    "{S} nói gần đúng rồi đó! Chữ «{word}» còn sai chính tả, {s} đánh vần lại rồi viết lại cả câu "
    "giúp {t} nhé?",
)
# DI-167: the judgment right, the corrected sentence in a wrong word order.
WORD_ORDER_EN = (
    "{S} nhận ra câu đó chưa đúng rồi, giỏi lắm! Có điều câu {s} sửa bị đảo trật tự từ: trong tiếng Anh, "
    "việc làm đứng ngay sau người làm, nên mình nói: {right} {S} nói lại câu đó giúp {t} nhé?"
)
# ENG-5i (DI-177): every word of the sentence, in a wrong order ("We around the bay took a boat trip.").
SCRAMBLED_EN = (
    "{S} nói đủ các từ rồi, nhưng trật tự từ chưa đúng. Trong tiếng Anh mình nói ai trước, rồi làm gì, "
    "rồi mới tới ở đâu. {S} sắp lại câu rồi nói lại giúp {t} nhé?",
    "Các từ {s} chọn đúng hết rồi đó! Chỉ có thứ tự là bị đảo: người làm, rồi việc làm, rồi nơi chốn. "
    "{S} thử nói lại theo thứ tự đó nhé?",
)
# DI-169: after the model sentence, the child's repeat that is not right yet: what to look at, then wait.
SAY_AGAIN_EN = (
    "{S} nói gần đúng rồi! Chữ «{word}» chưa đúng, câu mẫu là: {right} {S} nói lại cả câu giúp {t} nhé?",
    "Mình nói lại cả câu một lần nữa nhé: {right} Lần này {s} nói chậm từng chữ theo {t} được không?",
)
_FEELING_MOVES = frozenset(
    {
        Move.REDIRECT,
        Move.EXPLAIN,
        Move.HINT,
        Move.NUDGE,
        Move.OFFER_CHOICE,
        Move.WORKED_GUIDANCE,
        Move.PROBE,
        Move.COGNITIVE_CONFLICT,
        Move.ASK_CONFIRM,
    }
)
# ENG-5i (DI-179): WORKED_GUIDANCE too: "We ate seafod." was walked through "eat đổi thành ate" although the
# child had said "ate"; only the spelling of "seafod" was owed.
_SLIP_MOVES = frozenset(
    {Move.HINT, Move.PROBE, Move.COGNITIVE_CONFLICT, Move.OFFER_CHOICE, Move.VERIFY, Move.WORKED_GUIDANCE}
)


def _fmt(ctx: RenderContext, template: str, **extra: str) -> str:
    t, s = ctx.persona.tutor_self, ctx.persona.student_address
    return template.format(T=_cap(t), t=t, S=_cap(s), s=s, **extra)


def english_special(ctx: RenderContext) -> RenderedMessage | None:
    """ENG-5h: the English templates that answer what the child just did, before the move's own words.
    None for Mathematics and for every other case."""
    if not _english(ctx):
        return None
    d, check = ctx.decision, ctx.check
    detail = (check.detail or {}) if check is not None else {}
    if "SAY_AGAIN" in d.reason_codes:
        right = str((getattr(ctx.item.answer, "accept", None) or [""])[0])
        word = (detail.get("off_words") or [""])[0]
        pick = SAY_AGAIN_EN[0] if word else SAY_AGAIN_EN[1]
        return _msg(_fmt(ctx, pick, word=word, right=right), "TEMPLATE", f"{ctx.item.id}:SAY_AGAIN")
    feeling = feeling_of(ctx.student_text)
    if feeling is not None and d.move in _FEELING_MOVES:
        variants = next(v for name, _, v in FEELINGS_EN if name == feeling)
        pick = variants[max(ctx.state.affect_signals - 1, 0) % len(variants)]
        return _msg(_fmt(ctx, pick), "TEMPLATE", f"FEELING:{feeling}")
    if detail.get("en_code") == "EN_SLIP" and detail.get("slips") and d.move in _SLIP_MOVES:
        pick = SLIP_EN[ctx.state.attempt_no % len(SLIP_EN)]
        return _msg(_fmt(ctx, pick, word=detail["slips"][0]), "TEMPLATE", f"{ctx.item.id}:SLIP")
    if detail.get("scrambled") and d.move in _SLIP_MOVES:
        pick = SCRAMBLED_EN[ctx.state.attempt_no % len(SCRAMBLED_EN)]
        return _msg(_fmt(ctx, pick), "TEMPLATE", f"{ctx.item.id}:SCRAMBLED")
    if detail.get("word_order") and d.move == Move.VERIFY:
        return _msg(_fmt(ctx, WORD_ORDER_EN, right=detail["word_order"]), "TEMPLATE", f"{ctx.item.id}:ORDER")
    return None


class TemplateRenderer:
    """`MessageRenderer` that only uses approved lesson content and fixed sentences (no network)."""

    version = TEMPLATE_VERSION

    def render(self, ctx: RenderContext) -> RenderedMessage:
        if (special := english_special(ctx)) is not None:
            return special
        if "CONVERSATION" in ctx.decision.reason_codes:
            if "CONTINUE" in ctx.decision.reason_codes:
                return _msg(f"Ừ, mình thử nhé. {ctx.resume_prompt}", "TEMPLATE")
            if "AMBIGUOUS_REPLY" in ctx.decision.reason_codes:
                return _msg("Cô chưa rõ điều con muốn nói. Con nói thêm cho cô một chút nhé?", "TEMPLATE")
            if "REACTION" in ctx.decision.reason_codes:
                return _msg(f"Mình quay lại bài nhé. {ctx.resume_prompt}".strip(), "TEMPLATE")
            if "DECLINE" in ctx.decision.reason_codes:
                return _msg("Mình nghỉ một chút nhé. Khi sẵn sàng, con nhắn cô để mình học tiếp.", "TEMPLATE")
            if (ctx.focus or "").startswith("con tiếp nhận lời hướng dẫn"):
                if _english(ctx):  # DI-157: no "thẻ" of a Mathematics exercise card in an English lesson
                    return _msg(f"Ừ, mình làm tiếp nhé. {ctx.resume_prompt}".strip(), "TEMPLATE")
                return _msg("Ừ, con thử làm tiếp câu trên thẻ nhé. Cô theo dõi cùng con.", "TEMPLATE")
            from cavat.modules.tutor.dialogue import conversion_ground

            rule = conversion_ground(ctx.item) or (
                ctx.evidence[0]
                if ctx.evidence
                else "Mình cùng đọc lại câu nhé."
                if _english(ctx)
                else "Mình cùng xem lại từng bước của bài nhé."
            )
            said = fold((ctx.student_text or "").lower())
            lead = (
                "Ừ, cô nói gọn nhé."
                if any(cue in said for cue in ("noi ngan", "noi nhieu", "dai dong"))
                else "Không sao, mình đi từng chút nhé."
                if classify_intent(ctx.student_text or "") == Outcome.NEGATIVE_AFFECT
                else "Mình xem một ví dụ nhé:"
            )
            return _msg(f"{lead} {rule} {ctx.resume_prompt}".strip(), "TEMPLATE")
        if ctx.follow_up:
            return _msg(f"Phần này con trả lời đúng rồi. {ctx.follow_up}", "TEMPLATE")
        return _with_lead(ctx, _RENDERERS[ctx.decision.move](ctx))
