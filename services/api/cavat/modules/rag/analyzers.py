"""Text analyzers of the Hybrid RAG, one per subject (ENG-2, ADR-061, DI-121).

An analyzer turns a text into the tokens BM25 counts (``tokens``, on the text with diacritics and on its
folded form) and into the content words that coverage weighs (``content_words``). BM25 itself
(``bm25.py``) only counts: which words a text is made of is the subject's business.

- **Mathematics** (``MATH``) is the analyzer the RAG has always used, moved here unchanged: Vietnamese
  syllables and adjacent pairs, ``core/vi_text``, the decimal dot read as the Vietnamese comma, and the
  filler words of a child's question. Its output is byte for byte what ``bm25.tokens`` gave before ENG-2.
- **English** (``ENGLISH``): lowercase, punctuation dropped, contractions written out ("I'm" = "I am",
  "didn't" = "did not", "father's" = "father"), then the same two forms and pairs, so that a question in
  Vietnamese with English words in it ("seashells nghĩa là gì hả cô") still matches: the Vietnamese words
  fold, the English ones stay as they are. A verb in the past meets its base form ("collected" and
  "collect", "went" and "go", "did" and "do"): every English word of four letters or more, and every
  irregular past form, also gives its lemma as a token (``lemma``). ``core/vi_text`` is used, not changed
  (english-module-rules G4).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from cavat.core.subjects import check_subject
from cavat.core.vi_text import fold, normalize


class Analyzer(Protocol):
    name: str

    def tokens(self, text: str, folded: bool) -> list[str]: ...

    def content_words(self, text: str) -> list[str]: ...


# --- Mathematics (unchanged from bm25.py before ENG-2) ---------------------------------------------

# A dot used as the decimal mark (0.25, 3.5) becomes the Vietnamese comma; a thousands dot (1.000) stays.
_DECIMAL_DOT = re.compile(r"(?<![\d.])0\.(?=\d)|(?<=\d)\.(?=\d{1,2}(?![\d.]))")


# Words of a child's question that carry no content (folded): addressing, particles, question words. Not
# "biet" or "hieu": folded, "biết"/"hiểu" are "biệt" (đặc biệt) and "hiệu" (the difference of a subtraction).
FILLER = frozenset(
    "co oi a ah u ui con em minh ban hoi cho voi the nao sao gi la nhi vay day ma thi va cua nhe khong "
    "duoc chua roi ha ho giup tai vi lam cai nay kia nhu bao may nghia".split()
)
_NUMBER = re.compile(r"^[\d.,/]+$")


def content_words(text: str) -> list[str]:
    """Syllables of ``text`` (as typed, normalized) that carry content: no filler word, no number."""
    norm = normalize(_DECIMAL_DOT.sub(lambda m: m.group(0).replace(".", ","), text))
    return [w for w in dict.fromkeys(norm.split()) if fold(w) not in FILLER and not _NUMBER.match(w)]


def tokens(text: str, folded: bool) -> list[str]:
    """Syllables and adjacent pairs of the normalized (or folded) text, filler words left out.

    A filler would otherwise make phrases out of grammar: "phần nguyên là gì" would match "phần nguyên là
    7" through the pair "nguyên là" better than the definition "bên trái dấu phẩy là phần nguyên".
    """
    norm = normalize(_DECIMAL_DOT.sub(lambda m: m.group(0).replace(".", ","), text))
    words = (fold(norm) if folded else norm).split()
    keep = [fold(w) not in FILLER for w in words]
    pairs = [
        f"{a}_{b}" for i, (a, b) in enumerate(zip(words, words[1:], strict=False)) if keep[i] and keep[i + 1]
    ]
    return [w for w, k in zip(words, keep, strict=True) if k] + pairs


@dataclass(frozen=True)
class _MathAnalyzer:
    name: str = "vi-math/1"

    def tokens(self, text: str, folded: bool) -> list[str]:
        return tokens(text, folded)

    def content_words(self, text: str) -> list[str]:
        return content_words(text)


MATH: Analyzer = _MathAnalyzer()


# --- English -----------------------------------------------------------------------------------------

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})
# Written out before the punctuation goes: "I'm" would otherwise be the two words "i" and "m".
_CONTRACTIONS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), repl)
    for pattern, repl in (
        (r"\bwon't\b", "will not"),
        (r"\bcan't\b", "can not"),
        (r"\bshan't\b", "shall not"),
        (r"\bcannot\b", "can not"),
        (r"\blet's\b", "let us"),
        (r"n't\b", " not"),
        (r"'m\b", " am"),
        (r"'re\b", " are"),
        (r"'ve\b", " have"),
        (r"'ll\b", " will"),
        (r"'d\b", " would"),
        # "'s" after a pronoun or a question word is "is" ("he's", "what's"); after a noun it is the
        # possessive ("my father's car"): the noun alone carries the meaning.
        (r"\b(he|she|it|that|what|who|where|there|here|this)'s\b", r"\1 is"),
        (r"'s\b", ""),
    )
)
# Folded Vietnamese fillers that are also English words of a primary class: typed without diacritics they
# are English ("the", "a", "may"); with diacritics ("thế", "ạ", "mấy") they are the Vietnamese fillers.
_ENGLISH_HOMOGRAPHS = frozenset({"a", "the", "may"})


# The irregular past forms of the verbs a primary class meets (Global Success 5, a unit about what a family
# did: "Did you go…? We went…"). Not exhaustive: a form not listed is a word of its own.
_IRREGULAR_PAST = {
    "did": "do", "went": "go", "had": "have", "was": "be", "were": "be", "made": "make", "saw": "see",
    "ate": "eat", "came": "come", "took": "take", "got": "get", "gave": "give", "bought": "buy",
    "swam": "swim", "ran": "run", "flew": "fly", "wrote": "write", "built": "build", "caught": "catch",
    "drank": "drink", "found": "find", "left": "leave", "met": "meet", "sang": "sing", "sat": "sit",
    "slept": "sleep", "spent": "spend", "taught": "teach", "told": "tell", "thought": "think",
    "won": "win", "wore": "wear", "rode": "ride", "drew": "draw", "grew": "grow", "knew": "know",
    "sent": "send", "stood": "stand", "brought": "bring", "began": "begin", "drove": "drive",
    "felt": "feel", "heard": "hear", "kept": "keep", "lost": "lose", "paid": "pay", "said": "say",
    "sold": "sell", "spoke": "speak", "threw": "throw", "understood": "understand", "woke": "wake",
}  # fmt: skip
_DOUBLED = re.compile(r"([bgmnprt])\1$")  # "stopped" -> "stopp" -> "stop"; not "called", "added"


def lemma(word: str) -> str:
    """The form an English word is matched on besides itself: the base of a past form, without a final
    "e", so that "baked" and "bake" meet ("bak"), as do "visited" and "visit", "studied" and "study",
    "stopped" and "stop", "went" and "go". Words shorter than four letters, and words with Vietnamese
    letters, are their own lemma."""
    if word in _IRREGULAR_PAST:
        word = _IRREGULAR_PAST[word]
    elif len(word) >= 5 and word.endswith("ied"):
        word = word[:-3] + "y"
    elif len(word) >= 6 and word.endswith("eed"):  # "agreed" -> "agree"; "need", "feed" stay
        word = word[:-1]
    elif len(word) >= 5 and word.endswith("ed"):
        word = _DOUBLED.sub(r"\1", word[:-2])
    if len(word) >= 4 and word.isascii() and word.isalpha() and word.endswith("e"):
        word = word[:-1]
    return word


def english_normalize(text: str) -> str:
    """Lowercase NFC, contractions written out, punctuation dropped (``core/vi_text.normalize``)."""
    text = unicodedata.normalize("NFC", text).lower().translate(_APOSTROPHES)
    for pattern, repl in _CONTRACTIONS:
        text = pattern.sub(repl, text)
    return normalize(text)


def _filler(word: str) -> bool:
    folded = fold(word)
    return folded in FILLER and (folded != word or word not in _ENGLISH_HOMOGRAPHS)


@dataclass(frozen=True)
class _EnglishAnalyzer:
    name: str = "en-vi/1"

    def tokens(self, text: str, folded: bool) -> list[str]:
        norm = english_normalize(text)
        words = (fold(norm) if folded else norm).split()
        # The filler test reads each word as typed: folded, "thế" and "the" would be the same word.
        keep = [not _filler(w) for w in norm.split()]
        pairs = [
            f"{a}_{b}"
            for i, (a, b) in enumerate(zip(words, words[1:], strict=False))
            if keep[i] and keep[i + 1]
        ]
        kept = [w for w, k in zip(words, keep, strict=True) if k]
        lemmas = [base for w in kept if (base := lemma(w)) != w]  # "collected" also counts as "collect"
        return kept + lemmas + pairs

    def content_words(self, text: str) -> list[str]:
        """The question's content words on their lemma, which every text of the index holds as a token."""
        words = english_normalize(text).split()
        return list(dict.fromkeys(lemma(w) for w in words if not _filler(w) and not _NUMBER.match(w)))


ENGLISH: Analyzer = _EnglishAnalyzer()

ANALYZERS: dict[str, Analyzer] = {"math": MATH, "english": ENGLISH}


def analyzer_for(subject: str) -> Analyzer:
    """The analyzer of a subject; an unknown or missing subject is an error (no fallback)."""
    return ANALYZERS[check_subject(subject)]
