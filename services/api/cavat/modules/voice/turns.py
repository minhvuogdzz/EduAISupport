"""A spoken turn the server heard, kept on disk next to its recording until the child sends it (ENG-6).

``POST /v1/voice/transcribe`` in an English session writes ``<uuid>.json`` beside ``<uuid>.<ext>`` in
``var/storage/voice/in/<day>/<student hash>/`` (rule V3: audio stays on disk, never in the database). It
answers a ``voice_turn_id`` (``<day>/<uuid>``). The response command sends that id back; the session reads
the record from disk, checks it belongs to this student and this session, and writes the
VOICE_TURN_RECORDED event and the q of ITEM_RESOLVED from it. The client never sends q, a language or an
audio path: it could not make a low confidence look high (rule 4).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_TURN_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})/([0-9a-f]{32})$")


class VoiceTurn(BaseModel):
    """What the server heard on one recording, as written beside it."""

    model_config = ConfigDict(extra="forbid")

    voice_turn_id: str
    session_id: str
    student_hash: str
    audio_ref: str  # path under var/storage/voice, e.g. "in/2026-11-13/<hash>/<uuid>.webm"
    language: Literal["vi", "en"]
    asr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    model: str
    heard: str


def student_hash(student: str) -> str:
    """The folder of a student's recordings: a hash, never the id (as ADR-030 stores them)."""
    return hashlib.sha256(student.encode()).hexdigest()[:16]


def save_turn(voice_dir: Path, turn: VoiceTurn) -> None:
    day, uuid = _parts(turn.voice_turn_id)
    path = voice_dir / "in" / day / turn.student_hash / f"{uuid}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(turn.model_dump_json(), encoding="utf-8")


def load_turn(voice_dir: Path, voice_turn_id: str, *, student: str, session_id: str) -> VoiceTurn | None:
    """The turn of this id when it is this student's and this session's; None otherwise (unknown id, a
    record of someone else, a missing or damaged file). The id is checked before any path is built."""
    match = _TURN_ID.match(voice_turn_id or "")
    if match is None:
        return None
    path = voice_dir / "in" / match[1] / student_hash(student) / f"{match[2]}.json"
    try:
        turn = VoiceTurn.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError, json.JSONDecodeError):
        return None
    if turn.voice_turn_id != voice_turn_id or turn.session_id != session_id:
        return None
    if turn.student_hash != student_hash(student):
        return None
    return turn


def _parts(voice_turn_id: str) -> tuple[str, str]:
    match = _TURN_ID.match(voice_turn_id)
    if match is None:
        raise ValueError(f"not a voice turn id: {voice_turn_id!r}")
    return match[1], match[2]
