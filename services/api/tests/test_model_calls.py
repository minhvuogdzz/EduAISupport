"""CFG-2: every model call of a session command is written down: the model that answered, the tokens the
provider counted, the gateway's estimate before sending, and each step down the chain (MODEL_FALLBACK).

No call to Groq: behind the real router, a provider where Qwen is out of quota and gpt-oss answers.
"""

from __future__ import annotations

import json

import pytest
from cavat.core.events import PAYLOAD_MODELS, EventType
from cavat.core.memory_db import InMemoryDatabase
from cavat.db import ensure_indexes
from cavat.main import app
from cavat.modules.ai_gateway.base import (
    ChatMessage,
    ChatRequest,
    ChatResult,
    ModelClass,
    PromptTooLong,
    QuotaExceeded,
    Usage,
    estimate_prompt_tokens,
)
from cavat.modules.ai_gateway.router import AIRouter, RecordingRouter
from cavat.modules.session import api as session_api
from cavat.modules.session.api import get_database
from cavat.modules.session.model_calls import model_call_events
from fastapi.testclient import TestClient

QWEN, GPT_OSS = "qwen/qwen3.8-27b", "openai/gpt-oss-120b"
SCHEMA = {
    "type": "object",
    "properties": {"message": {"type": "string"}},
    "required": ["message"],
    "additionalProperties": False,
}
HINT = {"message": "Con thử so sánh hai phần mười xem?", "safety_flag": False, "policy_feedback": ""}


class QwenOutOfQuota:
    """Qwen answers 429; gpt-oss writes the tutor's turns and the provider counts the tokens. The other
    prompts (reading, move choice, grounded answer) are out of quota on every model."""

    def chat(self, request, model):
        if model == QWEN or request.schema_name != "tutor_turn":
            raise QuotaExceeded("429", model=model)
        return ChatResult(model, json.dumps(HINT, ensure_ascii=False), dict(HINT), Usage(812, 31, 843))


def request(schema_name: str = "tutor_turn") -> ChatRequest:
    messages = (ChatMessage("system", "Gia sư Toán lớp 5."), ChatMessage("user", "con không biết"))
    return ChatRequest(messages=messages, json_schema=SCHEMA, schema_name=schema_name)


def payloads(events):
    return [PAYLOAD_MODELS[EventType(e.event_type)].model_validate(e.payload) for e in events]


def test_the_recording_router_keeps_each_call_and_lends_the_rest():
    shared = AIRouter(chat_provider=QwenOutOfQuota(), max_calls_per_session=9)
    router = RecordingRouter(shared)
    sent = request()
    outcome = router.chat(ModelClass.TUTOR_REASONING, sent, calls_used=0)
    [call] = router.calls
    assert call.outcome is outcome and call.purpose == "tutor_turn" and call.messages == 2
    assert call.estimated_tokens == estimate_prompt_tokens(sent)
    assert call.prompt_chars == len("Gia sư Toán lớp 5.") + len("con không biết")
    assert call.schema_chars == len(json.dumps(SCHEMA, ensure_ascii=False))
    assert router.max_calls_per_session == 9 and router.quota is shared.quota


def test_a_step_down_the_chain_is_a_fallback_and_the_answer_carries_its_tokens():
    router = RecordingRouter(AIRouter(chat_provider=QwenOutOfQuota()))
    router.chat(ModelClass.TUTOR_REASONING, request(), calls_used=0)
    events = model_call_events(router.calls, "attempt-1")
    assert [e.event_type for e in events] == ["MODEL_FALLBACK", "MODEL_CALLED"]
    assert {e.item_attempt_id for e in events} == {"attempt-1"}
    moved, called = payloads(events)
    assert (moved.from_model, moved.to_model, moved.reason) == (QWEN, GPT_OSS, "QUOTA")
    assert moved.purpose == called.purpose == "tutor_turn"
    assert (called.model, called.fallback_reason) == (GPT_OSS, None)
    assert (called.prompt_tokens, called.completion_tokens) == (812, 31)
    assert [(a.model, a.sent, a.error) for a in called.attempts] == [
        (QWEN, True, "QuotaExceeded"),
        (GPT_OSS, True, None),
    ]


def test_a_call_no_model_answered_says_why_and_one_that_reached_no_model_leaves_nothing():
    router = RecordingRouter(AIRouter(chat_provider=QwenOutOfQuota(), max_calls_per_session=2))
    router.chat(ModelClass.LIGHTWEIGHT, request("reading"), calls_used=0)  # 429 on Qwen and gpt-oss-20b
    router.chat(ModelClass.LIGHTWEIGHT, request("reading"), calls_used=2)  # the cap is used up
    moved, called = payloads(model_call_events(router.calls))
    assert (moved.from_model, moved.to_model) == (QWEN, "openai/gpt-oss-20b")
    assert called.model is None and called.fallback_reason == "quota_exceeded"
    assert called.prompt_tokens == 0 and called.estimated_tokens > 0


def test_a_prompt_refused_before_sending_is_called_but_not_a_fallback():
    class TooLong:
        def chat(self, request, model):
            raise PromptTooLong("too long", model=model, estimated_tokens=3100)

    router = RecordingRouter(AIRouter(chat_provider=TooLong()))
    router.chat(ModelClass.TUTOR_REASONING, request(), calls_used=0)
    [called] = payloads(model_call_events(router.calls))
    assert called.fallback_reason == "prompt_too_long"
    assert [(a.model, a.sent) for a in called.attempts] == [(QWEN, False)]


@pytest.fixture
async def memory(monkeypatch):
    monkeypatch.setattr(session_api, "tutor_router", lambda: AIRouter(chat_provider=QwenOutOfQuota()))
    database = InMemoryDatabase()
    await ensure_indexes(database)
    app.dependency_overrides[get_database] = lambda: database
    yield database
    app.dependency_overrides.pop(get_database, None)


async def test_a_session_writes_down_its_model_calls(memory):
    from test_chapter_session_api import MINH, reply_text, send, start

    client = TestClient(app)
    state = start(client)
    for key, text in (("k0", None), ("k1", "3/7")):
        sent = send(client, state, text or reply_text(state), key)
        assert sent.status_code == 200, sent.text
        state = client.get(f"/v1/sessions/{state['session_id']}/state", headers=MINH).json()

    doc = await memory["learning_sessions"].find_one({"_id": state["session_id"]})
    stored = [e for e in doc["events"] if e["event_type"] in ("MODEL_CALLED", "MODEL_FALLBACK")]
    for e in stored:
        PAYLOAD_MODELS[EventType(e["event_type"])].model_validate(e["payload"])
    written = [e["payload"] for e in stored if e["event_type"] == "MODEL_CALLED" and e["payload"]["model"]]
    assert written and {p["model"] for p in written} == {GPT_OSS}
    assert all(p["purpose"] == "tutor_turn" and p["prompt_tokens"] == 812 for p in written)
    assert all(p["estimated_tokens"] > 0 and p["prompt_chars"] > 0 for p in written)
    moved = [e["payload"] for e in stored if e["event_type"] == "MODEL_FALLBACK"]
    assert (QWEN, GPT_OSS, "QUOTA") in {(p["from_model"], p["to_model"], p["reason"]) for p in moved}
