"""Gemini adapter: vision/OCR (geometry images, photographed problems) and RAG embeddings. ADR-017.

``GeminiChat`` is a chat model of the gateway: the evaluation baseline (EVAL-1) and, when the owner lists
it in ``TUTOR_MODELS``, a model of the tutor's chain (BRAIN-1, ADR-034). The ``google-genai`` SDK is
imported only inside this module.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import SecretStr

from .base import (
    ChatRequest,
    ChatResult,
    InvalidModelOutput,
    ModelUnavailable,
    QuotaExceeded,
    Usage,
    VisionResult,
    parse_reset_duration,
)

DEFAULT_VISION_MODEL = "gemini-3.8-flash"


class GeminiVision:
    def __init__(
        self,
        api_key: str | SecretStr | None = None,
        *,
        model: str = DEFAULT_VISION_MODEL,
        fallbacks: tuple[str, ...] = (),
        client: Any = None,
    ) -> None:
        """``client``: a fake with ``models.generate_content`` for tests; otherwise a real one is built.

        ``fallbacks``: models tried in turn when one is rate limited or down (ADR-016: each free model has its
        own daily quota).
        """
        self.model = model
        self.models = (model, *fallbacks)
        if client is None:
            key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            if not key:
                raise ValueError("Gemini API key is empty")
            from google import genai

            client = genai.Client(api_key=key)
        self._client = client

    def __repr__(self) -> str:
        return f"GeminiVision(models={self.models!r})"

    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        """The first model of the chain that answers; the last error when none does."""
        last: Exception | None = None
        for model in self.models:
            try:
                return self._describe(model, image_bytes, prompt, mime_type)
            except (QuotaExceeded, ModelUnavailable) as exc:
                last = exc
        assert last is not None
        raise last

    def describe_with(
        self, model: str, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        """One given model, no fallback (a second reading must come from another model than the first)."""
        return self._describe(model, image_bytes, prompt, mime_type)

    def _describe(self, model: str, image_bytes: bytes, prompt: str, mime_type: str) -> VisionResult:
        from google.genai import errors, types

        # Gemini 3 takes a thinking level; 2.5 a thinking budget (0: no thinking, enough to copy a page).
        thinking = (
            types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
            if model.startswith(("gemini-3", "gemini-4"))
            else types.ThinkingConfig(thinking_budget=0)
        )
        config = types.GenerateContentConfig(thinking_config=thinking)
        contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]
        try:
            response = self._client.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as exc:
            if exc.code == 429:
                raise QuotaExceeded("Gemini rate limited", model=model, reset_at=None) from exc
            raise ModelUnavailable(f"Gemini HTTP {exc.code}: {_api_message(exc)}", model=model) from exc
        except Exception as exc:  # network errors from the SDK transport
            raise ModelUnavailable(f"Gemini call failed: {type(exc).__name__}", model=model) from exc
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise InvalidModelOutput("empty vision response", model=model)
        return VisionResult(model=model, text=text, usage=_usage(getattr(response, "usage_metadata", None)))


class GeminiChat:
    """Gemini as a chat model: the market baseline of the evaluation (EVAL-1) and, since BRAIN-1 (ADR-034), a
    model of the tutor's chain when the owner puts one in ``TUTOR_MODELS``. ``chat`` walks ``models`` (the
    baseline); ``chat_with`` is one model, as the router's chain wants it (each free model has its own
    daily quota)."""

    def __init__(
        self,
        api_key: str | SecretStr,
        *,
        models: tuple[str, ...] = (),
        client: Any = None,
        timeout_s: float = 25.0,
    ) -> None:
        self.models = models
        if client is None:
            from google import genai
            from google.genai import types

            key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            # a tutor turn waits for this call: a Gemini that hangs must fail, and the chain goes on
            client = genai.Client(
                api_key=key, http_options=types.HttpOptions(timeout=max(10_000, int(timeout_s * 1000)))
            )
        self._client = client

    def chat(self, request: ChatRequest) -> ChatResult:
        last: Exception | None = None
        for model in self.models:
            try:
                return self.chat_with(request, model)
            except (QuotaExceeded, ModelUnavailable, InvalidModelOutput) as exc:
                last = exc
        assert last is not None
        raise last

    def chat_with(self, request: ChatRequest, model: str) -> ChatResult:
        from google.genai import errors, types

        system = "\n".join(m.content for m in request.messages if m.role == "system") or None
        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)]
            )
            for m in request.messages
            if m.role != "system"
        ]
        thinking = (
            types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
            if model.startswith(("gemini-3", "gemini-4"))
            else types.ThinkingConfig(thinking_budget=0)
        )
        settings: dict[str, Any] = {
            "system_instruction": system,
            "temperature": request.temperature,
            "max_output_tokens": max(request.max_output_tokens, 2048)
            if model.startswith("gemini-4")
            else max(request.max_output_tokens, 1024)
            if model.startswith("gemini-3")
            else request.max_output_tokens,
            "thinking_config": thinking,
        }
        if request.json_schema is not None:
            settings["response_mime_type"] = "application/json"
            settings["response_json_schema"] = _plain_schema(request.json_schema)
        try:
            response = self._client.models.generate_content(
                model=model, contents=contents, config=types.GenerateContentConfig(**settings)
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise _chat_quota_error(exc, model) from exc
            raise ModelUnavailable(f"Gemini HTTP {exc.code}: {_api_message(exc)}", model=model) from exc
        except Exception as exc:  # network errors from the SDK transport
            raise ModelUnavailable(f"Gemini call failed: {type(exc).__name__}", model=model) from exc
        candidates = getattr(response, "candidates", None)
        if candidates:
            reason = getattr(candidates[0], "finish_reason", None)
            name = getattr(reason, "name", str(reason)) if reason else "STOP"
            if name != "STOP":
                raise InvalidModelOutput("Gemini completion did not finish normally", model=model)
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise InvalidModelOutput("empty chat response", model=model)
        data = None
        if request.json_schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise InvalidModelOutput("content is not valid JSON", model=model) from exc
            if not isinstance(data, dict):
                raise InvalidModelOutput("content is not a JSON object", model=model)
        return ChatResult(
            model=model, text=text, data=data, usage=_usage(getattr(response, "usage_metadata", None))
        )


def _chat_quota_error(exc: Any, model: str, *, now: datetime | None = None) -> QuotaExceeded:
    """Honor Gemini's structured RetryInfo and distinguish daily from minute limits.

    Never infer that all 429s recover after the dispatcher's generic ten-minute pause.
    """
    now = now or datetime.now(UTC)
    raw = getattr(exc, "details", {})
    error = raw.get("error", raw) if isinstance(raw, dict) else {}
    details = error.get("details", []) if isinstance(error, dict) else []
    kinds: set[str] = set()
    delays = []
    for detail in details if isinstance(details, list) else []:
        if not isinstance(detail, dict):
            continue
        if isinstance(detail.get("retryDelay"), str):
            try:
                delay = parse_reset_duration(detail["retryDelay"])
            except (ValueError, OverflowError):
                delay = None
            if delay is not None:
                delays.append(delay)
        violations = detail.get("violations", [])
        for violation in violations if isinstance(violations, list) else []:
            if not isinstance(violation, dict):
                continue
            identity = (
                (str(violation.get("quotaId", "")) + str(violation.get("quotaMetric", "")))
                .lower()
                .replace("_", "")
            )
            if "perday" in identity:
                kinds.add("TPD" if "token" in identity else "RPD")
            elif "perminute" in identity:
                kinds.add("TPM" if "token" in identity else "RPM")
    limit = next((kind for kind in ("RPD", "TPD", "RPM", "TPM") if kind in kinds), None)
    reset_at = now + max(max(delays), timedelta(seconds=1)) if delays else None
    if reset_at is None and limit == "RPD":
        # Google documents daily request resets at midnight Pacific; account for DST.
        from zoneinfo import ZoneInfo

        pacific = ZoneInfo("America/Los_Angeles")
        tomorrow = now.astimezone(pacific).date() + timedelta(days=1)
        reset_at = datetime.combine(tomorrow, datetime.min.time(), tzinfo=pacific).astimezone(UTC)
    return QuotaExceeded(
        f"Gemini HTTP 429{f' ({limit})' if limit else ''}: {_api_message(exc)}",
        model=model,
        reset_at=reset_at,
        limit=limit,
    )


def _plain_schema(schema: Any) -> Any:
    """Strip Groq's strict-object keyword at every level, including meaning-check array items."""
    if isinstance(schema, dict):
        return {k: _plain_schema(v) for k, v in schema.items() if k != "additionalProperties"}
    if isinstance(schema, list):
        return [_plain_schema(value) for value in schema]
    return schema


def _api_message(exc: Any) -> str:
    return str(getattr(exc, "message", "") or "")[:160]


DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"


class GeminiEmbeddings:
    """EMBEDDING model class (Hybrid RAG, plan v1 5.5.2): several texts in one request."""

    def __init__(
        self,
        api_key: str | SecretStr | None = None,
        *,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int = 768,
        client: Any = None,
    ) -> None:
        self.model, self.dimensions = model, dimensions
        if client is None:
            key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            if not key:
                raise ValueError("Gemini API key is empty")
            from google import genai

            client = genai.Client(api_key=key)
        self._client = client

    def embed(self, texts: list[str], *, task: str) -> list[list[float]]:
        from google.genai import errors, types

        config = types.EmbedContentConfig(task_type=task, output_dimensionality=self.dimensions)
        try:
            response = self._client.models.embed_content(model=self.model, contents=texts, config=config)
        except errors.APIError as exc:
            if exc.code == 429:
                raise QuotaExceeded(
                    "Gemini embeddings rate limited", model=self.model, reset_at=None
                ) from exc
            raise ModelUnavailable(f"Gemini HTTP {exc.code}", model=self.model) from exc
        except Exception as exc:  # network errors from the SDK transport
            raise ModelUnavailable(f"Gemini call failed: {type(exc).__name__}", model=self.model) from exc
        vectors = [list(e.values) for e in (getattr(response, "embeddings", None) or [])]
        if len(vectors) != len(texts):
            raise InvalidModelOutput("embedding count differs from the texts", model=self.model)
        return vectors


def _usage(meta: Any) -> Usage:
    if meta is None:
        return Usage()
    prompt = getattr(meta, "prompt_token_count", None) or 0
    completion = getattr(meta, "candidates_token_count", None) or 0
    total = getattr(meta, "total_token_count", None) or prompt + completion
    return Usage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)
