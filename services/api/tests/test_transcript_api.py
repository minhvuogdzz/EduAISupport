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
    # Semantic listening preserves the actual words; normalization only supplies analysis signals.
    emoji = next(t for t in turns if t["text"] == "😭😭 ko bít lm jjjj")
    assert emoji["student"]["conducted"] == {
        "raw": "😭😭 ko bít lm jjjj",
        "signals": ["EMOJI", "STRETCHED", "TEENCODE"],
        "route": "PASS",
    }
    routes = [t["student"]["conducted"]["route"] for t in turns if t["student"] and t["student"]["conducted"]]
    assert routes == ["PASS", "UNSTICK"]


def test_a_key_slip_is_asked_about_and_the_teacher_sees_how_it_was_read(client):
    """REFORM-5, through the API: "ki" at the theory question and "kkk" at an item are asked about (nothing
    graded, nothing praised) and the teacher's transcript says what the tutor made of them (a 200, not a 500
    on the new labels)."""
    state = start(client)
    asked = advance(client, state, "s0", "ki")  # at the theory question
    assert asked["teaching"]["awaiting"] == "THEORY_REPLY"
    assert asked["transcript"][-1]["text"].endswith("?") and "Đúng rồi" not in asked["transcript"][-1]["text"]
    state = advance(client, asked, "s1")  # the right reply, then the first item
    assert state["teaching"]["awaiting"] == "ANSWER"
    slipped = advance(client, state, "s2", "kkk")
    helped = advance(client, slipped, "s3", "tt")

    turns = turns_of(client, helped)
    reads = [t["student"]["read"] for t in turns if t["student"] and t["student"]["read"]]
    assert [(r["label"], r["source"]) for r in reads] == [
        ("AMBIGUOUS_TYPO", "RULE"),
        ("GIBBERISH", "RULE"),
        ("GIBBERISH", "RULE"),
    ]
    for after in (slipped, helped):  # the tutor's reply to a slip: one question, no praise
        said = after["transcript"][-1]["text"]
        assert said.count("?") == 1 and "Đúng rồi" not in said, said
    assert slipped["transcript"][-1]["text"] != helped["transcript"][-1]["text"]  # asked once, then helped


def test_an_answer_from_the_trusted_web_source_is_in_the_transcript(client, monkeypatch):
    from cavat.modules.rag.chunks import Chunk
    from cavat.modules.rag.retrieve import RagIndex
    from cavat.modules.teaching.official_web import BOOK_URL, HOST
    from cavat.modules.teaching.web import WebPage
    from test_grounded import ScriptedRouter

    state = start(client)
    page = WebPage(
        "SGV – Toán 5",
        BOOK_URL,
        "Mẫu số cho biết một hình được chia thành bao nhiêu phần bằng nhau.",
        HOST,
        asked="mẫu số",
        excerpt_hash="test-hash",
    )

    class Source:
        name = "NXB Giáo dục Việt Nam"

        def lookup(self, query):
            assert query == "mẫu số"
            return page

    async def index(_):
        return RagIndex(
            [
                Chunk(
                    "seed",
                    "Ý bài đang học.",
                    "theory",
                    "math-g5-decimals",
                    "KC-DEC-FRAC",
                    "chapter",
                    "Phân số thập phân",
                    True,
                )
            ],
            None,
            {"KC-DEC-FRAC": set()},
        )

    monkeypatch.setattr(session_api, "_web_source", lambda: Source())
    monkeypatch.setattr(session_api._rag_service, "current", index)
    router = ScriptedRouter(
        "Mẫu số cho biết cả hình được chia thành bao nhiêu phần bằng nhau.",
        {"supported": True, "quotes": [page.text]},
    )
    monkeypatch.setattr(session_api, "tutor_router", lambda: router)
    asked = advance(client, state, "w0", "mẫu số là gì vậy cô")

    teach = [t["teach"] for t in turns_of(client, asked) if t.get("teach")]
    answer = teach[-1]
    assert answer["kind"] == "ANSWER" and answer["source"] == "WEB" and answer["grounded"], (
        answer,
        [(r.schema_name, r.messages[1].content[-300:]) for r in router.requests],
    )
    assert answer["sources"] == [f"NXB Giáo dục Việt Nam: SGV – Toán 5 · {BOOK_URL}"]
    assert answer["web"] == {
        "query": "mẫu số",
        "title": page.title,
        "url": BOOK_URL,
        "excerpt": page.text,
        "excerpt_hash": "test-hash",
    }


def test_greetings_through_the_api_do_not_grade_or_move_the_pending_question(client):
    state = start(client)
    prompt = state["teaching"]["prompt"]
    for i in range(4):
        state = advance(client, state, f"hi-{i}", "hi")
        assert state["teaching"]["awaiting"] == "THEORY_REPLY"
        assert state["teaching"]["prompt"] == prompt
        assert state["transcript"][-1]["text"] == "Cô chào con! Cô đang nghe đây."
    turns = turns_of(client, state)
    assert all(not t["student"] or t["student"]["outcome"] is None for t in turns)
    assert not any(t.get("tutor", {}).get("hint_level") for t in turns if t.get("tutor"))


def test_the_voice_of_the_child_and_the_purpose_of_a_retell_are_in_the_transcript(client):
    """The words a child said (ADR-030) are marked as spoken; a retell says whether it retold or recalled."""
    state = start(client)
    n = 0
    while state["teaching"]["awaiting"] != "RETELL":
        state = advance(client, state, f"v{n}")
        n += 1
    sid = state["session_id"]
    for key, said in (("v-voice-1", "Con không nhớ ạ."), ("v-voice-2", "Con vẫn không nhớ ạ.")):
        # the first is taught again (REFORM-6): the retell is judged on the second
        body = {
            "item_attempt_id": state["teaching"]["input_id"],
            "kind": "ANSWER",
            "content": {"text": said},
            "modality": "VOICE",
            "expected_state_version": state["state_version"],
        }
        sent = client.post(
            f"/v1/sessions/{sid}/responses", json=body, headers={**MINH, "Idempotency-Key": key}
        )
        assert sent.status_code == 200, sent.text
        state = client.get(f"/v1/sessions/{sid}/state", headers=MINH).json()

    turns = turns_of(client, state)
    spoken = next(t for t in turns if t["text"] == "Con vẫn không nhớ ạ.")
    assert spoken["student"]["voice"] is True
    assert spoken["student"]["retell"]["purpose"] == "RETELL"
    typed = next(
        t
        for t in turns
        if t["actor"] == "student" and t["text"] not in ("Con không nhớ ạ.", "Con vẫn không nhớ ạ.")
    )
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
