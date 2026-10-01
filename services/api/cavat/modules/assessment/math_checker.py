"""Deterministic answer checking and misconception diagnosis for Math Grade 5 (ADR-010).

The LLM never decides whether a math answer is correct. This module does, using exact
arithmetic and "bug rules": each rule reproduces how a known misconception would answer, so a
wrong answer that matches a rule's prediction is evidence of that misconception.

Words in the student's message are matched with `tolerant_pattern`: diacritics may be left out,
but a mark that was typed must fit the word ("bang" can be "bằng", "bảng" cannot). When a message
can be read two ways, the checker returns UNPARSEABLE so the tutor asks again instead of grading
a guess.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from fractions import Fraction
from functools import cmp_to_key

from cavat.core.pedagogy import ErrorClass, Outcome
from cavat.modules.assessment.vi_numbers import (
    ParsedNumber,
    extract_numbers,
    format_vi,
    normalize_text,
    parse_literal,
    phrase_regex,
    tolerant_pattern,
)
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    ChoiceOption,
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


def _words(*words: str) -> str:
    """Regex alternation of tolerant whole words or phrases."""
    return "(?:" + "|".join(tolerant_pattern(w) for w in words) + ")"


# "không" as children type it.
_NOT = ("không", "ko", "k", "hông", "hok", "khg")

# --------------------------------------------------------------------------- intents

_ANSWER_DEMAND_RE = phrase_regex(
    ["đáp án là gì", "cho con đáp án", "cho em đáp án", "nói đáp án", "đáp án đi", "cho đáp án"]
)
_HELP_RE = phrase_regex(
    [f"{neg} {verb}" for neg in (*_NOT, "chưa") for verb in ("biết", "hiểu")]
    + ["gợi ý", "khó quá", "giúp con", "giúp em", "chịu", "bỏ qua"]
)
_OR_RE = phrase_regex(["hay", "hoặc"])
_SILENT_RE = re.compile(r"[\s.…?!]*")


def classify_intent(text: str) -> Outcome | None:
    """Detect messages that are not an attempt at the answer (silence, asking for help...)."""
    t = normalize_text(text)
    if _SILENT_RE.fullmatch(t):
        return Outcome.NO_RESPONSE
    if _ANSWER_DEMAND_RE.search(t):
        return Outcome.ANSWER_DEMAND
    if _HELP_RE.search(t):
        has_answer = bool(extract_numbers(t)) or bool(_relations(t))
        if not has_answer or _OR_RE.search(t):
            return Outcome.HELP_REQUEST
    return None


# --------------------------------------------------------------------------- relations

_REL_WORDS: list[tuple[str, str]] = [
    ("bằng nhau", "="),
    ("bé hơn", "<"),
    ("nhỏ hơn", "<"),
    ("ít hơn", "<"),
    ("lớn hơn", ">"),
    ("to hơn", ">"),
    ("nhiều hơn", ">"),
    ("bằng", "="),
    ("<", "<"),
    (">", ">"),
    ("=", "="),
]
# "dấu bé hơn", "dấu <": the sign to write in the blank, not a claim about the number just before it.
_SIGN_WORDS = [(f"dấu {w}", rel) for w, rel in _REL_WORDS] + [("dấu bé", "<"), ("dấu lớn", ">")]
_ALL_REL_WORDS = _SIGN_WORDS + _REL_WORDS
_REL_RE = phrase_regex(w for w, _ in _ALL_REL_WORDS)
_BY_MEANS_RE = re.compile(tolerant_pattern("bằng cách"))  # "làm bằng cách..." claims no equality
# Between a number and a relation word, these end the clause: "< vì 2 < 3", "0,30, bé hơn".
_CLAUSE_BREAK_RE = re.compile(rf"[,;:.!?…]|{_words('vì', 'nên', 'do', 'bởi', 'tại', 'nhưng')}")
_FLIP = {"<": ">", ">": "<", "=": "="}


def _relations(t: str) -> list[tuple[int, int, str, bool]]:
    """(start, end, relation, names_sign) for every relation word or sign in normalized text `t`."""
    by_means = {m.start() for m in _BY_MEANS_RE.finditer(t)}
    found = []
    for m in _REL_RE.finditer(t):
        if m.start() in by_means:
            continue
        i = m.lastindex - 1
        found.append((m.start(), m.end(), _ALL_REL_WORDS[i][1], i < len(_SIGN_WORDS)))
    return found


def _cmp_values(a: Fraction, b: Fraction) -> str:
    return "<" if a < b else ">" if a > b else "="


def _cmp_ints(a: int, b: int) -> str:
    return "<" if a < b else ">" if a > b else "="


def _written_as(n: ParsedNumber, refs: list[ParsedNumber]) -> int | None:
    """Index of the number in `refs` that `n` stands for, or None.

    Same text first, then the same digits with the other separator ("0.50" is "0,50", not "0,5"),
    then the only reference with the same value ("0,30" is "0,3").
    """
    for same in (
        lambda r: r.text == n.text,
        lambda r: r.value == n.value and (r.int_part, r.frac_part) == (n.int_part, n.frac_part),
    ):
        hits = [i for i, r in enumerate(refs) if same(r)]
        if hits:
            return hits[0]
    hits = [i for i, r in enumerate(refs) if r.value == n.value]
    return hits[0] if len(hits) == 1 else None


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
    return {0: "L", 1: "R"}.get(_written_as(n, [left, right]))


def parse_relation(text: str, left: ParsedNumber, right: ParsedNumber, ask: str = "sign") -> str | None:
    """Read the student's claim as a relation between `left` and `right` ('<', '>' or '=').

    Each relation word is read against the nearest number on each side within its clause. A claim
    naming both numbers beats a one-sided claim ("0,3 lớn hơn"), which beats a bare sign ("<",
    "dấu bé hơn"). Claims about other numbers ("vì 25 > 3") are ignored; contradictory claims
    ("< hay >") give None.
    """
    t = normalize_text(text)
    nums = [(n.start, n.end, _map_side(n, left, right)) for n in extract_numbers(t)]
    both: set[str] = set()
    one_sided: set[str] = set()
    bare: set[str] = set()
    for start, end, rel, names_sign in _relations(t):
        # Nearest number on each side in the same clause: "L", "R", None (another number) or "" (none).
        before = [side for _, e, side in nums if e <= start and not _CLAUSE_BREAK_RE.search(t, e, start)]
        after = [side for s, _, side in nums if s >= end and not _CLAUSE_BREAK_RE.search(t, end, s)]
        a = before[-1] if before else ""
        b = after[0] if after else ""
        if a and b and a != b:
            both.add(rel if a == "L" else _FLIP[rel])
        elif names_sign or (a == "" and b == ""):
            bare.add(rel)
        elif a is None or b is None or a == b:
            continue  # a claim about another number ("vì 25 > 3")
        elif a:
            one_sided.add(rel if a == "L" else _FLIP[rel])
        else:
            one_sided.add(_FLIP[rel] if b == "L" else rel)
    for claims in (both, one_sided, bare):
        if claims:
            return next(iter(claims)) if len(claims) == 1 else None
    sides = {side for _, _, side in nums if side}
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

# The sign of a chain written the other way round: "0,305 > 0,3 > 0,25 > 0,2" still lists an ascending order.
_CHAIN_AGAINST = {"asc": ">", "desc": "<"}


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
    t = normalize_text(text)
    picked: list[str] = []
    for n in extract_numbers(t):
        i = _written_as(n, nums)
        if i is None or nums[i].text in picked:
            return CheckResult(Outcome.UNPARSEABLE, correct_answer="; ".join(correct))
        picked.append(nums[i].text)
    if len(picked) != len(nums):
        return CheckResult(Outcome.UNPARSEABLE, correct_answer="; ".join(correct))
    if {rel for _, _, rel, _ in _relations(t)} == {_CHAIN_AGAINST[spec.direction]}:
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


# --------------------------------------------------------------------------- numeric

# Text just before a value given to an unknown: "x = ", "x là ", "số x bằng ".
_ASSIGNED_RE = re.compile(rf"(?<!\w)[a-z]\s*(?:=|:|{_words('là', 'bằng')})\s*$")


def _check_numeric(spec: NumericAnswer, text: str) -> CheckResult:
    target = parse_literal(spec.value)
    t = normalize_text(text)
    nums = extract_numbers(t)
    if not nums:
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=spec.value)
    # "0,65 > 0,6 nên x = 6": the value given to the unknown is the answer wherever it stands;
    # otherwise the first number is. Two different values for the unknown cannot be graded.
    assigned = [n for n in nums if _ASSIGNED_RE.search(t, 0, n.start)]
    if len({n.value for n in assigned}) > 1:
        values = list(dict.fromkeys(format_vi(n.value) for n in assigned))
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=spec.value, detail={"assigned": values})
    n = assigned[0] if assigned else nums[0]
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


# --------------------------------------------------------------------------- choice

# The polite particle "ạ" ("Hoa ạ", "B ạ"). Only with its dot below: a bare "a" may be option A.
_PARTICLE_RE = re.compile(r"(?<!\w)ạ(?!\w)")
_OPENERS_RE = re.compile(rf"^(?:{_words('thưa cô', 'dạ', 'vâng')}[\s,.!:]*)+")
_LETTER_RE = re.compile(
    rf"^(?:{_words('con', 'em', 'mình')}\s+)?(?:{_words('chọn')}\s+)?"
    rf"(?:{_words('phương án', 'đáp án', 'câu', 'ý')}\s*(?:{_words('là')}\s*)?)?([a-z])\s*[.)]?$"
)
# "Bạn nào chạy nhanh hơn?" asks about "chạy nhanh".
_ASKED_RE = re.compile(r"(?<!\w)(?:nào|ai)\s+(.+?)\s+hơn\s*\?")
_COMPARATIVE_RE = re.compile(rf"(\w+)\s+{tolerant_pattern('hơn')}")


def _strip_courtesy(t: str) -> str:
    """Drop the particle "ạ" and a leading "dạ"/"vâng"/"thưa cô": "dạ, b ạ" -> "b"."""
    return normalize_text(_OPENERS_RE.sub("", _PARTICLE_RE.sub(" ", t).strip()))


def _read_choice(stem: str, options: list[ChoiceOption], t: str) -> tuple[ChoiceOption | None, list[str]]:
    """The option the student chose, and the ids of every option they named."""
    letter = _LETTER_RE.match(t)
    if letter:
        return next((o for o in options if o.id.lower() == letter.group(1)), None), []
    mentions = sorted(
        (m.start(), m.end(), o.id)
        for o in options
        for phrase in (o.text, *o.aliases)
        for m in re.finditer(tolerant_pattern(phrase), t)
    )
    named = list(dict.fromkeys(oid for _, _, oid in mentions))
    by_id = {o.id: o for o in options}
    asked = _ASKED_RE.search(normalize_text(stem))
    if asked and named:
        # "Hoa chạy nhanh hơn Lan" answers "Bạn nào chạy nhanh hơn?" with Hoa; "Lan chạy chậm hơn"
        # uses another comparative, which the checker cannot interpret safely.
        asked_words = [tolerant_pattern(w) for w in asked.group(1).split()]
        numbers_end = [n.end for n in extract_numbers(t)]
        same: set[str] = set()
        other = False
        for c in _COMPARATIVE_RE.finditer(t):
            subject = max(((e, oid) for _, e, oid in mentions if e <= c.start()), default=None)
            if subject is None or any(subject[0] < e <= c.start() for e in numbers_end):
                continue  # not about an option, e.g. "vì 9,75 bé hơn 9,8"
            if any(re.fullmatch(w, c.group(1)) for w in asked_words):
                same.add(subject[1])
            else:
                other = True
        if same or other:
            return (by_id[same.pop()] if len(same) == 1 else None), named
    return (by_id[named[0]] if len(named) == 1 else None), named


def _check_choice(stem: str, spec: ChoiceAnswer, text: str) -> CheckResult:
    correct = next(o for o in spec.options if o.correct)
    chosen, named = _read_choice(stem, spec.options, _strip_courtesy(normalize_text(text)))
    if chosen is None:
        detail = {"mentioned": named} if len(named) > 1 else {}
        return CheckResult(Outcome.UNPARSEABLE, correct_answer=correct.id, detail=detail)
    if chosen.correct:
        return CheckResult(Outcome.CORRECT, normalized=chosen.id, correct_answer=correct.id)
    result = CheckResult(Outcome.WRONG, normalized=chosen.id, correct_answer=correct.id)
    return _with_diagnosis(result, [(m, chosen.misconception_confidence) for m in chosen.misconceptions])


# --------------------------------------------------------------------------- boolean

_TRUE_WORD = _words("đúng", "chính xác")
_FALSE_WORD = _words("sai", "nhầm")
_NEGATION = rf"{_words(*_NOT, 'chưa')}\s+(?:{_words('hề')}\s+)?"
_UNDECIDED_RE = re.compile(rf"{_words('đúng', 'sai')}\s+{_words('hay', 'hoặc')}\s+{_words('đúng', 'sai')}")
_NOT_FALSE_RE = re.compile(_NEGATION + _FALSE_WORD)
_NOT_TRUE_RE = re.compile(_NEGATION + _TRUE_WORD)
_FALSE_RE = re.compile(_FALSE_WORD)
_TRUE_RE = re.compile(_TRUE_WORD)
_NO_RE = re.compile(rf"^{_words(*_NOT)}")
_YES_RE = re.compile(rf"^{_words('có', 'vâng', 'dạ', 'ừ')}")


def parse_verdict(text: str) -> bool | None:
    """Read a true/false verdict ("đúng", "sai", "không đúng", "không sai"...), or a yes/no."""
    t = normalize_text(text)
    if _UNDECIDED_RE.search(t):
        return None
    if _NOT_FALSE_RE.search(t):
        return True
    if _NOT_TRUE_RE.search(t):
        return False
    if _FALSE_RE.search(t):
        return False
    if _TRUE_RE.search(t):
        return True
    if _NO_RE.match(t):
        return False
    if _YES_RE.match(t):
        return True
    return None


def _check_boolean(spec: BooleanAnswer, text: str) -> CheckResult:
    # A bare "dạ"/"vâng" acknowledges the question; it is not a verdict on the statement.
    verdict = parse_verdict(_strip_courtesy(normalize_text(text)))
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
        return _check_choice(item.stem, spec, text)
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
