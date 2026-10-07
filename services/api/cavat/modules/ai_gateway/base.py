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
# [ASSUME] Conservative estimate without a tokenizer: Vietnamese with diacritics tokenizes at
# roughly 3 characters per token or worse, so 3 over-counts rather than under-counts.
CHARS_PER_TOKEN = 3
MESSAGE_OVERHEAD_TOKENS = 4


class ModelClass(StrEnum):
    TUTOR_REASONING = "tutor_reasoning"
    LIGHTWEIGHT = "lightweight"
    EVAL_JUDGE = "eval_judge"
    STT_VI = "stt_vi"
    VISION_OCR = "vision_ocr"
    EMBEDDING = "embedding"  # Hybrid RAG vectors (plan v1 5.5.2, ADR-017: Gemini)


CHAT_MODEL_CLASSES = frozenset({ModelClass.TUTOR_REASONING, ModelClass.LIGHTWEIGHT, ModelClass.EVAL_JUDGE})


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
    """Provider rate limit hit (HTTP 429). ``reset_at`` is when the quota frees up, if known."""

    def __init__(self, message: str, *, model: str | None = None, reset_at: datetime | None = None) -> None:
        super().__init__(message, model=model)
        self.reset_at = reset_at


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


class VisionProvider(Protocol):
    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult: ...


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str], *, task: str) -> list[list[float]]: ...


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
        candidates = [t for t in (snap.blocked_until, snap.reset_requests_at, snap.reset_tokens_at) if t]
        return max(candidates) if candidates else None
