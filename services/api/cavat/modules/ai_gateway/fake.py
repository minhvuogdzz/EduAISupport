"""Scripted fake models for tests: no network, no API key.

A script step is a ``dict`` (JSON answer), a ``str`` (raw text) or an ``Exception`` (raised).
Steps are consumed in order, either from one shared list or from a list per model name.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .base import (
    MAX_PROMPT_TOKENS,
    ChatRequest,
    ChatResult,
    InvalidModelOutput,
    QuotaTracker,
    Transcription,
    Usage,
    VisionResult,
    check_prompt_size,
    estimate_tokens,
)

Step = dict[str, Any] | str | Exception


class ScriptExhausted(AssertionError):
    """The code under test made more calls than the script planned."""


@dataclass
class FakeChatModel:
    script: Sequence[Step] | Mapping[str, Sequence[Step]]
    max_prompt_tokens: int = MAX_PROMPT_TOKENS
    quota: QuotaTracker = field(default_factory=QuotaTracker)
    calls: list[tuple[str, ChatRequest]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.script, Mapping):
            self._queues: dict[str | None, list[Step]] = {m: list(s) for m, s in self.script.items()}
        else:
            self._queues = {None: list(self.script)}

    def chat(self, request: ChatRequest, model: str) -> ChatResult:
        estimated = check_prompt_size(request, model, self.max_prompt_tokens)  # same rule as the real adapter
        self.calls.append((model, request))
        queue = self._queues.get(model) if None not in self._queues else self._queues[None]
        if not queue:
            raise ScriptExhausted(f"no scripted step left for model {model!r}")
        step = queue.pop(0)
        if isinstance(step, Exception):
            raise step
        text = json.dumps(step, ensure_ascii=False) if isinstance(step, dict) else step
        data = None
        if request.json_schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise InvalidModelOutput("content is not valid JSON", model=model) from exc
            if not isinstance(data, dict):
                raise InvalidModelOutput("content is not a JSON object", model=model)
        completion = estimate_tokens(text)
        usage = Usage(
            prompt_tokens=estimated, completion_tokens=completion, total_tokens=estimated + completion
        )
        return ChatResult(model=model, text=text, data=data, usage=usage)


@dataclass
class FakeSpeechToText:
    script: list[str | Exception]
    calls: list[tuple[str, str]] = field(default_factory=list)

    def transcribe(
        self, audio: bytes, *, model: str, language: str = "vi", filename: str = "audio.webm"
    ) -> Transcription:
        self.calls.append((model, language))
        if not self.script:
            raise ScriptExhausted("no scripted transcription left")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return Transcription(model=model, text=step, language=language)


@dataclass
class FakeVision:
    script: list[str | Exception]
    model: str = "fake-vision"
    calls: list[str] = field(default_factory=list)

    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        self.calls.append(prompt)
        if not self.script:
            raise ScriptExhausted("no scripted vision answer left")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return VisionResult(model=self.model, text=step)
