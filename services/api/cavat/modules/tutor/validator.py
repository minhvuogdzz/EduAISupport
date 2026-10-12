"""Output validator for tutor messages (blueprint PART 13.4). Deterministic and offline (T03).

`validate_message` matches the `MessageValidator` protocol and runs on every tutor turn, template or LLM.
Text checks run on NFC lower case that KEEPS diacritics (`normalize_text`), as the lesson.yaml header
requires for `leak_patterns`: folding would make "Minh" match "mình" and "an sai" match "bạn sai".
"""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from fractions import Fraction
from itertools import combinations

from cavat.core.pedagogy import MOVES_ALLOWED_TO_REVEAL, MOVES_REQUIRING_QUESTION, Move
from cavat.modules.assessment.vi_numbers import extract_numbers, normalize_text, parse_literal, parse_number
from cavat.modules.content.lesson_package import (
    ChoiceAnswer,
    ChoiceOption,
    CompareAnswer,
    Item,
    NumericAnswer,
    OpenAnswer,
    OrderAnswer,
)
from cavat.modules.tutor.contracts import (
    RenderContext,
    ValidationCode,
    ValidationIssue,
    ValidationResult,
)

# VERIFY and CONFIRM_ADVANCE only follow a correct answer, so restating the answer there reveals nothing.
MOVES_AFTER_SOLVED = frozenset({Move.VERIFY, Move.CONFIRM_ADVANCE})
MOVES_SKIPPING_LEAK_CHECK = MOVES_ALLOWED_TO_REVEAL | MOVES_AFTER_SOLVED

_NUM = r"\d+(?:[.,]\d+)?"
_UNIT = r"(?:\s*(?:xăng-ti-mét|ki-lô-gam|mét|lít|giây|cm|kg|m|g|l)\b)?"
_RELATIONS: dict[str, Callable[[Fraction, Fraction], bool]] = {
    "lớn hơn hoặc bằng": operator.ge,
    "bé hơn hoặc bằng": operator.le,
    "nhỏ hơn hoặc bằng": operator.le,
    "lớn hơn": operator.gt,
    "bé hơn": operator.lt,
    "nhỏ hơn": operator.lt,
    "nặng hơn": operator.gt,
    "nhẹ hơn": operator.lt,
    "dài hơn": operator.gt,
    "ngắn hơn": operator.lt,
    "nhiều hơn": operator.gt,
    "ít hơn": operator.lt,
    "bằng": operator.eq,
    ">=": operator.ge,
    "<=": operator.le,
    "≥": operator.ge,
    "≤": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}
_REL_ALT = "|".join(re.escape(r) for r in _RELATIONS)  # dict order keeps longer phrases first
# Lookahead so chains like "0,2 < 0,25 < 0,3" yield every adjacent pair.
_RELATION_RE = re.compile(rf"(?<![\d.,])(?=({_NUM}){_UNIT}\s*({_REL_ALT})\s*({_NUM})(?![\d]))")
_ASSIGN_RE = re.compile(rf"(?:\b[a-z]|\bđáp án|\bkết quả)\s*(?:=|bằng\b|là\b)\s*({_NUM})(?![\d])")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_QUESTION_RE = re.compile(r"\?+")

PII_PATTERNS = [
    r"\bđịa chỉ\b",
    r"\bsố điện thoại\b",
    r"\bsđt\b",
    r"\be-?mail\b",
    r"\bmật khẩu\b",
    r"\bhọ (và )?tên\b",
    r"\btên đầy đủ\b",
    r"\bngày sinh\b",
    r"\bnhà (của )?(con|em|bạn) ở (đâu|chỗ nào|phố|đường)\b",
    r"\b(con|em|bạn) (học|ở) trường (nào|gì)\b",
    r"\b(facebook|zalo|tiktok|messenger|instagram)\b",
]
INTELLIGENCE_PRAISE_PATTERNS = [
    r"\bthông minh\b",
    r"\bthiên tài\b",
    r"\bthần đồng\b",
    r"\bsáng dạ\b",
    r"\bnhanh trí\b",
    r"\bhọc giỏi\b",
    r"\bgiỏi (quá|thế|ghê|lắm|nhất)\b",
    r"\b(con|em|bạn) (thật |rất |quá |siêu )?giỏi\b",
]


# Scripts that are never Vietnamese: CJK, kana, Hangul, Cyrillic, Thai, Arabic, Hebrew, Devanagari.
_FOREIGN_SCRIPT = re.compile(
    "[\u0400-\u04ff\u0590-\u05ff\u0600-\u06ff\u0900-\u097f\u0e00-\u0e7f\u3040-\u30ff"
    "\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)
# Letters the Vietnamese alphabet does not have (units such as "kg" and "km" use none of them).
_FOREIGN_LETTER = re.compile(r"(?<![\w-])[a-zà-ỹ]*[fjwz][a-zà-ỹ]*(?![\w-])")
# English words with no Vietnamese twin ("so" is in "so sánh", "to" means big: both stay out of the list).
_ENGLISH_WORDS = frozenset("the and is are of you your but this that it not yes like okay ok very".split())


def foreign_text(text: str) -> str | None:
    """A character or word that is not Vietnamese (Qwen sometimes switches language mid-sentence)."""
    if m := _FOREIGN_SCRIPT.search(text):
        return m.group(0)
    lowered = normalize_text(text)
    if m := _FOREIGN_LETTER.search(lowered):
        return m.group(0)
    return next((w for w in re.findall(r"[a-z]+", lowered) if w in _ENGLISH_WORDS), None)


# Other ways of calling the child than the lesson's ``student_address``. "bạn" stays out: a child who says
# "bị bạn đánh" is echoed with it. "em bé" is a baby, not the child.
_ADDRESSES = ("em", "cháu", "cậu")


def wrong_address(text: str, student_address: str) -> str | None:
    """A word that calls the child something else than the lesson does ("em" in a lesson that says "con")."""
    lowered = text.lower()
    for word in _ADDRESSES:
        if word != student_address and re.search(rf"(?<!\w){word}(?!\w)(?! bé)", lowered):
            return word
    return None


def _value(token: str) -> Fraction | None:
    n = parse_number(token)
    return n.value if n is not None else None


def _sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _is_question(sentence: str) -> bool:
    return sentence.rstrip(" \"'”»)").endswith("?")


def _answer_pairs(item: Item) -> set[frozenset[Fraction]]:
    """Pairs of numbers whose true relation is (part of) the answer."""
    ans = item.answer
    if isinstance(ans, CompareAnswer):
        return {frozenset({parse_literal(ans.left).value, parse_literal(ans.right).value})}
    if isinstance(ans, OrderAnswer):
        values = {parse_literal(n).value for n in ans.numbers}
        return {frozenset(p) for p in combinations(values, 2)}
    return set()


def _states_relation(sentence: str, pairs: set[frozenset[Fraction]]) -> str | None:
    for m in _RELATION_RE.finditer(sentence):
        a, b = _value(m.group(1)), _value(m.group(3))
        if a is None or b is None or frozenset({a, b}) not in pairs:
            continue
        if _RELATIONS[m.group(2)](a, b):
            return f"{m.group(1)} {m.group(2)} {m.group(3)}"
    return None


def _states_order(sentence: str, ans: OrderAnswer) -> bool:
    target = sorted({parse_literal(n).value for n in ans.numbers}, reverse=ans.direction == "desc")
    said = [n.value for n in extract_numbers(sentence) if n.value in set(target)]
    k = len(target)
    return any(said[i : i + k] == target for i in range(len(said) - k + 1))


def _mentions(sentence: str, name: str) -> bool:
    """``name`` as a whole: "0,3" is not in "0,35", but "3/7," (a comma after it) names 3/7."""
    name = normalize_text(name)
    found = re.search(rf"(?<![\w/])(?<!\d[,.]){re.escape(name)}(?![\w/])(?![,.]\d)", sentence)
    return bool(name) and found is not None


def _option_names(option: ChoiceOption) -> list[str]:
    return [option.text, *option.aliases, option.id]


def _states_choice(sentence: str, ans: ChoiceAnswer) -> bool:
    right = any(_mentions(sentence, n) for o in ans.options if o.correct for n in _option_names(o))
    other = any(_mentions(sentence, n) for o in ans.options if not o.correct for n in _option_names(o))
    return right and not other


def singles_out_choice(text: str, item: Item) -> bool:
    """A sentence names the right option and no other ("đáp án là 7/10", "con chọn 7/10 là đúng"); naming
    them all ("3/7, 7/10 hay 10/3") tells nothing. Found in CTX-1: a choice item without leak_patterns let
    such a model message through since T03. Approved hints may point at the option on purpose, so the LLM
    renderer applies it to model output only, unless the anchor itself singles it out."""
    if not isinstance(item.answer, ChoiceAnswer):
        return False
    return any(_states_choice(s, item.answer) for s in _sentences(normalize_text(text)))


def _leak(text: str, ctx: RenderContext) -> str | None:
    item = ctx.item
    lowered = normalize_text(text)
    for pattern in item.leak_patterns:
        if re.search(pattern, lowered):
            return f"leak_pattern {pattern}"
    if isinstance(item.answer, NumericAnswer):
        answer = parse_literal(item.answer.value).value
        for m in _ASSIGN_RE.finditer(lowered):
            if _value(m.group(1)) == answer:
                return f"states {m.group(0).strip()}"
    pairs = _answer_pairs(item)
    for sentence in _sentences(lowered):
        # No exemption for questions: "0,25 bé hơn 0,3, đúng không?" tells the answer. "Số nào lớn hơn?"
        # has no "NUMBER RELATION NUMBER" and never matches.
        stated = _states_relation(sentence, pairs)
        if stated:
            return f"states {stated}"
        if _is_question(sentence):
            continue  # a question may list the numbers of an order item
        if isinstance(item.answer, OrderAnswer) and _states_order(sentence, item.answer):
            return "states the final order"
    return None


def grounded_values(ctx: RenderContext) -> set[Fraction]:
    """Every number the tutor may say for this item: item, hints, solution, lesson counter-examples."""
    item, pkg = ctx.item, ctx.package
    texts = [item.stem, item.rephrase or "", item.verify_prompt or "", item.explanation or ""]
    texts += item.worked_solution + [h.text for h in item.hints] + [h.text for h in pkg.generic_hints]
    texts += [pkg.default_verify_prompt or "", ctx.student_text or "", ctx.last_tutor or "", *ctx.evidence]
    ans = item.answer
    if isinstance(ans, CompareAnswer):
        texts += [ans.left, ans.right]
    elif isinstance(ans, OrderAnswer):
        texts += ans.numbers
    elif isinstance(ans, NumericAnswer):
        texts += [ans.value, *ans.wrong_answers]
    elif isinstance(ans, ChoiceAnswer):
        for opt in ans.options:
            texts += [opt.text, *opt.aliases]
            if opt.probe is not None:
                texts += [opt.probe.prompt, opt.probe.left, opt.probe.right]
    elif isinstance(ans, OpenAnswer):
        texts.append(ans.sample_answer)
    for mis in pkg.misconceptions:
        for c in mis.counter_examples:
            if isinstance(ans, CompareAnswer):
                c = c.replace("{left}", ans.left).replace("{right}", ans.right)
            texts.append(c)
    return {n.value for t in texts for n in extract_numbers(t)}


def validate_message(text: str, ctx: RenderContext) -> ValidationResult:
    """Check one tutor message against the turn's decision and the lesson content (PART 13.4)."""
    if not text or not text.strip():
        return ValidationResult((ValidationIssue(ValidationCode.EMPTY),))
    issues: list[ValidationIssue] = []
    move = ctx.decision.move
    lowered = normalize_text(text)

    if move not in MOVES_SKIPPING_LEAK_CHECK:
        leak = _leak(text, ctx)
        if leak:
            issues.append(ValidationIssue(ValidationCode.ANSWER_LEAK, leak))

    questions = len(_QUESTION_RE.findall(text))
    if questions > 1:
        issues.append(ValidationIssue(ValidationCode.MULTIPLE_QUESTIONS, f"{questions} questions"))
    if move in MOVES_REQUIRING_QUESTION and (questions == 0 or not _is_question(text.strip())):
        detail = "no question" if questions == 0 else "the question must come last"
        issues.append(ValidationIssue(ValidationCode.MISSING_QUESTION, detail))

    foreign = foreign_text(text)
    if foreign:
        issues.append(ValidationIssue(ValidationCode.FOREIGN_TEXT, foreign))
    address = wrong_address(text, ctx.persona.student_address)
    if address:
        issues.append(ValidationIssue(ValidationCode.WRONG_ADDRESS, address))

    words = len(text.split())
    if words > ctx.max_words:
        issues.append(ValidationIssue(ValidationCode.TOO_LONG, f"{words} > {ctx.max_words} words"))

    for code, patterns in (
        (ValidationCode.PII_REQUEST, PII_PATTERNS),
        (ValidationCode.INTELLIGENCE_PRAISE, INTELLIGENCE_PRAISE_PATTERNS),
    ):
        hit = next((m.group(0) for p in patterns if (m := re.search(p, lowered))), None)
        if hit:
            issues.append(ValidationIssue(code, hit))

    grounded = grounded_values(ctx)
    ungrounded = [n.text for n in extract_numbers(text) if n.value not in grounded]
    if ungrounded:
        issues.append(ValidationIssue(ValidationCode.UNGROUNDED_NUMBER, ", ".join(ungrounded)))

    return ValidationResult(tuple(issues))
