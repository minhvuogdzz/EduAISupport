"""Voice live (ADR-030): the child speaks to the tutor and hears it.

- ``POST /v1/voice/transcribe``: the child's recording (webm/ogg/mp4/wav) -> words, STT_VI (Groq Whisper,
  free tier). The recording is kept on disk (``var/storage/voice/in``) like every original file. The words
  then go through ``/v1/sessions/{id}/responses`` with ``modality: VOICE``, the same path as typing.
- ``POST /v1/voice/speech``: a message of the tutor -> audio, TTS_VI (VieNeu-TTS, local), read from
  ``speech_text`` (numbers and signs written out); cached on disk by its words.
- ``GET /v1/voice/status``: what the server can do; without it the browser listens and reads by itself.
- ``POST /v1/voice/speech-plan`` (ENG-6): an English session's message in parts, each for the tutor's voice
  or the browser's English voice (``english_speech``, DI-133).

ENG-6 (ADR-064): with a ``session_id`` the backend picks the language Whisper hears from the session's
subject and the input it waits for (``listening``, DI-132); a client may send a ``language`` only to repeat
the one the session view gave it. In an English session the response also carries q (DI-109), the
language and a ``voice_turn_id`` the response command sends back, and asks the child to say it again when
q is low (DI-134). A Mathematics session (or no session) is ADR-030 as it was: "vi", the same response, the
same files.

Students only. The client never picks a model or a voice (rule 4).
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from cavat.config import get_settings
from cavat.modules.ai_gateway.base import AIGatewayError
from cavat.modules.voice import english_speech
from cavat.modules.voice.listening import MATH_LISTENING, MATH_PROFILE, Listening, VoiceProfile
from cavat.modules.voice.speech_text import MAX_SPEECH_CHARS, speech_text
from cavat.modules.voice.turns import VoiceTurn, save_turn, student_hash

MAX_AUDIO_BYTES = 3 * 1024 * 1024  # about a minute of webm/opus: a child's turn is a few seconds
_AUDIO = File()  # the child's recording, a multipart field "audio"
_SESSION = Form(default=None, max_length=64)  # ENG-6: the session the turn belongs to
_LANGUAGE = Form(default=None, max_length=8)  # ENG-6: the language the session view named, sent back
_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
}


class VoiceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, max_length=64)  # ENG-6: reads by the session's subject


class Transcript(BaseModel):
    """``text`` and ``model`` as ADR-030; the other fields only in a session that records voice turns
    (English): the response of a Mathematics session is the same as before ENG-6."""

    text: str
    model: str
    language: Literal["vi", "en"] | None = None
    confidence: float | None = None  # q of DI-109
    voice_turn_id: str | None = None  # sent back with the response command
    ask_again: bool | None = None  # DI-134: the tutor did not hear it clearly; the child says it again


class SpeechPartView(BaseModel):
    text: str
    voice: Literal["tutor", "browser_en"]


class SpeechPlan(BaseModel):
    parts: list[SpeechPartView]


@dataclass(frozen=True)
class SessionVoice:
    """What a session needs of voice: set by the session module from the session's own package."""

    session_id: str
    subject: str
    listening: Listening
    profile: VoiceProfile


# A dependency of the session module: (session_id) -> the session's voice, after checking its owner.
SessionVoiceResolver = Callable[[str], Awaitable[SessionVoice]]


class VoiceStatus(BaseModel):
    listen: bool  # the server turns speech into words (else the browser's own recognition)
    speak: bool  # the server has the tutor's voice (else the browser's own voice)
    speech_model: str | None


def _storage() -> Path:
    return get_settings().storage_dir / "voice"


def _no_sessions() -> SessionVoiceResolver:
    async def resolve(_: str) -> SessionVoice:
        raise VoiceError(422, "VALIDATION_ERROR", "voice is not linked to sessions here")

    return resolve


def ask_again(profile: VoiceProfile, text: str, confidence: float | None) -> bool:
    """DI-134: the tutor asks the child to say it again: nothing heard, or q below the subject's line."""
    if profile.ask_again_below is None:
        return False
    if not text.strip() or confidence == 0.0:
        return True
    return confidence is not None and confidence < profile.ask_again_below


def tutor_words(text: str, profile: VoiceProfile) -> str:
    """What the tutor's voice reads for ``text``: Mathematics' ``speech_text``, or for an English session
    the cleaned text, never a bare English word (rule V2b)."""
    if profile.speech == "tutor":
        return speech_text(text)
    words = english_speech.clean(text)
    return f"{english_speech.LEAD_IN} {words}" if english_speech.bare_english(words) else words


def build_router(
    student_identity: Callable[..., str],
    ai_router: Callable[[], Any],
    session_voice: Callable[..., SessionVoiceResolver] = _no_sessions,
) -> APIRouter:
    router = APIRouter(prefix="/v1/voice", tags=["voice"])
    who = Depends(student_identity)
    sessions = Depends(session_voice)

    @router.get("/status", response_model=VoiceStatus)
    async def status(_: str = who) -> VoiceStatus:
        gateway = ai_router()
        return VoiceStatus(
            listen=gateway.can_transcribe,
            speak=gateway.speech_model is not None,
            speech_model=gateway.speech_model,
        )

    @router.post("/transcribe", response_model=Transcript, response_model_exclude_none=True)
    async def transcribe(
        audio: UploadFile = _AUDIO,
        session_id: str | None = _SESSION,
        language: str | None = _LANGUAGE,
        student: str = who,
        resolve: SessionVoiceResolver = sessions,
    ) -> Transcript:
        voice = await resolve(session_id) if session_id else None
        listening = voice.listening if voice is not None else MATH_LISTENING
        profile = voice.profile if voice is not None else MATH_PROFILE
        if not listening.admits(language):
            # Rule 4: the client repeats the language the session view named; it cannot pick another one.
            raise VoiceError(422, "VALIDATION_ERROR", f"language {language!r} is not the one of this turn")
        data = await audio.read(MAX_AUDIO_BYTES + 1)
        if not data:
            raise VoiceError(422, "VALIDATION_ERROR", "the recording is empty")
        if len(data) > MAX_AUDIO_BYTES:
            raise VoiceError(413, "VALIDATION_ERROR", "the recording is too long")
        kind = (audio.content_type or "").split(";")[0]
        ext = _EXTENSIONS.get(kind)
        if ext is None:
            raise VoiceError(415, "VALIDATION_ERROR", f"unsupported audio type {kind!r}")
        day = datetime.now(UTC).date().isoformat()
        uuid = uuid4().hex
        name = f"{uuid}.{ext}"
        owner = student_hash(student)
        folder = _storage() / "in" / day / owner
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        gateway = ai_router()
        try:
            heard = await run_in_threadpool(
                gateway.transcribe, data, language=listening.language, filename=name
            )
        except AIGatewayError as exc:
            raise VoiceError(503, "MODEL_UNAVAILABLE", "speech-to-text is not available") from exc
        if voice is None or not profile.record_turns:
            return Transcript(text=heard.text, model=heard.model)  # ADR-030, as before ENG-6
        turn_id = None
        if heard.text.strip():
            turn_id = f"{day}/{uuid}"
            save_turn(
                _storage(),
                VoiceTurn(
                    voice_turn_id=turn_id,
                    session_id=voice.session_id,
                    student_hash=owner,
                    audio_ref=f"in/{day}/{owner}/{name}",
                    language=listening.language,
                    asr_confidence=heard.confidence,
                    model=heard.model,
                    heard=heard.text,
                ),
            )
        return Transcript(
            text=heard.text,
            model=heard.model,
            language=listening.language,
            confidence=heard.confidence,
            voice_turn_id=turn_id,
            ask_again=ask_again(profile, heard.text, heard.confidence),
        )

    @router.post("/speech-plan", response_model=SpeechPlan)
    async def speech_plan(
        body: SpeechRequest, _: str = who, resolve: SessionVoiceResolver = sessions
    ) -> SpeechPlan:
        """ENG-6 (DI-133): who reads which part. Mathematics, or no session: the whole message, the tutor."""
        voice = await resolve(body.session_id) if body.session_id else None
        if voice is None or voice.profile.speech == "tutor":
            return SpeechPlan(parts=[SpeechPartView(text=body.text, voice="tutor")])
        parts = english_speech.speech_plan(body.text, risky_voice=get_settings().english_tts_risky)
        return SpeechPlan(parts=[SpeechPartView(text=p.text, voice=p.voice) for p in parts])

    @router.post("/speech")
    async def speech(body: SpeechRequest, _: str = who, resolve: SessionVoiceResolver = sessions) -> Response:
        voice = await resolve(body.session_id) if body.session_id else None
        words = tutor_words(body.text, voice.profile if voice is not None else MATH_PROFILE)
        if not words:
            raise VoiceError(422, "VALIDATION_ERROR", "nothing to read")
        gateway = ai_router()
        model = gateway.speech_model
        if model is None:
            raise VoiceError(503, "MODEL_UNAVAILABLE", "the tutor's voice is not configured")
        key = hashlib.sha256(f"{model}\n{get_settings().vieneu_voice}\n{words}".encode()).hexdigest()[:32]
        cached = _storage() / "tts" / f"{key}.wav"
        if cached.exists():
            return Response(cached.read_bytes(), media_type="audio/wav")
        try:
            said = await run_in_threadpool(gateway.speak, words)
        except AIGatewayError as exc:
            raise VoiceError(503, "MODEL_UNAVAILABLE", "the tutor's voice is not available") from exc
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(said.audio)
        return Response(said.audio, media_type=said.content_type)

    return router


__all__ = ["MAX_SPEECH_CHARS", "SessionVoice", "VoiceError", "build_router"]
