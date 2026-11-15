"""ENG-5f: what a model call costs the session's cap (DI-153) and how long a refusing model rests (DI-154).

The English live run of 15/11/2026 (session of Vuong, Unit 11) counted every request sent against the cap of
160: 115 answers and 45 refusals (Groq 429 per minute, Qwen JSON, Gemini 400/504). The cap ran out two
thirds into the session and the tutor spoke only templates after. Offline, no network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cavat.modules.ai_gateway.base import (
    ChatMessage,
    ChatRequest,
    InvalidModelOutput,
    ModelClass,
    ModelUnavailable,
    QuotaExceeded,
)
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.gemini import GeminiChat
from cavat.modules.ai_gateway.router import (
    MAX_UNAVAILABLE_REST,
    UNAVAILABLE_REST,
    AIRouter,
    ChatDispatcher,
    FallbackReason,
    RecordingRouter,
)
from google.genai import errors as genai_errors

HEAD, NEXT = "openai/gpt-oss-120b", "openai/gpt-oss-20b"
CHAIN = {ModelClass.TUTOR_REASONING: (HEAD, NEXT), ModelClass.INTENT_AGENT: (HEAD, NEXT)}


def _request() -> ChatRequest:
    return ChatRequest(
        messages=(ChatMessage("system", "Bạn là gia sư."), ChatMessage("user", "Con chào cô.")),
        json_schema={"type": "object", "properties": {"utterance": {"type": "string"}}},
    )


class _Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 15, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class _HeadRefusesOncePerTurn:
    """Each turn the head answers 429 for one minute and the next model answers: the live run's pattern."""

    def __init__(self, clock: _Clock) -> None:
        self.clock, self.sent = clock, []

    def chat(self, request, model):
        self.sent.append(model)
        if model == HEAD:
            raise QuotaExceeded("TPM", model=HEAD, reset_at=self.clock.now + timedelta(seconds=5))
        return FakeChatModel([{"utterance": "Cô nghe con rồi."}]).chat(request, model)


def test_one_answer_costs_one_call_however_many_models_refused_first():
    fake = FakeChatModel(
        {
            HEAD: [QuotaExceeded("429", model=HEAD)],
            NEXT: [InvalidModelOutput("bad", model=NEXT)],
            "qwen/qwen3.8-27b": [{"utterance": "Mình tiếp nhé."}],
        }
    )
    router = AIRouter(
        chat_provider=fake,
        chains={ModelClass.TUTOR_REASONING: (HEAD, NEXT, "qwen/qwen3.8-27b")},
        max_calls_per_session=10,
    )
    outcome = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert outcome.result is not None and outcome.calls_made == 1 and outcome.calls_sent == 3


def test_a_chain_that_refuses_costs_nothing():
    fake = FakeChatModel({HEAD: [ModelUnavailable("503", model=HEAD)], NEXT: [QuotaExceeded("429")]})
    outcome = AIRouter(chat_provider=fake, chains=CHAIN, max_calls_per_session=10).chat(
        ModelClass.TUTOR_REASONING, _request(), calls_used=9
    )
    assert outcome.use_template and outcome.fallback_reason is FallbackReason.QUOTA_EXCEEDED
    assert outcome.calls_made == 0 and outcome.calls_sent == 2


def test_the_cap_still_stops_the_model_after_that_many_answers():
    fake = FakeChatModel([{"utterance": f"lời {i}"} for i in range(5)])
    router = AIRouter(chat_provider=fake, chains=CHAIN, max_calls_per_session=3)
    used = 0
    for _ in range(4):
        used += router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=used).calls_made
    last = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=used)
    assert used == 3 and last.fallback_reason is FallbackReason.SESSION_CAP and last.calls_sent == 0
    assert len(fake.calls) == 3


def test_a_refusal_every_turn_no_longer_halves_the_session():
    """The live run's shape: with a refusal before each answer, a cap of 160 gives 160 answers, not 80."""
    clock = _Clock()
    provider = _HeadRefusesOncePerTurn(clock)
    router = AIRouter(chat_provider=provider, chains=CHAIN, max_calls_per_session=160, clock=clock)
    used = answers = 0
    for _ in range(170):
        clock.now += timedelta(seconds=7)  # the head's minute limit has freed up by the next turn
        command = RecordingRouter(router.with_session_cap(160))
        outcome = command.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=used)
        used += outcome.calls_made
        answers += outcome.result is not None
    assert answers == 160 and used == 160
    assert provider.sent.count(HEAD) == 160  # each refusal was still tried, and seen in the trace


def test_one_command_adds_each_answer_once():
    """``RecordingRouter``: the listener and the tutor of one turn spend two calls, not their refusals."""
    clock = _Clock()
    router = RecordingRouter(
        AIRouter(chat_provider=_HeadRefusesOncePerTurn(clock), chains=CHAIN, clock=clock)
    )
    first = router.chat(ModelClass.INTENT_AGENT, _request(), calls_used=0)
    second = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert (first.calls_made, second.calls_made) == (1, 1)
    assert sum(c.outcome.calls_made for c in router.calls) == 2
    assert sum(c.outcome.calls_sent for c in router.calls) == 3  # the head rests after its first 429


# --- DI-154: a model that refuses the request itself rests the longest rest at once -----------------


def _gemini_error(code: int, message: str) -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"code": code, "message": message}})


def test_gemini_400_rests_the_longest_rest_at_once_and_the_turn_goes_on():
    clock = _Clock()
    refusal = _gemini_error(400, "Developer instruction is not enabled for api version v1.")
    gemini = GeminiChat("key", client=_OneOutcome(refusal))
    groq = FakeChatModel([{"utterance": "từ Groq"}] * 3)
    router = AIRouter(
        chat_provider=ChatDispatcher(groq, gemini),
        chains={ModelClass.TUTOR_REASONING: ("gemini-2.5-flash", HEAD)},
        clock=clock,
    )
    first = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert first.result is not None and first.result.model == HEAD and first.calls_made == 1
    assert first.attempts[0].error == "ModelUnavailable" and "HTTP 400" in first.attempts[0].detail

    clock.now += MAX_UNAVAILABLE_REST - timedelta(seconds=1)
    later = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=1)
    assert later.attempts[0].sent is False  # still resting, no request
    clock.now += timedelta(seconds=2)
    again = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=2)
    assert again.attempts[0].sent is True  # tried again once the rest is over


def test_gemini_504_keeps_the_short_doubling_rest():
    clock = _Clock()
    gemini = GeminiChat("key", client=_OneOutcome(_gemini_error(504, "Deadline expired")))
    router = AIRouter(
        chat_provider=ChatDispatcher(FakeChatModel([{"utterance": "x"}] * 3), gemini),
        chains={ModelClass.TUTOR_REASONING: ("gemini-3.8-flash", HEAD)},
        clock=clock,
    )
    router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    clock.now += UNAVAILABLE_REST + timedelta(seconds=1)
    again = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=1)
    assert again.attempts[0].sent is True  # a 5xx rests 30 s first (DI-99), unchanged


def test_groq_client_error_carries_its_status_and_429_408_keep_their_own_handling():
    from cavat.modules.ai_gateway.router import CLIENT_ERROR_TRANSIENT

    assert {408, 409, 429} <= CLIENT_ERROR_TRANSIENT
    assert ModelUnavailable("HTTP 404", status=404).status == 404
    assert ModelUnavailable("timeout").status is None


def test_gemini_daily_quota_is_skipped_until_the_bucket_the_provider_names_resets():
    """BRAIN-5 reused: a day limit (RPD) is not sent again in the session, as in the live run (argon)."""
    from test_ai_gateway import gemini_limit_error

    clock = _Clock()
    gemini = GeminiChat(
        "key", client=_OneOutcome(gemini_limit_error("GenerateRequestsPerDayPerProjectPerModel", "72212s"))
    )
    router = AIRouter(
        chat_provider=ChatDispatcher(FakeChatModel([{"utterance": "x"}] * 3), gemini),
        chains={ModelClass.TUTOR_REASONING: ("gemini-4-argon", HEAD)},
        clock=clock,
    )
    first = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert first.attempts[0].limit == "RPD" and first.calls_made == 1
    clock.now += timedelta(hours=3)
    later = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=1)
    assert later.attempts[0].sent is False and later.attempts[0].retry_after_s > 60 * 60


class _OneOutcome:
    """A fake ``google.genai`` client whose ``generate_content`` always raises or returns ``outcome``."""

    def __init__(self, outcome) -> None:
        self.models = self
        self.outcome = outcome

    def generate_content(self, **_kwargs):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome
