"""Voice in a session (ENG-6, ADR-064): the language of the next spoken turn, and the turn in the event log.

- ``session_voice``: the subject comes from the package the session runs (rule S1); the language from
  ``voice.listening.choose_language`` and what the session waits for (DI-132).
- ``with_voice_turn``: when a response command sends back the ``voice_turn_id`` of ``/v1/voice/transcribe``
  in a session whose subject records voice turns (English), its record is read from disk (never from the
  client) and written as VOICE_TURN_RECORDED beside the STUDENT_MESSAGE; when the answer was graded in this
  command, ITEM_RESOLVED gets ``modality: VOICE`` and ``asr_confidence = q`` (DI-109, rule E2). The grading
  and the teaching loop do not change: this only adds what the loop already said was heard by voice.
  A Mathematics session never comes past the profile check: its events are those of ADR-030.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from cavat.config import get_settings
from cavat.core.events import EventType, VoiceTurnRecorded
from cavat.modules.session import chapter_service, service
from cavat.modules.session.repository import LearningSession, NewEvent
from cavat.modules.voice.api import SessionVoice
from cavat.modules.voice.listening import choose_language, profile_for
from cavat.modules.voice.turns import load_turn


def session_voice(session: LearningSession, content: Any) -> SessionVoice:
    """The voice of ``session``; ``content`` is the chapter (teaching loop) or the lesson package it runs."""
    subject = content.package.subject if chapter_service.is_chapter(session) else content.subject
    profile = profile_for(subject, english_min_confidence=get_settings().english_asr_min_confidence)
    if chapter_service.is_chapter(session):
        awaiting, expecting, language = chapter_service.awaited_input(content, session)
    else:
        awaiting, expecting, language = None, None, None  # the fixed lesson plans are Mathematics
    listening = choose_language(
        subject,
        awaiting=awaiting,
        expecting=expecting,
        response_language=language,
        english_items=profile.english_items,
    )
    return SessionVoice(session_id=session.id, subject=subject, listening=listening, profile=profile)


def voice_view(voice: SessionVoice) -> dict[str, Any]:
    """``voice`` of the session view: the language the web sends back, and how the tutor's words are read."""
    return {
        "language": voice.listening.language,
        "allowed": list(voice.listening.allowed),
        "speech": voice.profile.speech,
    }


def with_voice_turn(
    step: service.Step,
    session: LearningSession,
    voice: SessionVoice,
    *,
    voice_turn_id: str | None,
    text: str,
    modality: str,
    student: str,
    voice_dir: Path,
) -> service.Step:
    """The step of one command with its spoken turn recorded and the q of the items it resolves.

    Runs on every command of a session that records voice turns: an item is often resolved on a later turn
    (the "vì sao" after the answer), and its q is the one of the graded answer that decided it.
    """
    if not voice.profile.record_turns:
        return step  # Mathematics: ADR-030 as it was
    events = list(step.events)
    turn = (
        load_turn(voice_dir, voice_turn_id, student=student, session_id=session.id)
        if voice_turn_id and modality == "VOICE"
        else None
    )
    already = turn is not None and any(
        e.event_type == EventType.VOICE_TURN_RECORDED and e.payload.get("voice_turn_id") == voice_turn_id
        for e in session.events
    )
    if turn is not None and not already:  # a recovery retry replays the same turn: it is recorded once
        said = next((i for i, e in enumerate(events) if e.event_type == EventType.STUDENT_MESSAGE), None)
        message = events[said] if said is not None else None
        payload = VoiceTurnRecorded(
            school_id=session.school_id,
            voice_turn_id=turn.voice_turn_id,
            message_ref=message.payload.get("item_id") if message is not None else None,
            audio_ref=turn.audio_ref,
            language=turn.language,
            asr_confidence=turn.asr_confidence,
            model=turn.model,
            heard=turn.heard,
            edited=text.strip() != turn.heard.strip(),
        )
        recorded = NewEvent(
            event_type=EventType.VOICE_TURN_RECORDED.value,
            payload=payload.model_dump(mode="json"),
            actor=chapter_service.actor_for(EventType.VOICE_TURN_RECORDED, session.student_id),
            item_attempt_id=message.item_attempt_id if message is not None else None,
        )
        events.insert(said + 1 if said is not None else len(events), recorded)
    for i, e in enumerate(events):
        if e.event_type != EventType.ITEM_RESOLVED:
            continue
        spoken = _deciding_voice(session, events, e.payload.get("item_id"))
        if spoken is not None:
            payload = {**e.payload, "modality": "VOICE", "asr_confidence": spoken.get("asr_confidence")}
            events[i] = e.model_copy(update={"payload": payload})
    return replace(step, events=events)


def _deciding_voice(
    session: LearningSession, step_events: list[NewEvent], item_id: str | None
) -> dict[str, Any] | None:
    """The VOICE_TURN_RECORDED payload of the command whose graded answer last decided ``item_id``, when that
    answer was spoken and sent as heard; None when it was typed (or edited, or there is none)."""
    groups: list[list[Any]] = []
    key: object = object()
    for e in session.events:
        if not groups or e.idempotency_key is None or e.idempotency_key != key:
            groups.append([])
        groups[-1].append(e)
        key = e.idempotency_key
    groups.append(list(step_events))
    for group in reversed(groups):
        answered = any(
            e.event_type == EventType.ANSWER_SUBMITTED and e.payload.get("item_id") == item_id for e in group
        )
        if answered:
            spoken = next((e.payload for e in group if e.event_type == EventType.VOICE_TURN_RECORDED), None)
            return spoken if spoken is not None and not spoken.get("edited") else None
    return None
