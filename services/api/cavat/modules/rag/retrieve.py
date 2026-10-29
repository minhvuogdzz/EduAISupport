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
from cavat.modules.assessment.math_terms import MATH_TERMS
from cavat.modules.observability.trace import traced
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
_DEFINITION = re.compile(
    r"\b(la gi|la cai gi|nghia la gi|goi la gi|la sao|nghia la sao|la nhu the nao|la hang nao|la canh nao"
    r"|la phan nao|la hinh nhu the nao|la hinh gi|gom may phan|gom nhung gi)\b"
)
# DI-50: the term a definition question asks about ("đường cao là gì vậy cô" -> "duong cao"), and the sentence
# forms that define it in a passage ("đường cao ... là", "gọi là đường cao", "đường cao gồm").
_TERM = re.compile(r"^(?:co oi |cho con hoi |the |vay )*(.+?)\s+(?:la|gom|nghia la|goi la)\b")
LATER_MARGIN = 0.03  # DI-50: how much closer a later period's passage must be to say "bài sau mình học"
DEFINES_FACTOR = 1.6  # DI-50: a passage that defines the term asked about, in a definition question
# DI-57 (RAG-4): how much better an earlier period must match a question than the period being learnt for
# the question to be taken as about that earlier period (cosine with vectors, keyword coverage without).
ROUTE_MARGIN_COSINE = 0.02
ROUTE_MARGIN_COVERAGE = 0.15
# DI-57, second rule (RAG-7): with vectors, an earlier period closer by less than the margin is taken when its
# keywords cover the question at least as well as the period being learnt does (False: the margin alone).
ROUTE_WHEN_KEYWORDS_AGREE = True
_FILLERS = ("cua tam giac", "cua hinh thang", "trong so thap phan")
# DI-79 (RAG-7): a question that names a term of grade-5 mathematics the corpus never uses is about
# mathematics outside the chapters ("diện tích hình tròn", "thể tích hình hộp chữ nhật"): no passage grounds
# it, however close its vector comes (such questions reached cosine 0.66, above the threshold). Matched
# folded, as children type without diacritics. The terms of the claim check (DI-40) and grade-5 terms
# of other chapters.
OUTSIDE_TERMS = (
    "thể tích", "hình hộp chữ nhật", "hình lập phương", "hình thoi", "bán kính", "đường kính", "số nguyên tố",
    "tối giản", "quy đồng", "số đo góc", "tỉ số", "tỉ số phần trăm", "trung bình cộng",
)  # fmt: skip
_TERMS_FOLDED = sorted({fold(normalize(t)) for t in (*MATH_TERMS, *OUTSIDE_TERMS)}, key=len, reverse=True)
_TERM_FOLDED_RE = re.compile(r"(?<!\w)(" + "|".join(map(re.escape, _TERMS_FOLDED)) + r")(?!\w)")


def defined_term(query: str) -> str | None:
    """The term of a definition question, folded, or None."""
    found = term_and_shape(query)
    return found[0] if found else None


def term_and_shape(query: str) -> tuple[str, str | None] | None:
    """The term of a definition question and the shape it names, folded, or None:
    "đường cao của hình thang là gì" -> ("duong cao", "cua hinh thang"). RAG-6: the shape is kept so that a
    passage that defines the term for another shape is not taken as the definition (DI-50)."""
    q = fold(normalize(query))
    if not _DEFINITION.search(q):
        return None
    m = _TERM.match(q)
    if not m:
        return None
    term, shape = m.group(1).strip(), None
    for filler in _FILLERS:
        if term.endswith(filler):
            term, shape = term.removesuffix(filler).strip(), filler
    return (term, shape) if 2 <= len(term) <= 40 else None


# RAG-6: where a sentence or a clause ends in a passage (a decimal comma or point is not an end).
_CLAUSES = re.compile(r"[!?:;()\[\]\n]+|(?<!\d)[.,]|[.,](?!\d)")


def defines(text: str, term: str, shape: str | None = None) -> bool:
    """The passage defines the term: "đường cao của tam giác là", "gọi là đường cao", "hình thang là".
    "đáy và đường cao là những cạnh nào" asks, it does not define: a question word after "là" is none.

    RAG-6: a definition opens its sentence or clause with the term, names it after "gọi là", or ends a clause
    with it ("Đáy dài hơn là đáy lớn"); a term in the middle of one is used, not defined ("Hàng cần làm tròn
    là hàng đơn vị", "đáy 6 m, chiều cao 5 m là:"). With ``shape`` (the shape the question names), a
    definition of the term for another shape does not count ("đường cao của tam giác là" for "đường cao của
    hình thang là gì"), nor does a passage that speaks only of another shape ("Độ dài đường cao gọi là chiều
    cao" in the triangle's period, for "chiều cao của hình thang là gì")."""
    # nor is a value ("phần nguyên là 0", "phần nguyên đều là 5", "gồm 9 đơn vị"): a number after "là"
    asks = r"(?!\s+(?:gi|nhung canh nao|canh nao|hang nao|phan nao|sao|bao nhieu|may|cai gi)\b)(?!\s*\d)"
    opens = re.compile(rf"{re.escape(term)}\b((?:\s+(?!deu\b)(?!\d)\w+){{0,4}})\s+(?:la|gom)\b{asks}")
    named = re.compile(rf"\bgoi la (?:\w+ )?{re.escape(term)}\b((?:\s+\w+){{0,3}})")
    # "Đáy dài hơn là đáy lớn": a clause that ends by naming the term describes it
    ends = re.compile(rf"\bla {re.escape(term)}()$")
    others = [f for f in _FILLERS if f != shape] if shape else []
    if shape:
        whole = fold(normalize(text))
        names = {f: f.split(" ", 1)[1] for f in _FILLERS}  # "cua tam giac" -> "tam giac"
        if not re.search(rf"\b{names[shape]}\b", whole) and any(
            re.search(rf"\b{names[f]}\b", whole) for f in others
        ):
            return False
    for clause in _CLAUSES.split(text):
        t = fold(normalize(clause))
        for m in (opens.match(t), named.search(t), ends.search(t)):
            if m and not any(other in m.group(1) for other in others):
                return True
    return False


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
        self._vocabulary = " " + " ".join(fold(normalize(c.text)) for c in chunks) + " "
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

    def later_node(self, query: str, node_id: str | None, order: list[str]) -> tuple[str, Retrieval] | None:
        """The node a question is about when it comes after ``node_id`` and the scope cannot reach it: the
        tutor says where it comes instead of answering (plan 5.5.3, no teaching ahead)."""
        if node_id is None or node_id not in order:
            return None
        found = self.retrieve(query, mode="question", k=3)  # the whole chapter; the vector is cached
        tied = [s.chunk.node_id for s in found.results if s.chunk.node_id]
        top = tied[0] if tied and found.grounded else None
        if top is None or top in self.distances(node_id) or top not in order:
            return None
        return (top, found) if order.index(top) > order.index(node_id) else None

    def question(
        self, query: str, node_id: str | None, order: list[str], *, k: int = 3, max_chars: int = 1800
    ) -> tuple[str | None, Retrieval]:
        """A child's question: the passages of its scope, or the later node it is about (DI-50).

        A later node wins only when its passage is clearly closer to the question than the best one in scope
        (``LATER_MARGIN``): "vì sao diện tích tam giác phải chia 2" is answered in the triangle's period
        although the trapezoid's formula divides by 2 too."""
        scoped = self.retrieve(query, node_id=node_id, mode="question", k=k, max_chars=max_chars)
        later = self.later_node(query, node_id, order)
        if later is None:
            return None, scoped

        def best(found: Retrieval) -> float:
            if found.semantic != "off":
                return max((s.cosine for s in found.results), default=0.0)
            return max((s.coverage for s in found.results), default=0.0)

        if not scoped.grounded or best(later[1]) - best(scoped) >= LATER_MARGIN:
            return later[0], later[1]
        return None, scoped

    def ancestors(self, node_id: str) -> set[str]:
        """Every node this one builds on, at any distance (the graph leads back to what a node builds on)."""
        seen: set[str] = set()
        todo = list(self.graph.get(node_id, ()))
        while todo:
            n = todo.pop()
            if n not in seen and n != node_id:
                seen.add(n)
                todo.extend(self.graph.get(n, ()))
        return seen

    def foreign_terms(self, query: str) -> list[str]:
        """DI-79: the mathematical terms of a question that no passage of the corpus uses (folded)."""
        named = dict.fromkeys(_TERM_FOLDED_RE.findall(fold(normalize(query))))
        return [t for t in named if f" {t} " not in self._vocabulary]

    def _route(
        self, node_id: str, cos_all: np.ndarray, coverage_all: list[float], semantic: bool
    ) -> str | None:
        """DI-57: the earlier period a question is about, when it matches clearly better than the period being
        learnt ("1 m bằng bao nhiêu cm" while learning areas is about lengths). Each period is scored by its
        best passage; only periods this one builds on (never a later one: no teaching ahead).

        RAG-7 (DI-57, second rule): with vectors, an earlier period that comes closer by less than the margin
        is taken too when its keywords cover the question at least as well as the period being learnt does
        ("hình thang có mấy cạnh song song" while learning trapezoid areas: 0.015 closer, same keywords)."""
        candidates = {node_id, *self.ancestors(node_id)}
        best: dict[str, float] = {}
        covered: dict[str, float] = {}
        for i, c in enumerate(self.chunks):
            if c.node_id in candidates:
                value = float(cos_all[i]) if semantic else coverage_all[i]
                best[c.node_id] = max(best.get(c.node_id, 0.0), value)
                covered[c.node_id] = max(covered.get(c.node_id, 0.0), coverage_all[i])
        here = best.get(node_id, 0.0)
        top = max((n for n in best if n != node_id), key=lambda n: best[n], default=None)
        if top is None:
            return None
        margin = ROUTE_MARGIN_COSINE if semantic else ROUTE_MARGIN_COVERAGE
        closer = best[top] - here
        if closer >= margin:
            return top
        keywords_agree = covered[top] >= covered.get(node_id, 0.0)
        return top if ROUTE_WHEN_KEYWORDS_AGREE and semantic and closer > 0 and keywords_agree else None

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

    @traced("rag")
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
        route: bool = True,
        define: bool = True,
    ) -> Retrieval:
        """The chunks to ground one tutor turn on.

        Ablations (5.5.5, RAG-5), one flag per component so that each is measured apart: ``keyword`` (BM25),
        ``semantic`` (vectors), ``rerank`` (the factors of step 5: kind, used, misconception, draft),
        ``route`` (DI-57: a question about an earlier period) and ``define`` (DI-50: the passage that defines
        the term asked about, without fading on the graph). Until RAG-5 ``rerank`` also switched routing and
        the definition boost, so the "re-ranking" row of the first ablation measured the three together."""
        started = time.perf_counter()
        if mode == "question" and _DEFINITION.search(fold(normalize(query))):
            mode = "definition"
        near = self.distances(node_id)
        if mode == "definition" and node_id is not None:
            # DI-50: a term is defined where it is taught, which may be any period this one builds on: every
            # ancestor is in scope, one step away (a definition does not fade with the distance on the graph).
            # Later periods stay out (the graph only leads back).
            near = {**{n: 1 for n in self.ancestors(node_id)}, **near}
        found_term = term_and_shape(query) if mode == "definition" else None
        term, shape = found_term or (None, None)

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

        routed = None
        if route and node_id is not None and mode in ("question", "definition"):
            routed = self._route(node_id, cos_all, coverage_all, semantic_name != "off")
            if routed is not None:
                # DI-57: the question is about an earlier period: its passages are as close as the period's
                near = {**{n: 1 for n in self.ancestors(node_id)}, **near, routed: 0}
        scope: list[tuple[int, int]] = []  # (chunk index, distance)
        for i, c in enumerate(self.chunks):
            if chapter_id and c.chapter_id not in (chapter_id, ""):
                continue
            if node_id is None:
                distance = 0
            elif c.node_id is None and c.candidates:
                # DI-50: a passage of several periods reaches a question only when all of them are in scope
                # (a chapter overview names later periods too: it never teaches ahead)
                if any(n not in near for n in c.candidates):
                    continue
                distance = max(UNASSIGNED_DISTANCE, min(near[n] for n in c.candidates))
            elif c.node_id is None:
                distance = UNASSIGNED_DISTANCE
            elif c.node_id in near:
                distance = near[c.node_id]
            else:
                continue
            scope.append((i, distance))

        def ranks(values: dict[int, float]) -> dict[int, int]:
            ordered = sorted((i for i, v in values.items() if v > 0), key=lambda i: -values[i])
            return {i: r for r, i in enumerate(ordered, 1)}

        bm25_rank = ranks({i: bm25_all[i] for i, _ in scope})
        cos_rank = ranks({i: float(cos_all[i]) for i, _ in scope}) if semantic_name != "off" else {}

        scored: list[Scored] = []
        for i, distance in scope:
            chunk = self.chunks[i]
            fused = sum(1 / (RRF_K + r) for r in (bm25_rank.get(i), cos_rank.get(i)) if r is not None)
            defining = bool(define and term and defines(chunk.text, term, shape))
            # DI-50: the passage that defines the term asked about is where it is taught: no fading with the
            # distance on the graph (the child asks again what an earlier period taught).
            fused *= 1.0 if defining else 1 / (1 + distance)
            final, reasons, factor = fused, [], 1.0
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
            if defining and fused > 0:
                factor *= DEFINES_FACTOR
                reasons.append(f"định nghĩa «{term}»")
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
            # DI-50: a passage longer than the whole budget would leave room for nothing else (a lesson-plan
            # page of 1 258 characters kept the definition out): it is passed over, used only if alone.
            if len(s.chunk.text) > max_chars or (chosen and size + len(s.chunk.text) > max_chars):
                continue
            chosen.append(s)
            size += len(s.chunk.text)
        if not chosen and ranked:
            chosen = ranked[:1]
        threshold = GROUNDED_COSINE.get(semantic_name)
        if threshold is not None:  # a calibrated model ran for this question: meaning decides
            best = max((s.cosine for s in chosen), default=0.0)
            grounded = best >= threshold
            why = f"cosine {best:.2f} {'≥' if grounded else '<'} {threshold:.2f}"
        else:  # keywords decide
            best = max((s.coverage for s in chosen), default=0.0)
            grounded = best >= GROUNDED_COVERAGE
            why = f"độ phủ từ khóa {best:.2f} {'≥' if grounded else '<'} {GROUNDED_COVERAGE:.2f}"
        foreign = self.foreign_terms(query)
        if grounded and foreign:  # DI-79: mathematics the chapters do not teach
            grounded, why = False, f"thuật ngữ ngoài chương: {', '.join(foreign)}"
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
