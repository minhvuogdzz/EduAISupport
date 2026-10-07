"""Index and the six steps of a retrieval (plan v1, 5.5.3).

1. Scope: the chunks of the chapter; with a node, its distance on the graph weighs every chunk.
2. Keywords: two-form BM25 (with and without diacritics), ranked.
3. Semantics: cosine of the query vector with the chunk vectors, ranked.
4. Fusion: Reciprocal Rank Fusion, score = sum of 1 / (60 + rank), weighted by 1 / (1 + graph distance).
5. Pedagogical re-ranking, deterministic: the kinds the step needs first, chunks not used yet in the
   session before used ones, the note of a misconception just detected first, approved before draft.
6. Selection within a size budget, with a trace of every signal for the teacher and the evaluation.

Grounding: the plan puts a threshold on the fused score, but RRF only ranks (the first passage of any
question scores 1/61 per list), so it cannot tell that no passage answers. With a semantic model whose
threshold was calibrated on the evaluation set, a retrieval is grounded when a chosen passage reaches that
cosine; without one (no key, quota, network), when a chosen passage covers at least half of the question's
content words (idf-weighted, ``TwoFormBM25.coverage``). Keywords alone let mathematics from another chapter
through ("cộng hai phân số khác mẫu số" shares five words with the chapter), so they do not overrule the
model when it ran.

Every threshold here that the plan does not fix is DI-17 (and listed in the plan, section 9).
"""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import numpy as np

from cavat.core.vi_text import fold, normalize
from cavat.modules.rag.bm25 import TwoFormBM25
from cavat.modules.rag.chunks import Chunk
from cavat.modules.rag.embed import Embedder, cosine

RRF_K = 60  # plan v1 5.5.3
MAX_DISTANCE = 2  # DI-17: beyond two steps on the graph a chunk is out of scope when a node is given
UNASSIGNED_DISTANCE = 1  # DI-17: a document passage tied to no node counts as one step away
USED_FACTOR = 0.5  # DI-17: a chunk already used in the session (re-teaching takes another way)
MISCONCEPTION_FACTOR = 1.5  # DI-17: the note of the misconception just detected
DRAFT_FACTOR = 0.9  # DI-17: draft content after approved content
KIND_FACTOR = {  # DI-17: what each mode needs first
    # The policy asks for the next way of teaching the node (plan 5.5.3: steps 1 and 5 decide most of it):
    # a theory variant comes first whatever its keyword rank; RRF scores inside one node differ by less
    # than 1.5 times, so 1.5 makes the kind decide and the signals choose among the variants.
    "teach": {
        "theory": 1.5,
        "source_passage": 1.2,
        "worked_example": 1.1,
        "method": 1.0,
        "misconception_note": 0.7,
    },
    # A hint points to a step of the method or of a worked example.
    "hint": {
        "method": 1.4,
        "worked_example": 1.3,
        "misconception_note": 1.2,
        "theory": 1.0,
        "source_passage": 1.0,
    },
    # A free question: whichever passage answers it, a definition, a worked example or the note on the very
    # mistake the child describes ("0,50 có lớn hơn 0,5 không"); the signals decide (plan 5.5.3).
    "question": {},
    # ...except "X là gì": it asks for a definition, which theory and method give; a note on a mistake about
    # X repeats the term more often in fewer words, so keywords alone put it first.
    "definition": {"theory": 1.3, "method": 1.3, "misconception_note": 0.8},
}
_DEFINITION = re.compile(r"\b(la gi|la cai gi|nghia la gi|goi la gi|la sao|nghia la sao|la nhu the nao)\b")
GROUNDED_COVERAGE = 0.5  # DI-17: share of the question's content words a chosen passage must contain
# DI-17: cosine from which a semantic model grounds a question, calibrated per model with `make eval-rag
# LIVE=1`: halfway between the off-topic question that comes closest (0.633) and the question on the
# chapter that comes least close (0.668) on rag-decimals-v1, then confirmed on the held-out set (30 unseen
# questions: all on the chapter at or above it, all off-topic below; closest off-topic 0.648). A model not
# listed grounds through keywords.
GROUNDED_COSINE: dict[str, float] = {"gemini-embedding-001": 0.65}


@dataclass(frozen=True)
class Scored:
    chunk: Chunk
    bm25: float
    bm25_rank: int | None
    cosine: float
    cosine_rank: int | None
    distance: int
    fused: float
    final: float
    coverage: float = 0.0  # share of the question's content words found in the passage
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class Retrieval:
    query: str
    node_id: str | None
    mode: str
    results: list[Scored]
    candidates: int
    grounded: bool
    semantic: str  # the embedder used, or "off" when it could not run (keywords and structure only)
    elapsed_ms: float
    ranked: list[Scored] = field(default_factory=list)  # every candidate in final order (evaluation)
    grounding: str = ""  # why it is grounded or not, for the teacher's trace


class RagIndex:
    """BM25 and vectors over a fixed list of chunks, and the node graph of the chapter(s)."""

    def __init__(
        self,
        chunks: list[Chunk],
        embedder: Embedder | None,
        graph: Mapping[str, Iterable[str]],
    ) -> None:
        self.chunks = chunks
        self.keyword = TwoFormBM25([c.text for c in chunks])
        self.graph = {n: set(neighbours) for n, neighbours in graph.items()}
        self.embedder: Embedder | None = None
        self.vectors: np.ndarray | None = None
        self.semantic_error: str | None = None
        if embedder is not None and chunks:
            try:
                self.vectors = embedder.embed([c.text for c in chunks], "RETRIEVAL_DOCUMENT")
                self.embedder = embedder
            except Exception as exc:  # quota, network: keywords and structure still work (5.5.4)
                self.semantic_error = f"{type(exc).__name__}: {exc}"[:200]

    def distances(self, node_id: str | None) -> dict[str, int]:
        if node_id is None:
            return {}
        seen, queue = {node_id: 0}, deque([node_id])
        while queue:
            current = queue.popleft()
            for nxt in self.graph.get(current, ()):
                if nxt not in seen and seen[current] < MAX_DISTANCE:
                    seen[nxt] = seen[current] + 1
                    queue.append(nxt)
        return seen

    def retrieve(
        self,
        query: str,
        *,
        chapter_id: str | None = None,
        node_id: str | None = None,
        mode: str = "question",
        used: frozenset[str] = frozenset(),
        misconception_id: str | None = None,
        k: int = 3,
        max_chars: int = 1800,
        keyword: bool = True,
        semantic: bool = True,
        rerank: bool = True,
    ) -> Retrieval:
        """The chunks to ground one tutor turn on. ``keyword``/``semantic``/``rerank``: ablations (5.5.5)."""
        started = time.perf_counter()
        if mode == "question" and _DEFINITION.search(fold(normalize(query))):
            mode = "definition"
        near = self.distances(node_id)
        scope: list[tuple[int, int]] = []  # (chunk index, distance)
        for i, c in enumerate(self.chunks):
            if chapter_id and c.chapter_id not in (chapter_id, ""):
                continue
            if node_id is None:
                distance = 0
            elif c.node_id is None:
                distance = UNASSIGNED_DISTANCE
            elif c.node_id in near:
                distance = near[c.node_id]
            else:
                continue
            scope.append((i, distance))

        bm25_all = self.keyword.scores(query) if keyword else [0.0] * len(self.chunks)
        coverage_all = self.keyword.coverage(query)
        cos_all = np.zeros(len(self.chunks), dtype=np.float32)
        semantic_name = "off"
        if semantic and self.embedder is not None and self.vectors is not None:
            try:
                q = self.embedder.embed([query], "RETRIEVAL_QUERY")[0]
                cos_all = cosine(self.vectors, q)
                semantic_name = self.embedder.name
            except Exception:  # noqa: BLE001 - quota or network: keywords and structure only
                semantic_name = "off"

        def ranks(values: dict[int, float]) -> dict[int, int]:
            ordered = sorted((i for i, v in values.items() if v > 0), key=lambda i: -values[i])
            return {i: r for r, i in enumerate(ordered, 1)}

        bm25_rank = ranks({i: bm25_all[i] for i, _ in scope})
        cos_rank = ranks({i: float(cos_all[i]) for i, _ in scope}) if semantic_name != "off" else {}

        scored: list[Scored] = []
        for i, distance in scope:
            chunk = self.chunks[i]
            fused = sum(1 / (RRF_K + r) for r in (bm25_rank.get(i), cos_rank.get(i)) if r is not None)
            fused *= 1 / (1 + distance)
            final, reasons = fused, []
            if rerank and fused > 0:
                factor = KIND_FACTOR.get(mode, {}).get(chunk.kind, 1.0)
                if factor != 1.0:
                    reasons.append(f"loại {chunk.kind} ×{factor}")
                if chunk.chunk_id in used:
                    factor *= USED_FACTOR
                    reasons.append("đã dùng trong buổi")
                if misconception_id and chunk.misconception_id == misconception_id:
                    factor *= MISCONCEPTION_FACTOR
                    reasons.append("đúng lỗi sai vừa gặp")
                if not chunk.approved:
                    factor *= DRAFT_FACTOR
                    reasons.append("bản nháp")
                final = fused * factor
            scored.append(
                Scored(
                    chunk,
                    bm25_all[i],
                    bm25_rank.get(i),
                    float(cos_all[i]),
                    cos_rank.get(i),
                    distance,
                    fused,
                    final,
                    coverage_all[i],
                    tuple(reasons),
                )
            )
        scored.sort(key=lambda s: (-s.final, s.chunk.chunk_id))
        ranked = [s for s in scored if s.final > 0]

        chosen: list[Scored] = []
        size = 0
        for s in ranked:
            if len(chosen) == k:
                break
            if chosen and size + len(s.chunk.text) > max_chars:
                continue
            chosen.append(s)
            size += len(s.chunk.text)
        threshold = GROUNDED_COSINE.get(semantic_name)
        if threshold is not None:  # a calibrated model ran for this question: meaning decides
            best = max((s.cosine for s in chosen), default=0.0)
            grounded = best >= threshold
            why = f"cosine {best:.2f} {'≥' if grounded else '<'} {threshold:.2f}"
        else:  # keywords decide
            best = max((s.coverage for s in chosen), default=0.0)
            grounded = best >= GROUNDED_COVERAGE
            why = f"độ phủ từ khóa {best:.2f} {'≥' if grounded else '<'} {GROUNDED_COVERAGE:.2f}"
        return Retrieval(
            query=query,
            node_id=node_id,
            mode=mode,
            results=chosen,
            candidates=len(scope),
            grounded=grounded,
            semantic=semantic_name,
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            ranked=ranked,
            grounding=why,
        )
