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
from cavat.modules.ai_gateway.router import AIRouter, FallbackReason, build_router, default_chat_chains
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from pydantic import SecretStr

FAKE_KEY = "gsk_test_not_a_real_key_123"
QWEN = "qwen/qwen3.8-27b"
GPT_OSS = "openai/gpt-oss-120b"
# BRAIN-1 (ADR-034): the tutor's default chain has three Groq models now (gpt-oss-120b, gpt-oss-20b,
# Qwen); the fallback tests keep their two-model story (Qwen, then gpt-oss-120b) by naming that chain.
TWO_MODELS = {**default_chat_chains(), ModelClass.TUTOR_REASONING: (QWEN, GPT_OSS)}
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


def test_every_model_of_the_intent_chain_gets_the_reasoning_effort_it_accepts():
    """REFORM-5: the intent agent runs on gpt-oss first. Groq refuses "none" on gpt-oss (low, medium, high
    only), and Qwen needs "none" or it bills about 390 tokens of thought for nothing (checked live)."""
    from cavat.modules.ai_gateway.router import default_chat_chains

    chain = default_chat_chains()[ModelClass.INTENT_AGENT]
    assert chain == ("openai/gpt-oss-120b", QWEN, "openai/gpt-oss-20b")
    for model in chain:
        rec = Recorder({model: [httpx.Response(200, json=_completion('{"utterance": "x"}', model))]})
        _groq(rec).chat(_request(), model)
        sent = json.loads(rec.requests[0].content)
        assert sent["reasoning_effort"] == ("none" if model == QWEN else "low"), model
        assert sent["response_format"]["json_schema"]["strict"] is True


def test_the_intent_agent_is_a_chat_class_whose_chain_names_the_brain_once():
    from cavat.modules.ai_gateway.base import CHAT_MODEL_CLASSES

    assert ModelClass.INTENT_AGENT in CHAT_MODEL_CLASSES
    router = build_router(Settings(_env_file=None, groq_api_key=SecretStr(FAKE_KEY), groq_model="qwen/next"))
    assert router.chain(ModelClass.INTENT_AGENT) == ("openai/gpt-oss-120b", "qwen/next", "openai/gpt-oss-20b")


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
    assert 'name="response_format"\r\n\r\nverbose_json' in form
    assert 'filename="answer.wav"' in form


@pytest.mark.parametrize(
    ("segments", "expected"),
    [
        ([], ""),
        (
            [
                {
                    "text": "Cảm ơn các bạn đã theo dõi và hẹn gặp lại.",
                    "no_speech_prob": 0.98,
                    "avg_logprob": -1.2,
                }
            ],
            "",
        ),
        (
            [
                {
                    "text": "Cảm ơn các bạn đã theo dõi và hẹn gặp lại.",
                    "no_speech_prob": 0.01,
                    "avg_logprob": -0.1,
                }
            ],
            "Cảm ơn các bạn đã theo dõi và hẹn gặp lại.",
        ),
        (
            [{"text": "không phẩy một", "no_speech_prob": 0.02, "avg_logprob": -0.2}],
            "không phẩy một",
        ),
        (
            [{"text": "không phẩy một", "no_speech_prob": 0.95, "avg_logprob": -0.1}],
            "không phẩy một",
        ),
    ],
)
def test_transcription_filters_non_speech_without_blacklisting_real_words(segments, expected):
    payload = {"text": " ".join(s["text"] for s in segments), "segments": segments}
    result = _groq(lambda r: httpx.Response(200, json=payload)).transcribe(b"audio")
    assert result.text == expected


def test_transcription_keeps_the_answer_but_drops_a_noisy_tail():
    payload = {
        "text": "không phẩy một Cảm ơn các bạn đã theo dõi và hẹn gặp lại.",
        "segments": [
            {"text": " không phẩy một", "no_speech_prob": 0.01, "avg_logprob": -0.1},
            {
                "text": " Cảm ơn các bạn đã theo dõi và hẹn gặp lại.",
                "no_speech_prob": 0.99,
                "avg_logprob": -1.1,
            },
        ],
    }
    result = _groq(lambda r: httpx.Response(200, json=payload)).transcribe(b"audio")
    assert result.text == "không phẩy một"


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
    router = AIRouter(chat_provider=_groq(rec), chains=TWO_MODELS)

    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)

    assert not outcome.use_template
    assert outcome.result is not None and outcome.result.model == GPT_OSS
    assert outcome.result.data == {"utterance": "Thử lại nhé."}
    assert rec.models_sent() == [QWEN, GPT_OSS]
    assert outcome.calls_made == 2


def test_429_on_whole_chain_tells_caller_to_use_template():
    rec = Recorder({QWEN: [_rate_limited()], GPT_OSS: [_rate_limited()]})
    router = AIRouter(chat_provider=_groq(rec), chains=TWO_MODELS)

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
    outcome = AIRouter(chat_provider=_groq(rec), chains=TWO_MODELS).chat(
        ModelClass.TUTOR_REASONING, _request(), calls_used=0
    )
    assert outcome.use_template and outcome.fallback_reason is FallbackReason.INVALID_OUTPUT
    assert [a.error for a in outcome.attempts] == ["ModelUnavailable", "InvalidModelOutput"]


def test_too_long_prompt_goes_to_template_without_any_request():
    rec = Recorder({QWEN: [], GPT_OSS: []})
    outcome = AIRouter(chat_provider=_groq(rec), chains=TWO_MODELS).chat(
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
    outcome = AIRouter(chat_provider=fake, max_calls_per_session=15, chains=TWO_MODELS).chat(
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
    assert router.chain(ModelClass.TUTOR_REASONING) == (GPT_OSS, QWEN, "openai/gpt-oss-20b")
    assert router.chain(ModelClass.LIGHTWEIGHT) == (GPT_OSS, QWEN, "openai/gpt-oss-20b")
    assert router.max_calls_per_session == 7
    with pytest.raises(ValueError):
        router.chain(ModelClass.VISION_OCR)
    # An eval judges on a model with its own quota; the other classes keep their chain (TQ-2).
    judge = build_router(settings, chains={ModelClass.EVAL_JUDGE: (GPT_OSS,)})
    assert judge.chain(ModelClass.EVAL_JUDGE) == (GPT_OSS,)
    assert judge.chain(ModelClass.TUTOR_REASONING) == (GPT_OSS, QWEN, "openai/gpt-oss-20b")


def test_configured_qwen_follows_120b_and_precedes_20b_for_live_roles():
    assert AIRouter().chain(ModelClass.TUTOR_REASONING)[1] == Settings.model_fields["groq_model"].default
    router = build_router(Settings(_env_file=None, groq_api_key=SecretStr(FAKE_KEY), groq_model="qwen/next"))
    for role in (
        ModelClass.TUTOR_REASONING,
        ModelClass.LIGHTWEIGHT,
        ModelClass.EVAL_JUDGE,
        ModelClass.INTENT_AGENT,
    ):
        assert router.chain(role) == (GPT_OSS, "qwen/next", "openai/gpt-oss-20b")


def test_env_example_lists_only_settings_the_app_reads():
    # CFG-1: .env is read with extra="ignore", so keys no code reads (LlamaCloud, Gemini Live) went unnoticed.
    template = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    keys = re.findall(r"^([A-Z][A-Z0-9_]*)=", template, flags=re.MULTILINE)
    assert "GROQ_MODEL" in keys
    assert [key for key in keys if key.lower() not in Settings.model_fields] == []


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


def test_gemini_vision_tries_the_next_free_model_when_one_is_rate_limited():
    """INGEST-1: 20 requests a day per free model; the owner's documents need 31 pages read."""
    quota = genai_errors.APIError(
        429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}
    )
    ok = genai_types.GenerateContentResponse(
        candidates=[
            genai_types.Candidate(
                content=genai_types.Content(role="model", parts=[genai_types.Part(text="7/10")])
            )
        ]
    )

    class ByModel:
        def __init__(self):
            self.calls = []

        def generate_content(self, *, model, contents, config):
            self.calls.append((model, config.thinking_config))
            if model == "gemini-3.8-flash":
                raise quota
            return ok

    fake = _FakeGenaiClient(None)
    fake.models = ByModel()
    vision = GeminiVision(client=fake, fallbacks=("gemini-2.5-flash", "gemini-3.5-flash-lite"))
    result = vision.describe_image(b"%PDF", "Chép lại trang.", mime_type="application/pdf")
    assert (result.text, result.model) == ("7/10", "gemini-2.5-flash")
    (first, _), (second, thinking) = fake.models.calls
    assert (first, second) == ("gemini-3.8-flash", "gemini-2.5-flash")
    assert thinking.thinking_budget == 0  # Gemini 2.5 takes a budget, not a level

    every = GeminiVision(client=_FakeGenaiClient(quota), fallbacks=("gemini-2.5-flash",))
    with pytest.raises(QuotaExceeded):
        every.describe_image(b"png", "Mô tả.")


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


# --- BRAIN-1 (ADR-034): models of two vendors in one chain --------------------------------------


def _gemini_answer(text: str):
    return genai_types.GenerateContentResponse(
        candidates=[
            genai_types.Candidate(
                content=genai_types.Content(role="model", parts=[genai_types.Part(text=text)])
            )
        ]
    )


def test_a_model_that_takes_no_reasoning_effort_is_sent_none():
    """Qwen: "none"; gpt-oss: "low"; any other model on Groq does not take the field at all."""
    model = "meta-llama/llama-4-scout-17b-16e-instruct"
    rec = Recorder({model: [httpx.Response(200, json=_completion('{"utterance": "x"}', model))]})
    _groq(rec).chat(_request(), model)
    assert "reasoning_effort" not in json.loads(rec.requests[0].content)


def test_tutor_models_is_one_line_that_sets_the_chain():
    from cavat.modules.ai_gateway.router import default_chat_chains, parse_models

    assert parse_models(" openai/gpt-oss-120b, gemini-3.5-flash ,, openai/gpt-oss-120b") == (
        "openai/gpt-oss-120b",
        "gemini-3.5-flash",
    )
    chains = default_chat_chains(QWEN, parse_models("gemini-3.5-flash,qwen/qwen3.8-27b"))
    assert chains[ModelClass.TUTOR_REASONING] == ("gemini-3.5-flash", QWEN)
    # Owner order: Qwen is preferred over 20B.
    assert default_chat_chains(QWEN)[ModelClass.TUTOR_REASONING] == (GPT_OSS, QWEN, "openai/gpt-oss-20b")
    assert chains[ModelClass.INTENT_AGENT] == default_chat_chains(QWEN)[ModelClass.INTENT_AGENT]


def test_gemini_chat_with_one_model_asks_for_json_and_parses_it():
    from cavat.modules.ai_gateway.gemini import GeminiChat

    fake = _FakeGenaiClient(_gemini_answer('{"utterance": "Chào con"}'))
    result = GeminiChat("key", client=fake).chat_with(_request(), "gemini-3.5-flash")
    assert result.data == {"utterance": "Chào con"} and result.model == "gemini-3.5-flash"
    config = fake.models.kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert "additionalProperties" not in config.response_json_schema


def test_gemini_chat_with_raises_the_gateways_errors():
    from cavat.modules.ai_gateway.gemini import GeminiChat

    quota = genai_errors.APIError(429, {"error": {"code": 429, "message": "quota"}})
    with pytest.raises(QuotaExceeded):
        GeminiChat("key", client=_FakeGenaiClient(quota)).chat_with(_request(), "gemini-3.5-flash")
    with pytest.raises(InvalidModelOutput):
        GeminiChat("key", client=_FakeGenaiClient(_gemini_answer("not json"))).chat_with(
            _request(), "gemini-3.5-flash"
        )


def test_the_dispatcher_sends_each_name_to_its_vendor_and_rests_a_gemini_that_is_out_of_quota():
    from cavat.modules.ai_gateway.gemini import GeminiChat
    from cavat.modules.ai_gateway.router import ChatDispatcher

    groq = FakeChatModel([{"utterance": "từ Groq"}, {"utterance": "lại từ Groq"}])
    quota = genai_errors.APIError(429, {"error": {"code": 429, "message": "quota"}})
    gemini = GeminiChat("key", client=_FakeGenaiClient(quota))
    dispatcher = ChatDispatcher(groq, gemini)
    router = AIRouter(
        chat_provider=dispatcher,
        chains={ModelClass.TUTOR_REASONING: ("gemini-3.5-flash", GPT_OSS)},
    )

    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)

    assert outcome.result is not None and outcome.result.model == GPT_OSS
    assert [a.error for a in outcome.attempts] == ["QuotaExceeded", None]
    assert dispatcher.quota.is_exhausted("gemini-3.5-flash")  # rests; the next turn does not send to it
    again = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert again.attempts[0].sent is False


def test_the_dispatcher_without_a_key_for_a_vendor_falls_through():
    from cavat.modules.ai_gateway.router import ChatDispatcher

    groq = FakeChatModel([{"utterance": "ok"}])
    router = AIRouter(
        chat_provider=ChatDispatcher(groq, None),
        chains={ModelClass.TUTOR_REASONING: ("gemini-3.5-flash", GPT_OSS)},
    )
    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert outcome.result is not None and outcome.attempts[0].error == "ModelUnavailable"


def test_gemini_deadline_respects_api_minimum(monkeypatch):
    from cavat.modules.ai_gateway.gemini import GeminiChat
    from google import genai

    observed = {}

    def create(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(genai, "Client", create)
    GeminiChat("synthetic-key", timeout_s=2)
    assert observed["http_options"].timeout == 10_000


def test_gemini_schema_removes_strict_keyword_inside_array_objects():
    from cavat.modules.ai_gateway.gemini import _plain_schema

    nested = {"type": "object", "additionalProperties": False}
    original = {"type": "array", "items": {"anyOf": [nested]}}
    converted = _plain_schema(original)
    assert "additionalProperties" not in converted["items"]["anyOf"][0]
    assert original["items"]["anyOf"][0]["additionalProperties"] is False


def gemini_limit_error(quota_id, retry=None):
    details = [
        {
            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
            "violations": [
                {
                    "quotaId": quota_id,
                    "quotaMetric": "generate_content_free_tier_requests",
                    "quotaValue": "20",
                }
            ],
        }
    ]
    if retry:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry})
    return genai_errors.APIError(429, {"error": {"code": 429, "message": "quota", "details": details}})


def test_gemini_daily_limit_keeps_the_real_seventeen_hour_retry_hint():
    from datetime import UTC, datetime, timedelta

    from cavat.modules.ai_gateway.gemini import _chat_quota_error

    now = datetime(2026, 10, 28, 20, tzinfo=UTC)
    error = _chat_quota_error(
        gemini_limit_error("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "62425s"),
        "gemini-2.5-flash",
        now=now,
    )
    assert error.limit == "RPD" and error.reset_at == now + timedelta(seconds=62425)


def test_gemini_minute_quota_does_not_wait_ten_minutes():
    from datetime import UTC, datetime, timedelta

    from cavat.modules.ai_gateway.gemini import _chat_quota_error

    now = datetime(2026, 10, 28, 20, tzinfo=UTC)
    error = _chat_quota_error(
        gemini_limit_error("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "32.5s"),
        "gemini-2.5-flash",
        now=now,
    )
    assert error.limit == "RPM" and error.reset_at == now + timedelta(seconds=32.5)


@pytest.mark.parametrize("month,day,utc_hour", [(10, 28, 7), (12, 28, 8)])
def test_gemini_daily_reset_without_hint_uses_pacific_midnight_and_dst(month, day, utc_hour):
    from datetime import UTC, datetime

    from cavat.modules.ai_gateway.gemini import _chat_quota_error

    now = datetime(2026, month, day, 2, tzinfo=UTC)
    error = _chat_quota_error(
        gemini_limit_error("GenerateRequestsPerDayPerProjectPerModel-FreeTier"), "gemini-2.5-flash", now=now
    )
    assert error.reset_at == datetime(2026, month, day, utc_hour, tzinfo=UTC)


def test_gemini_daily_limit_is_skipped_across_roles_past_the_old_ten_minute_pause():
    from datetime import UTC, datetime, timedelta

    from cavat.modules.ai_gateway.gemini import GeminiChat
    from cavat.modules.ai_gateway.router import ChatDispatcher

    now = datetime.now(UTC)
    gemini = GeminiChat(
        "key",
        client=_FakeGenaiClient(
            gemini_limit_error("GenerateRequestsPerDayPerProjectPerModel-FreeTier", "62425s")
        ),
    )
    groq = FakeChatModel([{"utterance": "first"}, {"utterance": "next"}])
    router = AIRouter(
        chat_provider=ChatDispatcher(groq, gemini),
        chains={
            ModelClass.TUTOR_REASONING: ("gemini-2.5-flash", GPT_OSS),
            ModelClass.EVAL_JUDGE: ("gemini-2.5-flash", GPT_OSS),
        },
        clock=lambda: now,
    )
    first = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    now += timedelta(minutes=11)
    again = router.chat(ModelClass.EVAL_JUDGE, _request(), calls_used=first.calls_made)
    assert again.result.model == GPT_OSS
    assert again.attempts[0].sent is False and again.attempts[0].retry_after_s > 60 * 60


def test_live_roles_share_owner_priority_and_return_to_head_after_quota_reset():
    now = datetime(2026, 10, 29, tzinfo=UTC)
    top = "gemini-4-argon"
    settings = Settings(_env_file=None, groq_api_key=FAKE_KEY, gemini_api_key="test-key", tts="off")
    router = build_router(settings)
    expected = (top, "gemini-2.5-flash", "gemini-3.8-flash", GPT_OSS, QWEN, "openai/gpt-oss-20b")
    for role in (
        ModelClass.TUTOR_REASONING,
        ModelClass.LIGHTWEIGHT,
        ModelClass.INTENT_AGENT,
        ModelClass.EVAL_JUDGE,
        ModelClass.TUTOR_MENTOR,
    ):
        assert router.chain(role) == expected
    fake = FakeChatModel(
        {
            top: [
                QuotaExceeded("day limit", model=top, reset_at=now + timedelta(seconds=60)),
                {"utterance": "back"},
            ],
            "gemini-2.5-flash": [{"utterance": "next"}, {"utterance": "still next"}],
        }
    )
    router._chat = fake
    router._clock = lambda: now
    first = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert first.result.model == "gemini-2.5-flash"
    second = router.chat(ModelClass.INTENT_AGENT, _request(), calls_used=0)
    assert second.result.model == "gemini-2.5-flash" and not second.attempts[0].sent
    now += timedelta(seconds=61)
    third = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert third.result.model == top
    assert [model for model, _ in fake.calls] == [top, "gemini-2.5-flash", "gemini-2.5-flash", top]


def test_qwen_is_used_before_20b_when_stronger_candidates_are_limited():
    now = datetime(2026, 10, 29, tzinfo=UTC)
    router = build_router(
        Settings(_env_file=None, groq_api_key=FAKE_KEY, gemini_api_key="test-key", tts="off")
    )
    chain = router.chain(ModelClass.TUTOR_REASONING)
    fake = FakeChatModel(
        {
            model: [QuotaExceeded("limit", model=model, reset_at=now + timedelta(seconds=60))]
            for model in chain[:4]
        }
        | {QWEN: [{"utterance": "qwen replies"}]}
    )
    router._chat = fake
    router._clock = lambda: now
    result = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert result.result.model == QWEN
    assert [model for model, _ in fake.calls] == list(chain[:5])


def test_quota_fallback_reuses_the_exact_question_context_and_only_returns_final_answer():
    first, second = "gemini-4-argon", GPT_OSS
    original = _request()
    provider = FakeChatModel(
        {
            first: [QuotaExceeded("429 usage exhausted", model=first)],
            second: [{"utterance": "Con thử nhìn hàng phần mười nhé."}],
        }
    )
    router = AIRouter(chat_provider=provider, chains={ModelClass.TUTOR_REASONING: (first, second)})
    out = router.chat(ModelClass.TUTOR_REASONING, original, calls_used=0)
    assert out.result.model == second and out.fallback_reason is None
    assert out.result.data == {"utterance": "Con thử nhìn hàng phần mười nhé."}
    assert len(provider.calls) == 2
    assert all(request is original for _, request in provider.calls)
    # Usage details remain in the technical trace, never in the returned utterance.
    assert out.attempts[0].error == "QuotaExceeded"
    assert "429" not in out.result.data["utterance"]
