"""Read and write numbers the Vietnamese way (decimal comma, dot as thousands separator).

All values are exact (fractions.Fraction) so comparison never suffers from float error.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from fractions import Fraction

# A number token: digits with optional separators, an optional "/denominator" and an optional "%".
_NUMBER_RE = re.compile(r"(?<![\d/])(\d+(?:[.,]\d+)*)(?:\s*/\s*(\d+))?(\s*%)?")


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


def _parse_plain(s: str) -> tuple[Fraction, str, str, bool] | None:
    commas, dots = s.count(","), s.count(".")
    ambiguous = False
    if commas > 1:
        return None
    if commas == 1:
        int_s, frac_s = s.split(",")
        if "." in int_s and not re.fullmatch(r"\d{1,3}(\.\d{3})+", int_s):
            return None
        int_s = int_s.replace(".", "")
        if "." in frac_s:
            return None
    elif dots == 1:
        # Children often type the English decimal point. Three digits after it could also be
        # a Vietnamese thousands group ("1.250"), so flag it for confirmation.
        int_s, frac_s = s.split(".")
        ambiguous = len(frac_s) == 3
    elif dots > 1:
        if not re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
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
    """Format an exact value the Vietnamese way: 1/4 -> '0,25'; 1/3 -> '1/3'."""
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
