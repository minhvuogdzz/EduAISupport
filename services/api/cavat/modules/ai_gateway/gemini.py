"""Gemini adapter: vision/OCR only (geometry images, photographed problems). ADR-017.

Gemini is never used for chat (free tier: 20 requests/day). The ``google-genai`` SDK is
imported only inside this module.
"""

from __future__ import annotations

from typing import Any

from pydantic import SecretStr

from .base import InvalidModelOutput, ModelUnavailable, QuotaExceeded, Usage, VisionResult

DEFAULT_VISION_MODEL = "gemini-3.8-flash"


class GeminiVision:
    def __init__(
        self,
        api_key: str | SecretStr | None = None,
        *,
        model: str = DEFAULT_VISION_MODEL,
        client: Any = None,
    ) -> None:
        """``client``: a fake with ``models.generate_content`` for tests; otherwise a real one is built."""
        self.model = model
        if client is None:
            key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
            if not key:
                raise ValueError("Gemini API key is empty")
            from google import genai

            client = genai.Client(api_key=key)
        self._client = client

    def __repr__(self) -> str:
        return f"GeminiVision(model={self.model!r})"

    def describe_image(
        self, image_bytes: bytes, prompt: str, *, mime_type: str = "image/png"
    ) -> VisionResult:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
        )
        contents = [types.Part.from_bytes(data=image_bytes, mime_type=mime_type), prompt]
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise QuotaExceeded("Gemini rate limited", model=self.model, reset_at=None) from exc
            raise ModelUnavailable(f"Gemini HTTP {exc.code}", model=self.model) from exc
        except Exception as exc:  # network errors from the SDK transport
            raise ModelUnavailable(f"Gemini call failed: {type(exc).__name__}", model=self.model) from exc
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            raise InvalidModelOutput("empty vision response", model=self.model)
        return VisionResult(
            model=self.model, text=text, usage=_usage(getattr(response, "usage_metadata", None))
        )


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
