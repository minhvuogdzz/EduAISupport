"""The words the tutor's voice reads (ADR-030): a written message of the tutor, made readable aloud.

The Grade 5 Math the tutor writes is full of numbers and signs ("3,05 < 3,5", "S = a × h : 2", "12 cm²").
A speech engine reads them by guess, so they are written out here the way a Vietnamese teacher says them
(vi-VN, decimal comma, rule 2): "ba phẩy không năm bé hơn ba phẩy năm". Deterministic, no model.
"""

from __future__ import annotations

import re

MAX_SPEECH_CHARS = 1200

_DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")
_GROUPS = ("", "nghìn", "triệu", "tỷ")
_UNITS = {
    "mm²": "mi-li-mét vuông",
    "cm²": "xăng-ti-mét vuông",
    "dm²": "đề-xi-mét vuông",
    "km²": "ki-lô-mét vuông",
    "m²": "mét vuông",
    "mm": "mi-li-mét",
    "cm": "xăng-ti-mét",
    "dm": "đề-xi-mét",
    "km": "ki-lô-mét",
    "kg": "ki-lô-gam",
    "ha": "héc-ta",
    "m": "mét",
    "g": "gam",
}
_SIGNS = {"<": "bé hơn", ">": "lớn hơn", "=": "bằng", "≤": "bé hơn hoặc bằng", "≥": "lớn hơn hoặc bằng"}
_OPERATORS = {"×": "nhân", "x": "nhân", "+": "cộng", "-": "trừ", "–": "trừ", ":": "chia", "÷": "chia"}
_NUMBER = r"\d+(?:,\d+)?"


def _three(n: int, full: bool) -> str:
    """0..999; ``full`` reads "không trăm" (a group after a bigger one)."""
    hundreds, tens, units = n // 100, n // 10 % 10, n % 10
    words: list[str] = []
    if hundreds or full:
        words += [_DIGITS[hundreds], "trăm"]
    if tens == 0:
        if units and words:
            words.append("linh")
    elif tens == 1:
        words.append("mười")
    else:
        words += [_DIGITS[tens], "mươi"]
    if units:
        if units == 1 and tens >= 2:
            words.append("mốt")
        elif units == 5 and tens >= 1:
            words.append("lăm")
        else:
            words.append(_DIGITS[units])
    return " ".join(words)


def read_integer(digits: str) -> str:
    """ "2025" -> "hai nghìn không trăm hai mươi lăm"; leading zeros are read one by one ("05")."""
    zeros = len(digits) - len(digits.lstrip("0"))
    rest = digits[zeros:]
    lead = ["không"] * (zeros if rest else max(zeros, 1))
    if not rest:
        return " ".join(lead)
    n = int(rest)
    if n >= 10**12:
        return " ".join([*lead, *(_DIGITS[int(d)] for d in rest)])
    groups, k = [], 0
    while n:
        groups.append((n % 1000, k))
        n, k = n // 1000, k + 1
    words: list[str] = []
    for i, (value, k) in enumerate(reversed(groups)):
        if value == 0:
            continue
        words += [_three(value, full=i > 0), _GROUPS[k]]
    return " ".join([*lead, *(w for w in words if w)])


def read_number(text: str) -> str:
    """ "3,05" -> "ba phẩy không năm" (vi-VN: the comma is the decimal mark)."""
    whole, _, frac = text.partition(",")
    spoken = read_integer(whole)
    return f"{spoken} phẩy {read_integer(frac)}" if frac else spoken


def speech_text(text: str) -> str:
    """The message as it is read aloud."""
    s = re.sub(r"[*_#`«»\"“”]", "", text)
    s = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", s)  # emoji
    s = re.sub(r"\s*\n+\s*", ". ", s)
    s = s.replace("…", ".").replace("...", ".")
    # vi-VN thousands: "1.015" or "1 015" is one number
    s = re.sub(r"\b\d{1,3}(?:[. ]\d{3})+(?![\d,])", lambda m: re.sub(r"[. ]", "", m[0]), s)
    # a fraction "3/10" -> "ba phần mười"
    s = re.sub(r"(\d+)\s*/\s*(\d+)", lambda m: f"{read_integer(m[1])} phần {read_integer(m[2])}", s)
    # units after a number
    unit = "|".join(re.escape(u) for u in sorted(_UNITS, key=len, reverse=True))
    s = re.sub(rf"({_NUMBER})\s*({unit})(?![\wÀ-ỹ])", lambda m: f"{m[1]} {_UNITS[m[2]]}", s)
    # an operator between two terms of a calculation or a formula ("a × h : 2"); ":" only with spaces
    # around it, as division is written in Grade 5 ("12 : 4"), so a time "8:30" is not "chia"
    term = rf"(?:{_NUMBER}|\b[a-zA-Z]\b)"
    s = re.sub(
        rf"(?<=[\w)])\s*([×+÷–]|(?<=\s)[-x:](?=\s))\s*(?={term}|\()", lambda m: f" {_OPERATORS[m[1]]} ", s
    )
    for sign, words in _SIGNS.items():
        s = s.replace(sign, f" {words} ")
    s = re.sub(_NUMBER, lambda m: read_number(m[0]), s)
    s = re.sub(r"\s+([,.?!])", r"\1", re.sub(r"\s+", " ", s)).strip()
    return s[:MAX_SPEECH_CHARS]
