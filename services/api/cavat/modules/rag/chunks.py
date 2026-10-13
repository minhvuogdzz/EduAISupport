"""The corpus of the Hybrid RAG (plan v1, 5.5.1): passages of approved (or draft) teaching content and of
the teacher's documents, each with where it comes from.

Chunks follow teaching units: one theory variant, one method, one worked example, one misconception note
is one chunk. A teacher's document is cut by paragraphs into passages of about 150-300 syllables,
overlapping by one sentence, never inside a line (formulas and table rows stay whole), each with its page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cavat.modules.content.chapter_package import Chapter

MIN_SYLLABLES, MAX_SYLLABLES = 150, 300  # plan v1 5.5.1 (tokens counted as syllables)
_PAGE_RE = re.compile(r"^\[Trang (\d+)\]\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    text: str
    kind: str  # theory | method | worked_example | misconception_note | source_passage
    chapter_id: str
    node_id: str | None  # None: a document passage not tied to one node
    source: str  # "chapter" or "document"
    title: str  # what the teacher reads as the source: "Phân số thập phân · cách giảng T1", "SGK, trang 3"
    approved: bool  # draft chapter content is used but ranked below approved sources
    document_id: str | None = None
    page: int | None = None
    misconception_id: str | None = None
    # theory: "reply" is the approved answer to the variant's question; a prompt built while that question
    # waits for the student's answer must leave it out (RAG-2).
    extra: dict[str, str] = field(default_factory=dict)
    # A document passage tied to no node: the nodes it could be about (DI-50). It may ground a question only
    # when one of them is in scope: a passage on a later period never reaches an earlier one.
    candidates: tuple[str, ...] = ()


def chapter_chunks(chapter: Chapter) -> list[Chunk]:
    """Teaching units of every node, and the notes on the misconceptions of its lessons."""
    pkg = chapter.package
    cid, approved = pkg.chapter_id, pkg.status in ("APPROVED", "PUBLISHED")
    out: list[Chunk] = []
    for node in pkg.nodes:
        for t in node.theory:
            text = f"{node.name}. {t.text} {t.ask}" + (f" {t.reply}" if t.reply else "")
            out.append(
                Chunk(
                    f"{node.id}:theory:{t.id}",
                    text,
                    "theory",
                    cid,
                    node.id,
                    "chapter",
                    f"{node.name} · cách giảng {t.id} ({t.representation})",
                    approved,
                    extra={"reply": t.reply} if t.reply else {},
                )
            )
        steps = " ".join(f"Bước {i}: {s}" for i, s in enumerate(node.method.steps, 1))
        out.append(
            Chunk(
                f"{node.id}:method",
                f"{node.name}. {node.method.rule} {steps}",
                "method",
                cid,
                node.id,
                "chapter",
                f"{node.name} · phương pháp",
                approved,
            )
        )
        for w in node.worked_examples:
            steps = " ".join(f"Bước {i}: {s}" for i, s in enumerate(w.steps, 1))
            out.append(
                Chunk(
                    f"{node.id}:example:{w.id}",
                    f"{w.problem} {steps} Đáp số: {w.answer}.",
                    "worked_example",
                    cid,
                    node.id,
                    "chapter",
                    f"{node.name} · cô làm mẫu {w.id}",
                    approved,
                )
            )
    for lesson in chapter.lessons.values():
        for m in lesson.misconceptions:
            # Counter-examples with {left}/{right} are templates the tutor fills in a session, not content.
            examples = [e for e in m.counter_examples if "{" not in e]
            text = f"Lỗi hay gặp: {m.name}. {m.description} " + " ".join(examples)
            out.append(
                Chunk(
                    f"{m.kc_id}:misconception:{m.id}",
                    text.strip(),
                    "misconception_note",
                    cid,
                    m.kc_id,
                    "chapter",
                    f"Lỗi sai {m.id}: {m.name}",
                    approved,
                    misconception_id=m.id,
                )
            )
    return out


def syllables(text: str) -> int:
    return len(text.split())


def _pieces(line: str) -> list[str]:
    """A line, or its sentences when the line alone is longer than a passage (a sentence is never cut)."""
    if syllables(line) <= MAX_SYLLABLES:
        return [line]
    return [s for s in _SENTENCE_END.split(line) if s.strip()]


def document_chunks(document_id: str, title: str, chapter_id: str | None, text: str) -> list[Chunk]:
    """Passages of 150-300 syllables cut at line ends, overlapping by one sentence, with their first page."""
    passages: list[tuple[int | None, str]] = []
    page: int | None = None  # the page being read ("[Trang n]" markers of the extracted text)
    start_page: int | None = None  # where the passage being built starts
    lines: list[str] = []
    size = 0  # syllables in ``lines``
    fresh = 0  # pieces in ``lines`` other than the sentence carried over from the previous passage

    def flush() -> None:
        nonlocal lines, size, fresh
        if not fresh:
            return
        passages.append((start_page, "\n".join(lines)))
        last = _SENTENCE_END.split(lines[-1])[-1].strip()  # the last sentence of the last line
        lines = [last] if syllables(last) < MIN_SYLLABLES else []
        size, fresh = (syllables(last) if lines else 0), 0

    for raw in text.splitlines():
        line = raw.strip()
        marker = _PAGE_RE.match(line)
        if marker:
            page = int(marker.group(1))
            continue
        if not line:  # a paragraph ends: a passage may end here
            if size >= MIN_SYLLABLES:
                flush()
            continue
        for piece in _pieces(line):
            n = syllables(piece)
            if size + n > MAX_SYLLABLES:
                if fresh:
                    flush()
                if size + n > MAX_SYLLABLES:  # the carried sentence would make it too long: drop it
                    lines, size = [], 0
            if not fresh:
                start_page = page
            lines.append(piece)
            size += n
            fresh += 1
    flush()
    return [
        Chunk(
            f"doc:{document_id}:{i}",
            body,
            "source_passage",
            chapter_id or "",
            None,
            "document",
            f"{title}" + (f", trang {p}" if p else ""),
            True,  # the teacher's own documents are the reference
            document_id=document_id,
            page=p,
        )
        for i, (p, body) in enumerate(passages, 1)
    ]
