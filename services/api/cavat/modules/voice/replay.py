"""The teacher hears a spoken turn again (ENG-7b, ADR-067; english-module-rules F4, F5, V3).

``GET /v1/teachers/voice/{audio_ref}`` answers the recording of one turn the child said in an English session.
``audio_ref`` is the path the VOICE_TURN_RECORDED event keeps (``in/<day>/<student hash>/<uuid>.<ext>``,
ADR-064); the recording itself stays on disk under ``var/storage/voice/in`` (rule V3).

What the endpoint checks, in order, before any byte is read:

1. the caller is a teacher (``teacher_identity``: a student or a parent token is refused, 401/403);
2. ``audio_ref`` has exactly the shape the server writes (day, 16-hex student hash, 32-hex uuid, a known
   audio extension): no ``..``, no absolute path, no other folder;
3. a session **of the teacher's school** (the repository filters ``school_id``, rule 5) recorded a turn with
   this very ``audio_ref``, and the student hash in the path is the one of that session's student: a file
   on disk that no turn of the school names is never served, nor a turn of another school;
4. the resolved path is still inside ``var/storage/voice/in`` (symbolic links included).

Any failure answers 404 with the same message, so the endpoint does not tell which recordings exist.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from cavat.core.events import EventType
from cavat.modules.session.repository import LearningSessionRepository
from cavat.modules.voice.api import VoiceError
from cavat.modules.voice.turns import student_hash

AUDIO_REF = re.compile(
    r"in/\d{4}-\d{2}-\d{2}/(?P<owner>[0-9a-f]{16})/[0-9a-f]{32}\.(?P<ext>webm|ogg|m4a|wav)"
)
MEDIA_TYPES = {"webm": "audio/webm", "ogg": "audio/ogg", "m4a": "audio/mp4", "wav": "audio/wav"}


class _VoiceTurnOwners(LearningSessionRepository):
    """The school's sessions, asked only which one recorded a turn with a given ``audio_ref``."""

    async def student_of(self, audio_ref: str) -> str | None:
        doc = await self._find_one(
            {"events.payload.audio_ref": audio_ref},
            projection={"student_id": 1, "events": 1},
        )
        if doc is None:
            return None
        recorded = any(
            e.get("event_type") == EventType.VOICE_TURN_RECORDED
            and (e.get("payload") or {}).get("audio_ref") == audio_ref
            for e in doc.get("events", [])
        )
        return doc.get("student_id") if recorded else None


def _not_found() -> VoiceError:
    return VoiceError(404, "NOT_FOUND", "no recording of this school has this reference")


def build_router(
    get_database: Callable[..., Any],
    teacher_identity: Callable[..., str],
    school_id: str,
    voice_dir: Callable[[], Path],
) -> APIRouter:
    router = APIRouter(prefix="/v1/teachers/voice", tags=["teacher-voice"])

    @router.get("/{audio_ref:path}", response_class=FileResponse)
    async def turn_audio(
        audio_ref: str,
        database: Annotated[Any, Depends(get_database)],
        teacher: Annotated[str, Depends(teacher_identity)],
    ) -> FileResponse:
        """Teacher: the recording of one spoken turn of the school (ADR-060 §9.1). Never for a student or a
        parent (rule F4); only a turn a session of this school recorded (rule F5)."""
        shape = AUDIO_REF.fullmatch(audio_ref)
        if shape is None:
            raise _not_found()
        student = await _VoiceTurnOwners(database, school_id).student_of(audio_ref)
        if student is None or student_hash(student) != shape["owner"]:
            raise _not_found()
        root = (voice_dir() / "in").resolve()
        path = (voice_dir() / audio_ref).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise _not_found()
        return FileResponse(
            path,
            media_type=MEDIA_TYPES[shape["ext"]],
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    return router
