"""SAFE-1: a child's worrying words reach the teacher. The distress words of DI-41 are met with care during
a theory wait and during an item (the item stays open, the words are not an attempt), raise SAFETY_FLAGGED,
and show first in the class view and on the student's turn of the transcript. In memory, templates only."""

from datetime import UTC, datetime

import pytest
from cavat.core.events import EventType
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service
from cavat.modules.session.api import get_database
from cavat.modules.teaching.loop import Awaiting, TeachingLoop
from fastapi.testclient import TestClient
from test_chapter_session_api import TEACHER, reply_text

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)
CHAPTER = chapter_service.chapters()["math-g5-decimals"]
AN = {"X-Demo-Student": "an"}
WORRY = "cô ơi hôm qua con bị bạn đánh đau lắm"


def loop_at_first_item() -> TeachingLoop:
    loop = TeachingLoop(CHAPTER, "s1")
    turn = loop.start(NOW)
    while turn.awaiting != Awaiting.ANSWER:
        turn = loop.on_student("Con nghĩ là được ạ.", NOW)
    return loop


def test_a_worrying_message_during_an_item_is_not_an_attempt():
    loop = loop_at_first_item()
    item, phase = loop.tutor.item.id, loop.tutor.phase
    turn = loop.on_student(WORRY, NOW)
    assert [e.event_type for e in turn.events] == [
        EventType.STUDENT_MESSAGE,
        EventType.SAFETY_FLAGGED,
        EventType.TEACH_MESSAGE_SENT,
    ]
    assert turn.events[1].payload == {"item_id": item, "source": "RULE"}
    assert "kể ngay với thầy cô hoặc bố mẹ" in turn.messages[0].text
    assert turn.awaiting == Awaiting.ANSWER and loop.tutor.item.id == item and loop.tutor.phase == phase
    again = TeachingLoop.resume(CHAPTER, "s1", [], loop.events)  # the replay does not feed it to the item
    assert again.tutor.item.id == item and again.tutor.phase == phase


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield TestClient(app)
    app.dependency_overrides.pop(get_database, None)


def send(client, state: dict, text: str, key: str) -> dict:
    body = {
        "item_attempt_id": state["teaching"]["input_id"],
        "kind": "ANSWER",
        "content": {"text": text},
        "expected_state_version": state["state_version"],
    }
    sent = client.post(
        f"/v1/sessions/{state['session_id']}/responses", json=body, headers={**AN, "Idempotency-Key": key}
    )
    assert sent.status_code == 200, sent.text
    return client.get(f"/v1/sessions/{state['session_id']}/state", headers=AN).json()


def test_the_teacher_sees_the_flag_first_in_the_class_and_on_the_turn(client):
    created = client.post("/v1/sessions", json={"student_display_name": "An"}, headers=AN).json()
    state = client.post(f"/v1/sessions/{created['session_id']}/join", headers=AN).json()
    state = send(client, state, reply_text(state), "k0")  # the theory question: now the first item
    assert state["teaching"]["awaiting"] == "ANSWER"
    state = send(client, state, WORRY, "k1")
    assert state["teaching"]["awaiting"] == "ANSWER" and state["transcript"][-1]["text"].startswith(
        "Cô nghe con"
    )

    overview = client.get("/v1/teachers/class", headers=TEACHER).json()
    [student] = [s for s in overview["students"] if s["display_name"] == "An"]
    first = student["attention"][0]
    assert first["kind"] == "SAFETY" and first["session_id"] == created["session_id"] and first["count"] == 1

    transcript = client.get(f"/v1/sessions/{created['session_id']}/transcript", headers=TEACHER).json()
    said = [t for s in transcript["segments"] for t in s["turns"] if t["actor"] == "student"]
    assert [t["student"]["safety"] for t in said if t["text"] == WORRY] == [True]
    assert not any(t["student"]["safety"] for t in said if t["text"] != WORRY)
