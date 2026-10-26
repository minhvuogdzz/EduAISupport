"""The conductor: the first reader of every message of the child, and the guard against a stuck tutor.

The owner asked for a "main agent" that keeps the conversation in hand when a child types like a child:
teen code ("ko bít lm j"), stretched words ("đúnggggg"), emoji, a long paragraph, or a heap of keywords
("phân số thập phân mẫu số tử số hàng phần mười") with no question and no answer in it. The loop's readers
(the checker, the intent lists of ADR-019, the context reader of CTX-1) each read one kind of message well;
the conductor sits in front of them and behind them:

- **before** the loop reads a message, it cleans the text the loop will grade (``clean``): emoji and
  decoration out, stretched letters back to one, "o,5" written with the letter o read as 0,5, a long
  paragraph cut to its end, where a child puts the answer. Teen code is read by the intent lists
  (``student_intent``), never rewritten in an answer: "k" may be "không" or the unit of a quantity.
- **after** the loop answered, it checks the tutor is not saying again what it said a moment ago on the
  same question (``repeats``): a child who does not understand the redirect gets the redirect again, and
  again. Then the next hint of the item is given at once (``UNSTICK``), as if the child had asked for it.

Everything is deterministic and recorded (``CONTEXT_ROUTED``): the text as typed, the text the loop read,
what was found and whether the tutor was unstuck. A replay reads the loop's own events and never runs the
conductor again (CLAUDE.md rule 3). The conductor decides no move: the item policy picks the hint (rule 1).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from cavat.modules.assessment.student_intent import expand_short_forms, keyword_dump
from cavat.modules.assessment.vi_numbers import normalize_text

# 0.2.0: REFORM-5, a message that is one letter typed over ("kk", "kkk", "tt") is kept, not shrunk to "k" (=
# không)
CONDUCTOR_VERSION = "conductor/0.2.0"
MAX_CHARS = 300  # a longer message keeps its end: a child writes the answer last
_STRETCH_RE = re.compile(r"([^\W\d_])\1{2,}")  # three or more of the same letter: "đúnggg"
_ONE_LETTER_RE = re.compile(r"([^\W\d_])\1+")  # the whole message: "kk", "kkk", "tttt"
MASH_KEEPS = 3  # such a message keeps this many letters ("kkkkkkkk" -> "kkk")
_PUNCT_RUN_RE = re.compile(r"([!?.…,])\1{2,}")
_O_AS_ZERO_RE = re.compile(r"(?<![\w])[oO](?=[,.]\d)")  # "o,5" typed with the letter o
_SPACES_RE = re.compile(r"[ \t]+")


def _is_decoration(ch: str) -> bool:
    """Emoji and pictographs; math signs (< > = × : ² ³ /) and letters stay."""
    if ch in "<>=×:²³/+-−%.,;!?()":
        return False
    cat = unicodedata.category(ch)
    return cat in ("So", "Sk", "Cs", "Co") or ch in "‍️"


@dataclass(frozen=True)
class Cleaned:
    raw: str
    text: str
    signals: tuple[str, ...] = field(default_factory=tuple)


def clean(raw: str) -> Cleaned:
    """The text the loop reads, and what was changed (signals for the teacher's transcript)."""
    signals: list[str] = []
    text = unicodedata.normalize("NFC", raw)
    stripped = "".join(ch for ch in text if not _is_decoration(ch))
    if stripped != text:
        signals.append("EMOJI")
        text = stripped
    letters = re.sub(r"[\W_]+", "", text)
    if _ONE_LETTER_RE.fullmatch(letters):
        # REFORM-5: laughter or a key held down, not a word stretched. Shrunk to one letter it would read "k",
        # which is "không": the loop asks what the child meant instead (``student_intent.is_keyboard_mash``).
        shrunk = letters[:MASH_KEEPS]
    else:
        shrunk = _STRETCH_RE.sub(r"\1", text)
    if shrunk != text:
        signals.append("STRETCHED")
        text = shrunk
    text = _PUNCT_RUN_RE.sub(r"\1", text)
    zero = _O_AS_ZERO_RE.sub("0", text)
    if zero != text:
        signals.append("O_AS_ZERO")
        text = zero
    text = _SPACES_RE.sub(" ", text).strip()
    if len(text) > MAX_CHARS:
        signals.append("LONG")
        text = "…" + text[-MAX_CHARS:].split(" ", 1)[-1]
    if expand_short_forms(text) != normalize_text(text):
        signals.append("TEENCODE")
    if keyword_dump(text):
        signals.append("KEYWORD_DUMP")
    return Cleaned(raw, text or raw.strip(), tuple(signals))


def repeats(new: Iterable[str], recent: Iterable[str]) -> bool:
    """The tutor is about to say what it said a moment ago on the same question."""
    said = {" ".join(t.split()) for t in recent if t}
    return any(" ".join(t.split()) in said for t in new if t)
