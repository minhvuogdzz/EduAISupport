"""Vendor-neutral contracts of the AI gateway (ADR-017, rule 6).

Business logic talks to the gateway by ``ModelClass``; only the adapters in this package
(``groq.py``, ``gemini.py``) know vendor URLs and SDKs.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol

# Groq free tier allows 8.000 token/minute; each call must stay <= 3.000 token (ADR-017).
MAX_PROMPT_TOKENS = 3000
MODEL_WAIT_MESSAGE = (
    "Cô đang thử lại để tiếp tục đúng chỗ mình vừa học. Con không cần gửi lại câu vừa rồi nhé."
)
# Estimate without a tokenizer. CFG-2 measured it on 35 real tutor calls (docs/poc/free-tier-quota.md):
# Qwen 3,15 characters per token, so 3 over-counts it by 14%; gpt-oss-120b 2,76 (about right) and
# gpt-oss-20b 2,07 (under by 13%). Two simulated sessions only [ASSUME].
CHARS_PER_TOKEN = 3
MESSAGE_OVERHEAD_TOKENS = 4


class ModelClass(StrEnum):
    TUTOR_REASONING = "tutor_reasoning"
    TUTOR_MENTOR = "tutor_mentor"
    LIGHTWEIGHT = "lightweight"
    # REFORM-5 (3.1): reads the few letters a child types when nothing else reads them ("ki", "kt", "ể"). Its
    # own chain, on gpt-oss-120b first: every Groq model has its own per-minute and per-day quota, so these
    # reads do not spend the tokens the tutor's own voice (Qwen) needs.
    INTENT_AGENT = "intent_agent"
    EVAL_JUDGE = "eval_judge"
    STT_VI = "stt_vi"
    TTS_VI = "tts_vi"  # the tutor's voice (ADR-030: VieNeu-TTS, local)
    VISION_OCR = "vision_ocr"
    EMBEDDING = "embedding"  # Hybrid RAG vectors (plan v1 5.5.2, ADR-017: Gemini)


CHAT_MODEL_CLASSES = frozenset(
    {
        ModelClass.TUTOR_REASONING,
        ModelClass.TUTOR_MENTOR,
        ModelClass.LIGHTWEIGHT,
        ModelClass.INTENT_AGENT,
        ModelClass.EVAL_JUDGE,
    }
)


@dataclass(frozen=True)
class ChatMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class ChatRequest:
    messages: tuple[ChatMessage, ...]
    # When set, the provider must return a JSON object matching this schema (strict mode).
    json_schema: Mapping[str, Any] | None = None
    schema_name: str = "tutor_output"
    max_output_tokens: int = 400
    temperature: float = 0.3


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ChatResult:
    model: str
    text: str
    # Parsed JSON object when the request carried a json_schema.
    data: dict[str, Any] | None = None
    usage: Usage = field(default_factory=Usage)


@dataclass(frozen=True)
class Transcription:
    model: str
    text: str
    language: str


@dataclass(frozen=True)
class Speech:
    model: str
    audio: bytes
    content_type: str = "audio/wav"


@dataclass(frozen=True)
class VisionResult:
    model: str
    text: str
    usage: Usage = field(default_factory=Usage)


class AIGatewayError(Exception):
    """Base error. Messages never contain API keys."""

    def __init__(self, message: str, *, model: str | None = None) -> None:
        super().__init__(message)
        self.model = model


class QuotaExceeded(AIGatewayError):
    """Provider rate limit hit (HTTP 429). ``reset_at`` is when the quota frees up, if known; ``limit`` is
    the limit the provider names: ITPM (input tokens per minute), TPM, TPD (tokens per day), RPM, RPD."""

    def __init__(
        self,
        message: str,
        *,
        model: str | None = None,
        reset_at: datetime | None = None,
        limit: str | None = None,
    ) -> None:
        super().__init__(message, model=model)
        self.reset_at = reset_at
        self.limit = limit


class ModelUnavailable(AIGatewayError):
    """Network error, timeout, 5xx, auth or unknown model: try the next model in the chain."""


class InvalidModelOutput(AIGatewayError):
    """The model answered but the output is not usable (not JSON, wrong shape, empty)."""


class PromptTooLong(AIGatewayError):
    """Refused before sending: the estimated prompt exceeds ``MAX_PROMPT_TOKENS``."""

    def __init__(self, message: str, *, model: str | None = None, estimated_tokens: int = 0) -> None:
        super().__init__(message, model=model)
        self.estimated_tokens = estimated_tokens


class ChatProvider(Protocol):
    def chat(self, request: ChatRequest, model: str) -> ChatResult: ...


class SpeechToText(Protocol):
    def transcribe(
        self, audio: bytes, *, model: str, language: str = "vi", filename: str = "audio.webm"
    ) -> Transcription: ...


class TextToSpeech(Protocol):
    name: str

    def speak(self, text: str) -> Speech: ...


class VisionProvider(Protocol):
    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], *, task: str) -> list[list[float]]: ...


# Groq names the limit in brackets: "... on input tokens per minute (ITPM): Limit 7000, Used 6360 ..." (seen
# 2026-10-25); the day limits are worded alike [ASSUME].
_LIMIT_KIND = re.compile(r"\(((?:I|O)?(?:TP|RP)[MD])\)")
_ORGANIZATION = re.compile(r"\s+in organization `[^`]*`")


def quota_limit(message: str) -> str | None:
    """The limit a Groq 429 names (ITPM, OTPM, TPM, TPD, RPM, RPD...), or None when the text names none."""
    found = _LIMIT_KIND.search(message)
    return found.group(1) if found else None


def error_detail(message: str, size: int = 200) -> str:
    """A provider error as the session log keeps it (CFG-3): without the organization id, cut short."""
    return _ORGANIZATION.sub("", message)[:size]


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def estimate_prompt_tokens(request: ChatRequest) -> int:
    """Upper-bound estimate of what the provider bills as prompt tokens (messages + schema)."""
    total = sum(estimate_tokens(m.content) + MESSAGE_OVERHEAD_TOKENS for m in request.messages)
    if request.json_schema is not None:
        total += estimate_tokens(json.dumps(request.json_schema, ensure_ascii=False))
    return total


def check_prompt_size(request: ChatRequest, model: str, limit: int = MAX_PROMPT_TOKENS) -> int:
    estimated = estimate_prompt_tokens(request)
    if estimated > limit:
        raise PromptTooLong(
            f"estimated prompt {estimated} tokens > limit {limit}", model=model, estimated_tokens=estimated
        )
    return estimated


_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def parse_reset_duration(value: str | None) -> timedelta | None:
    """Parse Groq reset values such as ``"2m59.56s"``, ``"7.66s"``, ``"120ms"`` or ``"1h2m"``."""
    if not value:
        return None
    value = value.strip()
    try:
        return timedelta(seconds=float(value))  # Retry-After style: plain seconds
    except ValueError:
        pass
    parts = _DURATION_PART.findall(value)
    if not parts or "".join(n + u for n, u in parts) != value:
        return None
    scale = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
    return timedelta(seconds=sum(float(n) * scale[u] for n, u in parts))


def _int_header(headers: Mapping[str, str], name: str) -> int | None:
    raw = headers.get(name)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


@dataclass(frozen=True)
class QuotaSnapshot:
    limit_requests: int | None = None
    remaining_requests: int | None = None
    reset_requests_at: datetime | None = None
    limit_tokens: int | None = None
    remaining_tokens: int | None = None
    reset_tokens_at: datetime | None = None
    # Set after a 429: nothing should be sent to this model before this time.
    blocked_until: datetime | None = None


class QuotaTracker:
    """Last known quota per model, read from ``x-ratelimit-*`` headers (in-process only)."""

    def __init__(self) -> None:
        self._snapshots: dict[str, QuotaSnapshot] = {}

    def update(self, model: str, headers: Mapping[str, str], now: datetime | None = None) -> QuotaSnapshot:
        now = now or datetime.now(UTC)
        reset_req = parse_reset_duration(headers.get("x-ratelimit-reset-requests"))
        reset_tok = parse_reset_duration(headers.get("x-ratelimit-reset-tokens"))
        snapshot = QuotaSnapshot(
            limit_requests=_int_header(headers, "x-ratelimit-limit-requests"),
            remaining_requests=_int_header(headers, "x-ratelimit-remaining-requests"),
            reset_requests_at=now + reset_req if reset_req is not None else None,
            limit_tokens=_int_header(headers, "x-ratelimit-limit-tokens"),
            remaining_tokens=_int_header(headers, "x-ratelimit-remaining-tokens"),
            reset_tokens_at=now + reset_tok if reset_tok is not None else None,
            blocked_until=self._snapshots.get(model, QuotaSnapshot()).blocked_until,
        )
        self._snapshots[model] = snapshot
        return snapshot

    def mark_exhausted(self, model: str, reset_at: datetime | None, now: datetime | None = None) -> None:
        now = now or datetime.now(UTC)
        # Unknown reset: back off for one minute (the token window of Groq).
        until = reset_at or now + timedelta(minutes=1)
        self._snapshots[model] = replace(self._snapshots.get(model, QuotaSnapshot()), blocked_until=until)

    def snapshot(self, model: str) -> QuotaSnapshot | None:
        return self._snapshots.get(model)

    def is_exhausted(self, model: str, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        snap = self._snapshots.get(model)
        if snap is None:
            return False
        if snap.blocked_until is not None and snap.blocked_until > now:
            return True
        if snap.remaining_requests == 0 and (snap.reset_requests_at is None or snap.reset_requests_at > now):
            return True
        return snap.remaining_tokens == 0 and (snap.reset_tokens_at is None or snap.reset_tokens_at > now)

    def reset_at(self, model: str) -> datetime | None:
        snap = self._snapshots.get(model)
        if snap is None:
            return None
        candidates = [
            reset
            for remaining, reset in (
                (snap.remaining_requests, snap.reset_requests_at),
                (snap.remaining_tokens, snap.reset_tokens_at),
            )
            if remaining == 0 and reset is not None
        ]
        if snap.blocked_until is not None:
            candidates.append(snap.blocked_until)
        return max(candidates) if candidates else None
