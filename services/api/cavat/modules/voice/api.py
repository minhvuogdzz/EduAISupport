"""Voice live (ADR-030): the child speaks to the tutor and hears it.

- ``POST /v1/voice/transcribe``: the child's recording (webm/ogg/mp4/wav) -> words, STT_VI (Groq Whisper,
  free tier). The recording is kept on disk (``var/storage/voice/in``) like every original file. The words
  then go through ``/v1/sessions/{id}/responses`` with ``modality: VOICE``, the same path as typing.
- ``POST /v1/voice/speech``: a message of the tutor -> audio, TTS_VI (VieNeu-TTS, local), read from
  ``speech_text`` (numbers and signs written out); cached on disk by its words.
- ``GET /v1/voice/status``: what the server can do; without it the browser listens and reads by itself.

Students only. The client never picks a model or a voice (rule 4).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from cavat.config import get_settings
from cavat.modules.ai_gateway.base import AIGatewayError
from cavat.modules.voice.speech_text import MAX_SPEECH_CHARS, speech_text

MAX_AUDIO_BYTES = 3 * 1024 * 1024  # about a minute of webm/opus: a child's turn is a few seconds
_AUDIO = File()  # the child's recording, a multipart field "audio"
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


class Transcript(BaseModel):
    text: str
    model: str


class VoiceStatus(BaseModel):
    listen: bool  # the server turns speech into words (else the browser's own recognition)
    speak: bool  # the server has the tutor's voice (else the browser's own voice)
    speech_model: str | None


def _storage() -> Path:
    return get_settings().storage_dir / "voice"


def build_router(student_identity: Callable[..., str], ai_router: Callable[[], Any]) -> APIRouter:
    router = APIRouter(prefix="/v1/voice", tags=["voice"])
    who = Depends(student_identity)

    @router.get("/status", response_model=VoiceStatus)
    async def status(_: str = who) -> VoiceStatus:
        gateway = ai_router()
        return VoiceStatus(
            listen=gateway.can_transcribe,
            speak=gateway.speech_model is not None,
            speech_model=gateway.speech_model,
        )

    @router.post("/transcribe", response_model=Transcript)
    async def transcribe(audio: UploadFile = _AUDIO, student: str = who) -> Transcript:
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
        name = f"{uuid4().hex}.{ext}"
        folder = _storage() / "in" / day / hashlib.sha256(student.encode()).hexdigest()[:16]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        gateway = ai_router()
        try:
            heard = await run_in_threadpool(gateway.transcribe, data, language="vi", filename=name)
        except AIGatewayError as exc:
            raise VoiceError(503, "MODEL_UNAVAILABLE", "speech-to-text is not available") from exc
        return Transcript(text=heard.text, model=heard.model)

    @router.post("/speech")
    async def speech(body: SpeechRequest, _: str = who) -> Response:
        words = speech_text(body.text)
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


__all__ = ["MAX_SPEECH_CHARS", "VoiceError", "build_router"]
