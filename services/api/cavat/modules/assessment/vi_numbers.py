"""Read and write numbers the Vietnamese way (decimal comma, dot as thousands separator).

All values are exact (fractions.Fraction) so comparison never suffers from float error. The module also
holds the text normalization the checkers share: `fold`, `normalize_text` and `tolerant_pattern`.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

# A number token: digits with optional separators, an optional "/denominator" and an optional "%".
_NUMBER_RE = re.compile(r"(?<![\d/])(\d+(?:[.,]\d+)*)(?:\s*/\s*(\d+))?(\s*%)?")
# An integer written with dots between thousands groups: "1.234", "12.500.000".
_GROUPED_RE = re.compile(r"[1-9]\d{0,2}(?:\.\d{3})+")


@dataclass(frozen=True)
class ParsedNumber:
    text: str  # the token as written
    value: Fraction
    form: str  # integer | decimal | fraction | percent
    int_part: str = ""  # digits before the decimal separator (integer/decimal forms)
    frac_part: str = ""  # digits after the decimal separator, trailing zeros kept
    ambiguous_separator: bool = False  # e.g. "1.250": thousands or decimal?
    start: int = 0
    end: int = 0


def fold(text: str) -> str:
    """Lowercase, strip Vietnamese diacritics (đ→d) and collapse whitespace, for tolerant matching."""
    lowered = unicodedata.normalize("NFC", text).lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip()


def normalize_text(text: str) -> str:
    """NFC, lowercase and single spaces. Unlike `fold` it keeps diacritics, so "bằng" and "bảng" differ."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text).lower()).strip()


def _lighter_forms(ch: str) -> str:
    """`ch` and every letter left when some of its diacritics are dropped: "ằ" -> "aàăằ"."""
    if ch == "đ":
        return "dđ"
    base, *marks = unicodedata.normalize("NFD", ch)
    forms = {
        unicodedata.normalize("NFC", base + "".join(kept))
        for n in range(len(marks) + 1)
        for kept in combinations(marks, n)
    }
    return "".join(sorted(forms))


def tolerant_pattern(phrase: str) -> str:
    """Regex for `phrase` as whole words in `normalize_text` output, allowing left-out diacritics.

    Children often type without diacritics, but a mark they did type must belong to the word:
    "bằng" matches "bằng", "băng" and "bang", not "bảng" (table); "đúng" matches "dung", not "dùng" (use).
    """
    phrase = normalize_text(phrase)
    parts = []
    for ch in phrase:
        if ch == " ":
            parts.append(r"\s+")
        elif ch.isalpha():
            forms = _lighter_forms(ch)
            parts.append(forms if len(forms) == 1 else f"[{forms}]")
        else:
            parts.append(re.escape(ch))
    pattern = "".join(parts)
    if phrase[:1].isalnum():
        pattern = r"(?<!\w)" + pattern
    if phrase[-1:].isalnum():
        pattern += r"(?!\w)"
    return pattern


def phrase_regex(phrases: Iterable[str]) -> re.Pattern[str]:
    """One regex for several phrases (see `tolerant_pattern`); group i + 1 is the i-th phrase.

    Alternatives are tried in order, so list a phrase before a shorter one it starts with
    ("bằng nhau" before "bằng").
    """
    return re.compile("|".join(f"({tolerant_pattern(p)})" for p in phrases))


def _parse_plain(s: str) -> tuple[Fraction, str, str, bool] | None:
    commas, dots = s.count(","), s.count(".")
    ambiguous = False
    if commas > 1:
        return None
    if commas == 1:
        int_s, frac_s = s.split(",")
        if "." in int_s and not _GROUPED_RE.fullmatch(int_s):
            return None
        int_s = int_s.replace(".", "")
        if "." in frac_s:
            return None
    elif dots == 1:
        # Children often type the English decimal point. Three digits after it could also be
        # a Vietnamese thousands group ("1.250"), so flag it for confirmation. "0.250" cannot
        # be a thousands group, so it is read as a decimal without asking.
        int_s, frac_s = s.split(".")
        ambiguous = _GROUPED_RE.fullmatch(s) is not None
    elif dots > 1:
        if not _GROUPED_RE.fullmatch(s):
            return None
        int_s, frac_s = s.replace(".", ""), ""
    else:
        int_s, frac_s = s, ""
    if not int_s.isdigit() or (frac_s and not frac_s.isdigit()):
        return None
    value = Fraction(int(int_s))
    if frac_s:
        value += Fraction(int(frac_s), 10 ** len(frac_s))
    return value, int_s, frac_s, ambiguous


def _from_match(m: re.Match[str]) -> ParsedNumber | None:
    body, denom, percent = m.group(1), m.group(2), m.group(3)
    parsed = _parse_plain(body)
    if parsed is None:
        return None
    value, int_s, frac_s, ambiguous = parsed
    text = m.group(0).strip()
    if denom is not None:
        if frac_s or int(denom) == 0:
            return None
        return ParsedNumber(text, Fraction(int(int_s), int(denom)), "fraction", start=m.start(), end=m.end())
    if percent:
        return ParsedNumber(
            text, value / 100, "percent", int_s, frac_s, ambiguous, start=m.start(), end=m.end()
        )
    form = "decimal" if frac_s else "integer"
    return ParsedNumber(text, value, form, int_s, frac_s, ambiguous, start=m.start(), end=m.end())


def extract_numbers(text: str) -> list[ParsedNumber]:
    """All numbers in `text`, in reading order, with their character spans."""
    out: list[ParsedNumber] = []
    for m in _NUMBER_RE.finditer(text):
        n = _from_match(m)
        if n is not None:
            out.append(n)
    return out


def parse_number(text: str) -> ParsedNumber | None:
    """The first number in `text`, or None."""
    nums = extract_numbers(text)
    return nums[0] if nums else None


def parse_literal(text: str) -> ParsedNumber:
    """Parse a number written in lesson content (always the Vietnamese form). Raises on bad input."""
    n = parse_number(text)
    if n is None or n.text != text.strip():
        raise ValueError(f"not a single number: {text!r}")
    return n


def format_vi(value: Fraction) -> str:
    """Format an exact value the Vietnamese way: 1/4 -> '0,25'; 1/3 -> '1/3'.

    No thousands separators, so the output always reads back to the same value with `parse_literal`.
    """
    if value.denominator == 1:
        return str(value.numerator)
    d, twos, fives = value.denominator, 0, 0
    while d % 2 == 0:
        d //= 2
        twos += 1
    while d % 5 == 0:
        d //= 5
        fives += 1
    if d != 1:
        return f"{value.numerator}/{value.denominator}"
    places = max(twos, fives)
    scaled = int(value * 10**places)
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).rjust(places + 1, "0")
    return f"{sign}{digits[:-places]},{digits[-places:]}"
