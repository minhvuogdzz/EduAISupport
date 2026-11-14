"""What the tutor listens for and how it speaks, by subject and by step (ENG-6, ADR-064, rules V1/V2).

The backend decides; the client only sends back what the session view told it (CLAUDE.md rule 4):

- **Mathematics** keeps the voice of ADR-030 exactly: Whisper always hears Vietnamese ("vi"), no voice turn
  is recorded as an event, the tutor's whole message goes to VieNeu after ``speech_text``.
- **English** (DI-132): Whisper hears English ("en") only when the session waits for an item answer whose
  ``response_language`` is "en" (repeat after the tutor, an English question and answer). Everything else
  hears Vietnamese: a meaning question, a "vì sao", a mixed answer ("either"), the theory replies and the
  retell, and an item that does not say its response language yet. Reason (PR #139): "en" translates
  Vietnamese into the target word ("anh trai" -> "brother"), a false "correct"; "vi" keeps Vietnamese words
  and still hears whole English sentences.
- Whisper's own language detection is never used (it hears Vietnamese-accented English as Malay and
  translates it): every language here is "vi" or "en".

The differences are data of a ``VoiceProfile`` per subject, not ``if subject == "english"`` in the
session code (rule S2).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cavat.core.subjects import check_subject

Language = Literal["vi", "en"]
SpeechMode = Literal["tutor", "mixed"]


@dataclass(frozen=True)
class VoiceProfile:
    """How voice works in the sessions of one subject."""

    # Record each spoken turn as a VOICE_TURN_RECORDED event and put its q on ITEM_RESOLVED (DI-109).
    record_turns: bool
    # Below this q the tutor asks the child to say it again (DI-134); None never asks (Mathematics).
    ask_again_below: float | None
    # "tutor": the whole message to the tutor's voice; "mixed": the English plan of ``english_speech``.
    speech: SpeechMode
    # Whether the response language of an item can make Whisper hear English.
    english_items: bool


MATH_PROFILE = VoiceProfile(record_turns=False, ask_again_below=None, speech="tutor", english_items=False)


def profile_for(subject: str, *, english_min_confidence: float = 0.6) -> VoiceProfile:
    """The voice profile of a subject; an unknown or missing subject is an error, never Mathematics."""
    check_subject(subject)
    if subject == "english":
        return VoiceProfile(
            record_turns=True,
            ask_again_below=english_min_confidence,
            speech="mixed",
            english_items=True,
        )
    return MATH_PROFILE


@dataclass(frozen=True)
class Listening:
    """The language Whisper hears for the next turn of a session, and the ones a client may send."""

    subject: str
    language: Language
    allowed: tuple[Language, ...]
    reason: str  # why, for the tests and the teacher: MATH, ITEM_EN, ITEM_VI, ITEM_EITHER, NOT_ITEM...

    def admits(self, language: str | None) -> bool:
        return language is None or language in self.allowed


def choose_language(
    subject: str,
    *,
    awaiting: str | None,
    expecting: str | None = None,
    response_language: str | None = None,
    english_items: bool | None = None,
) -> Listening:
    """DI-132: the language of the next spoken turn, from the subject and what the session waits for.

    ``awaiting`` is the teaching loop's ("ANSWER", "THEORY_REPLY", "RETELL"...), ``expecting`` the item's
    ("ANSWER" or "EXPLANATION"), ``response_language`` the item's (ENG-3b: "en" | "vi" | "either").
    """
    check_subject(subject)
    hears_english = profile_for(subject).english_items if english_items is None else english_items
    if not hears_english:
        return Listening(subject, "vi", ("vi",), "MATH" if subject == "math" else "VI_ONLY")
    if awaiting != "ANSWER":
        return Listening(subject, "vi", ("vi",), "NOT_ITEM")
    if expecting == "EXPLANATION":
        return Listening(subject, "vi", ("vi",), "EXPLANATION")
    if response_language == "en":
        return Listening(subject, "en", ("en",), "ITEM_EN")
    if response_language == "either":
        return Listening(subject, "vi", ("vi",), "ITEM_EITHER")
    if response_language == "vi":
        return Listening(subject, "vi", ("vi",), "ITEM_VI")
    return Listening(subject, "vi", ("vi",), "ITEM_UNSPECIFIED")


MATH_LISTENING = Listening("math", "vi", ("vi",), "MATH")
