"""T06a: AI gateway, fully offline (httpx.MockTransport and scripted fakes, no API key)."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from cavat.config import Settings
from cavat.modules.ai_gateway.base import (
    MAX_PROMPT_TOKENS,
    ChatMessage,
    ChatRequest,
    InvalidModelOutput,
    ModelClass,
    ModelUnavailable,
    PromptTooLong,
    QuotaExceeded,
    QuotaTracker,
    estimate_prompt_tokens,
    parse_reset_duration,
)
from cavat.modules.ai_gateway.fake import FakeChatModel, FakeSpeechToText, FakeVision, ScriptExhausted
from cavat.modules.ai_gateway.gemini import GeminiVision
from cavat.modules.ai_gateway.groq import GroqClient
from cavat.modules.ai_gateway.router import AIRouter, FallbackReason, build_router
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import SecretStr

FAKE_KEY = "gsk_test_not_a_real_key_123"
QWEN = "qwen/qwen3.8-27b"
GPT_OSS = "openai/gpt-oss-120b"
SCHEMA = {
    "type": "object",
    "properties": {"utterance": {"type": "string"}},
    "required": ["utterance"],
    "additionalProperties": False,
}
RATE_HEADERS = {
    "x-ratelimit-limit-requests": "1000",
    "x-ratelimit-remaining-requests": "999",
    "x-ratelimit-reset-requests": "1m26.4s",
    "x-ratelimit-limit-tokens": "8000",
    "x-ratelimit-remaining-tokens": "7852",
    "x-ratelimit-reset-tokens": "1.11s",
}


def _request(text: str = "Em hãy so sánh 0,25 và 0,3.", schema: dict | None = SCHEMA) -> ChatRequest:
    return ChatRequest(
        messages=(ChatMessage("system", "Bạn là gia sư Socratic."), ChatMessage("user", text)),
        json_schema=schema,
    )


def _completion(content: str, model: str = QWEN) -> dict:
    return {
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 28, "total_tokens": 148},
    }


def _rate_limited(retry_after: str = "7") -> httpx.Response:
    body = {
        "error": {"message": "Rate limit reached for model", "type": "tokens", "code": "rate_limit_exceeded"}
    }
    return httpx.Response(429, json=body, headers={**RATE_HEADERS, "retry-after": retry_after})


class Recorder:
    """MockTransport handler that answers per model and records every request sent."""

    def __init__(self, answers: dict[str, list[httpx.Response]]) -> None:
        self.answers = answers
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        model = json.loads(request.content)["model"]
        return self.answers[model].pop(0)

    def models_sent(self) -> list[str]:
        return [json.loads(r.content)["model"] for r in self.requests]


def _groq(handler) -> GroqClient:
    return GroqClient(FAKE_KEY, transport=httpx.MockTransport(handler))


# --- Groq adapter -------------------------------------------------------------------------------


def test_valid_json_is_parsed_and_request_is_shaped_for_groq():
    rec = Recorder(
        {
            QWEN: [
                httpx.Response(
                    200,
                    json=_completion('{"utterance": "Em so sánh hàng phần mười nhé."}'),
                    headers=RATE_HEADERS,
                )
            ]
        }
    )
    client = _groq(rec)

    result = client.chat(_request(), QWEN)

    assert result.data == {"utterance": "Em so sánh hàng phần mười nhé."}
    assert (result.usage.prompt_tokens, result.usage.total_tokens) == (120, 148)
    sent = rec.requests[0]
    assert sent.url == "https://api.groq.com/openai/v1/chat/completions"
    assert sent.headers["authorization"] == f"Bearer {FAKE_KEY}"
    body = json.loads(sent.content)
    assert body["reasoning_effort"] == "none"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    snap = client.quota.snapshot(QWEN)
    assert snap is not None and snap.remaining_tokens == 7852 and snap.limit_requests == 1000


def test_gpt_oss_fallback_uses_supported_reasoning_effort():
    rec = Recorder({GPT_OSS: [httpx.Response(200, json=_completion('{"utterance": "Ừ."}', GPT_OSS))]})
    _groq(rec).chat(_request(), GPT_OSS)
    assert json.loads(rec.requests[0].content)["reasoning_effort"] == "low"


@pytest.mark.parametrize("content", ["Đây không phải JSON", '["a", "b"]', ""])
def test_invalid_json_raises_invalid_model_output(content):
    rec = Recorder({QWEN: [httpx.Response(200, json=_completion(content))]})
    with pytest.raises(InvalidModelOutput):
        _groq(rec).chat(_request(), QWEN)


def test_schema_validation_failure_from_groq_is_invalid_output():
    body = {
        "error": {
            "message": "Generated JSON does not match the expected schema",
            "code": "json_validate_failed",
        }
    }
    rec = Recorder({QWEN: [httpx.Response(400, json=body)]})
    with pytest.raises(InvalidModelOutput):
        _groq(rec).chat(_request(), QWEN)


def test_429_raises_quota_exceeded_with_reset_time_and_blocks_model():
    rec = Recorder({QWEN: [_rate_limited(retry_after="7")]})
    client = _groq(rec)
    before = datetime.now(UTC)

    with pytest.raises(QuotaExceeded) as info:
        client.chat(_request(), QWEN)

    assert info.value.model == QWEN
    assert info.value.reset_at is not None
    assert before + timedelta(seconds=6) < info.value.reset_at < before + timedelta(seconds=9)
    assert client.quota.is_exhausted(QWEN)
    assert FAKE_KEY not in str(info.value)


@pytest.mark.parametrize("status", [500, 503, 401, 404])
def test_server_and_auth_errors_raise_model_unavailable(status):
    rec = Recorder({QWEN: [httpx.Response(status, json={"error": {"message": "boom"}})]})
    with pytest.raises(ModelUnavailable):
        _groq(rec).chat(_request(), QWEN)


def test_network_error_raises_model_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(ModelUnavailable):
        _groq(handler).chat(_request(), QWEN)


def test_too_long_prompt_is_refused_before_sending():
    rec = Recorder({QWEN: []})
    long_request = _request("Một câu rất dài. " * 1000)
    assert estimate_prompt_tokens(long_request) > MAX_PROMPT_TOKENS

    with pytest.raises(PromptTooLong) as info:
        _groq(rec).chat(long_request, QWEN)

    assert rec.requests == []
    assert info.value.estimated_tokens > MAX_PROMPT_TOKENS


def test_transcribe_uses_whisper_large_v3_in_vietnamese():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": " 0,25 bé hơn 0,3. "})

    result = _groq(handler).transcribe(b"RIFF....WAVE", filename="answer.wav")

    assert result.text == "0,25 bé hơn 0,3."
    assert result.model == "whisper-large-v3" and result.language == "vi"
    assert seen[0].url.path == "/openai/v1/audio/transcriptions"
    form = seen[0].content.decode("utf-8", errors="replace")
    assert 'name="model"\r\n\r\nwhisper-large-v3' in form
    assert 'name="language"\r\n\r\nvi' in form
    assert 'filename="answer.wav"' in form


def test_api_key_is_not_exposed_in_repr():
    client = GroqClient(SecretStr(FAKE_KEY), transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert FAKE_KEY not in repr(client)
    with pytest.raises(ValueError):
        GroqClient("")


# --- Quota tracker ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [("7.66s", 7.66), ("2m59.56s", 179.56), ("120ms", 0.12), ("1h2m3s", 3723.0), ("30", 30.0), ("abc", None)],
)
def test_parse_reset_duration(raw, seconds):
    delta = parse_reset_duration(raw)
    assert (delta.total_seconds() if delta else None) == (pytest.approx(seconds) if seconds else None)


def test_quota_tracker_marks_exhausted_until_reset():
    tracker = QuotaTracker()
    now = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
    tracker.update(QWEN, {**RATE_HEADERS, "x-ratelimit-remaining-tokens": "0"}, now)
    assert tracker.is_exhausted(QWEN, now)
    assert not tracker.is_exhausted(QWEN, now + timedelta(seconds=2))
    assert not tracker.is_exhausted(GPT_OSS, now)


# --- Router: fallback chain and session cap -----------------------------------------------------


def test_429_falls_back_to_gpt_oss():
    rec = Recorder(
        {
            QWEN: [_rate_limited()],
            GPT_OSS: [httpx.Response(200, json=_completion('{"utterance": "Thử lại nhé."}', GPT_OSS))],
        }
    )
    router = AIRouter(chat_provider=_groq(rec))

    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)

    assert not outcome.use_template
    assert outcome.result is not None and outcome.result.model == GPT_OSS
    assert outcome.result.data == {"utterance": "Thử lại nhé."}
    assert rec.models_sent() == [QWEN, GPT_OSS]
    assert outcome.calls_made == 2


def test_429_on_whole_chain_tells_caller_to_use_template():
    rec = Recorder({QWEN: [_rate_limited()], GPT_OSS: [_rate_limited()]})
    router = AIRouter(chat_provider=_groq(rec))

    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)

    assert outcome.use_template
    assert outcome.fallback_reason is FallbackReason.QUOTA_EXCEEDED
    assert rec.models_sent() == [QWEN, GPT_OSS]

    # Both models are now known exhausted: the next turn goes to templates without any request.
    again = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=outcome.calls_made)
    assert again.use_template and again.calls_made == 0
    assert len(rec.requests) == 2


def test_server_error_falls_back_then_template_on_invalid_output():
    rec = Recorder(
        {
            QWEN: [httpx.Response(503, json={"error": {"message": "down"}})],
            GPT_OSS: [httpx.Response(200, json=_completion("oops"))],
        }
    )
    outcome = AIRouter(chat_provider=_groq(rec)).chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert outcome.use_template and outcome.fallback_reason is FallbackReason.INVALID_OUTPUT
    assert [a.error for a in outcome.attempts] == ["ModelUnavailable", "InvalidModelOutput"]


def test_too_long_prompt_goes_to_template_without_any_request():
    rec = Recorder({QWEN: [], GPT_OSS: []})
    outcome = AIRouter(chat_provider=_groq(rec)).chat(
        ModelClass.TUTOR_REASONING, _request("Một câu rất dài. " * 1000), calls_used=0
    )
    assert outcome.use_template and outcome.fallback_reason is FallbackReason.PROMPT_TOO_LONG
    assert rec.requests == [] and outcome.calls_made == 0


def test_session_cap_stops_llm_calls():
    fake = FakeChatModel([{"utterance": "a"}])
    router = AIRouter(chat_provider=fake, max_calls_per_session=15)

    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=15)

    assert outcome.use_template and outcome.fallback_reason is FallbackReason.SESSION_CAP
    assert fake.calls == []


def test_session_cap_reached_mid_chain():
    fake = FakeChatModel({QWEN: [QuotaExceeded("429", model=QWEN)], GPT_OSS: [{"utterance": "b"}]})
    outcome = AIRouter(chat_provider=fake, max_calls_per_session=15).chat(
        ModelClass.TUTOR_REASONING, _request(), calls_used=14
    )
    assert outcome.fallback_reason is FallbackReason.SESSION_CAP
    assert [m for m, _ in fake.calls] == [QWEN]


def test_no_api_key_means_template_only_mode():
    router = build_router(Settings(_env_file=None, groq_api_key=None, gemini_api_key=None))
    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert outcome.use_template and outcome.fallback_reason is FallbackReason.NO_PROVIDER
    with pytest.raises(ModelUnavailable):
        router.transcribe(b"audio")
    with pytest.raises(ModelUnavailable):
        router.describe_image(b"png", "Mô tả hình.")


def test_build_router_reads_chain_and_cap_from_settings():
    settings = Settings(_env_file=None, groq_api_key=SecretStr(FAKE_KEY), max_llm_calls_per_session=7)
    router = build_router(settings)
    assert router.chain(ModelClass.TUTOR_REASONING) == (QWEN, GPT_OSS)
    assert router.chain(ModelClass.LIGHTWEIGHT) == (QWEN, "openai/gpt-oss-20b")
    assert router.max_calls_per_session == 7
    with pytest.raises(ValueError):
        router.chain(ModelClass.VISION_OCR)


def test_router_delegates_stt_and_vision():
    stt = FakeSpeechToText(["không phẩy hai lăm"])
    vision = FakeVision(["Hình chữ nhật dài 5 cm, rộng 3 cm."])
    router = AIRouter(stt_provider=stt, vision_provider=vision)
    assert router.transcribe(b"x").text == "không phẩy hai lăm"
    assert stt.calls == [("whisper-large-v3", "vi")]
    assert "5 cm" in router.describe_image(b"png", "Mô tả hình.").text


# --- Fake model ---------------------------------------------------------------------------------


def test_fake_chat_model_follows_script_and_enforces_rules():
    fake = FakeChatModel([{"utterance": "Em thử lại nhé."}, "không phải JSON"])
    first = fake.chat(_request(), QWEN)
    assert first.data == {"utterance": "Em thử lại nhé."} and first.usage.total_tokens > 0
    with pytest.raises(InvalidModelOutput):
        fake.chat(_request(), QWEN)
    with pytest.raises(ScriptExhausted):
        fake.chat(_request(), QWEN)
    with pytest.raises(PromptTooLong):
        FakeChatModel([{"utterance": "x"}]).chat(_request("dài " * 5000), QWEN)


# --- Gemini adapter (fake SDK client, no network) -----------------------------------------------


class _FakeModels:
    def __init__(self, outcome):
        self.outcome = outcome
        self.kwargs: dict = {}

    def generate_content(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class _FakeGenaiClient:
    def __init__(self, outcome):
        self.models = _FakeModels(outcome)


def test_gemini_describe_image_uses_low_thinking_level():
    response = genai_types.GenerateContentResponse(
        candidates=[
            genai_types.Candidate(
                content=genai_types.Content(
                    role="model", parts=[genai_types.Part(text="Tam giác vuông ABC.")]
                )
            )
        ],
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=300, candidates_token_count=10, total_token_count=310
        ),
    )
    fake = _FakeGenaiClient(response)
    vision = GeminiVision(client=fake)

    result = vision.describe_image(b"\x89PNG", "Mô tả hình vẽ.", mime_type="image/png")

    assert result.text == "Tam giác vuông ABC." and result.model == "gemini-3.8-flash"
    assert result.usage.total_tokens == 310
    config = fake.models.kwargs["config"]
    assert config.thinking_config.thinking_level == genai_types.ThinkingLevel.LOW
    image_part = fake.models.kwargs["contents"][0]
    assert image_part.inline_data.mime_type == "image/png"


def test_gemini_429_raises_quota_exceeded():
    error = genai_errors.APIError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    with pytest.raises(QuotaExceeded):
        GeminiVision(client=_FakeGenaiClient(error)).describe_image(b"png", "Mô tả.")


# --- Boundary: vendor SDKs and URLs live only in ai_gateway/ (rule 6) --------------------------

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parents[1]
VENDOR_PATTERNS = [
    re.compile(r"^\s*(from|import)\s+(google\.genai|google\s+import\s+genai|groq|openai|anthropic)\b", re.M),
    re.compile(r"api\.groq\.com|generativelanguage\.googleapis\.com|api\.openai\.com"),
]


def test_no_vendor_sdk_or_url_outside_ai_gateway():
    gateway = API_DIR / "cavat" / "modules" / "ai_gateway"
    roots = [API_DIR / "cavat", API_DIR / "scripts", REPO_ROOT / "evals"]
    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            if gateway in path.parents or ".venv" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if any(p.search(text) for p in VENDOR_PATTERNS):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []
