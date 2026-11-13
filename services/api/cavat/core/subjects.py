"""The subjects the tutor teaches (ENG-2, ADR-061): Mathematics and, from 12/11/2026, English.

A subject is part of every chapter or unit package, every chunk of the Hybrid RAG and every teacher
document. The backend sets it from the package a session runs; a client never chooses it (CLAUDE.md rule 4).

Data written before ENG-2 has no subject: it is all Mathematics (D-T9). ``with_legacy_subject`` is the one
place that reads such a stored document as Mathematics (DI-120). New data without a subject is an error:
the models declare ``subject`` without a default.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, get_args

Subject = Literal["math", "english"]
SUBJECTS: tuple[str, ...] = get_args(Subject)

# DI-120: a document stored before ENG-2 carries no "subject" field; it is read as Mathematics, the only
# subject there was. Applied on read only, never written back (no migration of cavat_dev or cavat_prod).
LEGACY_SUBJECT: Subject = "math"


def check_subject(subject: object) -> str:
    """``subject`` when it is a known subject; otherwise ValueError (no silent fallback to Mathematics)."""
    if subject not in SUBJECTS:
        raise ValueError(f"unknown or missing subject {subject!r}; expected one of {SUBJECTS}")
    return str(subject)


def with_legacy_subject(doc: Mapping[str, Any]) -> dict[str, Any]:
    """A stored document as read: without a "subject" key (written before ENG-2), Mathematics (DI-120).

    A key that is present keeps its value, even an empty or wrong one, so that validation rejects it.
    """
    out = dict(doc)
    if "subject" not in out:
        out["subject"] = LEGACY_SUBJECT
    return out
