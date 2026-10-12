"""Check an answer of the teacher's answer key against its question (INGEST-2), exactly, without a model.

An answer read from a document may be wrong three ways: the document is wrong, the reading is wrong (a
fraction in an image read as another, seen on the owner's answer key), or the answer is paired with the
wrong question. Each check below recomputes what it can from the question and compares:

- every relation written in the answer holds ("12 × 7 : 2 = 42", "0,8 kg > 750 g", "4,99 < 5,008");
- a conversion "3 m 5 dm = …… m", "7/10 = ……" has the answer's value, units converted;
- a rounding "≈ ……" gives the rounded value of the place the question names;
- a comparison "8,3 …… 8,29" is answered with the true sign, an order with the same numbers in order;
- "x is a natural number with 2,9 < x < 5,1", the digit place and value, "gồm 17 đơn vị, 1 phần mười…";
- the area of a triangle or a trapezoid, and the height or base from the area;
- a multiple-choice answer names an option, and a true/false answer the truth of a numeric statement.

A check that does not apply says nothing; an item no check applies to stays UNCHECKED for the teacher.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

from cavat.modules.assessment.vi_numbers import parse_number

# Units, by dimension, in the base unit of the dimension (m, kg, m²).
UNITS: dict[str, tuple[str, Fraction]] = {
    "mm": ("length", Fraction(1, 1000)),
    "cm": ("length", Fraction(1, 100)),
    "dm": ("length", Fraction(1, 10)),
    "m": ("length", Fraction(1)),
    "dam": ("length", Fraction(10)),
    "hm": ("length", Fraction(100)),
    "km": ("length", Fraction(1000)),
    "g": ("mass", Fraction(1, 1000)),
    "dag": ("mass", Fraction(1, 100)),
    "hg": ("mass", Fraction(1, 10)),
    "kg": ("mass", Fraction(1)),
    "yến": ("mass", Fraction(10)),
    "tạ": ("mass", Fraction(100)),
    "tấn": ("mass", Fraction(1000)),
    "mm²": ("area", Fraction(1, 10**6)),
    "cm²": ("area", Fraction(1, 10**4)),
    "dm²": ("area", Fraction(1, 100)),
    "m²": ("area", Fraction(1)),
    "dam²": ("area", Fraction(100)),
    "hm²": ("area", Fraction(10**4)),
    "ha": ("area", Fraction(10**4)),
    "km²": ("area", Fraction(10**6)),
}
_UNIT = r"(?:mm²|cm²|dm²|dam²|hm²|km²|m²|mm|cm|dm|dam|hm|km|ha|m|kg|dag|hg|g|yến|tạ|tấn)(?![\w²])"
_NUM = r"\d{1,3}(?: \d{3})+(?![\d/,])|\d+(?:[.,]\d+)*(?:\s*/\s*\d+)?"
_MIXED = r"\d+\s+\d+/\d+"
# One measure: "3 m 5 dm", "2 kg 350 g", "5 m² 25 dm²", "1,2 m", or a bare number "0,25", "3 5/10", "7/10".
MEASURE = re.compile(rf"(?:(?:{_NUM})\s*{_UNIT}(?:\s+(?:{_NUM})\s*{_UNIT})*|{_MIXED}|{_NUM})")
_RELATION = re.compile(r"\s*(<|>|=|≠|≈)\s*")
_PLACES = {
    "hàng nghìn": -3,
    "hàng trăm": -2,
    "hàng chục": -1,
    "hàng đơn vị": 0,
    "hàng phần mười": 1,
    "hàng phần trăm": 2,
    "hàng phần nghìn": 3,
}


@dataclass(frozen=True)
class Quantity:
    value: Fraction  # in the base unit of ``dimension`` (a bare number: itself)
    dimension: str  # length | mass | area | "" (a bare number)
    unit: str = ""  # the last unit written ("m" in "3 m 5 dm"): the unit the answer is given in


@dataclass(frozen=True)
class Finding:
    check: str  # RELATION | CONVERSION | ROUNDING | COMPARE | ORDER | RANGE | PLACE | COMPOSE | AREA | CHOICE
    ok: bool
    detail: str


def number(text: str) -> Fraction | None:
    """A Vietnamese number, fraction or mixed number ("3 5/10") as an exact value."""
    text = text.strip()
    if m := re.fullmatch(r"(\d+)\s+(\d+)\s*/\s*(\d+)", text):
        whole, num, den = (int(g) for g in m.groups())
        return Fraction(whole) + Fraction(num, den) if den else None
    if re.fullmatch(r"\d{1,3}(?: \d{3})+", text):  # "15 000"
        return Fraction(int(text.replace(" ", "")))
    parsed = parse_number(text)
    if parsed is None or parsed.text.replace(" ", "") != text.replace(" ", ""):
        return None
    return parsed.value


def quantity(text: str) -> Quantity | None:
    """A measure ("3 m 5 dm") or a number, else None. Mixing dimensions ("3 m 5 kg") is None."""
    text = text.strip().rstrip(".")
    pairs = re.findall(rf"({_NUM})\s*({_UNIT})", text)
    if pairs and re.fullmatch(rf"(?:{_NUM})\s*{_UNIT}(?:\s+(?:{_NUM})\s*{_UNIT})*", text):
        dims = {UNITS[u][0] for _, u in pairs}
        if len(dims) != 1:
            return None
        total = Fraction(0)
        for n, u in pairs:
            value = number(n)
            if value is None:
                return None
            total += value * UNITS[u][1]
        return Quantity(total, dims.pop(), pairs[-1][1])
    value = number(text)
    return Quantity(value, "") if value is not None else None


def evaluate(text: str) -> Quantity | None:
    """An arithmetic expression of the documents ("(11 + 7) × 5 : 2", "60 × 40 : 2 cm²"), else a quantity."""
    text = text.strip().rstrip(".")
    unit = ""
    if m := re.search(rf"\s({_UNIT})$", text):
        if re.search(r"[×:+\-−()]", text):  # "60 × 40 : 2 cm²": the unit is the result's
            unit, text = m.group(1), text[: m.start()].strip()
    if not re.search(r"[×:+\-−()]", text):
        q = quantity(text if not unit else f"{text} {unit}")
        return q
    tokens = re.findall(rf"{_MIXED}|{_NUM}|[×:+\-−()]", text)
    if "".join(tokens).replace(" ", "") != text.replace(" ", ""):
        return None
    value = _Expr(tokens).parse()
    if value is None:
        return None
    if unit:
        return Quantity(value * UNITS[unit][1], UNITS[unit][0], unit)
    return Quantity(value, "")


class _Expr:
    """Recursive descent over + − × : and parentheses, exact fractions."""

    def __init__(self, tokens: list[str]) -> None:
        self.tokens, self.i = tokens, 0

    def parse(self) -> Fraction | None:
        try:
            value = self._sum()
        except (ZeroDivisionError, IndexError, TypeError):
            return None
        return value if self.i == len(self.tokens) else None

    def _peek(self) -> str | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def _sum(self) -> Fraction:
        value = self._product()
        while self._peek() in ("+", "-", "−"):
            op = self.tokens[self.i]
            self.i += 1
            right = self._product()
            value = value + right if op == "+" else value - right
        return value

    def _product(self) -> Fraction:
        value = self._atom()
        while self._peek() in ("×", ":"):
            op = self.tokens[self.i]
            self.i += 1
            right = self._atom()
            value = value * right if op == "×" else value / right
        return value

    def _atom(self) -> Fraction:
        token = self.tokens[self.i]
        self.i += 1
        if token == "(":
            value = self._sum()
            if self._peek() != ")":
                raise IndexError
            self.i += 1
            return value
        value = number(token)
        if value is None:
            raise TypeError
        return value


def _same(a: Quantity, b: Quantity) -> bool | None:
    """Equal values; a bare number counts in the unit of the other side ("60 × 40 : 2 = 1200 cm²")."""
    if a.dimension and b.dimension:
        return a.value == b.value if a.dimension == b.dimension else None
    if a.dimension or b.dimension:
        unit = a.unit or b.unit
        scale = UNITS[unit][1]
        bare, measured = (a, b) if not a.dimension else (b, a)
        return bare.value * scale == measured.value
    return a.value == b.value


def _order(a: Quantity, b: Quantity) -> int | None:
    if a.dimension and b.dimension and a.dimension != b.dimension:
        return None
    if bool(a.dimension) != bool(b.dimension):
        unit = a.unit or b.unit
        av = a.value * UNITS[unit][1] if not a.dimension else a.value
        bv = b.value * UNITS[unit][1] if not b.dimension else b.value
    else:
        av, bv = a.value, b.value
    return (av > bv) - (av < bv)


def relations(text: str) -> list[tuple[str, str, str]]:
    """(left, sign, right) for each relation between two numeric terms written in ``text``."""
    out: list[tuple[str, str, str]] = []
    # An expression cut by a line break ("12 × 4 :\n2 = 24") is one line again.
    text = re.sub(r"([×:+\-−(])\s*\n\s*", r"\1 ", text)
    text = re.sub(r"\s*\n\s*([×:+\-−)])", r" \1", text)
    text = re.sub(rf"\(\s*({_NUM}(?:\s*{_UNIT})?)\s*\)", r"\1", text)  # "Lan (14,09)" is "Lan 14,09"
    for line in re.split(r"[;\n]|\.\s", text):
        pieces = _RELATION.split(line)
        if len(pieces) < 3:
            continue
        terms, signs = pieces[0::2], pieces[1::2]
        for k, sign in enumerate(signs):
            left = _edge(terms[k], suffix=True)
            # A name before the right term is its label ("Lan 1,40 > Mai 1,38").
            right = _edge(re.sub(r"^[A-ZĐ][a-zà-ỹ]+\s+(?=\d)", "", terms[k + 1].strip()), suffix=False)
            if left and right:
                out.append((left, sign, right))
    return out


_TERM = re.compile(rf"(?:\(?\s*(?:{_MIXED}|{_NUM})(?:\s*{_UNIT})?\s*\)?\s*(?:[×:+\-−]\s*)?)+")


def _edge(segment: str, *, suffix: bool) -> str:
    """The numeric term at the end (``suffix``) or the start of a piece of text, "" when there is none."""
    segment = segment.strip()
    candidates = [m for m in _TERM.finditer(segment) if m.group(0).strip()]
    if not candidates:
        return ""
    m = candidates[-1] if suffix else candidates[0]
    if suffix and segment[m.end() :].strip():
        return ""
    if not suffix and m.start() != 0:
        return ""
    # Part of a word or a number with a letter ("5,x3" is not "3"; "3x" is not "3").
    start = m.start() + len(m.group(0)) - len(m.group(0).lstrip())
    if suffix and start > 0 and (segment[start - 1].isalnum() or segment[start - 1] in ",."):
        return ""
    if not suffix and m.end() < len(segment) and segment[m.end()].isalpha() and segment[m.end() - 1] != " ":
        return ""
    term = m.group(0).strip().rstrip("×:+-−").strip()
    # A term followed or preceded by words is part of a sentence ("Đáy lớn: 24 − 9 = 15 cm" keeps "24 − 9").
    if evaluate(term) is not None:
        return term
    if suffix:  # "9 m: 8 × 9 : 2": the colon ends a phrase, the expression is what follows it
        for cut in re.finditer(r"[:×+\-−]\s*", term):
            rest = term[cut.end() :].strip()
            if rest and evaluate(rest) is not None and not re.search(r"[×:+\-−]\s*$", term[: cut.start()]):
                return rest
    return ""


_PLACE_WORDS = {"mười": 10, "trăm": 100, "nghìn": 1000}
_COMPUTING = frozenset(
    {"CONVERSION", "ROUNDING", "PLACE", "COMPOSE", "AREA", "WORDS", "EXTREME", "EQUAL", "RANGE", "DIGIT"}
)


def _plain(text: str) -> str:
    """Relations read as numbers: "3 phần trăm" is 3/100, labels "(1)" go, and a relation inside
    parentheses ("B (0,250 = 0,25)") stands on its own line."""
    text = re.sub(
        r"(\d+)\s+phần\s+(mười|trăm|nghìn)", lambda m: f"{m.group(1)}/{_PLACE_WORDS[m.group(2)]}", text
    )
    text = re.sub(r"\(\d\)\s*", "", text)
    return re.sub(r"\(([^()]*[<>=≠][^()]*)\)", r"\n\1\n", text)


def check_relations(text: str) -> list[Finding]:
    """Every relation written in an answer must hold (a reading or a typing error breaks one)."""
    findings = []
    for left, sign, right in relations(_plain(text)):
        a, b = evaluate(left), evaluate(right)
        if a is None or b is None or sign == "≈":
            continue
        if sign in ("=", "≠"):
            same = _same(a, b)
            if same is None:
                continue
            ok = same if sign == "=" else not same
        else:
            order = _order(a, b)
            if order is None:
                continue
            ok = order < 0 if sign == "<" else order > 0
        findings.append(Finding("RELATION", ok, f"{left} {sign} {right}"))
    return findings


def answer_quantity(answer: str, *, dimension: str | None = None) -> Quantity | None:
    """The value an answer gives: the term after the last "=" or "≈" of its first line, else its first term.

    ``dimension``: the last line giving a quantity of it, the result after the steps ("Đổi 0,6 m = 60 cm"
    then "S = … = 1200 cm²").
    """
    lines = answer.splitlines() if answer else []
    if dimension is not None:
        # Steps first, the result last ("Hình chữ nhật: … 24 m². Tam giác: … 6 m². Tổng: 30 m²."): read the
        # sentences from the end.
        lines = [p for line in lines for p in re.split(r"\.\s+", line) if p.strip()][::-1]
    for line in lines:
        line = re.sub(r"\(.*?\)", "", line).strip()
        for sign in ("≈", "="):
            if sign in line:
                line = line.rsplit(sign, 1)[1]
                break
        else:
            if ":" in line and not re.search(r"\d\s*:\s*\d", line):  # "Tổng: 30 m²", not "12 : 2"
                line = line.rsplit(":", 1)[1]
        term = _edge(line.strip().rstrip("."), suffix=False)
        q = evaluate(term) if term else None
        if dimension is None:
            return q
        if q is not None and q.dimension == dimension:
            return q
    return answer_quantity(answer) if dimension is not None else None


def round_to(value: Fraction, place: int) -> Fraction:
    """Round half up to ``place`` digits after the comma (0: units, -1: tens)."""
    scale = Fraction(10) ** place
    scaled = value * scale
    whole = int(scaled)
    if scaled - whole >= Fraction(1, 2):
        whole += 1
    return Fraction(whole) / scale


def place_named(text: str) -> int | None:
    lowered = text.lower()
    for name, place in sorted(_PLACES.items(), key=lambda kv: -len(kv[0])):
        if name in lowered:
            return place
    return None


def check_fill(stem: str, answer: str, context: str = "") -> list[Finding]:
    """A blank after "=" or "≈" in the question: the answer's value is the left side's, converted or
    rounded."""
    m = re.search(r"(.+?)\s*(=|≈)\s*(?:…+|\.{2,})\s*([^\s.…]*)", stem)
    if not m:
        return []
    left_text, sign, unit = m.group(1).strip(), m.group(2), m.group(3).strip()
    left_text = re.sub(r"^.*?:\s*", "", left_text)  # "Gồm …: " or "Phần nguyên …:" leaders
    left = evaluate(left_text)
    given = answer_quantity(answer)
    if left is None or given is None:
        return []
    if unit and unit in UNITS and not given.dimension:
        given = Quantity(given.value * UNITS[unit][1], UNITS[unit][0], unit)
    if sign == "≈":
        place = place_named(stem) if place_named(stem) is not None else place_named(context)
        if place is None or left.dimension or given.dimension:
            return []
        expected = round_to(left.value, place)
        return [Finding("ROUNDING", expected == given.value, f"{left_text} ≈ {_fmt(expected)}")]
    same = _same(left, given)
    if same is None:
        return []
    return [Finding("CONVERSION", same, f"{left_text} = {answer.splitlines()[0]}")]


def check_compare(stem: str, answer: str) -> list[Finding]:
    """ "8,3 …… 8,29" answered with a sign: the numbers are the question's and the sign is true."""
    m = re.search(rf"({MEASURE.pattern})\s*(?:…+|\.{{2,}})\s*({MEASURE.pattern})", stem)
    if not m:
        return []
    a, b = evaluate(m.group(1)), evaluate(m.group(2))
    sign = re.search(r"(<|>|=)", answer)
    if a is None or b is None or not sign:
        return []
    order = _order(a, b)
    if order is None:
        return []
    truth = {-1: "<", 0: "=", 1: ">"}[order]
    findings = [Finding("COMPARE", sign.group(1) == truth, f"{m.group(1)} {truth} {m.group(2)}")]
    # The answer writes the question's two numbers ("8,3 > 8,29"), not others.
    written = relations(answer.splitlines()[0])
    if written:
        left, _, right = written[0]
        x, y = evaluate(left), evaluate(right)
        if x is not None and y is not None:
            same = _same(x, a) and _same(y, b)
            findings.append(Finding("COMPARE", bool(same), f"{m.group(1)} và {m.group(2)}"))
    return findings


def check_order(stem: str, answer: str) -> list[Finding]:
    """An order: the answer lists the question's numbers, in the direction asked."""
    lowered = stem.lower()
    if "sắp xếp" not in lowered and "xếp" not in lowered:
        return []
    increasing = "bé đến lớn" in lowered or "thấp đến cao" in lowered or "gần đến xa" in lowered
    decreasing = "lớn đến bé" in lowered or "cao đến thấp" in lowered or "xa đến gần" in lowered
    if not (increasing or decreasing):
        return []
    asked = [evaluate(t) for t in re.split(r"\s*;\s*", stem.split(":", 1)[-1]) if evaluate(t.strip(" ."))]
    listed = re.findall(rf"{MEASURE.pattern}", answer.splitlines()[0])
    given = [evaluate(t) for t in listed]
    if not given or any(g is None for g in given):
        return []
    values = [g.value for g in given if g]
    ok = values == sorted(values, reverse=decreasing)
    findings = [Finding("ORDER", ok, answer.splitlines()[0])]
    asked_values = sorted(q.value for q in (evaluate(t.strip(" .")) for t in _listed_numbers(stem)) if q)
    if asked_values and len(asked_values) == len(values):
        findings.append(Finding("ORDER", sorted(values) == asked_values, "the numbers of the question"))
    del asked
    return findings


def _listed_numbers(stem: str) -> list[str]:
    """The numbers listed with ";" in a question ("5,08 ; 5,8 ; 5,008")."""
    m = re.search(rf"((?:{MEASURE.pattern})(?:\s*;\s*(?:{MEASURE.pattern}))+)", stem)
    return re.split(r"\s*;\s*", m.group(1)) if m else []


def check_range(stem: str, answer: str) -> list[Finding]:
    """The natural numbers x with a < x < b."""
    if "số tự nhiên" not in stem.lower():
        return []
    m = re.search(rf"({_NUM})\s*<\s*x\s*<\s*({_NUM})", stem)
    if not m:
        return []
    low, high = number(m.group(1)), number(m.group(2))
    if low is None or high is None:
        return []
    expected = [n for n in range(int(low), int(high) + 1) if low < n < high]
    after = answer.split("=", 1)[-1] if "x" in answer else answer
    given = sorted(
        int(v) for v in (number(t) for t in re.findall(r"\d+", after.splitlines()[0])) if v is not None
    )
    return [Finding("RANGE", given == expected, f"x = {' ; '.join(map(str, expected))}")]


def check_place(stem: str, answer: str) -> list[Finding]:
    """ "Số 64,138: chữ số 4 ở hàng …, giá trị …": the place and the value of that digit."""
    m = re.search(rf"(?:Số|số)\s+({_NUM})[:.,]?\s*chữ số\s+(\d)\b", stem)
    if not m:
        return []
    digits, digit = m.group(1), m.group(2)
    if "," not in digits:
        return []
    whole, frac = digits.split(",")
    places = [(c, len(whole) - 1 - i) for i, c in enumerate(whole)] + [
        (c, -(i + 1)) for i, c in enumerate(frac)
    ]
    found = [p for c, p in places if c == digit]
    if len(found) != 1:
        return []
    power = found[0]
    names = {v: k for k, v in _PLACES.items()}
    expected_place = names.get(-power)
    findings = []
    lowered = answer.lower()
    named = any(name.split(" ", 1)[1] in lowered for name in _PLACES)
    if expected_place and named:  # the answer names a place ("hàng phần trăm", or only "phần trăm")
        findings.append(Finding("PLACE", expected_place.split(" ", 1)[1] in lowered, expected_place))
    value = Fraction(int(digit)) * Fraction(10) ** power
    shown = re.search(r"giá trị\s*(?:là\s*)?(\d+(?:,\d+)?)", answer)
    bare = answer_quantity(answer) if not named and not shown else None
    if shown:
        findings.append(Finding("PLACE", number(shown.group(1)) == value, f"giá trị {_fmt(value)}"))
    elif bare is not None and not bare.dimension and "giá trị" in stem.lower():
        findings.append(Finding("PLACE", bare.value == value, f"giá trị {_fmt(value)}"))
    return findings


def check_compose(stem: str, answer: str) -> list[Finding]:
    """ "Gồm 17 đơn vị, 1 phần mười, 8 phần trăm": the number those places make."""
    lowered = stem.lower()
    if "gồm" not in lowered:
        return []
    weights = {
        "trăm": 100,
        "chục": 10,
        "đơn vị": 1,
        "phần mười": Fraction(1, 10),
        "phần trăm": Fraction(1, 100),
        "phần nghìn": Fraction(1, 1000),
    }
    total, found = Fraction(0), False
    for count, name in re.findall(r"(\d+)\s+(phần mười|phần trăm|phần nghìn|đơn vị|chục|trăm)", lowered):
        total += int(count) * weights[name]
        found = True
    given = answer_quantity(answer)
    if not found or given is None or given.dimension:
        return []
    return [Finding("COMPOSE", given.value == total, _fmt(total))]


_MORE_STEPS = re.compile(
    r"còn lại|trồng|thu hoạch|tiền|mỗi|cứ|gấp|tăng|giảm|hình chữ nhật|ghép|bằng hai cách|so sánh|lớn hơn",
    re.IGNORECASE,
)


def check_area(stem: str, answer: str, context: str = "") -> list[Finding]:
    """Triangle a × h : 2, trapezoid (a + b) × h : 2, and the height or a base from the area.

    Only a question that asks exactly that: a word problem with more steps (what is left, a harvest, a
    composite figure) is checked by the relations written in its answer instead.
    """
    if _MORE_STEPS.search(stem):
        return []
    text = f"{context} {stem}".lower()
    asks = _asked(stem)
    given = answer_quantity(answer, dimension="area" if asks == "s" else None)
    if given is None:
        return []
    terms = _area_terms(stem)
    lengths = {k: evaluate(v) for k, v in terms.items()}
    if any(v is None for v in lengths.values()):
        return []
    trapezoid = "hình thang" in text or "b" in lengths or "tổng" in lengths
    area, a, b, h, total = (lengths.get(k) for k in ("s", "a", "b", "h", "tổng"))
    if area is None and a is not None and h is not None and asks in ("s", ""):
        if trapezoid and b is None:
            return []
        expected = (a.value + (b.value if b else 0)) * h.value / 2
        return _compare(expected, given, [a, h] + ([b] if b else []), squared=True)
    if area is None:
        return []
    if asks == "h" and (total is not None or (a is not None and (b is not None or not trapezoid))):
        bases = total.value if total else a.value + (b.value if b else 0)  # type: ignore[union-attr]
        return _compare(area.value * 2 / bases, given, [area], squared=False)
    if asks in ("a", "đáy lớn", "tổng") and h is not None:
        bases = area.value * 2 / h.value
        if asks == "đáy lớn":
            if b is None:
                return []
            bases -= b.value
        elif asks == "a" and trapezoid:
            return []
        return _compare(bases, given, [area], squared=False)
    return []


def _asked(stem: str) -> str:
    """What the blank asks: "s" (the area), "h", "a" (a base), "đáy lớn", "tổng" (the two bases), ""."""
    lowered = stem.lower()
    blank = r"\s*=?\s*(?:…+|\.{2,})"
    if re.search(rf"đáy lớn{blank}", lowered):
        return "đáy lớn"
    if re.search(rf"tổng hai đáy{blank}", lowered):
        return "tổng"
    if re.search(rf"(?:chiều cao|\bh){blank}", lowered) or "tính chiều cao" in lowered:
        return "h"
    if re.search(rf"(?:\bđáy|\ba){blank}", lowered) or "độ dài đáy" in lowered:
        return "a"
    if re.search(rf"\bs{blank}", lowered) or "diện tích" in lowered:
        return "s"
    return ""


def _compare(
    expected: Fraction, given: Quantity, known: list[Quantity | None], *, squared: bool
) -> list[Finding]:
    """``expected`` is in base units when the known lengths have units (m², m), else a bare number."""
    measured = [q for q in known if q is not None and q.dimension]
    if not measured:
        if given.dimension:
            return []
        return [Finding("AREA", expected == given.value, _fmt(expected))]
    if given.dimension:
        return [
            Finding("AREA", expected == given.value, f"{_fmt(expected / UNITS[given.unit][1])} {given.unit}")
        ]
    # A bare answer is in the unit of the lengths of the question ("12 × 7 : 2 = 42" for cm and cm).
    units = {q.unit for q in measured if q.dimension == "length"}
    if len(units) != 1:
        return []
    unit = units.pop()
    scale = UNITS[unit][1] ** 2 if squared else UNITS[unit][1]
    return [
        Finding(
            "AREA",
            expected / scale == given.value,
            f"{_fmt(expected / scale)} {unit}{'²' if squared else ''}",
        )
    ]


def _area_terms(stem: str) -> dict[str, str]:
    """a, b, h, S and "tổng hai đáy" as written: "a = 6 cm, h = 4 cm", "Đáy 17 m, cao 12 m",
    "Đáy 11 cm và 5 cm, cao 6 cm", "S = 69 cm², đáy 23 cm"."""
    out: dict[str, str] = {}
    m_ = rf"(?:{_MIXED}|{_NUM})\s*{_UNIT}|(?:{_MIXED}|{_NUM})"
    for name, value in re.findall(rf"\b([abhS])\s*=\s*({m_})", stem):
        out[name.lower()] = value
    if m := re.search(rf"(?:hai đáy|đáy)\s+(?:dài\s+)?({m_})\s+(?:và|,)\s+({m_})", stem, re.IGNORECASE):
        out.setdefault("a", m.group(1))
        out.setdefault("b", m.group(2))
    else:
        if m := re.search(rf"đáy lớn\s+(?:dài\s+)?({m_})", stem, re.IGNORECASE):
            out.setdefault("a", m.group(1))
        if m := re.search(rf"đáy bé\s+(?:dài\s+)?({m_})", stem, re.IGNORECASE):
            out.setdefault("b", m.group(1))
        if "a" not in out and (m := re.search(rf"\bđáy\s+(?:dài\s+)?({m_})", stem, re.IGNORECASE)):
            out.setdefault("a", m.group(1))
    if m := re.search(rf"(?:chiều\s+)?cao\s+({m_})", stem, re.IGNORECASE):
        out.setdefault("h", m.group(1))
    if m := re.search(rf"tổng hai đáy\s+(?:là\s+)?({m_})", stem, re.IGNORECASE):
        out["tổng"] = m.group(1)
    if m := re.search(rf"\bS\s*=\s*({m_})", stem):
        out["s"] = m.group(1)
    return out


def check_choice(options: dict[str, str], answer: str) -> list[Finding]:
    """A multiple-choice answer names an option; the value it repeats is that option's."""
    m = re.match(r"\s*([A-D])\b", answer)
    if not m or not options:
        return [Finding("CHOICE", False, "no option named")] if options else []
    letter = m.group(1)
    if letter not in options:
        return [Finding("CHOICE", False, f"{letter} is not an option")]
    findings = [Finding("CHOICE", True, letter)]
    shown = re.match(rf"\s*{letter}\s*[—–\-]?\s*({MEASURE.pattern})\s*\.?\s*$", answer.splitlines()[0])
    if shown:
        a, b = evaluate(shown.group(1)), evaluate(options[letter])
        if a is not None and b is not None and _same(a, b) is not None:
            findings.append(Finding("CHOICE", bool(_same(a, b)), f"{letter}. {options[letter]}"))
    return findings


def check_true_false(stem: str, answer: str) -> list[Finding]:
    """ "0,50 = 0,5 ……" answered Đ or S: the truth of the numeric statement."""
    said = re.match(r"\s*(Đ|S)\b", answer)
    if not said:
        return []
    statement = re.sub(r"\s*(?:…+|\.{2,})\s*\(?(?:Đ/S)?\)?\s*$", "", stem).strip()
    found = check_relations(statement)
    if len(found) != 1:
        return []
    truth = found[0].ok
    return [Finding("TRUE_FALSE", (said.group(1) == "Đ") == truth, f"{statement}: {'Đ' if truth else 'S'}")]


def _fmt(value: Fraction) -> str:
    from cavat.modules.assessment.vi_numbers import format_vi

    return format_vi(value)


def check_item(
    stem: str,
    answer: str,
    *,
    options: dict[str, str] | None = None,
    context: str = "",
    question: str = "",
) -> list[Finding]:
    """Every check that applies to this question and its answer."""
    findings: list[Finding] = []
    stem = " ".join(stem.split())
    context = " ".join(context.split())
    findings += check_relations(answer)
    # The whole question too: an answer key may explain two sub-questions under the last one.
    sources = " ; ".join([context, question, stem, *(options or {}).values()])
    whole_answer = answer
    if options:
        findings += check_choice(options, answer)
        chosen = re.match(r"\s*([A-D])\b", answer)
        if not chosen or chosen.group(1) not in options:
            return findings
        # A worked answer ending "→ 2,07 m" ends on the chosen option's value.
        arrow = re.search(rf"→\s*({MEASURE.pattern})\s*\.?\s*$", answer.splitlines()[0])
        if arrow and (x := evaluate(arrow.group(1))) and (y := evaluate(options[chosen.group(1)])):
            same = _same(x, y)
            if same is not None:
                findings.append(Finding("CHOICE", same, f"→ {options[chosen.group(1)]}"))
        answer = options[chosen.group(1)]  # what the question's blank receives is the chosen option
    findings += check_true_false(stem, answer)
    findings += check_fill(stem, answer, context)
    findings += check_compare(stem, answer)
    findings += check_order(stem, answer)
    findings += check_range(stem, answer)
    findings += check_place(stem, answer) or check_digit_place(stem, answer, context)
    findings += check_compose(stem, answer)
    findings += check_words(stem, answer)
    findings += check_extreme(stem, answer)
    findings += check_equal_to(stem, answer)
    findings += check_rounding_said(stem, answer)
    findings += check_shapes(stem, answer)
    findings += check_named_measures(f"{context} {stem}", answer)
    findings += check_digit_x(stem, answer)
    if "diện tích" in f"{context} {stem}".lower() or re.search(r"\bS\s*=", stem):
        findings += check_area(stem, answer, context)
    if findings and all(f.ok for f in findings):  # an answer the other checks verified
        # What a check computed (a relation or a comparison only repeats the answer's own numbers), and the
        # value the answer gives when a computing check confirmed it.
        verified = _values(" ; ".join(f.detail for f in findings if f.check in _COMPUTING))
        given = answer_quantity(answer)
        if given is not None and any(f.check in _COMPUTING for f in findings):
            verified.add(given.value)
        findings += check_grounded(whole_answer, sources, verified)
    return findings


# --- INGEST-2, second round: numbers in words, places, extremes, roundings said, shapes, names, digits ---


def check_words(stem: str, answer: str) -> list[Finding]:
    """A decimal read in words: the number of the question in the answer's words, or the other way."""
    from cavat.modules.assessment.vi_words import decimal_from_words, is_number_words

    first = answer.splitlines()[0].strip().rstrip(".") if answer else ""
    numbers = [n for n in re.findall(r"\d+,\d+|\d+", stem)]
    if is_number_words(first) and "phẩy" in first.lower() and len(numbers) >= 1:
        value = decimal_from_words(first)
        target = number(numbers[-1])
        if value is not None and target is not None:
            return [Finding("WORDS", value == target, f"{numbers[-1]}: {first}")]
    spoken = re.findall(r"[“\"]?([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ\s]*phẩy[A-Za-zÀ-ỹ\s]*)[”\"]?", stem)
    for words in spoken:
        value = decimal_from_words(words.strip())
        given = answer_quantity(answer)
        if value is not None and given is not None and not given.dimension:
            return [Finding("WORDS", value == given.value, f"{words.strip()} = {_fmt(value)}")]
    return []


def check_digit_place(stem: str, answer: str, context: str = "") -> list[Finding]:
    """ "Cho số 63,248 … Chữ số 6 ở hàng …" or "Chữ số 5 trong mỗi số sau … a) 35,4": place and value.

    The number or the digit may be in the shared stem of the sub-questions (``context``).
    """
    digit = re.search(r"[Cc]hữ số\s+(\d)\b", stem) or re.search(r"[Cc]hữ số\s+(\d)\b", context)
    decimals = re.findall(r"\d+,\d+", stem) or re.findall(r"\d+,\d+", context)
    if not digit or not decimals:
        return []
    return check_place(f"Số {decimals[-1]}: chữ số {digit.group(1)}", answer)


def check_extreme(stem: str, answer: str) -> list[Finding]:
    """ "Số lớn nhất / bé nhất trong các số …": the largest or the smallest of the listed numbers."""
    lowered = stem.lower()
    largest, smallest = "lớn nhất" in lowered, "bé nhất" in lowered or "nhỏ nhất" in lowered
    if largest == smallest:
        return []
    listed = [evaluate(t.strip(" .:")) for t in _listed_numbers(stem)]
    given = answer_quantity(answer)
    if len(listed) < 2 or any(q is None for q in listed) or given is None:
        return []
    values = [q.value for q in listed if q]
    target = max(values) if largest else min(values)
    return [Finding("EXTREME", given.value == target, _fmt(target))]


def check_equal_to(stem: str, answer: str) -> list[Finding]:
    """ "Số nào dưới đây bằng 0,25?": the chosen value equals it."""
    m = re.search(rf"bằng\s+({_NUM})\s*\??", stem)
    given = answer_quantity(answer)
    if not m or given is None or given.dimension:
        return []
    target = number(m.group(1))
    return [Finding("EQUAL", target == given.value, f"= {m.group(1)}")] if target is not None else []


def check_rounding_said(stem: str, answer: str) -> list[Finding]:
    """ "Làm tròn 8,49 đến hàng đơn vị" answered "8,49 ≈ 8": the rounding of the place named."""
    place = place_named(stem)
    if place is None:
        return []
    findings = []
    for left, sign, right in relations(answer):
        if sign != "≈":
            continue
        a, b = evaluate(left), evaluate(right)
        if a is None or b is None or a.dimension != b.dimension:
            continue
        # A measure is rounded in the unit it is written in ("1,085 km ≈ 1,1 km").
        scale = UNITS[a.unit][1] if a.dimension else Fraction(1)
        expected = round_to(a.value / scale, place) * scale
        unit = f" {a.unit}" if a.dimension else ""
        findings.append(Finding("ROUNDING", expected == b.value, f"{left} ≈ {_fmt(expected / scale)}{unit}"))
    return findings


def check_shapes(stem: str, answer: str) -> list[Finding]:
    """Right triangles, right trapezoids, a house (rectangle and roof), and two shapes compared."""
    findings: list[Finding] = []
    given = answer_quantity(answer, dimension="area")
    m_ = rf"(?:{_NUM})\s*{_UNIT}|(?:{_NUM})"
    if given is not None and (m := re.search(rf"hai cạnh góc vuông\s+({m_})\s+và\s+({m_})", stem)):
        a, b = evaluate(m.group(1)), evaluate(m.group(2))
        if a and b:
            findings += _compare(a.value * b.value / 2, given, [a, b], squared=True)
    if given is not None and (
        m := re.search(
            rf"đáy lớn\s+({m_}),\s*đáy bé\s+({m_}),\s*cạnh bên vuông góc với đáy dài\s+({m_})", stem
        )
    ):
        a, b, h = (evaluate(g) for g in m.groups())
        if a and b and h:
            findings += _compare((a.value + b.value) * h.value / 2, given, [a, b, h], squared=True)
    if given is not None and (
        m := re.search(
            rf"hình chữ nhật\s+({m_})\s*[×x]\s*({m_}).*?tam giác.*?đáy\s+({m_}),\s*(?:chiều\s+)?cao\s+({m_})",
            stem,
        )
    ):
        x, y, a, h = (evaluate(g) for g in m.groups())
        if x and y and a and h:
            findings += _compare(x.value * y.value + a.value * h.value / 2, given, [x, y, a, h], squared=True)
    tri = re.search(rf"tam giác\s*\(đáy\s+({_NUM}),\s*cao\s+({_NUM})\)", stem, re.IGNORECASE)
    trap = re.search(
        rf"hình thang\s*\(đáy\s+({_NUM})\s+và\s+({_NUM}),\s*cao\s+({_NUM})\)", stem, re.IGNORECASE
    )
    if tri and trap:
        t = number(tri.group(1)) * number(tri.group(2)) / 2  # type: ignore[operator]
        z = (number(trap.group(1)) + number(trap.group(2))) * number(trap.group(3)) / 2  # type: ignore[operator]
        said = [number(n) for n in re.findall(r"\d+(?:,\d+)?", answer)]
        findings.append(Finding("AREA", t in said and z in said, f"tam giác {_fmt(t)}, hình thang {_fmt(z)}"))
        if (diff := abs(t - z)) and "lớn hơn" in answer:
            larger_said = "tam giác lớn" in " ".join(answer.split()).lower()
            findings.append(Finding("AREA", diff in said and larger_said == (t > z), f"hơn {_fmt(diff)}"))
    return findings


def check_named_measures(stem: str, answer: str) -> list[Finding]:
    """ "Hoa nhảy được 1,35 m; Lan … 1 m 4 dm" answered "Hoa 1,35 m; Lan 1,4 m": each name's measure."""
    findings = []
    for name, value in re.findall(rf"\b([A-ZĐ][a-zà-ỹ]*)\s*=?\s*({MEASURE.pattern})", answer):
        found = re.search(rf"\b{name}\b[^.;\d]{{0,40}}?({MEASURE.pattern})", stem)
        a, b = evaluate(value), evaluate(found.group(1)) if found else None
        if a is None or b is None or not a.dimension or not b.dimension:
            continue
        same = _same(a, b)
        if same is not None:
            findings.append(Finding("CONVERSION", same, f"{name}: {found.group(1)} = {value}"))  # type: ignore[union-attr]
    return findings


def check_digit_x(stem: str, answer: str) -> list[Finding]:
    """ "Tìm chữ số x để 7,1 < 7,x2 < 7,35" (or the largest x with 4,x6 < 4,75): the digits that fit."""
    m = re.search(rf"(?:({_NUM})\s*<\s*)?(\d*,?\d*)x(\d*)\s*<\s*({_NUM})", stem)
    if not m or "chữ số x" not in stem:
        return []
    low = number(m.group(1)) if m.group(1) else None
    high = number(m.group(4))
    head, tail = m.group(2), m.group(3)
    fits = []
    for d in range(10):
        value = number(f"{head}{d}{tail}")
        if value is None or high is None:
            continue
        if value < high and (low is None or value > low):
            fits.append(d)
    lowered = stem.lower()
    expected = (
        [max(fits)]
        if "lớn nhất" in lowered and fits
        else [min(fits)]
        if "bé nhất" in lowered and fits
        else fits
    )
    said = answer.splitlines()[0].split("(")[0] if answer else ""
    given = sorted({int(d) for d in re.findall(r"(?<!\d)(?<!\d,)(\d)(?!\d|,\d)", said.split("=", 1)[-1])})
    return [Finding("DIGIT", given == expected, f"x = {', '.join(map(str, expected))}")]


def _values(text: str) -> set[Fraction]:
    """Every value written in a text: numbers as they are, measures also in their base unit."""
    out: set[Fraction] = set()
    for m in MEASURE.finditer(_plain(text)):
        q = evaluate(m.group(0))
        if q is None:
            continue
        out.add(q.value)
        if q.dimension:  # "980 m" is also 0,98 (km), 9800 (dm)…: the same length in each unit
            out |= {q.value / factor for dim, factor in UNITS.values() if dim == q.dimension}
        for n in re.findall(rf"{_MIXED}|{_NUM}", m.group(0)):
            if (v := number(n)) is not None:
                out.add(v)
    return out


def explanation_of(answer: str) -> str:
    """What explains an answer rather than gives it: the lines after the first, and parentheses."""
    first, _, rest = answer.partition("\n")
    inside = " ; ".join(re.findall(r"\(([^()]*)\)", first))
    return "\n".join(t for t in (inside, rest) if t.strip())


def check_grounded(answer: str, sources: str, verified: set[Fraction]) -> list[Finding]:
    """Each number of two or more digits in an answer and its explanation comes from the question (by
    value, units converted), is what the other checks computed (``verified``), a side of an equality of the
    answer that holds (a conversion, a computation), or the question's "x" with a digit put in. A digit
    changed by a misreading or a typo makes a number that is none of these; so may a sound intermediate
    step ("tô 3 cột, 30 ô"), which is why this only asks the teacher to look (REVIEW)."""
    explanation = answer
    allowed = _values(sources) | verified
    for left, sign, right in relations(_plain(answer)):
        if sign != "=":  # a comparison makes no new number ("12,01 < 12,7" is true and still made up)
            continue
        holds = check_relations(f"{left} {sign} {right}")
        if holds and all(f.ok for f in holds):
            allowed |= _values(left) | _values(right)
    for pattern in re.finditer(r"(\d+,\d*)x(\d*)", sources):  # "5,x3" with each digit
        allowed |= {
            v for d in range(10) if (v := number(f"{pattern.group(1)}{d}{pattern.group(2)}")) is not None
        }
    stray = []
    for m in MEASURE.finditer(explanation):
        token = m.group(0)
        if len(re.sub(r"\D", "", token)) < 2:
            continue
        values = _values(token)
        if values and not values & allowed:
            stray.append(token.strip())
    if not stray:
        return []
    return [Finding("GROUNDED", False, "số không có trong đề: " + "; ".join(dict.fromkeys(stray)))]
