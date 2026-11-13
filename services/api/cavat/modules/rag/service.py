"""The school's Hybrid RAG index: built from the chapter content and the teacher's documents, rebuilt
whenever that corpus changes (a document uploaded or deleted, a chapter version changed).

A document passage is tied to the node it talks about when one node clearly stands out (``tag_passages``,
DI-17); otherwise it stays a chapter-level passage, one step away from every node.

ENG-2 (ADR-061): one index per subject of the school, built from that subject's chapters, documents and
graph only (filtered when the index is built, not when it is read).
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool

from cavat.config import get_settings
from cavat.core.repository import utc_now
from cavat.core.subjects import check_subject
from cavat.modules.content.chapter_package import ORDER_RELATIONS, Chapter
from cavat.modules.library.repository import RAG_KINDS, DocumentRepository, TeacherDocument
from cavat.modules.rag.analyzers import analyzer_for
from cavat.modules.rag.bm25 import TwoFormBM25
from cavat.modules.rag.chunks import Chunk, chapter_chunks, document_chunks
from cavat.modules.rag.embed import Embedder, GatewayEmbedder
from cavat.modules.rag.retrieve import RagIndex

TAG_MARGIN = 1.5  # DI-17
SPREAD_SHARE, SPREAD_NODES = 0.5, 3  # DI-50: three nodes at half the best score or more: a passage of several
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

    ENG-2: a passage is only ever compared with the chunks of its own subject, read with that subject's
    analyzer: an English passage is never tied to a node of Mathematics, nor the other way round, also when
    it names no chapter.
    """
    by_subject: dict[str, list[Chunk]] = {}
    for c in reference:
        if c.node_id:
            by_subject.setdefault(c.subject, []).append(c)
    indexes = {
        subject: TwoFormBM25([c.text for c in tied], analyzer_for(subject))
        for subject, tied in by_subject.items()
    }
    out = []
    for passage in passages:
        tied = by_subject.get(passage.subject, [])
        if not tied:
            out.append(passage)
            continue
        best: dict[str, float] = {}
        for c, score in zip(tied, indexes[passage.subject].scores(passage.text), strict=True):
            if passage.chapter_id and c.chapter_id != passage.chapter_id:
                continue
            best[c.node_id or ""] = max(best.get(c.node_id or "", 0.0), score)
        ordered = sorted(best.items(), key=lambda kv: -kv[1])
        first = ordered[0] if ordered else ("", 0.0)
        second = ordered[1][1] if len(ordered) > 1 else 0.0
        # DI-50: a passage about several periods (a chapter overview, a list of mistakes of every lesson)
        # scores close to its best on many nodes: it is tied to none of them, whatever its margin.
        spread = tuple(n for n, score in ordered if score > 0 and score >= SPREAD_SHARE * first[1])
        if first[1] > 0 and first[1] >= TAG_MARGIN * second and len(spread) < SPREAD_NODES:
            chapter = next(c.chapter_id for c in tied if c.node_id == first[0])
            out.append(replace(passage, node_id=first[0], chapter_id=passage.chapter_id or chapter))
        else:  # the nodes it may be about: it reaches a question only when every one of them is in scope
            out.append(replace(passage, candidates=spread))
    return out


@dataclass
class SubjectIndex:
    """The index of one subject and what it was built from (ENG-2)."""

    index: RagIndex | None = None
    signature: str | None = None
    built_at: datetime | None = None
    documents: list[TeacherDocument] = field(default_factory=list)


class RagService:
    """The school's indexes, one per subject (ENG-2, ADR-061): the chapters, documents and graph of a
    subject make its own ``RagIndex``; nothing of another subject is ever put in it. A caller always names
    the subject: the one of the chapter or unit package the session runs, set by the backend."""

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
        self._lock = asyncio.Lock()  # one build at a time
        self._subjects: dict[str, SubjectIndex] = {}

    def chapters(self, subject: str) -> dict[str, Chapter]:
        """The chapters (or units) of one subject."""
        check_subject(subject)
        return {cid: c for cid, c in self._chapters().items() if c.package.subject == subject}

    def state(self, subject: str) -> SubjectIndex:
        """What the service keeps for one subject (its index, when it was built, from which documents)."""
        return self._subjects.setdefault(check_subject(subject), SubjectIndex())

    def _signature_of(self, chapters: dict[str, Chapter], docs: list[TeacherDocument]) -> str:
        parts = [f"{cid}:{c.package.version}" for cid, c in sorted(chapters.items())]
        parts += [f"{d.id}:{d.sha256}:{d.status}:{len(d.text)}:{d.chapter_id}:{d.kind}" for d in docs]
        return hashlib.sha256("|".join(parts).encode()).hexdigest()

    def _build(self, subject: str, chapters: dict[str, Chapter], docs: list[TeacherDocument]) -> RagIndex:
        chunks: list[Chunk] = []
        graph: dict[str, set[str]] = {}
        for chapter in chapters.values():
            assert chapter.package.subject == subject  # filtered by ``chapters(subject)``
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
            assert doc.subject == subject  # filtered by ``DocumentRepository.list_all(subject)``
            if doc.text and doc.kind in RAG_KINDS:  # never an answer key or a test (rule 2)
                passages += document_chunks(doc.id, doc.title, doc.chapter_id, doc.text, subject=subject)
        chunks += tag_passages(passages, chunks)
        if not self._embedder_made:
            self._embedder, self._embedder_made = self._make_embedder(), True
        return RagIndex(chunks, self._embedder, graph, subject=subject)

    def _stale(self, kept: SubjectIndex, signature: str) -> bool:
        if kept.index is None or signature != kept.signature:
            return True
        failed = kept.index.semantic_error is not None
        return failed and kept.built_at is not None and utc_now() - kept.built_at > SEMANTIC_RETRY

    async def current(self, database: Any, subject: str, *, force: bool = False) -> RagIndex:
        """The index of one subject's corpus as it is now: rebuilt when one of its documents or chapter
        versions changed. ``subject`` is required: there is no index of every subject."""
        check_subject(subject)
        docs = await DocumentRepository(database, self.school_id).list_all(subject)
        chapters = self.chapters(subject)
        signature = self._signature_of(chapters, docs)
        async with self._lock:
            kept = self.state(subject)
            if force or self._stale(kept, signature):
                kept.index = await run_in_threadpool(self._build, subject, chapters, docs)
                kept.signature, kept.built_at, kept.documents = signature, utc_now(), docs
            assert kept.index is not None
            return kept.index
