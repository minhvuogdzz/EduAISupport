"""Choose a model by ``ModelClass``, walk the fallback chain, enforce the per-session cap (ADR-017).

Chain for chat: the models of ``TUTOR_MODELS`` (BRAIN-1, ADR-034), by default the measured order ->
tell the caller to use an approved template. The tutor session never stops because of a provider. Callers
never pick a model name (rule 4).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import SecretStr

from cavat.config import Settings, get_settings
from cavat.modules.observability.trace import traced

from .base import (
    CHAT_MODEL_CLASSES,
    AIGatewayError,
    ChatProvider,
    ChatRequest,
    ChatResult,
    EmbeddingProvider,
    InvalidModelOutput,
    ModelClass,
    ModelUnavailable,
    PromptTooLong,
    QuotaExceeded,
    QuotaTracker,
    Speech,
    SpeechToText,
    TextToSpeech,
    Transcription,
    VisionProvider,
    VisionResult,
    error_detail,
    estimate_prompt_tokens,
)

DEFAULT_MAX_LLM_CALLS_PER_SESSION = 15
# The model of the lightweight and judge chains is named in the settings (GROQ_MODEL, Qwen).
DEFAULT_TUTOR_MODEL: str = Settings.model_fields["groq_model"].default
# Owner priority (2026-10-29): Gemini, then GPT-OSS 120B, Qwen, GPT-OSS 20B.
# Gemini candidates are wired from settings when credentials are available in build_router.
DEFAULT_TUTOR_CHAIN: tuple[str, ...] = ("openai/gpt-oss-120b", DEFAULT_TUTOR_MODEL, "openai/gpt-oss-20b")


def parse_models(value: str) -> tuple[str, ...]:
    """``TUTOR_MODELS``: model names separated by commas, in the order they are tried."""
    return tuple(dict.fromkeys(m.strip() for m in value.split(",") if m.strip()))


def _tutor_chain(primary: str) -> tuple[str, ...]:
    """The owner-ranked Groq candidates, with the configured Qwen model in the middle."""
    return tuple(dict.fromkeys((DEFAULT_TUTOR_CHAIN[0], primary, DEFAULT_TUTOR_CHAIN[-1])))


def default_chat_chains(
    primary: str = DEFAULT_TUTOR_MODEL, tutor_models: tuple[str, ...] = ()
) -> dict[ModelClass, tuple[str, ...]]:
    return {
        ModelClass.TUTOR_REASONING: tutor_models or _tutor_chain(primary),
        ModelClass.TUTOR_MENTOR: (),
        ModelClass.LIGHTWEIGHT: (primary, "openai/gpt-oss-20b"),
        # REFORM-5 (DI-78): gpt-oss-120b reads a typo best of the free models and has a quota of its own; the
        # tutor's Qwen and the smaller gpt-oss follow. build_router appends the owner-authorized Gemini
        # support models (ADR-045).
        ModelClass.INTENT_AGENT: ("openai/gpt-oss-120b", primary, "openai/gpt-oss-20b"),
        ModelClass.EVAL_JUDGE: (primary, "openai/gpt-oss-120b"),
    }


class FallbackReason(StrEnum):
    NO_PROVIDER = "no_provider"  # no API key configured: template-only mode
    SESSION_CAP = "session_cap"  # MAX_LLM_CALLS_PER_SESSION reached
    PROMPT_TOO_LONG = "prompt_too_long"
    QUOTA_EXCEEDED = "quota_exceeded"
    MODEL_UNAVAILABLE = "model_unavailable"
    INVALID_OUTPUT = "invalid_output"


@dataclass(frozen=True)
class Attempt:
    model: str
    sent: bool  # False when skipped (known exhausted) or refused before sending
    error: str | None = None  # error class name, None on success
    # CFG-3: the provider's words (without the organization id), the limit a 429 names (TPM, TPD, RPM, RPD)
    # and the seconds until it frees up, when known: a minute limit and a day limit read differently.
    detail: str = ""
    limit: str | None = None
    retry_after_s: float | None = None


@dataclass(frozen=True)
class ChatOutcome:
    result: ChatResult | None
    fallback_reason: FallbackReason | None
    # Requests actually sent to a provider; the caller adds this to the session's counter.
    calls_made: int
    attempts: tuple[Attempt, ...] = ()

    @property
    def use_template(self) -> bool:
        return self.result is None


_REASON_BY_ERROR: dict[type[AIGatewayError], FallbackReason] = {
    QuotaExceeded: FallbackReason.QUOTA_EXCEEDED,
    ModelUnavailable: FallbackReason.MODEL_UNAVAILABLE,
    InvalidModelOutput: FallbackReason.INVALID_OUTPUT,
}


def _seconds_until(moment: datetime | None, now: datetime) -> float | None:
    return None if moment is None else round(max((moment - now).total_seconds(), 0.0), 1)


class AIRouter:
    def __init__(
        self,
        *,
        chat_provider: ChatProvider | None = None,
        stt_provider: SpeechToText | None = None,
        tts_provider: TextToSpeech | None = None,
        vision_provider: VisionProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        chains: Mapping[ModelClass, tuple[str, ...]] | None = None,
        stt_model: str = "whisper-large-v3",
        max_calls_per_session: int = DEFAULT_MAX_LLM_CALLS_PER_SESSION,
        quota: QuotaTracker | None = None,
        model_only_speech: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        transient_retry_s: float = 0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model_only_speech = model_only_speech
        self._chat = chat_provider
        self._stt = stt_provider
        self._tts = tts_provider
        self._vision = vision_provider
        self._embedding = embedding_provider
        self._chains = dict(chains or default_chat_chains())
        self._stt_model = stt_model
        self.max_calls_per_session = max_calls_per_session
        self.quota = quota or getattr(chat_provider, "quota", None) or QuotaTracker()
        self._clock = clock
        self._unavailable_until: dict[str, datetime] = {}
        self._transient_retry_s, self._sleep = transient_retry_s, sleeper

    def chain(self, model_class: ModelClass) -> tuple[str, ...]:
        if model_class not in CHAT_MODEL_CLASSES:
            raise ValueError(f"{model_class} is not a chat model class")
        return self._chains[model_class]

    def has_available_chat(self) -> bool:
        """Whether a chat candidate remains; this never probes or spends quota."""
        now = self._clock()
        return self._chat is not None and any(
            not self.quota.is_exhausted(model, now) and self._unavailable_until.get(model, now) <= now
            for chain in self._chains.values()
            for model in chain
        )

    def with_session_cap(self, limit: int) -> AIRouter:
        """Same providers and quota tracker, a separate finite limit for a full chapter (DI-90)."""
        from copy import copy

        scoped = copy(self)
        scoped.max_calls_per_session = limit
        return scoped

    @traced("model")
    def chat(self, model_class: ModelClass, request: ChatRequest, *, calls_used: int) -> ChatOutcome:
        """Try the chain for ``model_class``. ``calls_used`` comes from the session state (SessionContext)."""
        outcome = self._attempt_chat(model_class, request, calls_used=calls_used)
        if (
            outcome.result is not None
            or self._transient_retry_s <= 0
            or outcome.fallback_reason
            not in (FallbackReason.QUOTA_EXCEEDED, FallbackReason.MODEL_UNAVAILABLE)
            or calls_used + outcome.calls_made >= self.max_calls_per_session
        ):
            return outcome
        now = self._clock()
        resets = [
            max(self.quota.reset_at(model) or now, self._unavailable_until.get(model, now))
            for model in self.chain(model_class)
        ]
        # One short recovery attempt only after the entire chain failed. Daily exhaustion and long
        # cooldowns still return immediately; never spin or re-send against a known quota limit.
        delay = min(((reset - now).total_seconds() for reset in resets if reset > now), default=0)
        if not 0 < delay <= self._transient_retry_s:
            return outcome
        self._sleep(delay + 0.05)
        retried = self._attempt_chat(model_class, request, calls_used=calls_used + outcome.calls_made)
        return ChatOutcome(
            retried.result,
            retried.fallback_reason,
            outcome.calls_made + retried.calls_made,
            outcome.attempts + retried.attempts,
        )

    def _attempt_chat(self, model_class: ModelClass, request: ChatRequest, *, calls_used: int) -> ChatOutcome:
        chain = self.chain(model_class)
        if self._chat is None:
            return ChatOutcome(None, FallbackReason.NO_PROVIDER, 0)
        attempts: list[Attempt] = []
        calls_made = 0
        reason = FallbackReason.QUOTA_EXCEEDED
        for model in chain:
            if calls_used + calls_made >= self.max_calls_per_session:
                return ChatOutcome(None, FallbackReason.SESSION_CAP, calls_made, tuple(attempts))
            if self.quota.is_exhausted(model, self._clock()):
                wait = _seconds_until(self.quota.reset_at(model), self._clock())
                attempts.append(Attempt(model, sent=False, error=QuotaExceeded.__name__, retry_after_s=wait))
                reason = FallbackReason.QUOTA_EXCEEDED
                continue
            unavailable = self._unavailable_until.get(model)
            if unavailable and unavailable > self._clock():
                attempts.append(
                    Attempt(
                        model,
                        sent=False,
                        error="ModelUnavailable",
                        retry_after_s=_seconds_until(unavailable, self._clock()),
                    )
                )
                reason = FallbackReason.MODEL_UNAVAILABLE
                continue
            try:
                result = self._chat.chat(request, model)
            except PromptTooLong as exc:
                # Every Groq model shares the same budget: no point trying the next one.
                attempts.append(
                    Attempt(model, sent=False, error=PromptTooLong.__name__, detail=error_detail(str(exc)))
                )
                return ChatOutcome(None, FallbackReason.PROMPT_TOO_LONG, calls_made, tuple(attempts))
            except (QuotaExceeded, ModelUnavailable, InvalidModelOutput) as exc:
                calls_made += 1
                limit = exc.limit if isinstance(exc, QuotaExceeded) else None
                reset = exc.reset_at if isinstance(exc, QuotaExceeded) else None
                if isinstance(exc, QuotaExceeded):
                    existing = self.quota.reset_at(model)
                    until = reset or self._clock() + timedelta(minutes=1)
                    self.quota.mark_exhausted(
                        model, max(existing, until) if existing else until, self._clock()
                    )
                elif isinstance(exc, ModelUnavailable):
                    self._unavailable_until[model] = self._clock() + timedelta(seconds=30)
                attempts.append(
                    Attempt(
                        model,
                        sent=True,
                        error=type(exc).__name__,
                        detail=error_detail(str(exc)),
                        limit=limit,
                        retry_after_s=_seconds_until(reset, self._clock()),
                    )
                )
                reason = _REASON_BY_ERROR[type(exc)]
                continue
            calls_made += 1
            attempts.append(Attempt(model, sent=True))
            return ChatOutcome(result, None, calls_made, tuple(attempts))
        return ChatOutcome(None, reason, calls_made, tuple(attempts))

    @traced("model")
    def transcribe(
        self, audio: bytes, *, language: str = "vi", filename: str = "audio.webm"
    ) -> Transcription:
        """STT_VI. On error the caller falls back to the browser Web Speech API."""
        if self._stt is None:
            raise ModelUnavailable("no speech-to-text provider configured")
        return self._stt.transcribe(audio, model=self._stt_model, language=language, filename=filename)

    @property
    def can_transcribe(self) -> bool:
        return self._stt is not None

    @property
    def speech_model(self) -> str | None:
        """TTS_VI, or None: the browser's own voice reads the tutor (ADR-030)."""
        return self._tts.name if self._tts is not None else None

    @traced("model")
    def speak(self, text: str) -> Speech:
        """TTS_VI (VieNeu-TTS, local). Not counted in the per-session LLM cap; the voice module caches."""
        if self._tts is None:
            raise ModelUnavailable("no text-to-speech provider configured")
        return self._tts.speak(text)

    @property
    def embedding_model(self) -> str | None:
        """The EMBEDDING model, or None without a Gemini key (the RAG then uses keywords and structure)."""
        return _embedding_name(self._embedding)

    @traced("model")
    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        """EMBEDDING (Gemini). Not counted in the per-session LLM cap; the RAG caches every vector."""
        if self._embedding is None:
            raise ModelUnavailable("no embedding provider configured")
        return self._embedding.embed(texts, task=task)

    @traced("model")
    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        """VISION_OCR (Gemini). Not counted in the per-session LLM cap."""
        if self._vision is None:
            raise ModelUnavailable("no vision provider configured")
        return self._vision.describe_image(image_bytes, prompt, mime_type=mime_type)

    @property
    def vision_models(self) -> tuple[str, ...]:
        """The vision chain, first model first (empty without a vision provider)."""
        return tuple(getattr(self._vision, "models", ())) if self._vision is not None else ()

    @traced("model")
    def describe_image_with(
        self, model: str, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        """VISION_OCR on one model of the chain, no fallback (INGEST-1: a second, independent reading)."""
        if self._vision is None:
            raise ModelUnavailable("no vision provider configured")
        return self._vision.describe_with(model, image_bytes, prompt, mime_type=mime_type)


@dataclass(frozen=True)
class ChatCall:
    """One ``chat`` as ``RecordingRouter`` saw it (CFG-2); the session writes it down as MODEL_CALLED."""

    model_class: ModelClass
    purpose: str  # the request's schema name (tutor_turn, reading, move_choice, grounded_turn)
    outcome: ChatOutcome
    estimated_tokens: int  # what the provider adapter checks against MAX_PROMPT_TOKENS before sending
    prompt_chars: int  # characters of the messages
    schema_chars: int  # characters of the JSON schema (0 without one)
    messages: int


class RecordingRouter:
    """The router of one session command (CFG-2): every call goes to the shared router, which remembers
    which models are out of quota, and each ``chat`` is kept so the session can write down which model
    answered and the tokens the provider counted. Everything else is the shared router's."""

    def __init__(self, router: AIRouter) -> None:
        self._router = router
        self.calls: list[ChatCall] = []
        self._start_calls: int | None = None
        self._spent = 0

    def chat(self, model_class: ModelClass, request: ChatRequest, *, calls_used: int) -> ChatOutcome:
        if self._start_calls is None:
            self._start_calls = calls_used
        used = max(calls_used, self._start_calls + self._spent)
        outcome = self._router.chat(model_class, request, calls_used=used)
        self._spent += outcome.calls_made
        schema = "" if request.json_schema is None else json.dumps(request.json_schema, ensure_ascii=False)
        self.calls.append(
            ChatCall(
                model_class=model_class,
                purpose=request.schema_name,
                outcome=outcome,
                estimated_tokens=estimate_prompt_tokens(request),
                prompt_chars=sum(len(m.content) for m in request.messages),
                schema_chars=len(schema),
                messages=len(request.messages),
            )
        )
        return outcome

    def __getattr__(self, name: str) -> Any:
        return getattr(self._router, name)


GEMINI_QUOTA_PAUSE = timedelta(minutes=10)  # a free Gemini model that answered 429 rests this long


class ChatDispatcher:
    """BRAIN-1 (ADR-034): one ``ChatProvider`` for models of two vendors. A name that starts with "gemini"
    goes to Gemini, every other name to Groq; they share the quota tracker, so a model that answered 429 is
    skipped by the router for a while whatever its vendor. Gemini's free tier trains on what it is sent: only
    the tutor's words and the child's given name go (the prompt builders mask contact data)."""

    def __init__(self, groq: ChatProvider | None, gemini: Any | None = None) -> None:
        self._groq, self._gemini = groq, gemini
        self.quota: QuotaTracker = getattr(groq, "quota", None) or QuotaTracker()

    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        if not model.startswith("gemini"):
            if self._groq is None:
                raise ModelUnavailable("no Groq key", model=model)
            return self._groq.chat(request, model)
        if self._gemini is None:
            raise ModelUnavailable("no Gemini key", model=model)
        # Builders bound learning context; Gemini can also accept the static mentor instructions.
        try:
            return self._gemini.chat_with(request, model)
        except QuotaExceeded as exc:
            self.quota.mark_exhausted(model, exc.reset_at or datetime.now(UTC) + GEMINI_QUOTA_PAUSE)
            raise


def _embedding_name(provider: EmbeddingProvider | None) -> str | None:
    return getattr(provider, "model", None)


def groq_key(settings: Settings, *, for_eval: bool = False) -> SecretStr | None:
    """The Groq key of a router (CFG-3): ``GROQ_API_KEY_EVAL`` for evaluations and batch jobs when it is
    set, else ``GROQ_API_KEY``. A key that is not set or empty is no key."""
    eval_key = settings.groq_api_key_eval
    key = eval_key if for_eval and eval_key is not None and eval_key.get_secret_value() else None
    key = key or settings.groq_api_key
    return key if key is not None and key.get_secret_value() else None


def build_router(
    settings: Settings | None = None,
    chains: Mapping[ModelClass, tuple[str, ...]] | None = None,
    *,
    for_eval: bool = False,
) -> AIRouter:
    """Wire real adapters from settings. Missing keys leave the router in template-only mode.

    ``chains`` overrides the model chain of some classes (an eval can judge on a model with its own quota).
    ``for_eval``: the router of an evaluation or a batch job, on ``GROQ_API_KEY_EVAL`` when it is set.
    """
    settings = settings or get_settings()
    groq = None
    key = groq_key(settings, for_eval=for_eval)
    if key is not None:
        from .groq import GroqClient

        groq = GroqClient(key)
    vision = embeddings = gemini_chat = None
    if settings.gemini_api_key is not None and settings.gemini_api_key.get_secret_value():
        from .gemini import GeminiChat, GeminiEmbeddings, GeminiVision

        gemini_chat = GeminiChat(settings.gemini_api_key, timeout_s=10.0)

        vision = GeminiVision(
            settings.gemini_api_key,
            model=settings.gemini_vision_model,
            fallbacks=settings.gemini_vision_fallbacks,
        )
        embeddings = GeminiEmbeddings(settings.gemini_api_key, model=settings.gemini_embedding_model)
    tts = None
    if settings.tts == "vieneu":
        from .vieneu import VieneuSpeech

        tts = VieneuSpeech(settings.vieneu_url, voice=settings.vieneu_voice)
    tutor_models = parse_models(settings.tutor_models)
    mentor = (
        tuple(dict.fromkeys((settings.tutor_mentor_model, *settings.gemini_tutor_fallbacks)))
        if (gemini_chat is not None and settings.tutor_mentor_model)
        else ()
    )
    needs_gemini = bool(mentor) or any(m.startswith("gemini") for m in tutor_models)
    chat = ChatDispatcher(groq, gemini_chat if needs_gemini else None) if (groq or needs_gemini) else None
    planned = default_chat_chains(settings.groq_model, tutor_models)
    # Every live chat role follows the same owner-ranked chain. A successful stronger model
    # returns immediately; AIRouter shares quota cooldowns and retries the head after reset.
    # An explicit TUTOR_MODELS is a complete ordered override, also shared across roles.
    live_models = tutor_models or tuple(dict.fromkeys((*mentor, *planned[ModelClass.TUTOR_REASONING])))
    for role in (
        ModelClass.TUTOR_REASONING,
        ModelClass.LIGHTWEIGHT,
        ModelClass.INTENT_AGENT,
        ModelClass.EVAL_JUDGE,
    ):
        planned[role] = live_models
    planned[ModelClass.TUTOR_MENTOR] = live_models if mentor else ()
    return AIRouter(
        chat_provider=chat,
        stt_provider=groq,
        tts_provider=tts,
        vision_provider=vision,
        embedding_provider=embeddings,
        chains={**planned, **(chains or {})},
        stt_model=settings.groq_stt_model,
        max_calls_per_session=settings.max_llm_calls_per_session,
        model_only_speech=True,
        transient_retry_s=6,
    )
