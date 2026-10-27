"""The figures of a chapter from the teacher's documents (FIG-1, ADR-037): ``make figures`` and the tests
share this. No database and no model here: documents, bank items and the original PDFs go in, matched and
rendered figures come out (``ChapterFigures``), and ``service`` stores them.

For each question of the item bank whose text holds "[Hình: …]":

1. the descriptions of the document's page are paired with the drawings that ``finder`` found on the page
   (``matching.match_page``), once per page;
2. the question takes the pair of its own description, in the order the question writes them.

A question whose description has no drawing is reported, never guessed; so is a drawing that no question
claims (a figure the reading of the document did not describe).
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from cavat.modules.figures.finder import FigureDocument
from cavat.modules.figures.matching import (
    PageMatch,
    Pair,
    alt_of,
    clean_tag,
    match_page,
    split_pages,
    tags_of,
)

QUESTION_KINDS = ("BAI_TAP", "PHIEU", "DE_KIEM_TRA")


class DocumentLike(Protocol):
    id: str
    filename: str
    kind: str
    chapter_id: str | None
    text: str
    stored_path: str


def question_id_of(item: Mapping[str, Any]) -> str:
    """ "DTTGHT-BT-13b" and "DTTGHT-BT-13a" are two items of the question "DTTGHT-BT-13"."""
    item_id = str(item["item_id"])
    return item_id[:-1] if item.get("part") else item_id


@dataclass
class Question:
    question_id: str
    document_id: str
    page: int
    label: str
    tags: list[str]
    item_ids: list[str] = field(default_factory=list)


@dataclass
class FigureMatch:
    question_id: str
    order: int
    tag: str
    alt: str
    item_ids: list[str]
    document_id: str
    filename: str
    page: int
    box: list[float]
    score: float
    confidence: str  # SURE | REVIEW
    labels: list[str]
    panels: int
    png: bytes
    width: int
    height: int
    sha256: str


@dataclass
class Unmatched:
    question_id: str
    order: int
    tag: str
    document_id: str
    filename: str
    page: int
    reason: str  # NO_FILE | NO_DRAWING | NOT_ON_PAGE


@dataclass
class Spare:
    document_id: str
    filename: str
    page: int
    box: list[float]
    labels: list[str]
    png: bytes
    kind: str  # the document's kind: a drawing of a worksheet no description names, or a lecture's


@dataclass
class OtherDocument:
    """A document that is not a question sheet (a lecture, a lesson plan): its figures, for the count."""

    filename: str
    kind: str
    tags: int
    drawings: int
    paired: int


@dataclass
class ChapterFigures:
    chapter_id: str
    matches: list[FigureMatch] = field(default_factory=list)
    unmatched: list[Unmatched] = field(default_factory=list)
    spare: list[Spare] = field(default_factory=list)
    others: list[OtherDocument] = field(default_factory=list)
    questions: int = 0  # questions whose text holds a description
    tags: int = 0  # descriptions in them
    drawings: int = 0  # drawings found on the pages that hold a description

    @property
    def matched_questions(self) -> int:
        return len({m.question_id for m in self.matches})

    @property
    def unmatched_questions(self) -> list[str]:
        """The questions with at least one description that got no drawing."""
        return sorted({u.question_id for u in self.unmatched})


def questions_of(items: Iterable[Mapping[str, Any]]) -> list[Question]:
    """The questions of an item bank that write at least one description, in the bank's order."""
    found: dict[tuple[str, str], Question] = {}
    for item in items:
        tags = tags_of(str(item.get("question", "")))
        if not tags:
            continue
        key = (str(item["document_id"]), question_id_of(item))
        question = found.setdefault(
            key,
            Question(key[1], key[0], int(item.get("page", 0)), str(item.get("label", "")), tags),
        )
        question.item_ids.append(str(item["item_id"]))
    return list(found.values())


def png_of(image: Any) -> bytes:
    out = io.BytesIO()
    image.save(out, "PNG", optimize=True)
    return out.getvalue()


def plan_chapter(
    chapter_id: str,
    documents: Sequence[DocumentLike],
    items: Iterable[Mapping[str, Any]],
    read_pdf: Callable[[DocumentLike], bytes | None],
) -> ChapterFigures:
    """Find, pair and render the figures of one chapter. ``read_pdf`` gives a document's original file."""
    result = ChapterFigures(chapter_id)
    questions = questions_of(items)
    result.questions = len(questions)
    result.tags = sum(len(q.tags) for q in questions)
    wanted: dict[str, list[Question]] = {}
    for question in questions:
        wanted.setdefault(question.document_id, []).append(question)

    for doc in documents:
        data = read_pdf(doc) if doc.filename.lower().endswith(".pdf") else None
        asked = wanted.get(doc.id, [])
        if data is None:
            for q in asked:
                result.unmatched += [
                    Unmatched(q.question_id, n, tag, doc.id, doc.filename, q.page, "NO_FILE")
                    for n, tag in enumerate(q.tags, 1)
                ]
            continue
        pages = split_pages(doc.text)
        with FigureDocument(data) as pdf:
            matches = {
                page: match_page(page, tags_of(text), pdf.find(page))
                for page, text in pages.items()
                if page <= pdf.pages
            }
            if doc.kind in QUESTION_KINDS or asked:
                for page in range(1, pdf.pages + 1):
                    matches.setdefault(page, match_page(page, [], pdf.find(page)))
            result.drawings += sum(
                len(m.pairs) + len(m.spare) for page, m in matches.items() if tags_of(pages.get(page, ""))
            )
            _claim(result, doc, asked, matches, pdf)
            _spare(result, doc, matches, pdf)
            if not asked and doc.kind not in QUESTION_KINDS:
                result.others.append(_other(doc, pages, matches))
    result.matches.sort(key=lambda m: (m.question_id, m.order))
    return result


def _claim(
    result: ChapterFigures,
    doc: DocumentLike,
    asked: list[Question],
    matches: dict[int, PageMatch],
    pdf: FigureDocument,
) -> None:
    """Give each question the pair of each of its descriptions (first unclaimed pair with the same words)."""
    taken: set[tuple[int, int]] = set()
    for q in asked:
        for order, tag in enumerate(q.tags, 1):
            found = _find_pair(matches, tag, q.page, taken)
            if found is None:
                known = any(clean_tag(t) == tag for m in matches.values() for t in _page_tags(m))
                reason = "NO_DRAWING" if known else "NOT_ON_PAGE"
                result.unmatched.append(
                    Unmatched(q.question_id, order, tag, doc.id, doc.filename, q.page, reason)
                )
                continue
            page, index, pair = found
            taken.add((page, index))
            image = pdf.render(pair.region)
            png = png_of(image)
            result.matches.append(
                FigureMatch(
                    question_id=q.question_id,
                    order=order,
                    tag=tag,
                    alt=alt_of(tag),
                    item_ids=list(q.item_ids),
                    document_id=doc.id,
                    filename=doc.filename,
                    page=page,
                    box=pair.region.box.as_list(),
                    score=round(pair.score, 3),
                    confidence=pair.confidence,
                    labels=list(pair.region.labels),
                    panels=pair.region.panels,
                    png=png,
                    width=image.width,
                    height=image.height,
                    sha256=hashlib.sha256(png).hexdigest(),
                )
            )


def _page_tags(match: PageMatch) -> list[str]:
    return [p.tag for p in match.pairs] + match.unmatched_tags


def _find_pair(
    matches: dict[int, PageMatch], tag: str, page: int, taken: set[tuple[int, int]]
) -> tuple[int, int, Pair] | None:
    order = [page, page + 1, *sorted(p for p in matches if p not in (page, page + 1))]
    for number in order:
        match = matches.get(number)
        if match is None:
            continue
        for index, pair in enumerate(match.pairs):
            if pair.tag == tag and (number, index) not in taken:
                return number, index, pair
    return None


def _spare(
    result: ChapterFigures,
    doc: DocumentLike,
    matches: dict[int, PageMatch],
    pdf: FigureDocument,
) -> None:
    """The drawings no description claims, on the pages of a question sheet (a figure the reading of the
    document did not describe: the teacher sees them in the preview)."""
    if doc.kind not in QUESTION_KINDS:
        return
    for page, match in sorted(matches.items()):
        for region in match.spare:
            png = png_of(pdf.render(region))
            result.spare.append(
                Spare(doc.id, doc.filename, page, region.box.as_list(), list(region.labels), png, doc.kind)
            )


def _other(doc: DocumentLike, pages: dict[int, str], matches: dict[int, PageMatch]) -> OtherDocument:
    tags = sum(len(tags_of(t)) for t in pages.values())
    paired = sum(len(m.pairs) for m in matches.values())
    drawings = sum(len(m.pairs) + len(m.spare) for m in matches.values())
    return OtherDocument(doc.filename, doc.kind, tags, drawings, paired)
