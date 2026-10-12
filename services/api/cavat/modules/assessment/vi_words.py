"""Numbers read in Vietnamese words: "mười bốn phẩy hai trăm linh năm" is 14,205 (INGEST-2).

The decimals chapter asks to read and write decimals in words, so the answer key of those questions is in
words. The part after "phẩy" is read as a whole number with its leading zeros said: "không phẩy không
tám" is 0,08, "ba phẩy không năm" is 3,05.
"""

from __future__ import annotations

import re
from fractions import Fraction

_DIGITS = {
    "không": 0,
    "một": 1,
    "mốt": 1,
    "hai": 2,
    "ba": 3,
    "bốn": 4,
    "tư": 4,
    "năm": 5,
    "lăm": 5,
    "nhăm": 5,
    "sáu": 6,
    "bảy": 7,
    "tám": 8,
    "chín": 9,
}
_WORDS = set(_DIGITS) | {"mười", "mươi", "trăm", "linh", "lẻ", "nghìn", "ngàn", "phẩy"}


def is_number_words(text: str) -> bool:
    """Only number words (and "phẩy"), at least two of them or one digit word."""
    words = _tokens(text)
    return bool(words) and all(w in _WORDS for w in words)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", text.lower())


def whole_number(words: list[str]) -> int | None:
    """A whole number below a million from its words, None when the words do not make one."""
    if not words:
        return None
    if "nghìn" in words or "ngàn" in words:
        i = max(i for i, w in enumerate(words) if w in ("nghìn", "ngàn"))
        high = whole_number(words[:i])
        low = whole_number(words[i + 1 :]) if words[i + 1 :] else 0
        if high is None or low is None or low >= 1000:
            return None
        return high * 1000 + low
    return _below_thousand(words)


def _below_thousand(words: list[str]) -> int | None:
    value = 0
    rest = list(words)
    if "trăm" in rest:
        i = rest.index("trăm")
        if i != 1 or rest[0] not in _DIGITS:
            return None
        value += _DIGITS[rest[0]] * 100
        rest = rest[2:]
        if rest[:1] and rest[0] in ("linh", "lẻ"):
            rest = rest[1:]
            if len(rest) != 1 or rest[0] not in _DIGITS:
                return None
            return value + _DIGITS[rest[0]]
    if not rest:
        return value
    if rest[0] == "mười":
        tens, rest = 10, rest[1:]
    elif len(rest) >= 2 and rest[1] == "mươi" and rest[0] in _DIGITS:
        tens, rest = _DIGITS[rest[0]] * 10, rest[2:]
    else:
        tens = 0
    if tens:
        if not rest:
            return value + tens
        if len(rest) == 1 and rest[0] in _DIGITS and rest[0] != "không":
            return value + tens + _DIGITS[rest[0]]
        return None
    if len(rest) == 1 and rest[0] in _DIGITS:
        return value + _DIGITS[rest[0]]
    return None


def decimal_from_words(text: str) -> Fraction | None:
    """The value of a decimal read in words ("hai phẩy bảy mươi lăm" is 2,75), None if it is not one."""
    words = _tokens(text)
    if not words or not all(w in _WORDS for w in words):
        return None
    if "phẩy" not in words:
        n = whole_number(words)
        return Fraction(n) if n is not None else None
    i = words.index("phẩy")
    whole = whole_number(words[:i])
    frac_words = words[i + 1 :]
    zeros = 0
    while zeros < len(frac_words) - 1 and frac_words[zeros] == "không":
        zeros += 1
    rest = whole_number(frac_words[zeros:])
    if whole is None or rest is None:
        return None
    digits = "0" * zeros + str(rest)
    return Fraction(whole) + Fraction(int(digits), 10 ** len(digits))
