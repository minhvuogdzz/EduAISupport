"""Choose a model by ``ModelClass``, walk the fallback chain, enforce the per-session cap (ADR-017).

Chain for chat: Qwen -> gpt-oss -> tell the caller to use an approved template. The tutor
session never stops because of a provider. Callers never pick a model name (rule 4).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from cavat.config import Settings, get_settings

from .base import (
    CHAT_MODEL_CLASSES,
    AIGatewayError,
    ChatProvider,
    ChatRequest,
    ChatResult,
    InvalidModelOutput,
    ModelClass,
    ModelUnavailable,
    PromptTooLong,
    QuotaExceeded,
    QuotaTracker,
    SpeechToText,
    Transcription,
    VisionProvider,
    VisionResult,
)

DEFAULT_MAX_LLM_CALLS_PER_SESSION = 15


def default_chat_chains(primary: str = "qwen/qwen3.8-27b") -> dict[ModelClass, tuple[str, ...]]:
    return {
        ModelClass.TUTOR_REASONING: (primary, "openai/gpt-oss-120b"),
        ModelClass.LIGHTWEIGHT: (primary, "openai/gpt-oss-20b"),
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


class AIRouter:
    def __init__(
        self,
        *,
        chat_provider: ChatProvider | None = None,
        stt_provider: SpeechToText | None = None,
        vision_provider: VisionProvider | None = None,
        chains: Mapping[ModelClass, tuple[str, ...]] | None = None,
        stt_model: str = "whisper-large-v3",
        max_calls_per_session: int = DEFAULT_MAX_LLM_CALLS_PER_SESSION,
        quota: QuotaTracker | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._chat = chat_provider
        self._stt = stt_provider
        self._vision = vision_provider
        self._chains = dict(chains or default_chat_chains())
        self._stt_model = stt_model
        self.max_calls_per_session = max_calls_per_session
        self.quota = quota or getattr(chat_provider, "quota", None) or QuotaTracker()
        self._clock = clock

    def chain(self, model_class: ModelClass) -> tuple[str, ...]:
        if model_class not in CHAT_MODEL_CLASSES:
            raise ValueError(f"{model_class} is not a chat model class")
        return self._chains[model_class]

    def chat(self, model_class: ModelClass, request: ChatRequest, *, calls_used: int) -> ChatOutcome:
        """Try the chain for ``model_class``. ``calls_used`` comes from the session state (SessionContext)."""
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
                attempts.append(Attempt(model, sent=False, error=QuotaExceeded.__name__))
                reason = FallbackReason.QUOTA_EXCEEDED
                continue
            try:
                result = self._chat.chat(request, model)
            except PromptTooLong:
                # Every Groq model shares the same budget: no point trying the next one.
                attempts.append(Attempt(model, sent=False, error=PromptTooLong.__name__))
                return ChatOutcome(None, FallbackReason.PROMPT_TOO_LONG, calls_made, tuple(attempts))
            except (QuotaExceeded, ModelUnavailable, InvalidModelOutput) as exc:
                calls_made += 1
                attempts.append(Attempt(model, sent=True, error=type(exc).__name__))
                reason = _REASON_BY_ERROR[type(exc)]
                continue
            calls_made += 1
            attempts.append(Attempt(model, sent=True))
            return ChatOutcome(result, None, calls_made, tuple(attempts))
        return ChatOutcome(None, reason, calls_made, tuple(attempts))

    def transcribe(
        self, audio: bytes, *, language: str = "vi", filename: str = "audio.webm"
    ) -> Transcription:
        """STT_VI. On error the caller falls back to the browser Web Speech API."""
        if self._stt is None:
            raise ModelUnavailable("no speech-to-text provider configured")
        return self._stt.transcribe(audio, model=self._stt_model, language=language, filename=filename)

    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        """VISION_OCR (Gemini). Not counted in the per-session LLM cap."""
        if self._vision is None:
            raise ModelUnavailable("no vision provider configured")
        return self._vision.describe_image(image_bytes, prompt, mime_type=mime_type)


def build_router(
    settings: Settings | None = None, chains: Mapping[ModelClass, tuple[str, ...]] | None = None
) -> AIRouter:
    """Wire real adapters from settings. Missing keys leave the router in template-only mode.

    ``chains`` overrides the model chain of some classes (an eval can judge on a model with its own quota).
    """
    settings = settings or get_settings()
    groq = None
    if settings.groq_api_key is not None and settings.groq_api_key.get_secret_value():
        from .groq import GroqClient

        groq = GroqClient(settings.groq_api_key)
    vision = None
    if settings.gemini_api_key is not None and settings.gemini_api_key.get_secret_value():
        from .gemini import GeminiVision

        vision = GeminiVision(settings.gemini_api_key, model=settings.gemini_vision_model)
    return AIRouter(
        chat_provider=groq,
        stt_provider=groq,
        vision_provider=vision,
        chains={**default_chat_chains(settings.groq_model), **(chains or {})},
        stt_model=settings.groq_stt_model,
        max_calls_per_session=settings.max_llm_calls_per_session,
    )
