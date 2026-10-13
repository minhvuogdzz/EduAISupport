"""TTS_VI adapter: VieNeu-TTS (github.com/pnnbao97/VieNeu-TTS, Apache-2.0), run locally (ADR-030).

VieNeu runs in its own virtual environment (`services/voice`, `make voice`), because its package brings
its own web stack; this adapter only speaks HTTP to it. Free and on the machine: nothing leaves it.
"""

from __future__ import annotations

from typing import Any

from .base import InvalidModelOutput, ModelUnavailable, Speech

TIMEOUT_S = 30.0  # a long reply on a CPU: about half its length in seconds


class VieneuSpeech:
    name = "vieneu-tts"

    def __init__(self, url: str, *, voice: str = "", client: Any | None = None) -> None:
        self.url, self.voice = url.rstrip("/"), voice
        self._client = client

    def speak(self, text: str) -> Speech:
        if self._client is None:
            import httpx

            self._client = httpx.Client(timeout=TIMEOUT_S)
        try:
            response = self._client.post(f"{self.url}/speech", json={"text": text, "voice": self.voice})
        except Exception as exc:  # the voice server is not running: the browser reads instead
            reason = f"VieNeu-TTS is not reachable ({type(exc).__name__})"
            raise ModelUnavailable(reason, model=self.name) from exc
        if response.status_code != 200:
            raise ModelUnavailable(f"VieNeu-TTS answered {response.status_code}", model=self.name)
        if not response.content:
            raise InvalidModelOutput("VieNeu-TTS returned no audio", model=self.name)
        return Speech(model=self.name, audio=response.content, content_type="audio/wav")
