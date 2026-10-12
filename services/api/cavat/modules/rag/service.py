"""The school's Hybrid RAG index: built from the chapter content and the teacher's documents, rebuilt
whenever that corpus changes (a document uploaded or deleted, a chapter version changed).

A document passage is tied to the node it talks about when one node clearly stands out (``tag_passages``,
DI-17); otherwise it stays a chapter-level passage, one step away from every node.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool

from cavat.config import get_settings
from cavat.core.repository import utc_now
from cavat.modules.content.chapter_package import ORDER_RELATIONS, Chapter
from cavat.modules.library.repository import RAG_KINDS, DocumentRepository, TeacherDocument
from cavat.modules.rag.bm25 import TwoFormBM25
from cavat.modules.rag.chunks import Chunk, chapter_chunks, document_chunks
from cavat.modules.rag.embed import Embedder, GatewayEmbedder
from cavat.modules.rag.retrieve import RagIndex

TAG_MARGIN = 1.5  # DI-17
SEMANTIC_RETRY = timedelta(minutes=10)  # after a failed embedding call (quota, network), try again


def default_embedder() -> Embedder | None:
    """Gemini through the gateway when a key is configured; without one, keywords and structure only.

    The offline trigram vectors are for the tests: they match spelling, not meaning, so a session without a
    key runs as when the model is down, on keywords and structure (plan v1 5.5.4).
    """
    from cavat.modules.ai_gateway.router import build_router

    settings = get_settings()
    router = build_router(settings)
    model = router.embedding_model
    if model is None:
        return None
    cache = settings.storage_dir / "rag" / f"embeddings-{model}.jsonl"
    return GatewayEmbedder(router.embed, model, cache)


def tag_passages(passages: list[Chunk], reference: list[Chunk]) -> list[Chunk]:
    """Tie each passage to the node of the chapter passages it is most like (DI-17).

    Every passage is scored with BM25 against the chapter's own chunks (theory, method, examples, notes);
    a node scores its best chunk. The best node is kept when it scores at least 1.5 times the second one;
    otherwise the passage stays chapter-level, one step from every node. Measured on 11 sample passages:
    7 tied right, 4 left at chapter level, none tied wrong (a node profile of name, description and rule
    tied 5).
    """
    tied = [c for c in reference if c.node_id]
    if not tied:
        return passages
    index = TwoFormBM25([c.text for c in tied])
    out = []
    for passage in passages:
        best: dict[str, float] = {}
        for c, score in zip(tied, index.scores(passage.text), strict=True):
            if passage.chapter_id and c.chapter_id != passage.chapter_id:
                continue
            best[c.node_id or ""] = max(best.get(c.node_id or "", 0.0), score)
        ordered = sorted(best.items(), key=lambda kv: -kv[1])
        first = ordered[0] if ordered else ("", 0.0)
        second = ordered[1][1] if len(ordered) > 1 else 0.0
        if first[1] > 0 and first[1] >= TAG_MARGIN * second:
            chapter = next(c.chapter_id for c in tied if c.node_id == first[0])
            out.append(replace(passage, node_id=first[0], chapter_id=passage.chapter_id or chapter))
        else:
            out.append(passage)
    return out


class RagService:
    def __init__(
        self,
        school_id: str,
        chapters: Callable[[], dict[str, Chapter]],
        embedder: Callable[[], Embedder | None] = default_embedder,
    ) -> None:
        self.school_id = school_id
        self._chapters = chapters
        self._make_embedder = embedder
        self._embedder: Embedder | None = None  # made once: its cache of vectors lives as long as the service
        self._embedder_made = False
        self._index: RagIndex | None = None
        self._lock = asyncio.Lock()  # one build at a time
        self._signature: str | None = None
        self.built_at: datetime | None = None
        self.documents: list[TeacherDocument] = []

    def chapters(self) -> dict[str, Chapter]:
        return self._chapters()

    def _signature_of(self, docs: list[TeacherDocument]) -> str:
        parts = [f"{cid}:{c.package.version}" for cid, c in sorted(self._chapters().items())]
        parts += [f"{d.id}:{d.sha256}:{d.status}:{len(d.text)}:{d.chapter_id}:{d.kind}" for d in docs]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _build(self, docs: list[TeacherDocument]) -> RagIndex:
        chapters = self._chapters()
        chunks: list[Chunk] = []
        graph: dict[str, set[str]] = {}
        for chapter in chapters.values():
            chunks += chapter_chunks(chapter)
            for r in chapter.package.relations:
                # Plan 5.5.3, step 1: a node reaches what it builds on (its prerequisites, the basic node it
                # applies) and the nodes like it, never the nodes that come after it (no teaching ahead).
                if r.type in ORDER_RELATIONS:
                    graph.setdefault(r.target, set()).add(r.source)
                else:
                    graph.setdefault(r.source, set()).add(r.target)
                    graph.setdefault(r.target, set()).add(r.source)
        passages: list[Chunk] = []
        for doc in docs:
            if doc.text and doc.kind in RAG_KINDS:  # never an answer key or a test (rule 2)
                passages += document_chunks(doc.id, doc.title, doc.chapter_id, doc.text)
        chunks += tag_passages(passages, chunks)
        if not self._embedder_made:
            self._embedder, self._embedder_made = self._make_embedder(), True
        return RagIndex(chunks, self._embedder, graph)

    def _stale(self, signature: str) -> bool:
        if self._index is None or signature != self._signature:
            return True
        failed = self._index.semantic_error is not None
        return failed and self.built_at is not None and utc_now() - self.built_at > SEMANTIC_RETRY

    async def current(self, database: Any, *, force: bool = False) -> RagIndex:
        """The index of the corpus as it is now: rebuilt when a document or a chapter version changed."""
        docs = await DocumentRepository(database, self.school_id).list_all()
        signature = self._signature_of(docs)
        async with self._lock:
            if force or self._stale(signature):
                self._index = await run_in_threadpool(self._build, docs)
                self._signature, self.built_at, self.documents = signature, utc_now(), docs
            assert self._index is not None
            return self._index
