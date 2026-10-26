"""CFG-3: a 429 says which limit it hit and when it frees up, and `make model-usage` reads it back.

No call to Groq: a provider that answers 429 the way Groq words it, and sessions built from the events
``model_call_events`` writes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cavat.config import Settings
from cavat.core.memory_db import InMemoryDatabase
from cavat.modules.ai_gateway.base import (
    ChatMessage,
    ChatRequest,
    ChatResult,
    ModelClass,
    QuotaExceeded,
    QuotaTracker,
    Usage,
    error_detail,
    quota_limit,
)
from cavat.modules.ai_gateway.groq import GroqClient
from cavat.modules.ai_gateway.router import (
    AIRouter,
    RecordingRouter,
    build_router,
    default_chat_chains,
    groq_key,
)
from cavat.modules.session import model_usage
from cavat.modules.session.model_calls import model_call_events
from pydantic import SecretStr

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
QWEN, GPT_OSS = "qwen/qwen3.8-27b", "openai/gpt-oss-120b"
# BRAIN-1 (ADR-034): the tutor's default chain has three Groq models now (gpt-oss-120b, gpt-oss-20b,
# Qwen); the fallback tests keep their two-model story (Qwen, then gpt-oss-120b) by naming that chain.
TWO_MODELS = {**default_chat_chains(), ModelClass.TUTOR_REASONING: (QWEN, GPT_OSS)}
# The minute limit as Groq worded it on 2026-10-25 (the organization id is made up here); the day limit is
# worded alike [ASSUME].
MINUTE = (
    "Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_01k9abcdef0123456789xyz` "
    "service tier `on_demand` on input tokens per minute (ITPM): Limit 7000, Used 6360, Requested 2182. "
    "Please try again in 13.217142857s. Need more tokens? Upgrade to Dev Tier today at "
    "https://console.groq.com/settings/billing"
)
DAY = MINUTE.replace("input tokens per minute (ITPM)", "tokens per day (TPD)").replace("7000", "200000")
HINT = {"message": "Con thử so sánh hai phần mười xem?", "safety_flag": False, "policy_feedback": ""}


def request(name: str = "tutor_turn") -> ChatRequest:
    return ChatRequest(messages=(ChatMessage("user", "con không biết"),), schema_name=name)


# --- the 429 and its limit ------------------------------------------------------------------------------


def test_the_limit_a_429_names_and_the_text_without_the_organization():
    assert (quota_limit(MINUTE), quota_limit(DAY)) == ("ITPM", "TPD")
    assert quota_limit("Rate limit reached on requests per day (RPD)") == "RPD"
    assert quota_limit("something else") is None
    kept = error_detail(MINUTE)
    assert "org_01k9" not in kept and "(ITPM)" in kept and len(error_detail("x" * 999)) == 200


@pytest.mark.parametrize(("text", "limit"), [(MINUTE, "ITPM"), (DAY, "TPD")])
def test_the_groq_adapter_hands_the_limit_up(text, limit):
    body = {"error": {"message": text, "type": "tokens", "code": "rate_limit_exceeded"}}
    client = GroqClient(
        "gsk_test_not_a_real_key_123",
        transport=httpx.MockTransport(lambda r: httpx.Response(429, json=body, headers={"retry-after": "2"})),
    )
    with pytest.raises(QuotaExceeded) as info:
        client.chat(request(), QWEN)
    assert info.value.limit == limit


class MinuteLimitedQwen:
    """Qwen answers 429 on its minute limit, gpt-oss writes. Like the Groq adapter, it marks the model
    out of quota, so the router does not send to it again until it frees up."""

    def __init__(self) -> None:
        self.quota = QuotaTracker()

    def chat(self, request, model):
        if model == QWEN:
            self.quota.mark_exhausted(model, NOW + timedelta(seconds=13.2), NOW)
            raise QuotaExceeded(
                f"rate limited: {MINUTE}", model=model, reset_at=NOW + timedelta(seconds=13.2), limit="ITPM"
            )
        return ChatResult(model, json.dumps(HINT), dict(HINT), Usage(800, 30, 830))


def test_each_attempt_says_which_limit_and_for_how_long():
    router = RecordingRouter(
        AIRouter(chat_provider=MinuteLimitedQwen(), chains=TWO_MODELS, clock=lambda: NOW)
    )
    router.chat(ModelClass.TUTOR_REASONING, request(), calls_used=0)
    router.chat(ModelClass.TUTOR_REASONING, request(), calls_used=1)  # Qwen is known out now: not sent again
    first, second = (e.payload for e in model_call_events(router.calls) if e.event_type == "MODEL_CALLED")
    sent, answered = first["attempts"]
    assert (sent["sent"], sent["limit"], sent["retry_after_s"]) == (True, "ITPM", 13.2)
    assert "org_01k9" not in sent["detail"] and "tokens per minute" in sent["detail"]
    assert answered["error"] is None and answered["limit"] is None
    skipped = second["attempts"][0]
    assert (
        skipped["sent"] is False and skipped["error"] == "QuotaExceeded" and skipped["retry_after_s"] == 13.2
    )


# --- the report ------------------------------------------------------------------------------------------


class Qwen:
    def chat(self, request, model):
        return ChatResult(model, json.dumps(HINT), dict(HINT), Usage(1000, 50, 1050))


def session(sid: str, provider, calls: int = 2, created: datetime = NOW) -> dict:
    router = RecordingRouter(AIRouter(chat_provider=provider, chains=TWO_MODELS, clock=lambda: NOW))
    for _ in range(calls):
        router.chat(ModelClass.TUTOR_REASONING, request(), calls_used=0)
    events = [
        {"event_type": e.event_type, "payload": e.payload, "sequence_no": i + 1}
        for i, e in enumerate(model_call_events(router.calls))
    ]
    return {
        "_id": sid,
        "school_id": "demo-school",
        "student_display_name": "Minh",
        "lesson_id": "math-g5-decimals",
        "state": {"lifecycle": "ACTIVE"},
        "created_at": created,
        "updated_at": created,
        "events": events,
    }


def test_the_report_counts_tokens_models_and_the_limit_of_each_429():
    summary = model_usage.summarize([session("s1", Qwen(), 3), session("s2", MinuteLimitedQwen(), 2)])
    one, two = summary["sessions"]
    assert (one["calls"], one["prompt_tokens"], one["completion_tokens"]) == (3, 3000, 150)
    assert one["by_model"] == {QWEN: 3} and one["refused"] == {}
    assert two["by_model"] == {GPT_OSS: 2} and two["refused"] == {"ITPM": 1} and two["skipped"] == 1
    assert two["fallbacks"] == {f"{QWEN} -> {GPT_OSS} (QUOTA)": 2}
    total = summary["total"]
    assert total["sessions"] == 2 and total["calls"] == 5 and total["refused"] == {"ITPM": 1}
    assert total["qwen_tokens_per_session"] == 3150 and total["sessions_per_day"] == 63
    text = model_usage.render(summary)
    assert "ITPM ×1" in text and "Tổng 2 buổi" in text and "org_01k9" not in text


def test_a_session_before_cfg2_counts_as_no_call():
    old = {"_id": "old", "events": [{"event_type": "TUTOR_MESSAGE_SENT", "payload": {}}]}
    summary = model_usage.summarize([old])
    assert summary["sessions"][0]["calls"] == 0 and summary["total"]["sessions_per_day"] is None
    assert "không gọi model nào" in model_usage.render(summary)


async def test_load_reads_one_school_and_the_recent_sessions_only():
    database = InMemoryDatabase()
    mine = session("new", Qwen(), 1, created=NOW)
    old = session("old", Qwen(), 1, created=NOW - timedelta(days=30))
    other = {**session("other", Qwen(), 1), "school_id": "another-school"}
    for doc in (mine, old, other):
        await database["learning_sessions"].insert_one(doc)
    recent = await model_usage.load(database, "demo-school", since=NOW - timedelta(days=7))
    assert [d["_id"] for d in recent] == ["new"]
    assert [d["_id"] for d in await model_usage.load(database, "demo-school", session_id="old")] == ["old"]


# --- the eval key ---------------------------------------------------------------------------------------


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_evaluations_use_the_eval_key_when_there_is_one():
    both = settings(groq_api_key=SecretStr("gsk_students"), groq_api_key_eval=SecretStr("gsk_eval"))
    assert groq_key(both).get_secret_value() == "gsk_students"
    assert groq_key(both, for_eval=True).get_secret_value() == "gsk_eval"
    only = settings(groq_api_key=SecretStr("gsk_students"))
    assert groq_key(only, for_eval=True).get_secret_value() == "gsk_students"
    empty = settings(groq_api_key=SecretStr("gsk_students"), groq_api_key_eval=SecretStr(""))
    assert groq_key(empty, for_eval=True).get_secret_value() == "gsk_students"
    assert groq_key(settings(), for_eval=True) is None


def test_the_router_of_an_evaluation_is_built_on_the_eval_key():
    both = settings(groq_api_key=SecretStr("gsk_students"), groq_api_key_eval=SecretStr("gsk_eval"))
    heard = {}
    for name, flag in (("students", False), ("eval", True)):
        router = build_router(both, for_eval=flag)
        heard[name] = router._chat._groq._http.headers["authorization"]
    assert heard == {"students": "Bearer gsk_students", "eval": "Bearer gsk_eval"}
    only_eval = settings(groq_api_key_eval=SecretStr("gsk_eval"), tts="off")
    assert build_router(only_eval, for_eval=True)._chat is not None
    assert build_router(only_eval)._chat is None  # the students' router has no key of its own
