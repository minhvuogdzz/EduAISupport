"""Validator of the tutor's words in an English session (ENG-5a, ADR-065, DI-137, DI-138).

The tutor speaks Vietnamese and says the English target inside a sentence (english-module-rules.md V2b).
Every English passage is marked ``[[en: …]]`` (G9 of ``docs/pedagogy/english-g5/README.md``) so that the
voice reads it with the English voice and the screen shows it without the marks. The model is asked to
write the marks; ``mark_english`` adds the ones it forgot, deterministically, before anything is checked.

What this module adds to the Math validator, which it calls unchanged on the Vietnamese part:
- ``ANSWER_LEAK`` on the English target (DI-110 normalization, whole words), except for a "say after me"
  item, whose model sentence the tutor reads first (DI-108), and the moves that may reveal (H7);
- ``MATH_TERM``: a term of the other subject in the tutor's words (P3, DI-137);
- ``OUT_OF_UNIT_ENGLISH``: an English word that is not in the unit's words (DI-138);
- ``BARE_ENGLISH``: a turn made only of English, with no Vietnamese sentence to carry it (V2b);
- ``BROKEN_MARKER``: an unclosed mark or Vietnamese inside a mark.

The Math validator (``validator.validate_message``) is not modified: ``validator_for("math")`` returns it.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from enum import StrEnum
from functools import partial

from cavat.core.en_text import contains_words, normalize_answer
from cavat.core.subjects import check_subject
from cavat.modules.content.lesson_package import (
    ChoiceAnswer,
    Item,
    LessonPackage,
    OpenAnswer,
    PhraseAnswer,
    WordOrderAnswer,
)
from cavat.modules.tutor.contracts import RenderContext, ValidationCode, ValidationIssue, ValidationResult
from cavat.modules.tutor.validator import (
    MOVES_SKIPPING_LEAK_CHECK,
    _closes_a_solved_item,
    singles_out_choice,
    validate_message,
)

VALIDATOR_VERSION = "english-validator/1.0.0"
SAY_AFTER_ME = "say_after_me"  # ENG-3b G10: ``Item.kind`` of a "con nói theo cô" item, when the schema has it


class EnglishCode(StrEnum):
    MATH_TERM = "MATH_TERM"
    OUT_OF_UNIT_ENGLISH = "OUT_OF_UNIT_ENGLISH"
    BARE_ENGLISH = "BARE_ENGLISH"
    BROKEN_MARKER = "BROKEN_MARKER"


# Notes for the retry prompt (Vietnamese, as the tutor's instructions are).
CODE_NOTES_EN: dict[str, str] = {
    EnglishCode.MATH_TERM: "có thuật ngữ của môn khác: giờ này chỉ ôn Tiếng Anh, đưa con về câu đang làm",
    EnglishCode.OUT_OF_UNIT_ENGLISH: "dùng từ tiếng Anh ngoài bài: chỉ dùng từ và mẫu câu của bài",
    EnglishCode.BARE_ENGLISH: "câu tiếng Anh thiếu câu dẫn tiếng Việt: đặt sau câu dẫn có dấu hai chấm",
    EnglishCode.BROKEN_MARKER: "đánh dấu sai: mỗi đoạn tiếng Anh viết đúng [[en: …]], không lẫn tiếng Việt",
    ValidationCode.ANSWER_LEAK: "đã nói câu trả lời đích của câu đang chờ: gợi ý đúng mức, để con tự nói",
}

# ---------------------------------------------------------------------------------------------- marks

MARK_OPEN, MARK_CLOSE = "[[en:", "]]"
_MARK = re.compile(r"\[\[en:\s*(.*?)\s*\]\]", re.S)
_QUOTES = "'‘’\"“”"
_QUOTED_MARK = re.compile(rf"[{_QUOTES}]\s*(\[\[en:.*?\]\])\s*[{_QUOTES}]", re.S)


def english_spans(text: str) -> list[str]:
    """The English passages of a marked text, in order."""
    return [m.group(1) for m in _MARK.finditer(text)]


def display_text(text: str) -> str:
    """What the screen shows: the marks removed, the English kept ("[[en: We swam.]]" -> "We swam.")."""
    return " ".join(_MARK.sub(lambda m: m.group(1), text).split())


def speech_segments(text: str) -> list[tuple[str, str]]:
    """What the voice reads, in order: ("vi", "Con nói theo cô:"), ("en", "We swam in the sea.") (G9)."""
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _MARK.finditer(text):
        before = text[pos : m.start()].strip()
        if before:
            out.append(("vi", before))
        out.append(("en", m.group(1)))
        pos = m.end()
    rest = text[pos:].strip()
    if rest:
        out.append(("vi", rest))
    return out


# ---------------------------------------------------------------------------------------------- words

# DI-138: English words any grade 5 sentence needs, whatever the unit (pronouns, be/do, articles,
# prepositions, question words, greetings). Everything else must come from the unit's own texts.
BASE_WORDS = frozenset(
    """a an the i you we he she they it me us him her them my your our his their its this that these those
    is am are was were be been do does did not no yes and or but so to in on at of for with from about by
    what when where who why how which there here some any very too please thank thanks hello hi goodbye bye
    good great well done can could will would let let's""".split()
)
# Words a Vietnamese sentence writes without any diacritic: never taken as English by themselves.
VI_ASCII = frozenset(
    """con cho theo anh em khi hay trong sang sau sai an do no to la va ma ban nha tranh nghe che chi thi gi
    ai hai ba tai nay nao sao vui bao ra tin tim minh nhan cao vao dau sinh kia chu cu lo mo co mua xem
    trang hoa hong lan mai long sa pa ha so qua""".split()
)
_ONSET = r"(?:ngh|ng|gh|gi|kh|nh|ph|qu|th|tr|ch|[bcdghklmnprstvx])?"
_VI_SYLLABLE = re.compile(rf"{_ONSET}[aeiouy]{{1,3}}(?:ng|nh|ch|[cmnpt])?")
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?|\d+", re.UNICODE)
_CONTRACTIONS = {
    "didn't": "did not",
    "i'm": "i am",
    "we're": "we are",
    "it's": "it is",
    "what's": "what is",
    "isn't": "is not",
    "wasn't": "was not",
    "weren't": "were not",
    "don't": "do not",
    "doesn't": "does not",
    "let's": "let us",
}


def _ascii_word(word: str) -> bool:
    return word.isascii() and word.replace("'", "").isalpha()


def is_english_word(word: str, lexicon: frozenset[str] = frozenset()) -> bool:
    """A word that is English and not a Vietnamese word written without diacritics.

    A word with a Vietnamese letter is Vietnamese, and so is a common Vietnamese word written without
    diacritics ("con", "hay", "so"). Another ASCII word is English when it is one of ``BASE_WORDS`` ("the",
    "you") or of the unit's ``lexicon`` ("buy", "boat"), when it cannot be a Vietnamese syllable ("swim",
    "did", "yes"), or when it has a letter the Vietnamese alphabet lacks (f, j, w, z)."""
    w = word.lower().replace("’", "'")
    if not _ascii_word(w) or w in VI_ASCII or w in ("a", "i"):
        return False
    if w in BASE_WORDS or w in lexicon or re.search(r"[fjwz']", w):
        return True
    return _VI_SYLLABLE.fullmatch(w) is None


_QUOTED_TEXT = re.compile(r"['‘\"“]([^'’\"”]+)['’\"”]")


def unit_lexicon(packages: Iterable[LessonPackage], extra_texts: Iterable[str] = ()) -> frozenset[str]:
    """Every English word the tutor may say in the unit (DI-138), from the unit's approved texts only
    (stems, answers, options, hints, solutions, concepts, misconceptions), plus ``BASE_WORDS``: the words
    of the English runs ``mark_english`` finds, of the quoted English ("'buy souvenirs' là làm gì?") and of
    the English answers. A Vietnamese word written without diacritics ("qua") is not taken."""
    words: set[str] = set(BASE_WORDS)
    for text in [*_package_texts(packages), *extra_texts]:
        text = unicodedata.normalize("NFC", text).replace("’", "'")
        english = [*english_spans(mark_english(text)), *(q for q in _QUOTED_TEXT.findall(text))]
        if is_english_text(text):
            english.append(text)
        for part in english:
            if not is_english_text(part) and not any(is_english_word(w) for w in _WORD.findall(part)):
                continue
            for w in _WORD.findall(part):
                w = w.lower()
                if _ascii_word(w) and w not in VI_ASCII:
                    words.add(w)
                    words.update(_CONTRACTIONS.get(w, "").split())
    return frozenset(words)


def _package_texts(packages: Iterable[LessonPackage]) -> list[str]:
    texts: list[str] = []
    for pkg in packages:
        texts += [pkg.title, *(o.text for o in pkg.objectives), *(h.text for h in pkg.generic_hints)]
        texts += [k.description for k in pkg.kcs] + [k.name for k in pkg.kcs]
        texts += [f"{c.name} {c.explanation}" for c in pkg.concepts]
        for mis in pkg.misconceptions:
            texts += [mis.name, mis.description, *mis.counter_examples]
        for item in pkg.items:
            texts += [item.stem, item.rephrase or "", item.explanation or "", *item.worked_solution]
            texts += [h.text for h in item.hints]
            texts += _answer_texts(item)
    return texts


def _answer_texts(item: Item) -> list[str]:
    ans = item.answer
    if isinstance(ans, PhraseAnswer):
        return [*ans.accept, *(p for g in ans.required for p in g), *ans.wrong_answers]
    if isinstance(ans, WordOrderAnswer):
        return [" ".join(ans.tokens)]
    if isinstance(ans, OpenAnswer):
        groups = ans.facts.phrases if ans.facts else []
        return [ans.sample_answer, *(p for g in groups for p in g)]
    if isinstance(ans, ChoiceAnswer):
        return [t for o in ans.options for t in (o.text, *o.aliases)]
    return []


# ---------------------------------------------------------------------------------------------- marking


def mark_english(text: str, lexicon: frozenset[str] = frozenset()) -> str:
    """``text`` with every English run inside ``[[en: …]]`` (G9). Marks already there are kept.

    A run is a sequence of words with at least one English word and no Vietnamese word, with the
    punctuation between them and the ".?!" right after it (see ``_kind``). Quotes around a marked run are
    dropped: the mark is the quotation."""
    out: list[str] = []
    pos = 0
    for m in _MARK.finditer(text):
        out.append(_mark_plain(text[pos : m.start()], lexicon))
        out.append(f"{MARK_OPEN} {m.group(1)}{MARK_CLOSE}")
        pos = m.end()
    out.append(_mark_plain(text[pos:], lexicon))
    marked = "".join(out)
    return _QUOTED_MARK.sub(lambda m: m.group(1), marked)


def _kind(word: str, lexicon: frozenset[str] = frozenset()) -> str:
    """EN, AMBIG (may sit inside an English run: "I", "a", a number, a proper name such as "Nha Trang"),
    or VI (ends a run: a word with a Vietnamese letter, or a common Vietnamese word written in lower case
    without diacritics, such as "con" or "hay" in "buy hay bought")."""
    if word.isdigit():
        return "AMBIG"
    if not _ascii_word(word.replace("’", "'")):
        return "VI"
    if word.lower() in VI_ASCII:
        return "AMBIG" if word[0].isupper() else "VI"
    return "EN" if is_english_word(word, lexicon) else "AMBIG"


def _mark_plain(text: str, lexicon: frozenset[str]) -> str:
    words = [(m.start(), m.end(), m.group(0)) for m in _WORD.finditer(text)]
    runs: list[tuple[int, int]] = []
    i = 0
    while i < len(words):
        if _kind(words[i][2], lexicon) == "VI":
            i += 1
            continue
        j = i
        while (
            j + 1 < len(words)
            and _kind(words[j + 1][2], lexicon) != "VI"
            and _joined(text, words[j], words[j + 1])
        ):
            j += 1
        run = words[i : j + 1]
        while run and run[0][2].lower() in VI_ASCII:
            run = run[1:]  # "Sau did…": a capital Vietnamese word opening the sentence is not English
        if any(_kind(w, lexicon) == "EN" for _, _, w in run):
            end = run[-1][1]
            tail = re.match(r"(?:\s*…|[.?!])+", text[end:])
            runs.append((run[0][0], end + (tail.end() if tail else 0)))
        i = j + 1
    out, pos = [], 0
    for start, end in runs:
        out += [text[pos:start], f"{MARK_OPEN} {text[start:end]}{MARK_CLOSE}"]
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _joined(text: str, left: tuple[int, int, str], right: tuple[int, int, str]) -> bool:
    """Two words belong to one English run when only spaces, commas or a hyphen stand between them; a
    full stop or a colon closes the run ("Con nói theo cô: Yes, I did." is one run after the colon)."""
    return re.fullmatch(r"[\s,\-…]*", text[left[1] : right[0]]) is not None


def english_speech(text: str, lexicon: frozenset[str] = frozenset()) -> tuple[str, str]:
    """(screen text, speech text): what the session stores for an English tutor turn (ENG-5b, ENG-6)."""
    marked = mark_english(text, lexicon)
    return display_text(marked), marked


# ---------------------------------------------------------------------------------------------- math

# DI-137: the terms of the other subject the tutor never says in an English session. Narrower than
# ``assessment.math_terms`` on purpose: "so sánh", "hàng", "cộng" or "giây" are ordinary Vietnamese words
# an English lesson uses ("so sánh do và did"). The subject's name "Toán" is not a term:
# a redirect may name it.
MATH_TERMS_BLOCK = (
    "số thập phân", "phân số", "tử số", "mẫu số", "phần nguyên", "phần thập phân", "phần mười", "phần trăm",
    "phần nghìn", "hàng phần mười", "số tự nhiên", "tia số", "diện tích", "chu vi", "tam giác", "hình thang",
    "hình chữ nhật", "hình vuông", "hình tròn", "đường cao", "đáy lớn", "đáy bé", "chiều cao", "phép tính",
    "phép cộng", "phép trừ", "phép nhân", "phép chia", "xăng-ti-mét", "mét vuông", "ki-lô-gam", "đề-xi-mét",
    "decimal", "fraction", "numerator", "denominator", "area", "triangle", "trapezoid", "perimeter",
    "plus", "minus", "multiply", "divide",
)  # fmt: skip
_MATH_TERM_RE = re.compile(
    r"(?<!\w)(" + "|".join(sorted(map(re.escape, MATH_TERMS_BLOCK), key=len, reverse=True)) + r")(?!\w)"
)
_ARITHMETIC = re.compile(r"\d+(?:[.,]\d+)?\s*(?:[+\-−×x*:÷=<>]|bằng|cộng|trừ|nhân|chia)\s*\d")


def math_terms_in(text: str) -> list[str]:
    """The terms of ``MATH_TERMS_BLOCK`` and the arithmetic in ``text``, in order, once each."""
    lowered = unicodedata.normalize("NFC", text).lower()
    found = _MATH_TERM_RE.findall(lowered) + [m.group(0) for m in _ARITHMETIC.finditer(lowered)]
    return list(dict.fromkeys(found))


# ---------------------------------------------------------------------------------------------- leak


# DI-110 is one function for the checker and for the leak check: ``core/en_text`` (ENG-4, ADR-063).
normalize_en = normalize_answer
_contains = contains_words


def _target_groups(item: Item) -> tuple[list[str], list[list[str]]]:
    """(whole target sentences, groups of accepted phrasings) when the item's answer is an English target.

    ``phrase`` (ADR-062, DI-125): ``accept`` and ``required``; ``word_order``: each accepted order as a
    sentence. An item answered in Vietnamese (``open``, a "vì sao" item of level C) is not an English target:
    its key phrases are ordinary Vietnamese words and its leak is guarded by ``leak_patterns``."""
    ans = item.answer
    sentences: list[str] = []
    groups: list[list[str]] = []
    if isinstance(ans, PhraseAnswer):
        sentences, groups = list(ans.accept), [list(g) for g in ans.required]
    elif isinstance(ans, WordOrderAnswer):
        sentences = [" ".join(order) for order in ans.accept]
    elif isinstance(ans, OpenAnswer):
        sentences = [ans.sample_answer]
        groups = [list(g) for g in ans.facts.phrases] if ans.facts else []
    sentences = [s for s in sentences if is_english_text(s)]
    if not all(g and all(p.isascii() for p in g) for g in groups):
        groups = []  # one group is a Vietnamese idea: the answer is a reason, not an English target
    return sentences, groups


def is_english_text(text: str) -> bool:
    """ASCII words only, at least one of them English: an English sentence, not a Vietnamese one."""
    words = _WORD.findall(text)
    return (
        bool(words)
        and all(_ascii_word(w) or w.isdigit() for w in words)
        and any(is_english_word(w) for w in words)
    )


def english_leak(text: str, item: Item) -> str | None:
    """The target the text gives away, if any (DI-108, DI-110).

    A leak is the whole target sentence, or a text that holds one phrasing of every required group with at
    least one of them not already in the question (the question may quote part of the answer)."""
    said = normalize_en(display_text(text))
    stem = normalize_en(" ".join((item.stem, item.rephrase or "")))
    sentences, groups = _target_groups(item)
    for sentence in sentences:
        target = normalize_en(sentence)
        if len(target.split()) >= 2 and _contains(said, target) and not _contains(stem, target):
            return f"states {sentence}"
    if groups:
        hits = [next((p for p in g if _contains(said, normalize_en(p))), None) for g in groups]
        if all(hits) and any(not _contains(stem, normalize_en(p)) for p in hits if p):
            return "states " + " … ".join(p for p in hits if p)
    if isinstance(item.answer, ChoiceAnswer) and singles_out_choice(display_text(text), item):
        return "singles out the right option"
    return None


def is_say_after_me(item: Item, say_after_me: bool | None = None) -> bool:
    """A "con nói theo cô" item (DI-108): the caller says so, or the item's ``kind`` does (ADR-062)."""
    return bool(say_after_me) if say_after_me is not None else getattr(item, "kind", None) == SAY_AFTER_ME


# ---------------------------------------------------------------------------------------------- validator

_PLACEHOLDER = "«»"


def _vietnamese_part(marked: str) -> str:
    """The text with every English passage replaced by a neutral placeholder; a quoted English question is
    not the tutor's question, unless it closes the turn (the tutor asks the child to ask it)."""
    parts: list[str] = []
    pos = 0
    matches = list(_MARK.finditer(marked))
    for k, m in enumerate(matches):
        parts.append(marked[pos : m.start()])
        last = k == len(matches) - 1 and not marked[m.end() :].strip()
        parts.append(_PLACEHOLDER + ("?" if last and m.group(1).rstrip().endswith("?") else ""))
        pos = m.end()
    parts.append(marked[pos:])
    return " ".join("".join(parts).split())


def _bare(marked: str) -> str | None:
    """English the voice would read with no Vietnamese around it (V2b, DI-138): a turn made only of English.
    A word inside a Vietnamese sentence ("Câu hỏi có did là chuyện đã qua") is not bare: the sentence is
    its context, and the voice (ENG-6) reads the marked passage inside it."""
    vietnamese = [w for w in _WORD.findall(_MARK.sub(" ", marked)) if not w.isdigit()]
    if english_spans(marked) and not vietnamese:
        return "no Vietnamese lead-in"
    return None


def validate_english_message(
    text: str,
    ctx: RenderContext,
    *,
    lexicon: frozenset[str],
    say_after_me: bool | None = None,
) -> ValidationResult:
    """Check one tutor message of an English session. ``lexicon`` is ``unit_lexicon`` of the unit."""
    if not text or not text.strip():
        return ValidationResult((ValidationIssue(ValidationCode.EMPTY),))
    issues: list[ValidationIssue] = []
    if text.count(MARK_OPEN) != len(_MARK.findall(text)):
        issues.append(ValidationIssue(EnglishCode.BROKEN_MARKER, "unclosed [[en:"))
    marked = mark_english(text, lexicon)
    shown = display_text(marked)

    # The Math validator, unchanged, on the Vietnamese part: questions, address, praise, echo, PII, safety
    # words, foreign scripts, numbers. Its leak and length checks are replaced by the English ones below.
    base = validate_message(_vietnamese_part(marked), ctx)
    issues += [i for i in base.issues if i.code not in (ValidationCode.ANSWER_LEAK, ValidationCode.TOO_LONG)]

    words = len(shown.split())
    if words > ctx.max_words:
        issues.append(ValidationIssue(ValidationCode.TOO_LONG, f"{words} > {ctx.max_words} words"))
    if math := math_terms_in(shown):
        issues.append(ValidationIssue(EnglishCode.MATH_TERM, ", ".join(math)))
    for span in english_spans(marked):
        vietnamese = [
            w for w in _WORD.findall(span) if not _ascii_word(w.replace("’", "'")) and not w.isdigit()
        ]
        if vietnamese:
            issues.append(
                ValidationIssue(EnglishCode.BROKEN_MARKER, "Vietnamese inside [[en:]]: " + vietnamese[0])
            )
    outside = sorted(
        {
            w.lower()
            for span in english_spans(marked)
            for w in _WORD.findall(span.replace("’", "'"))
            if _ascii_word(w) and w.lower() not in lexicon
        }
    )
    if outside:
        issues.append(ValidationIssue(EnglishCode.OUT_OF_UNIT_ENGLISH, ", ".join(outside)))
    if bare := _bare(marked):
        issues.append(ValidationIssue(EnglishCode.BARE_ENGLISH, bare))

    exempt = (
        ctx.decision.move in MOVES_SKIPPING_LEAK_CHECK
        or _closes_a_solved_item(ctx)
        or ctx.answer_revealed
        or is_say_after_me(ctx.item, say_after_me)
    )
    if not exempt:
        leak = english_leak(marked, ctx.item)
        for pattern in ctx.item.leak_patterns:
            if leak is None and re.search(pattern, shown.lower()):
                leak = f"leak_pattern {pattern}"
        if leak:
            issues.append(ValidationIssue(ValidationCode.ANSWER_LEAK, leak))
    return ValidationResult(tuple(dict.fromkeys(issues)))


def validator_for(
    subject: str, *, lexicon: frozenset[str] | None = None, say_after_me: bool | None = None
) -> Callable[[str, RenderContext], ValidationResult]:
    """The validator of ``subject`` (from the session's package, rule S1). Mathematics: the Math validator
    itself, untouched. English: ``validate_english_message`` bound to the unit's lexicon."""
    if check_subject(subject) == "math":
        return validate_message
    if lexicon is None:
        raise ValueError("an English session needs the unit's lexicon (unit_lexicon)")
    return partial(validate_english_message, lexicon=lexicon, say_after_me=say_after_me)
