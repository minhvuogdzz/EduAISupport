"""Groq adapter: OpenAI-compatible HTTP API via ``httpx`` (no vendor SDK). ADR-017.

Chat: Qwen (tutor brain) and gpt-oss fallbacks. Speech-to-text: Whisper.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from .base import (
    MAX_PROMPT_TOKENS,
    ChatRequest,
    ChatResult,
    InvalidModelOutput,
    ModelUnavailable,
    PromptTooLong,
    QuotaExceeded,
    QuotaTracker,
    Transcription,
    Usage,
    check_prompt_size,
    parse_reset_duration,
    quota_limit,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_STT_MODEL = "whisper-large-v3"


def reasoning_effort_for(model: str) -> str:
    """Qwen supports ``"none"`` (verified, ~148 vs ~392 token). gpt-oss only accepts low/medium/high."""
    return "low" if model.startswith("openai/gpt-oss") else "none"


class GroqClient:
    def __init__(
        self,
        api_key: str | SecretStr,
        *,
        base_url: str = GROQ_BASE_URL,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
        quota: QuotaTracker | None = None,
        max_prompt_tokens: int = MAX_PROMPT_TOKENS,
    ) -> None:
        key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
        if not key:
            raise ValueError("Groq API key is empty")
        self.quota = quota or QuotaTracker()
        self.max_prompt_tokens = max_prompt_tokens
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=timeout,
        )

    def __repr__(self) -> str:
        return f"GroqClient(base_url={str(self._http.base_url)!r})"

    def close(self) -> None:
        self._http.close()

    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        # Refuse before sending: a request above the per-minute budget can never run.
        check_prompt_size(request, model, self.max_prompt_tokens)
        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_completion_tokens": request.max_output_tokens,
            "reasoning_effort": reasoning_effort_for(model),
        }
        if request.json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.schema_name,
                    "schema": dict(request.json_schema),
                    "strict": True,
                },
            }
        payload = self._send(model, "/chat/completions", json=body)
        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise InvalidModelOutput("response has no choices[0].message.content", model=model) from exc
        data = _parse_json_object(text, model) if request.json_schema is not None else None
        if data is None and not text.strip():
            raise InvalidModelOutput("empty completion", model=model)
        return ChatResult(model=model, text=text, data=data, usage=_usage(payload.get("usage")))

    def transcribe(
        self,
        audio: bytes,
        *,
        model: str = DEFAULT_STT_MODEL,
        language: str = "vi",
        filename: str = "audio.webm",
    ) -> Transcription:
        payload = self._send(
            model,
            "/audio/transcriptions",
            data={"model": model, "language": language, "response_format": "json", "temperature": "0"},
            files={"file": (filename, audio)},
        )
        text = payload.get("text")
        if not isinstance(text, str):
            raise InvalidModelOutput("transcription has no text", model=model)
        return Transcription(model=model, text=text.strip(), language=language)

    def _send(self, model: str, path: str, **kwargs: Any) -> dict[str, Any]:
        now = datetime.now(UTC)
        try:
            response = self._http.post(path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ModelUnavailable(f"timeout calling {path}", model=model) from exc
        except httpx.HTTPError as exc:
            raise ModelUnavailable(
                f"network error calling {path}: {type(exc).__name__}", model=model
            ) from exc
        self.quota.update(model, response.headers, now)
        status = response.status_code
        if status == 429:
            reset_at = _reset_at(response.headers, now)
            self.quota.mark_exhausted(model, reset_at, now)
            raise QuotaExceeded(
                f"rate limited: {_error_text(response)}",
                model=model,
                reset_at=reset_at,
                limit=quota_limit(_error_text(response, 2000)),
            )
        if status == 413:
            raise PromptTooLong(f"provider rejected request size: {_error_text(response)}", model=model)
        if status == 400 and _error_code(response) == "json_validate_failed":
            raise InvalidModelOutput(f"output failed schema: {_error_text(response)}", model=model)
        if status >= 400:
            raise ModelUnavailable(f"HTTP {status}: {_error_text(response)}", model=model)
        try:
            payload = response.json()
        except ValueError as exc:
            raise InvalidModelOutput("response body is not JSON", model=model) from exc
        if not isinstance(payload, dict):
            raise InvalidModelOutput("response body is not a JSON object", model=model)
        return payload


def _parse_json_object(text: str, model: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidModelOutput("content is not valid JSON", model=model) from exc
    if not isinstance(data, dict):
        raise InvalidModelOutput("content is not a JSON object", model=model)
    return data


def _usage(raw: Any) -> Usage:
    if not isinstance(raw, dict):
        return Usage()
    return Usage(
        prompt_tokens=int(raw.get("prompt_tokens") or 0),
        completion_tokens=int(raw.get("completion_tokens") or 0),
        total_tokens=int(raw.get("total_tokens") or 0),
    )


def _reset_at(headers: Mapping[str, str], now: datetime) -> datetime | None:
    delta = parse_reset_duration(headers.get("retry-after"))
    if delta is None:
        deltas = [
            d
            for d in (
                parse_reset_duration(headers.get("x-ratelimit-reset-tokens")),
                parse_reset_duration(headers.get("x-ratelimit-reset-requests")),
            )
            if d is not None
        ]
        delta = max(deltas) if deltas else None
    return now + delta if delta is not None else None


def _error_body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    error = body.get("error") if isinstance(body, dict) else None
    return error if isinstance(error, dict) else {}


def _error_code(response: httpx.Response) -> str | None:
    code = _error_body(response).get("code")
    return code if isinstance(code, str) else None


def _error_text(response: httpx.Response, size: int = 200) -> str:
    message = _error_body(response).get("message")
    text = message if isinstance(message, str) else response.text
    return text[:size]
