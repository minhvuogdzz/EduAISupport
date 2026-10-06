"""Vietnamese text normalization shared by the retell rubric (M1-3) and the Hybrid RAG indexes (M1-5).

Students often type without diacritics ("phan nguyen"), so matching is done on two forms: the normalized
text (lowercase NFC, punctuation removed) and its folded form (diacritics removed, đ -> d). Number
punctuation is kept: a comma, dot or slash between two digits stays (0,25 · 1.000 · 7/100).
"""

from __future__ import annotations

import re
import unicodedata

# Any symbol that is not part of a word, and , . / unless they sit between two digits.
_PUNCT = re.compile(r"[^\w\s,./]|_|(?<!\d)[,./]|[,./](?!\d)")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    return " ".join(_PUNCT.sub(" ", text).split())


def fold(text: str) -> str:
    """Remove diacritics: "phần nguyên" -> "phan nguyen". Expects normalized (lowercase) text."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return unicodedata.normalize("NFC", "".join(c for c in decomposed if unicodedata.category(c) != "Mn"))


def contains_phrase(text: str, phrase: str) -> bool:
    """Whole-word match of ``phrase`` in ``text``, with or without diacritics on either side."""
    t, p = normalize(text), normalize(phrase)
    if not p:
        return False
    return f" {p} " in f" {t} " or f" {fold(p)} " in f" {fold(t)} "
