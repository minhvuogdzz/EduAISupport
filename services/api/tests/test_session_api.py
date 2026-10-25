"""Session API (T08): one lesson end to end, idempotency, optimistic concurrency, session rules.

Always runs on the in-memory database (the dependency is overridden), never on Atlas.
"""

from fractions import Fraction

import httpx
import pytest
from cavat.core.events import PAYLOAD_MODELS, EventType
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.assessment.math_checker import check_answer
from cavat.modules.assessment.vi_numbers import parse_literal
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    CompareAnswer,
    NumericAnswer,
    OrderAnswer,
)
from cavat.modules.session import api as session_api
from cavat.modules.session import service
from cavat.modules.session.api import get_database
from cavat.modules.session.repository import LearningSessionRepository
from fastapi.testclient import TestClient

PKG = service.lesson_packages()[service.DEFAULT_LESSON_ID]
MINH = {"X-Demo-Student": "minh"}
TEACHER = {"X-Demo-Teacher": "1"}


@pytest.fixture(autouse=True)
def templates_only(monkeypatch):
    """No test may call a real model, whatever TUTOR_RENDERER says in .env; a test installs a fake router."""
    monkeypatch.setattr(session_api, "tutor_router", lambda: None)


@pytest.fixture
async def memory():
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)


@pytest.fixture
def client(memory):
    return TestClient(app)


def correct_text(item_id: str) -> str:
    item, ans = PKG.item(item_id), PKG.item(item_id).answer
    if isinstance(ans, CompareAnswer):
        left, right = parse_literal(ans.left).value, parse_literal(ans.right).value
        sign = "<" if left < right else ">" if left > right else "="
        larger, smaller = (ans.left, ans.right) if left > right else (ans.right, ans.left)
        text = {"sign": sign, "larger": larger, "smaller": smaller}[ans.ask]
    elif isinstance(ans, OrderAnswer):
        key = lambda n: Fraction(parse_literal(n).value)  # noqa: E731
        text = "; ".join(sorted(ans.numbers, key=key, reverse=ans.direction == "desc"))
    elif isinstance(ans, NumericAnswer):
        text = ans.value
    elif isinstance(ans, ChoiceAnswer):
        text = next(o.id for o in ans.options if o.correct)
    elif isinstance(ans, BooleanAnswer):
        text = "đúng" if ans.value else "sai"
    else:
        raise AssertionError(item_id)
    assert check_answer(item, text, PKG).outcome == "CORRECT", (item_id, text)
    return text


def start(client, headers=MINH):
    created = client.post(
        "/v1/sessions",
        json={"student_display_name": "Minh", "lesson_id": service.DEFAULT_LESSON_ID},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["lifecycle_state"] == "READY" and created.json()["item"] is None
    joined = client.post(f"/v1/sessions/{created.json()['session_id']}/join", headers=headers)
    assert joined.status_code == 200, joined.text
    return joined.json()


def send(client, state, text, key, headers=MINH, **override):
    body = {
        "item_attempt_id": state["item"]["item_attempt_id"],
        "kind": "ANSWER",
        "content": {"text": text},
        "modality": "TEXT",
        "expected_state_version": state["state_version"],
        **override,
    }
    url = f"/v1/sessions/{state['session_id']}/responses"
    return client.post(url, json=body, headers={**headers, "Idempotency-Key": key})


def get_state(client, state, headers=MINH):
    return client.get(f"/v1/sessions/{state['session_id']}/state", headers=headers).json()


async def stored(memory, state):
    return await LearningSessionRepository(memory, service.DEMO_SCHOOL_ID).get(state["session_id"])


def test_join_shows_the_first_item_without_its_answer(client):
    state = start(client)
    assert state["lifecycle_state"] == "ACTIVE"
    assert state["item"]["item_id"] == "CC-01" and state["activity"]["type"] == "CONCEPT_CHECK"
    assert state["allowed_commands"] == ["ANSWER", "HINT_REQUEST"]
    assert state["progress"] == {"items_done": 0, "items_total": 8}
    assert [t["actor"] for t in state["transcript"]] == ["tutor"]
    assert all(set(o) == {"id", "text"} for o in state["item"]["options"])
    # joining again changes nothing
    again = client.post(f"/v1/sessions/{state['session_id']}/join", headers=MINH).json()
    assert again["state_version"] == state["state_version"]


async def test_a_whole_lesson_reaches_the_summary(client, memory):
    state = start(client)
    for n in range(60):
        if state["lifecycle_state"] != "ACTIVE":
            break
        item = state["item"]
        explaining = item["expecting"] == "EXPLANATION"
        text = "vì con so sánh từng hàng từ trái sang phải" if explaining else correct_text(item["item_id"])
        ack = send(client, state, text, f"k{n}")
        assert ack.status_code == 200, ack.text
        state = get_state(client, state)
        assert state["state_version"] == ack.json()["state_version"]
    assert state["lifecycle_state"] == "COMPLETED" and state["item"] is None
    assert state["activity"]["type"] == "SUMMARY" and state["allowed_commands"] == []
    assert state["progress"] == {"items_done": 8, "items_total": 8}
    assert state["transcript"][-1]["actor"] == "tutor" and state["transcript"][-1]["move"] is None

    session = await stored(memory, state)
    types = [e.event_type for e in session.events]
    assert types.count("ITEM_RESOLVED") == 8 and types[-1] == "SESSION_COMPLETED"
    assert [e.sequence_no for e in session.events] == list(range(1, len(types) + 1))
    started = [e.payload["activity_type"] for e in session.events if e.event_type == "ACTIVITY_STARTED"]
    assert started == ["CONCEPT_CHECK", "GUIDED_PRACTICE", "EXIT_ASSESSMENT"]
    for e in session.events:
        model = PAYLOAD_MODELS.get(EventType(e.event_type))
        if model is not None:
            model.model_validate(e.payload)
    assert all(e.school_id == service.DEMO_SCHOOL_ID for e in session.events)
    assert session.ended_at is not None and session.events_copied_upto == len(types)


async def test_resending_a_command_writes_nothing_new(client, memory):
    state = start(client)
    first = send(client, state, "con không biết", "same-key")
    count = len((await stored(memory, state)).events)
    # resent with the now stale version: the key wins and the first answer comes back
    second = send(client, state, "con không biết", "same-key")
    assert second.status_code == 200 and second.json() == first.json()
    assert first.json()["tutor_turn_id"] is not None
    assert len((await stored(memory, state)).events) == count


def test_stale_state_version_is_a_conflict(client):
    state = start(client)
    assert send(client, state, "con không biết", "k1").status_code == 200
    stale = send(client, state, correct_text("CC-01"), "k2")
    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["code"] == "STATE_VERSION_CONFLICT"
    assert error["details"] == {"expected": state["state_version"], "current": state["state_version"] + 1}


def test_session_rules_are_enforced_by_the_backend(client):
    state = start(client)
    sid = state["session_id"]
    assert client.get(f"/v1/sessions/{sid}/state").status_code == 401
    other = client.get(f"/v1/sessions/{sid}/state", headers={"X-Demo-Student": "lan"})
    assert other.status_code == 403 and other.json()["error"]["code"] == "NOT_SESSION_OWNER"
    assert client.get("/v1/sessions/nope/state", headers=MINH).json()["error"]["code"] == "NOT_FOUND"

    stale_item = send(client, state, "<", "k1", item_attempt_id="old")
    assert stale_item.status_code == 409 and stale_item.json()["error"]["code"] == "STALE_ITEM"
    no_key = client.post(
        f"/v1/sessions/{sid}/responses",
        json={
            "item_attempt_id": state["item"]["item_attempt_id"],
            "content": {"text": "<"},
            "expected_state_version": state["state_version"],
        },
        headers=MINH,
    )
    assert no_key.status_code == 422 and no_key.json()["error"]["code"] == "VALIDATION_ERROR"
    choice = client.post(
        f"/v1/sessions/{sid}/choices",
        json={"choice_id": "HINT", "expected_state_version": state["state_version"]},
        headers={**MINH, "Idempotency-Key": "k2"},
    )
    assert choice.status_code == 409
    assert choice.json()["error"]["code"] == "COMMAND_NOT_ALLOWED_IN_ACTIVITY"
    too_long = send(client, state, "x" * 501, "k3")
    assert too_long.status_code == 422
    assert get_state(client, state)["state_version"] == state["state_version"]  # nothing was written

    created = client.post("/v1/sessions", json={"lesson_id": service.DEFAULT_LESSON_ID}, headers=MINH).json()
    not_joined = send(client, {**state, "session_id": created["session_id"]}, "<", "k4")
    assert not_joined.status_code == 409 and not_joined.json()["error"]["code"] == "INVALID_STATE"


def test_hint_request_delivers_a_hint(client):
    state = start(client)
    for _ in range(2):  # get past the concept check to a practice item
        state = advance(client, state)
    assert state["item"]["item_id"] == "GP-01"
    ack = client.post(
        f"/v1/sessions/{state['session_id']}/hint-requests",
        json={
            "item_attempt_id": state["item"]["item_attempt_id"],
            "expected_state_version": state["state_version"],
        },
        headers={**MINH, "Idempotency-Key": "hint-1"},
    )
    assert ack.status_code == 200, ack.text
    after = get_state(client, state)
    student, tutor = after["transcript"][-2:]
    assert (student["actor"], tutor["actor"]) == ("student", "tutor")
    assert tutor["turn_id"] == ack.json()["tutor_turn_id"]
    assert after["item"]["item_attempt_id"] == state["item"]["item_attempt_id"]
    # "Xin gợi ý" gets the hint at once (DI-35).
    assert (tutor["move"], tutor["hint_level"]) == ("HINT", 1)
    assert after["pending_choice"] is None

    # A typed "con không biết" gets the choice, once per item; the offer itself carries no hint level.
    assert send(client, after, "con không biết", "dont-know-1").status_code == 200
    offered = get_state(client, state)
    assert (offered["transcript"][-1]["move"], offered["transcript"][-1]["hint_level"]) == (
        "OFFER_CHOICE",
        None,
    )
    assert [c["choice_id"] for c in offered["pending_choice"]] == ["HINT", "RETRY"]

    chosen = client.post(
        f"/v1/sessions/{state['session_id']}/choices",
        json={"choice_id": "HINT", "expected_state_version": offered["state_version"]},
        headers={**MINH, "Idempotency-Key": "choice-1"},
    )
    assert chosen.status_code == 200, chosen.text
    hinted = get_state(client, state)
    assert (hinted["transcript"][-1]["move"], hinted["transcript"][-1]["hint_level"]) == ("HINT", 2)
    assert hinted["pending_choice"] is None


def advance(client, state):
    """Answer the current item correctly (and its "vì sao" if asked) until the next item is shown."""
    attempt = state["item"]["item_attempt_id"]
    for n in range(6):
        explaining = state["item"]["expecting"] == "EXPLANATION"
        text = "vì con so sánh từng hàng" if explaining else correct_text(state["item"]["item_id"])
        assert send(client, state, text, f"{attempt}-{n}").status_code == 200
        state = get_state(client, state)
        if state["item"] is None or state["item"]["item_attempt_id"] != attempt:
            return state
    raise AssertionError("item did not resolve")


def test_wrong_answers_never_leak_the_answer_or_internal_labels(client):
    state = start(client)
    for _ in range(2):
        state = advance(client, state)
    wrong = ">" if correct_text("GP-01") == "<" else "<"
    for n in range(3):
        assert send(client, state, wrong, f"w{n}").status_code == 200
        state = get_state(client, state)
    text = str(state)
    assert "DEC-M" not in text and "rule_ids" not in text and "misconception" not in text
    answer = PKG.item("GP-01").answer
    stated = f"{answer.left} {correct_text('GP-01')} {answer.right}"
    assert all(stated not in t["text"] for t in state["transcript"] if t["actor"] == "tutor")


def llm_router(monkeypatch, fake):
    monkeypatch.setattr(
        session_api, "tutor_router", lambda: AIRouter(chat_provider=fake, max_calls_per_session=15)
    )
    return fake


class RewordingModel(FakeChatModel):
    """A model that does its job: it rewords the approved sentence ([MỤC TIÊU LƯỢT NÀY]) of the prompt."""

    PREFIXES = ("Minh ơi, ", "Con nghe cô nhé, ")

    def chat(self, request, model):
        lines = request.messages[-1].content.splitlines()
        anchor = lines[next(i for i, line in enumerate(lines) if line.startswith("[MỤC TIÊU LƯỢT NÀY]")) + 1]
        prefix = self.PREFIXES[len(self.calls) % len(self.PREFIXES)]
        message = f"{prefix}{anchor[0].lower()}{anchor[1:]}"
        self._queues[None].append(reply(message, safety_flag=len(self.calls) == 1))
        return super().chat(request, model)


def reply(message, safety_flag=False):
    return {"message": message, "safety_flag": safety_flag, "policy_feedback": ""}


async def test_llm_phrases_the_live_turn_and_past_turns_are_never_sent_again(client, memory, monkeypatch):
    fake = llm_router(monkeypatch, RewordingModel([]))
    state = start(client)
    for _ in range(2):
        state = advance(client, state)  # concept checks answered correctly: template-only moves
    assert state["item"]["item_id"] == "GP-01" and not fake.calls
    wrong = ">" if correct_text("GP-01") == "<" else "<"

    assert send(client, state, wrong, "w1").status_code == 200
    state = get_state(client, state)
    first = state["transcript"][-1]["text"]
    assert first.startswith("Minh ơi, ") and len(fake.calls) == 1
    assert send(client, state, wrong, "w2").status_code == 200
    state = get_state(client, state)
    assert state["transcript"][-1]["text"].startswith("Con nghe cô nhé, ")
    assert len(fake.calls) == 2  # the first turn was replayed with templates, not sent to the model again
    prompt = fake.calls[1][1].messages[-1].content
    assert first in prompt and "Minh" in prompt  # history comes from the event log

    session = await stored(memory, state)
    assert session.state.activity["llm_calls"] == 2
    sources = [e.payload["source"] for e in session.events if e.event_type == "TUTOR_MESSAGE_SENT"]
    assert sources[-2:] == ["LLM", "LLM"]
    assert [e.event_type for e in session.events].count("SAFETY_FLAGGED") == 1


def test_a_leaking_model_falls_back_to_the_template(client, monkeypatch):
    answer = PKG.item("GP-01").answer
    leak = f"Đáp án là {answer.left} {correct_text('GP-01')} {answer.right} nhé. Con hiểu chưa?"
    fake = llm_router(monkeypatch, FakeChatModel([reply(leak), reply(leak)]))
    state = start(client)
    for _ in range(2):
        state = advance(client, state)
    wrong = ">" if correct_text("GP-01") == "<" else "<"
    assert send(client, state, wrong, "w1").status_code == 200
    state = get_state(client, state)
    assert len(fake.calls) == 2 and leak not in [t["text"] for t in state["transcript"]]


def test_after_the_probe_the_screen_asks_for_words_and_the_reply_is_not_graded(client):
    state = start(client)
    sid = state["session_id"]
    for _ in range(2):
        state = advance(client, state)
    assert send(client, state, "=", "p1").status_code == 200  # wrong, no known misconception: PROBE
    state = get_state(client, state)
    assert state["transcript"][-1]["move"] == "PROBE"
    assert state["item"]["expecting"] == "EXPLANATION"
    assert state["allowed_commands"] == ["ANSWER", "HINT_REQUEST"]  # a hint may still be asked for

    assert send(client, state, "thì nó bằng thật mà", "p2", kind="EXPLANATION").status_code == 200
    state = get_state(client, state)
    hint = state["transcript"][-1]
    assert (hint["move"], hint["hint_level"]) == ("HINT", 1)
    assert state["item"]["expecting"] == "ANSWER"

    transcript = client.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER).json()
    block = next(seg for seg in transcript["segments"] if seg.get("item_id") == "GP-01")
    said = [t["student"] for t in block["turns"] if t["actor"] == "student"]
    assert [(s["kind"], s["outcome"]) for s in said] == [("ANSWER", "WRONG"), ("EXPLANATION", None)]
    assert block["turns"][-1]["tutor"]["source"] == "TEMPLATE"  # the item's own level 1 hint


def test_teacher_sees_outcomes_misconceptions_and_rules(client):
    state = start(client)
    sid = state["session_id"]
    for _ in range(2):
        state = advance(client, state)
    wrong = ">" if correct_text("GP-01") == "<" else "<"
    assert send(client, state, f"0,25 {wrong} 0,3", "w1").status_code == 200

    assert client.get("/v1/sessions").status_code == 401  # the teacher header is required
    assert client.get(f"/v1/sessions/{sid}/transcript", headers=MINH).status_code == 401
    listed = client.get("/v1/sessions", headers=TEACHER).json()
    assert [s["session_id"] for s in listed] == [sid]
    assert listed[0]["engine"] == "live" and listed[0]["student_display_name"] == "Minh"
    assert listed[0]["progress"] == {"items_done": 2, "items_total": 8}
    assert listed[0]["misconception_ids"] == ["DEC-M01"]

    transcript = client.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER).json()
    assert transcript["session"] == listed[0]
    items = [seg for seg in transcript["segments"] if seg["kind"] == "item"]
    assert [(i["item_id"], i["position"], i["resolution"]) for i in items] == [
        ("CC-01", 1, "INDEPENDENT"),
        ("CC-02", 2, "INDEPENDENT"),
        ("GP-01", 3, None),
    ]
    assert items[0]["activity_type"] == "CONCEPT_CHECK" and items[0]["stem"] == PKG.item("CC-01").stem
    first = items[0]["turns"]
    assert first[0]["tutor"]["move"] == "PRESENT" and first[0]["tutor"]["rule_ids"] == ["R-PRESENT"]
    assert (first[1]["actor"], first[1]["student"]["outcome"]) == ("student", "CORRECT")

    answer, reply = items[2]["turns"][-2:]
    assert answer["student"]["kind"] == "ANSWER" and answer["student"]["outcome"] == "WRONG"
    assert answer["student"]["normalized_answer"]
    assert answer["student"]["misconception"]["id"] == "DEC-M01"
    assert answer["student"]["misconception"]["name"] == PKG.misconception("DEC-M01").name
    assert reply["actor"] == "tutor" and reply["tutor"]["rule_ids"] and reply["tutor"]["source"] == "TEMPLATE"
    assert client.get("/v1/sessions/nope/transcript", headers=TEACHER).status_code == 404


async def walk_whole_lesson(http: httpx.AsyncClient) -> dict:
    created = await http.post(
        "/v1/sessions",
        json={"student_display_name": "Minh", "lesson_id": service.DEFAULT_LESSON_ID},
        headers=MINH,
    )
    assert created.status_code == 201, created.text
    sid = created.json()["session_id"]
    state = (await http.post(f"/v1/sessions/{sid}/join", headers=MINH)).json()
    for n in range(60):
        if state["lifecycle_state"] != "ACTIVE":
            break
        explaining = state["item"]["expecting"] == "EXPLANATION"
        body = {
            "item_attempt_id": state["item"]["item_attempt_id"],
            "content": {
                "text": "vì con so sánh từng hàng" if explaining else correct_text(state["item"]["item_id"])
            },
            "expected_state_version": state["state_version"],
        }
        ack = await http.post(
            f"/v1/sessions/{sid}/responses", json=body, headers={**MINH, "Idempotency-Key": f"walk-{n}"}
        )
        assert ack.status_code == 200, ack.text
        state = (await http.get(f"/v1/sessions/{sid}/state", headers=MINH)).json()
    return state


async def test_a_whole_lesson_on_the_database(db):
    """The session API on real storage: the in-memory database, and a throwaway ``cavat_test_*``
    database on Atlas when MONGODB_URI is set (guarded and dropped by the ``db`` fixture)."""
    app.dependency_overrides[get_database] = lambda: db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            state = await walk_whole_lesson(http)
            assert state["lifecycle_state"] == "COMPLETED"
            assert state["progress"] == {"items_done": 8, "items_total": 8}
            sid = state["session_id"]
            listed = (await http.get("/v1/sessions", headers=TEACHER)).json()
            assert [s["session_id"] for s in listed] == [sid] and listed[0]["lifecycle_state"] == "COMPLETED"
            transcript = (await http.get(f"/v1/sessions/{sid}/transcript", headers=TEACHER)).json()
            assert [seg["kind"] for seg in transcript["segments"]].count("item") == 8
            assert transcript["segments"][-1]["kind"] == "session"
    finally:
        app.dependency_overrides.pop(get_database, None)
    session = await LearningSessionRepository(db, service.DEMO_SCHOOL_ID).get(sid)
    assert session.events_copied_upto == len(session.events) > 0
