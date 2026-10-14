"""Gemini adapter: vision/OCR (geometry images, photographed problems) and RAG embeddings. ADR-017.

Gemini is never the tutor (free tier: 20 requests/day); ``GeminiChat`` only answers as the market baseline
of the evaluation (EVAL-1). The ``google-genai`` SDK is
imported only inside this module.
"""

from __future__ import annotations

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
            if model.startswith("gemini-3")
            else types.ThinkingConfig(thinking_budget=0)
        )
        config = types.GenerateContentConfig(thinking_config=thinking)
        contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]
        try:
            response = self._client.models.generate_content(model=model, contents=contents, config=config)
        except errors.APIError as exc:
            if exc.code == 429:
                raise QuotaExceeded("Gemini rate limited", model=model, reset_at=None) from exc
            raise ModelUnavailable(f"Gemini HTTP {exc.code}", model=model) from exc
        except Exception as exc:  # network errors from the SDK transport
            raise ModelUnavailable(f"Gemini call failed: {type(exc).__name__}", model=model) from exc
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise InvalidModelOutput("empty vision response", model=model)
        return VisionResult(model=model, text=text, usage=_usage(getattr(response, "usage_metadata", None)))


class GeminiChat:
    """EVAL-1 only: Gemini as the baseline "chatbot on the market" the tutor is compared with. Never the tutor
    (ADR-017: the tutor is Qwen); a chain of free models, each with 20 requests a day."""

    def __init__(self, api_key: str | SecretStr, *, models: tuple[str, ...], client: Any = None) -> None:
        self.models = models
        if client is None:
            from google import genai

            key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            client = genai.Client(api_key=key)
        self._client = client

    def chat(self, request: ChatRequest) -> ChatResult:
        from google.genai import errors, types

        system = "\n".join(m.content for m in request.messages if m.role == "system") or None
        contents = [
            types.Content(
                role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)]
            )
            for m in request.messages
            if m.role != "system"
        ]
        last: Exception | None = None
        for model in self.models:
            thinking = (
                types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
                if model.startswith("gemini-3")
                else types.ThinkingConfig(thinking_budget=0)
            )
            config = types.GenerateContentConfig(
                system_instruction=system,
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens,
                thinking_config=thinking,
            )
            try:
                response = self._client.models.generate_content(model=model, contents=contents, config=config)
            except errors.APIError as exc:
                last = (QuotaExceeded if exc.code == 429 else ModelUnavailable)(
                    f"Gemini HTTP {exc.code}", model=model
                )
                continue
            except Exception as exc:
                last = ModelUnavailable(f"Gemini call failed: {type(exc).__name__}", model=model)
                continue
            text = (getattr(response, "text", None) or "").strip()
            if text:
                return ChatResult(
                    model=model, text=text, usage=_usage(getattr(response, "usage_metadata", None))
                )
            last = InvalidModelOutput("empty chat response", model=model)
        assert last is not None
        raise last


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
