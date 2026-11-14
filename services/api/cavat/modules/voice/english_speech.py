"""The tutor's voice in an English session (ENG-6, ADR-064, DI-133): who reads which part of a message.

The tutor speaks Vietnamese and says the English target words and sentences. The POC (PR #139,
``docs/poc/english-voice-decision.md``) found how VieNeu-TTS v3 Turbo reads them:

- A bare English word ("Mother.") is repeated or gets extra syllables about half the time; inside a
  Vietnamese lead-in ending with a colon ("Con nói theo cô: mother.") it is clean 11 times out of 12. Rule
  V2b: an English sentence of one or two words is never sent alone; it gets that measured lead-in.
- A whole English sentence, or one after a colon, is read clearly (6/6), so it goes to VieNeu as written.
- "ate" is read so that it is heard as "are" ("We ate seafood." -> "We are seafood."), and a verb table
  ("go, went. Eat, ate.") breaks completely. A child would learn the wrong past form. With
  ``ENGLISH_TTS_RISKY=browser`` (default) the English part that holds "ate" or a pair of the verb table is
  read by the browser's English voice (option B of the POC: Whisper heard that mix right 100%); the
  Vietnamese around it stays with VieNeu. ``vieneu`` sends everything to VieNeu.

Deterministic, no model. The plan is a list of parts in reading order; the web reads "tutor" parts with
``POST /v1/voice/speech`` and "browser_en" parts with its own en-US voice. Mathematics never comes here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from cavat.modules.voice.speech_text import MAX_SPEECH_CHARS

Voice = Literal["tutor", "browser_en"]
RiskyVoice = Literal["browser", "vieneu"]

# V2b: the lead-in measured cleanest in the POC (3 of 24 readings with an extra sound, 11 of 12 heard right).
LEAD_IN = "Con nói theo cô:"
# Unit 11 "Family time" past forms (SGK Tiếng Anh 5 Global Success, ENG-3) with their base form. A pair of
# them side by side is the verb table the POC heard break ("go, went" -> "nguồn quên").
PAST_OF: dict[str, str] = {
    "go": "went",
    "eat": "ate",
    "buy": "bought",
    "take": "took",
    "swim": "swam",
    "see": "saw",
    "do": "did",
    "have": "had",
    "visit": "visited",
    "collect": "collected",
    "make": "made",
    "play": "played",
}
_VI_LETTERS = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
_VI_LETTER = re.compile(f"[{_VI_LETTERS}]", re.IGNORECASE)
# Vietnamese words the tutor writes without a tone mark that are not English words.
_PLAIN_VI = frozenset(
    "con cho theo nghe xin xem khi sao anh em hay trong nhanh thanh chung cung mua vui giup toan hoa".split()
)
_RISKY_WORD = re.compile(r"\bate\b", re.IGNORECASE)
_PAIR = re.compile(
    r"\b(" + "|".join(PAST_OF) + r")\b\s*[,:;/–—→\-]+\s*\b(" + "|".join(PAST_OF.values()) + r")\b",
    re.IGNORECASE,
)
_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen"
).split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


@dataclass(frozen=True)
class SpeechPart:
    text: str
    voice: Voice


def english_number(n: int) -> str:
    """0..999 in English words ("4" -> "four", "21" -> "twenty-one"); larger numbers stay digits."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f"-{_ONES[ones]}" if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return f"{_ONES[hundreds]} hundred" + (f" and {english_number(rest)}" if rest else "")
    return str(n)


def clean(text: str) -> str:
    """Markdown, emoji and line breaks out, as ``speech_text`` does for Mathematics, without its reading of
    numbers and signs in Vietnamese (an English "x" or "-" is not "nhân" or "trừ")."""
    s = re.sub(r"[*_#`«»\"“”]", "", text)
    s = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", s)  # emoji
    s = re.sub(r"\s*\n+\s*", ". ", s)
    s = s.replace("…", ".").replace("...", ".")
    s = re.sub(r"\.(\s*\.)+", ".", s)
    s = re.sub(r"\s+([,.?!:])", r"\1", re.sub(r"\s+", " ", s)).strip()
    return s[:MAX_SPEECH_CHARS]


def is_vietnamese_word(token: str) -> bool:
    word = re.sub(r"[^\w]", "", token).lower()
    return bool(_VI_LETTER.search(word)) or word in _PLAIN_VI


def is_english(text: str) -> bool:
    """Words in Latin letters only, none of them Vietnamese ("We went to Ha Long Bay." is English)."""
    words = [w for w in text.split() if re.search(r"[A-Za-z]", w)]
    return bool(words) and not any(is_vietnamese_word(w) for w in text.split())


def risky(text: str) -> bool:
    """English the tutor's voice reads wrong: "ate", or a base/past pair of the verb table."""
    return bool(_RISKY_WORD.search(text) or _PAIR.search(text))


def _english_numbers(text: str) -> str:
    return re.sub(r"\b\d{1,3}\b", lambda m: english_number(int(m[0])), text)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _word_count(text: str) -> int:
    return len([w for w in text.split() if re.search(r"\w", w)])


def _split_lead(sentence: str) -> tuple[str, str] | None:
    """A Vietnamese lead-in ending with a colon and the English after it ("Con nói theo cô: We ate.")."""
    head, colon, tail = sentence.rpartition(":")
    if not colon or not head.strip() or not tail.strip() or not is_english(tail):
        return None
    return head.strip() + ":", tail.strip()


def _runs(sentence: str) -> list[tuple[str, bool]]:
    """The sentence in runs of Vietnamese and English words: (text, is_english)."""
    runs: list[tuple[str, bool]] = []
    for token in sentence.split():
        english = bool(re.search(r"[A-Za-z]", token)) and not is_vietnamese_word(token)
        lettered = bool(re.search(r"\w", token))
        if runs and (runs[-1][1] == english or not lettered):
            runs[-1] = (f"{runs[-1][0]} {token}", runs[-1][1])
        else:
            runs.append((token, english))
    return runs


def speech_plan(text: str, *, risky_voice: RiskyVoice = "browser") -> list[SpeechPart]:
    """The message of the tutor as parts to read, in order (DI-133)."""
    parts: list[SpeechPart] = []
    to_browser = risky_voice == "browser"

    def say(words: str, voice: Voice = "tutor") -> None:
        words = words.strip()
        if not words:
            return
        if voice == "browser_en":
            words = _english_numbers(words)
        if parts and parts[-1].voice == voice:
            parts[-1] = SpeechPart(f"{parts[-1].text} {words}", voice)
        else:
            parts.append(SpeechPart(words, voice))

    for sentence in _sentences(clean(text)):
        lead = _split_lead(sentence)
        if lead is not None:
            head, tail = lead
            if to_browser and risky(tail):
                say(head)
                say(tail, "browser_en")
            else:
                say(f"{head} {_english_numbers(tail)}")
        elif is_english(sentence):
            if to_browser and risky(sentence):
                say(sentence, "browser_en")
            elif _word_count(sentence) < 3:
                say(f"{LEAD_IN} {_english_numbers(sentence)}")  # V2b: never a bare English word
            else:
                say(_english_numbers(sentence))
        elif to_browser and risky(sentence):
            for run, english in _runs(sentence):
                say(run, "browser_en" if english and risky(run) else "tutor")
        else:
            say(sentence)
    return parts


def bare_english(text: str) -> bool:
    """A text the tutor's voice must never get alone (V2b): English of one or two words, no lead-in."""
    sentence = clean(text)
    return is_english(sentence) and _word_count(sentence) < 3 and _split_lead(sentence) is None
