"""The teacher's view of the Hybrid RAG (RAG-1): what it holds, and what it retrieves for a question.

The owner asked where the RAG takes its data from: ``/status`` lists every source (the chapter's teaching
units and the teacher's documents, with how many passages each gave and to which nodes they were tied);
``/search`` runs the six steps for a question and shows every signal of every passage.

ENG-2 (ADR-061): every endpoint reads the index of one subject (``subject``, Mathematics when the teacher's
page does not name one, DI-123) and says which; every passage shows its subject.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool

from cavat.core.subjects import Subject
from cavat.modules.rag.retrieve import Scored
from cavat.modules.rag.service import RagService

# DI-123: the teacher's RAG page shows Mathematics unless it names another subject (the page was made before
# there was a second one). A session never comes here: its subject is the one of its package.
SubjectQuery = Annotated[Subject, Query()]


def build_router(database_dependency: Any, teacher_dependency: Any, service: Any) -> APIRouter:
    """``service()``: the process's RagService (tests swap it for one with the offline embedder)."""
    router = APIRouter(prefix="/v1/teachers/rag", tags=["teacher-rag"])
    database_dep, teacher_dep = Depends(database_dependency), Depends(teacher_dependency)

    def names(subject: str) -> dict[str, str]:
        rag: RagService = service()
        return {n.id: n.name for c in rag.chapters(subject).values() for n in c.package.nodes}

    def status_of(rag: RagService, index: Any) -> dict[str, Any]:
        kept = rag.state(index.subject)
        by_doc: dict[str, list[Any]] = {}
        for c in index.chunks:
            if c.document_id:
                by_doc.setdefault(c.document_id, []).append(c)
        per_node = Counter(c.node_id for c in index.chunks if c.node_id)
        return {
            "subject": index.subject,
            "chunks": len(index.chunks),
            "by_source": dict(Counter(c.source for c in index.chunks)),
            "by_kind": dict(Counter(c.kind for c in index.chunks)),
            "nodes": [
                {"node_id": n.id, "name": n.name, "chunks": per_node.get(n.id, 0)}
                for chapter in rag.chapters(index.subject).values()
                for n in chapter.package.nodes
            ],
            "documents": [
                {
                    "document_id": d.id,
                    "title": d.title,
                    "status": d.status,
                    "passages": len(by_doc.get(d.id, [])),
                    "tied_to_node": sum(1 for c in by_doc.get(d.id, []) if c.node_id),
                }
                for d in kept.documents
            ],
            "semantic": index.embedder.name if index.embedder else "off",
            # False: the offline trigram vectors (spelling, not meaning; plan v1 5.5.4)
            "semantic_is_model": bool(getattr(index.embedder, "semantic", False)),
            "semantic_error": index.semantic_error,
            "built_at": kept.built_at,
        }

    def result(s: Scored, node_name: dict[str, str]) -> dict[str, Any]:
        c = s.chunk
        return {
            "chunk_id": c.chunk_id,
            "subject": c.subject,
            "title": c.title,
            "kind": c.kind,
            "source": c.source,
            "node_id": c.node_id,
            "node_name": node_name.get(c.node_id or "", None),
            "document_id": c.document_id,
            "page": c.page,
            "approved": c.approved,
            "text": c.text,
            "bm25": round(s.bm25, 3),
            "bm25_rank": s.bm25_rank,
            "cosine": round(s.cosine, 3),
            "cosine_rank": s.cosine_rank,
            "distance": s.distance,
            "fused": round(s.fused, 5),
            "final": round(s.final, 5),
            "coverage": round(s.coverage, 3),
            "reasons": list(s.reasons),
        }

    @router.get("/status")
    async def status(
        subject: SubjectQuery = "math", database: Any = database_dep, teacher: str = teacher_dep
    ):
        rag: RagService = service()
        return status_of(rag, await rag.current(database, subject))

    @router.post("/rebuild")
    async def rebuild(
        subject: SubjectQuery = "math", database: Any = database_dep, teacher: str = teacher_dep
    ):
        rag: RagService = service()
        return status_of(rag, await rag.current(database, subject, force=True))

    @router.get("/search")
    async def search(
        q: Annotated[str, Query(min_length=1, max_length=300)],
        node: Annotated[str | None, Query()] = None,
        mode: Annotated[Literal["question", "teach", "hint"], Query()] = "question",
        k: Annotated[int, Query(ge=1, le=10)] = 5,
        subject: SubjectQuery = "math",
        database: Any = database_dep,
        teacher: str = teacher_dep,
    ):
        rag: RagService = service()
        index = await rag.current(database, subject)
        # The query vector may be a network call: off the event loop.
        found = await run_in_threadpool(
            lambda: index.retrieve(q, node_id=node or None, mode=mode, k=k, max_chars=6000)
        )
        node_name = names(subject)
        return {
            "subject": found.subject,
            "query": found.query,
            "node_id": found.node_id,
            "mode": found.mode,
            "grounded": found.grounded,
            "grounding": found.grounding,
            "semantic": found.semantic,
            "candidates": found.candidates,
            "elapsed_ms": found.elapsed_ms,
            "results": [result(s, node_name) for s in found.results],
        }

    return router
