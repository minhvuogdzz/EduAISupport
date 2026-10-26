"""The teacher's transcript over the session API (REFORM 4.4): every turn the tutor can write comes back as
a 200, not as a ``ResponseValidationError``. Always on the in-memory database, with templates only.

The two turns that used to fail are the ones written after the view models were drawn: the conductor's own
hint (``UNSTICK``) and an answer taken from the trusted web source (``WEB``)."""

from typing import Literal, get_args, get_origin

import pytest
from cavat.config import get_settings
from cavat.core.events import (
    ContextRouted,
    QuestionParked,
    RetellJudged,
    StudentMessage,
    TeachMessageSent,
    TutorMessageSent,
)
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.rag.service import RagService
from cavat.modules.session import api as session_api
from cavat.modules.session import chapter_service, service
from cavat.modules.session.api import (
    ConductedView,
    RetellView,
    StudentAnnotation,
    TeachAnnotation,
    TutorAnnotation,
    get_database,
)
from cavat.modules.teaching.web import WebPage
from fastapi.testclient import TestClient
from test_chapter_session_api import MINH, TEACHER, advance, start

BOILING = WebPage(
    title="Điểm sôi",
    url="https://vi.wikipedia.org/wiki/Điểm_sôi",
    text="Điểm sôi là nhiệt độ mà chất lỏng chuyển thành hơi.",
    host="vi.wikipedia.org",
)


class FakeSource:
    name = "Wikipedia tiếng Việt"

    def lookup(self, query):
        return BOILING


@pytest.fixture
async def memory(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)
    monkeypatch.setattr(
        session_api,
        "_rag_service",
        RagService(service.DEMO_SCHOOL_ID, chapter_service.chapters, embedder=lambda: None),
    )
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)
    get_settings.cache_clear()


@pytest.fixture
def client(memory):
    return TestClient(app)


def turns_of(client, state: dict) -> list[dict]:
    got = client.get(f"/v1/sessions/{state['session_id']}/transcript", headers=TEACHER)
    assert got.status_code == 200, got.text
    return [t for segment in got.json()["segments"] for t in segment["turns"]]


def test_a_hint_the_conductor_gave_is_in_the_transcript(client):
    """A child the same redirect does not reach is given the next hint by the conductor: that turn is
    ``UNSTICK``, with what the conductor found in the message that led to it."""
    state = advance(client, start(client), "u0")  # the theory question, then the first item
    state = advance(client, state, "u1", "😭😭 ko bít lm jjjj")
    state = advance(client, state, "u2", "xyz abc def")
    state = advance(client, state, "u3", "xyz abc def")

    turns = turns_of(client, state)
    unstuck = [t for t in turns if t["student"] and t["student"]["kind"] == "UNSTICK"]
    assert unstuck and unstuck[0]["actor"] == "student"
    assert unstuck[0]["text"].startswith("(Gia sư tự đưa gợi ý")
    # the loop read the cleaned words; what the child typed is kept next to what the conductor found in it
    emoji = next(t for t in turns if t["text"] == "ko bít lm j")
    assert emoji["student"]["conducted"] == {
        "raw": "😭😭 ko bít lm jjjj",
        "signals": ["EMOJI", "STRETCHED", "TEENCODE"],
        "route": "PASS",
    }
    routes = [t["student"]["conducted"]["route"] for t in turns if t["student"] and t["student"]["conducted"]]
    assert routes == ["PASS", "UNSTICK"]


def test_an_answer_from_the_trusted_web_source_is_in_the_transcript(client, monkeypatch):
    monkeypatch.setattr(session_api, "_web_source", lambda: FakeSource())
    state = start(client)
    asked = advance(client, state, "w0", "điểm sôi là gì vậy cô")

    teach = [t["teach"] for t in turns_of(client, asked) if t.get("teach")]
    answer = teach[-1]
    assert answer["kind"] == "ANSWER" and answer["source"] == "WEB"
    assert answer["sources"] == ["Wikipedia tiếng Việt: Điểm sôi · https://vi.wikipedia.org/wiki/Điểm_sôi"]


def test_the_voice_of_the_child_and_the_purpose_of_a_retell_are_in_the_transcript(client):
    """The words a child said (ADR-030) are marked as spoken; a retell says whether it retold or recalled."""
    state = start(client)
    n = 0
    while state["teaching"]["awaiting"] != "RETELL":
        state = advance(client, state, f"v{n}")
        n += 1
    sid = state["session_id"]
    body = {
        "item_attempt_id": state["teaching"]["input_id"],
        "kind": "ANSWER",
        "content": {"text": "Con không nhớ ạ."},
        "modality": "VOICE",
        "expected_state_version": state["state_version"],
    }
    sent = client.post(
        f"/v1/sessions/{sid}/responses", json=body, headers={**MINH, "Idempotency-Key": "v-voice"}
    )
    assert sent.status_code == 200, sent.text
    state = client.get(f"/v1/sessions/{sid}/state", headers=MINH).json()

    turns = turns_of(client, state)
    spoken = next(t for t in turns if t["text"] == "Con không nhớ ạ.")
    assert spoken["student"]["voice"] is True
    assert spoken["student"]["retell"]["purpose"] == "RETELL"
    typed = next(t for t in turns if t["actor"] == "student" and t["text"] != "Con không nhớ ạ.")
    assert typed["student"]["voice"] is False


def values(annotation) -> set[str]:
    """The strings a ``Literal`` field allows, through ``X | None``."""
    if get_origin(annotation) is Literal:
        return set(get_args(annotation))
    return set().union(*(values(arg) for arg in get_args(annotation)))


def allowed(model, field: str) -> set[str]:
    return values(model.model_fields[field].annotation)


def test_the_transcript_views_allow_every_value_the_events_can_carry():
    """The view models repeat the ``Literal`` sets of the event payloads. This is what failed: a value added
    to an event (``UNSTICK``, ``WEB``) and not to the view is a 500 on the teacher's page, so the sets are
    compared here instead of being found one at a time by a teacher."""
    assert allowed(StudentMessage, "kind") <= allowed(StudentAnnotation, "kind")
    assert {"HINT_REQUEST", "CHOICE", "UNSTICK"} <= allowed(StudentAnnotation, "kind")
    assert "UNSTICK" in allowed(ContextRouted, "route")  # the conductor's own hint is the turn "UNSTICK"
    assert allowed(TeachMessageSent, "source") <= allowed(TeachAnnotation, "source")
    assert allowed(QuestionParked, "reason") <= allowed(TeachAnnotation, "parked")
    assert allowed(TutorMessageSent, "source") <= allowed(TutorAnnotation, "source")
    assert allowed(RetellJudged, "purpose") <= allowed(RetellView, "purpose")
    assert allowed(ContextRouted, "route") <= allowed(ConductedView, "route")
