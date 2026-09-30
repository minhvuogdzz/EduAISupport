"""Deterministic answer checking and misconception diagnosis for Math Grade 5 (ADR-010).

The LLM never decides whether a math answer is correct. This module does, using exact
arithmetic and "bug rules": each rule reproduces how a known misconception would answer, so a
wrong answer that matches a rule's prediction is evidence of that misconception.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cmp_to_key

from cavat.core.pedagogy import ErrorClass, Outcome
from cavat.modules.assessment.vi_numbers import ParsedNumber, extract_numbers, fold, format_vi, parse_literal
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    CompareAnswer,
    Item,
    LessonPackage,
    NumericAnswer,
    OpenAnswer,
    OrderAnswer,
)


@dataclass
class CheckResult:
    outcome: Outcome
    normalized: str | None = None  # the student's answer in canonical form ("<", "0,65", "B", "false"...)
    correct_answer: str | None = None
    error_class: ErrorClass | None = None
    misconception_id: str | None = None
    misconception_confidence: float = 0.0
    candidates: list[tuple[str, float]] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- intents

_ANSWER_DEMAND = ("dap an la gi", "cho con dap an", "cho em dap an", "noi dap an", "dap an di", "cho dap an")
_HELP = ("goi y", "khong biet", "khong hieu", "kho qua", "giup con", "giup em", "chiu", "bo qua")


def classify_intent(text: str) -> Outcome | None:
    """Detect messages that are not an attempt at the answer (silence, asking for help...)."""
    t = fold(text)
    if not t or t in {".", "..", "...", "?"}:
        return Outcome.NO_RESPONSE
    if any(p in t for p in _ANSWER_DEMAND):
        return Outcome.ANSWER_DEMAND
    if any(p in t for p in _HELP):
        has_answer = bool(extract_numbers(t)) or bool(_REL_RE.search(t))
        if not has_answer or " hay " in f" {t} ":
            return Outcome.HELP_REQUEST
    return None


# --------------------------------------------------------------------------- relations

_REL_WORDS: list[tuple[str, str]] = [
    ("bang nhau", "="),
    ("be hon", "<"),
    ("nho hon", "<"),
    ("it hon", "<"),
    ("lon hon", ">"),
    ("to hon", ">"),
    ("nhieu hon", ">"),
    ("bang", "="),
    ("<", "<"),
    (">", ">"),
    ("=", "="),
]
_REL_RE = re.compile("|".join(re.escape(w) for w, _ in _REL_WORDS))
_REL_MAP = dict(_REL_WORDS)
_FLIP = {"<": ">", ">": "<", "=": "="}


def _cmp_values(a: Fraction, b: Fraction) -> str:
    return "<" if a < b else ">" if a > b else "="


def _cmp_ints(a: int, b: int) -> str:
    return "<" if a < b else ">" if a > b else "="


# --------------------------------------------------------------------------- bug rules

BugRule = Callable[[ParsedNumber, ParsedNumber], str | None]


def bug_longer_is_larger(a: ParsedNumber, b: ParsedNumber) -> str | None:
    """DEC-M01: compare the decimal parts as whole numbers (0,25 > 0,3 because 25 > 3)."""
    ai, bi = int(a.int_part or "0"), int(b.int_part or "0")
    if ai != bi:
        return _cmp_ints(ai, bi)
    return _cmp_ints(int(a.frac_part or "0"), int(b.frac_part or "0"))


def bug_shorter_is_larger(a: ParsedNumber, b: ParsedNumber) -> str | None:
    """DEC-M02: fewer decimal digits means larger (0,4 > 0,45)."""
    ai, bi = int(a.int_part or "0"), int(b.int_part or "0")
    if ai != bi:
        return _cmp_ints(ai, bi)
    la, lb = len(a.frac_part), len(b.frac_part)
    if la != lb:
        return ">" if la < lb else "<"
    return _cmp_ints(int(a.frac_part or "0"), int(b.frac_part or "0"))


def bug_ignore_zero_placeholder(a: ParsedNumber, b: ParsedNumber) -> str | None:
    """DEC-M03: drop the zero right after the comma (0,05 = 0,5). Applies only if such a zero exists."""
    if not (a.frac_part.startswith("0") or b.frac_part.startswith("0")):
        return None
    ai, bi = int(a.int_part or "0"), int(b.int_part or "0")
    if ai != bi:
        return _cmp_ints(ai, bi)
    return _cmp_ints(int(a.frac_part.lstrip("0") or "0"), int(b.frac_part.lstrip("0") or "0"))


def bug_ignore_integer_part(a: ParsedNumber, b: ParsedNumber) -> str | None:
    """DEC-M04: compare only the decimal parts (2,1 < 1,99). Applies only if integer parts differ."""
    if int(a.int_part or "0") == int(b.int_part or "0"):
        return None
    return _cmp_ints(int(a.frac_part or "0"), int(b.frac_part or "0"))


def bug_trailing_zero_larger(a: ParsedNumber, b: ParsedNumber) -> str | None:
    """DEC-M05: a trailing zero makes the number larger (0,50 > 0,5). Applies only to equal values."""
    if a.value != b.value or len(a.frac_part) == len(b.frac_part):
        return None
    return ">" if len(a.frac_part) > len(b.frac_part) else "<"


BUG_RULES: dict[str, BugRule] = {
    "trailing_zero_larger": bug_trailing_zero_larger,
    "ignore_zero_placeholder": bug_ignore_zero_placeholder,
    "ignore_integer_part": bug_ignore_integer_part,
    "longer_is_larger": bug_longer_is_larger,
    "shorter_is_larger": bug_shorter_is_larger,
}
# Most specific rules first; a specific rule hides the general rule it specializes.
BUG_RULE_PRIORITY = list(BUG_RULES)
SPECIALIZES: dict[str, str] = {
    "trailing_zero_larger": "longer_is_larger",
    "ignore_zero_placeholder": "longer_is_larger",
}


def _rule_order(pkg: LessonPackage) -> list[tuple[str, str]]:
    """(misconception_id, bug_rule) pairs for misconceptions that have a known bug rule, by priority."""
    pairs = [(m.id, m.bug_rule) for m in pkg.misconceptions if m.bug_rule in BUG_RULES]
    return sorted(pairs, key=lambda p: BUG_RULE_PRIORITY.index(p[1]))


def _rank(matches: list[tuple[str, str]]) -> list[tuple[str, float]]:
    """Drop general rules hidden by a matched specific rule, then assign confidences."""
    rules = {rule for _, rule in matches}
    kept = [(mid, rule) for mid, rule in matches if not any(SPECIALIZES.get(r) == rule for r in rules)]
    if not kept:
        return []
    if len(kept) == 1:
        return [(kept[0][0], 0.8)]
    return [(kept[0][0], 0.6)] + [(mid, 0.4) for mid, _ in kept[1:]]


def _with_diagnosis(result: CheckResult, ranked: list[tuple[str, float]]) -> CheckResult:
    result.candidates = ranked
    if ranked:
        result.misconception_id, result.misconception_confidence = ranked[0]
        result.error_class = ErrorClass.CONCEPTUAL
    else:
        result.error_class = ErrorClass.UNKNOWN
    return result


# --------------------------------------------------------------------------- compare


def _map_side(n: ParsedNumber, left: ParsedNumber, right: ParsedNumber) -> str | None:
    if n.text == left.text:
        return "L"
    if n.text == right.text:
        return "R"
    if n.value == left.value and n.value != right.value:
        return "L"
    if n.value == right.value and n.value != left.value:
        return "R"
    return None


def parse_relation(text: str, left: ParsedNumber, right: ParsedNumber, ask: str = "sign") -> str | None:
    """Read the student's claim as a relation between `left` and `right` ('<', '>' or '=')."""
    t = fold(text)
    mapped = [(n.start, s) for n in extract_numbers(t) if (s := _map_side(n, left, right))]
    rels = [(m.start(), _REL_MAP[m.group(0)]) for m in _REL_RE.finditer(t)]
    if rels:
        pos, rel = rels[0]
        before = [s for p, s in mapped if p < pos]
        after = [s for p, s in mapped if p > pos]
        a = before[-1] if before else None
        b = after[0] if after else None
        if a and b:
            if a == b:
                return None
            return rel if a == "L" else _FLIP[rel]
        if a:
            return rel if a == "L" else _FLIP[rel]
        if b:
            return _FLIP[rel] if b == "L" else rel
        return rel
    sides = {s for _, s in mapped}
    if ask in ("larger", "smaller") and len(sides) == 1:
        chosen = sides.pop()
        larger_is_left = chosen == "L" if ask == "larger" else chosen == "R"
        return ">" if larger_is_left else "<"
    return None


def _check_compare(spec: CompareAnswer, text: str, pkg: LessonPackage) -> CheckResult:
    left, right = parse_literal(spec.left), parse_literal(spec.right)
    correct = _cmp_values(left.value, right.value)
    rel = parse_relation(text, left, right, spec.ask)
    if rel is None:
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=correct)
    if rel == correct:
        return CheckResult(Outcome.CORRECT, normalized=rel, correct_answer=correct)
    matches = []
    for mid, rule in _rule_order(pkg):
        pred = BUG_RULES[rule](left, right)
        if pred is not None and pred != correct and pred == rel:
            matches.append((mid, rule))
    result = CheckResult(Outcome.WRONG, normalized=rel, correct_answer=correct)
    return _with_diagnosis(result, _rank(matches))


# --------------------------------------------------------------------------- order


def _sorted_by(nums: list[ParsedNumber], rule: BugRule | None, direction: str) -> list[str]:
    def cmp(a: ParsedNumber, b: ParsedNumber) -> int:
        rel = (rule(a, b) if rule else None) or _cmp_values(a.value, b.value)
        return {"<": -1, "=": 0, ">": 1}[rel]

    ordered = sorted(nums, key=cmp_to_key(cmp))
    if direction == "desc":
        ordered.reverse()
    return [n.text for n in ordered]


def _check_order(spec: OrderAnswer, text: str, pkg: LessonPackage) -> CheckResult:
    nums = [parse_literal(s) for s in spec.numbers]
    correct = _sorted_by(nums, None, spec.direction)
    t = fold(text)
    picked: list[str] = []
    for n in extract_numbers(t):
        match = next((x for x in nums if x.text == n.text), None) or next(
            (x for x in nums if x.value == n.value), None
        )
        if match is None or match.text in picked:
            return CheckResult(Outcome.UNPARSEABLE, correct_answer="; ".join(correct))
        picked.append(match.text)
    if len(picked) != len(nums):
        return CheckResult(Outcome.UNPARSEABLE, correct_answer="; ".join(correct))
    rels = {_REL_MAP[m.group(0)] for m in _REL_RE.finditer(t)}
    if rels == {">"} and spec.direction == "asc":  # wrote a descending chain for an ascending question
        picked.reverse()
    normalized = "; ".join(picked)
    if picked == correct:
        return CheckResult(Outcome.CORRECT, normalized=normalized, correct_answer="; ".join(correct))
    matches = []
    for mid, rule in _rule_order(pkg):
        pred = _sorted_by(nums, BUG_RULES[rule], spec.direction)
        if pred != correct and pred == picked:
            matches.append((mid, rule))
    result = CheckResult(Outcome.WRONG, normalized=normalized, correct_answer="; ".join(correct))
    return _with_diagnosis(result, _rank(matches))


# --------------------------------------------------------------------------- numeric / choice / boolean


def _check_numeric(spec: NumericAnswer, text: str) -> CheckResult:
    target = parse_literal(spec.value)
    nums = extract_numbers(fold(text))
    if not nums:
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=spec.value)
    n = nums[0]
    if n.ambiguous_separator:
        return CheckResult(
            Outcome.NEEDS_CONFIRMATION,
            normalized=format_vi(n.value),
            correct_answer=spec.value,
            detail={"interpretation": format_vi(n.value)},
        )
    if n.value == target.value:
        return CheckResult(Outcome.CORRECT, normalized=format_vi(n.value), correct_answer=spec.value)
    result = CheckResult(Outcome.WRONG, normalized=format_vi(n.value), correct_answer=spec.value)
    for wrong, mid in spec.wrong_answers.items():
        if parse_literal(wrong).value == n.value:
            return _with_diagnosis(result, [(mid, 0.8)])
    return _with_diagnosis(result, [])


_LETTER_ANSWER = re.compile(r"^(?:phuong an|dap an|chon)?\s*([a-d])\s*[.)]?$")


def _mentions(t: str, phrase: str) -> int | None:
    m = re.search(r"(?<![a-z0-9])" + re.escape(fold(phrase)) + r"(?![a-z0-9])", t)
    return m.start() if m else None


def _check_choice(spec: ChoiceAnswer, text: str) -> CheckResult:
    correct = next(o for o in spec.options if o.correct)
    t = fold(text)
    chosen, ambiguous = None, False
    letter = _LETTER_ANSWER.match(t)
    if letter:
        chosen = next((o for o in spec.options if o.id.lower() == letter.group(1)), None)
    else:
        hits = []
        for o in spec.options:
            positions = [p for p in (_mentions(t, c) for c in [o.text, *o.aliases]) if p is not None]
            if positions:
                hits.append((min(positions), o))
        if hits:
            hits.sort(key=lambda h: h[0])
            chosen, ambiguous = hits[0][1], len(hits) > 1
    if chosen is None:
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=correct.id)
    if chosen.correct:
        return CheckResult(
            Outcome.CORRECT, normalized=chosen.id, correct_answer=correct.id, detail={"ambiguous": ambiguous}
        )
    result = CheckResult(
        Outcome.WRONG, normalized=chosen.id, correct_answer=correct.id, detail={"ambiguous": ambiguous}
    )
    if chosen.misconceptions:
        conf = chosen.misconception_confidence * (0.8 if ambiguous else 1.0)
        return _with_diagnosis(result, [(m, conf) for m in chosen.misconceptions])
    return _with_diagnosis(result, [])


_FALSE_RE = re.compile(r"\b(khong|chua)\s+(dung|chinh xac)\b|\bsai\b|\bnham\b")
_TRUE_RE = re.compile(r"\bdung\b|\bchinh xac\b")


def parse_verdict(text: str) -> bool | None:
    """Read a true/false verdict ("đúng", "sai", "không đúng"...)."""
    t = fold(text)
    if _FALSE_RE.search(t):
        return False
    if _TRUE_RE.search(t):
        return True
    if re.match(r"^(khong|ko)\b", t):
        return False
    if re.match(r"^(co|vang|da|u)\b", t):
        return True
    return None


def _check_boolean(spec: BooleanAnswer, text: str) -> CheckResult:
    verdict = parse_verdict(text)
    correct = "true" if spec.value else "false"
    if verdict is None:
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=correct)
    got = "true" if verdict else "false"
    if verdict == spec.value:
        return CheckResult(Outcome.CORRECT, normalized=got, correct_answer=correct)
    result = CheckResult(Outcome.WRONG, normalized=got, correct_answer=correct)
    mid = spec.wrong_answers.get(got)
    return _with_diagnosis(result, [(mid, 0.7)] if mid else [])


# --------------------------------------------------------------------------- entry point


def check_answer(item: Item, text: str, pkg: LessonPackage) -> CheckResult:
    """Check one student message against `item`. Never calls an LLM."""
    intent = classify_intent(text)
    if intent is not None:
        return CheckResult(intent)
    spec = item.answer
    if isinstance(spec, CompareAnswer):
        return _check_compare(spec, text, pkg)
    if isinstance(spec, OrderAnswer):
        return _check_order(spec, text, pkg)
    if isinstance(spec, NumericAnswer):
        return _check_numeric(spec, text)
    if isinstance(spec, ChoiceAnswer):
        return _check_choice(spec, text)
    if isinstance(spec, BooleanAnswer):
        return _check_boolean(spec, text)
    if isinstance(spec, OpenAnswer):
        return CheckResult(Outcome.NEEDS_LLM, normalized=text.strip())
    raise TypeError(f"unsupported answer type: {type(spec).__name__}")


def rule_family(pkg: LessonPackage, mis_id: str | None) -> str | None:
    """The general bug rule behind a misconception (a specialization maps to its parent)."""
    if mis_id is None:
        return None
    m = pkg.misconception(mis_id)
    if m is None or m.bug_rule is None:
        return mis_id
    return SPECIALIZES.get(m.bug_rule, m.bug_rule)
