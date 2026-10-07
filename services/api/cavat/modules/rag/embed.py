"""Vectors of the Hybrid RAG (plan v1, 5.5.2-5.5.4).

- ``GatewayEmbedder``: the EMBEDDING model class of the AI gateway (Gemini), texts sent in batches, every
  vector cached on disk by a hash of (model, text) so the free-tier quota is spent once per passage.
- ``HashEmbedder``: deterministic, offline (hashed character trigrams of the folded text): the tests and a
  session without a key still run (5.5.4). It is a weak semantic signal and is labelled as such.
Cosine is written here with numpy; no vector database (D-T7, ADR-018).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

import numpy as np

from cavat.core.vi_text import fold, normalize


class Embedder(Protocol):
    name: str
    semantic: bool  # False for the offline trigram vectors: spelling, not meaning

    def embed(self, texts: Sequence[str], task: str) -> np.ndarray: ...


class HashEmbedder:
    """Character trigrams of the folded text hashed into ``dims`` buckets, L2-normalized."""

    def __init__(self, dims: int = 512) -> None:
        self.dims = dims
        self.name = f"hash-trigram-{dims}"
        self.semantic = False

    def embed(self, texts: Sequence[str], task: str) -> np.ndarray:
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for row, text in enumerate(texts):
            t = f" {fold(normalize(text))} "
            for i in range(len(t) - 2):
                h = int.from_bytes(hashlib.blake2b(t[i : i + 3].encode(), digest_size=4).digest(), "little")
                out[row, h % self.dims] += 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


class GatewayEmbedder:
    """Embeddings from the gateway, cached on disk; ``batch`` texts per request."""

    def __init__(
        self,
        embed_batch: Callable[[list[str], str], list[list[float]]],
        model: str,
        cache_file: Path,
        batch: int = 64,
    ) -> None:
        self._embed_batch = embed_batch
        self.name = model
        self.semantic = True
        self._cache_file = cache_file
        self._batch = batch
        self._cache: dict[str, list[float]] = {}
        if cache_file.is_file():
            for line in cache_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self._cache[entry["k"]] = entry["v"]

    def _key(self, text: str, task: str) -> str:
        return hashlib.sha256(f"{self.name}|{task}|{text}".encode()).hexdigest()

    def embed(self, texts: Sequence[str], task: str) -> np.ndarray:
        keys = [self._key(t, task) for t in texts]
        missing = [i for i, k in enumerate(keys) if k not in self._cache]
        new_lines = []
        for start in range(0, len(missing), self._batch):
            part = missing[start : start + self._batch]
            vectors = self._embed_batch([texts[i] for i in part], task)
            for i, v in zip(part, vectors, strict=True):
                self._cache[keys[i]] = v
                new_lines.append(json.dumps({"k": keys[i], "v": v}))
        if new_lines:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            with self._cache_file.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(new_lines) + "\n")
        matrix = np.array([self._cache[k] for k in keys], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) if len(matrix) else np.zeros((0, 1))
        return matrix / np.where(norms == 0, 1, norms) if len(matrix) else matrix


def cosine(matrix: np.ndarray, vector: np.ndarray) -> np.ndarray:
    """Cosine of every (normalized) row with a (normalized) vector."""
    if matrix.size == 0:
        return np.zeros(0, dtype=np.float32)
    return matrix @ vector
