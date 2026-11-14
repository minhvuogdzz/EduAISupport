"""English text shared by the English modules (ENG-4, ADR-063): the answer normalization DI-110 and the
irregular past forms a primary class meets.

- ``IRREGULAR_PAST`` was the table of the English RAG analyzer (ENG-2, ``rag/analyzers.py``); it moved
  here unchanged so that the RAG and the deterministic checker read the same verbs. The RAG output is the
  same byte for byte (``tests/golden/rag-math-before-eng2.json``, ``test_rag_subjects.py``).
- ``normalize_answer`` is the normalization ``en-vi/1`` of the checker (DI-110, DI-128): only the fixed
  table of contractions of DI-110 is written out. The RAG analyzer of the same family expands more forms
  ("can't", "'ll", the possessive "'s"), because retrieval wants recall; grading may only accept the
  variants the owner approved (english-module-rules N4), so the two stay apart.

``core/vi_text`` is not touched (english-module-rules G4).
"""

from __future__ import annotations

import re
import unicodedata

APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "`": "'", "´": "'"})

# The irregular past forms of the verbs a primary class meets (Global Success 5, a unit about what a family
# did: "Did you go…? We went…"). Not exhaustive: a form not listed is a word of its own.
IRREGULAR_PAST = {
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

# DI-110: the only contractions the checker writes out. Any other apostrophe joins its word ("don't" is
# "dont"), so that no variant outside the table becomes acceptable by accident (DI-128).
ANSWER_CONTRACTIONS: tuple[tuple[str, str], ...] = (
    ("didn't", "did not"),
    ("i'm", "i am"),
    ("we're", "we are"),
    ("it's", "it is"),
    ("what's", "what is"),
    ("isn't", "is not"),
    ("wasn't", "was not"),
    ("weren't", "were not"),
)
_CONTRACTION_RES = tuple(
    (re.compile(rf"(?<![\w']){re.escape(short)}(?![\w'])"), full) for short, full in ANSWER_CONTRACTIONS
)
_NOT_WORD = re.compile(r"[^\w\s]|_")
_SENTENCE_END = re.compile(r"[.!?;:\n]+")


def normalize_answer(text: str) -> str:
    """DI-110 ``en-vi/1``: lowercase NFC, the contractions of the table written out, other apostrophes
    dropped inside the word, punctuation dropped, spaces collapsed. Vietnamese letters stay as typed."""
    text = unicodedata.normalize("NFC", text).translate(APOSTROPHES).lower()
    for pattern, full in _CONTRACTION_RES:
        text = pattern.sub(full, text)
    text = text.replace("'", "")
    return " ".join(_NOT_WORD.sub(" ", text).split())


def sentences(text: str) -> list[str]:
    """The normalized sentences of ``text``, split where it has an end mark (a voice transcript may have
    none: then it is one sentence)."""
    return [s for part in _SENTENCE_END.split(text) if (s := normalize_answer(part))]


def contains_words(text: str, phrase: str) -> bool:
    """``phrase`` occurs in ``text`` on word boundaries (both already normalized): "ate seafood" is in
    "we ate seafood", not in "we ate seafoods" nor in "late seafood"."""
    return bool(phrase) and f" {phrase} " in f" {text} "
