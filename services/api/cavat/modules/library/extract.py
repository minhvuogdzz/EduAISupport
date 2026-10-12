"""Read the text of a teacher's document (DOC-1, INGEST-1). Self-written on low-level libraries (ADR-018,
D-T11): pypdf for the text layer of a PDF, the standard library for DOCX (a zip of XML), Gemini for what the
text layer does not hold (ADR-017 gives Gemini the images and OCR).

A PDF is read page by page (INGEST-1). The text layer alone loses what is drawn: in the owner's documents
the fractions are small images ("Các phân số thập phân , , viết là 0,1 ; 0,01") and the geometry figures
are vector drawings whose labels come out as "H A B C 7 cm 12 cm". Such a page is read again by Gemini,
and the reading is checked before it replaces the text layer (DI-43): every number of the text layer must
be in Gemini's text. A page that fails keeps its text layer and is marked for the teacher to look at; the
numbers only Gemini read (the fractions, the measures of a figure) are listed for the teacher too.

Pages are marked "[Trang n]" so a passage found later by the RAG can say where it comes from.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

from pypdf import PageObject, PdfReader, PdfWriter

from cavat.modules.assessment.vi_numbers import extract_numbers

# One page of a PDF (INGEST-1): the caller adds the "[Trang n]" marker.
OCR_PAGE_PROMPT = (
    "Chép lại đầy đủ và đúng nguyên văn mọi chữ, số và công thức trên trang tài liệu này "
    "(tiếng Việt có dấu). "
    "Giữ nguyên xuống dòng, tiêu đề, số thứ tự câu và các chữ a), b), c). Phân số viết a/b (ví dụ 7/10), "
    "hỗn số viết phần nguyên rồi phân số (ví dụ 3 1/2), số thập phân dùng dấu phẩy. "
    "Bảng viết mỗi hàng một dòng, các ô cách nhau bằng dấu |. "
    "Hình vẽ thì mô tả trong ngoặc vuông: tên hình, các điểm, độ dài ghi "
    "trên hình, cạnh nào là đáy, đường nào là đường cao, góc vuông ở đâu, ví dụ "
    "[Hình: tam giác ABC, đáy BC = 12 cm, đường cao AH = 7 cm vuông góc với BC]. "
    "Không giải bài, không thêm lời nào khác."
)
OCR_PAGE_VERSION = "ocr-page/1"

OCR_PROMPT = (
    "Chép lại đầy đủ và đúng nguyên văn mọi chữ, số và công thức trong tài liệu này (tiếng Việt có dấu). "
    "Giữ nguyên xuống dòng, tiêu đề, số thứ tự câu. Phân số viết a/b, số thập phân dùng dấu phẩy. "
    "Mỗi trang mở đầu bằng [Trang n]. Hình vẽ thì mô tả ngắn trong ngoặc vuông, ví dụ "
    "[Hình: tam giác ABC, đáy BC = 6 cm, chiều cao AH = 4 cm]. Không giải bài, không thêm lời nào khác."
)

KINDS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
MIN_CHARS_PER_PAGE = 40  # DI: a PDF page with less text than this is a scan, read by OCR
# What a figure leaves in the text layer (DI-43): its point labels, three or more single capitals in a row
# ("H A B C"), or its measures alone on consecutive lines ("5 m", "3 m", "2 m" around a house).
_FIGURE_LABELS = re.compile(r"(?<!\S)(?:[A-Z]\s+){2,}[A-Z](?!\S)")
_MEASURE_LINE = r"[ \t]*\d+(?:,\d+)?[ \t]*(?:mm|cm|dm|m|km)[ \t]*"
_FIGURE_MEASURES = re.compile(rf"(?m)^{_MEASURE_LINE}\n{_MEASURE_LINE}$")
# A number line: its ticks and the point on it, each alone on a line ("3", "4", "3,5", "M").
_FIGURE_TICKS = re.compile(r"(?m)^(?:[ \t]*\d+(?:,\d+)?[ \t]*\n){2,}[ \t]*[A-Z][ \t]*$")

Ocr = Callable[[bytes, str, str], str]  # (file bytes, mime type, prompt) -> text


@dataclass(frozen=True)
class PageRead:
    """How one page of a PDF was read (INGEST-1), for the teacher and the evaluation."""

    page: int
    method: str  # pdf-text | ocr-gemini
    reason: str = ""  # why it was read again: IMAGES | FIGURE | SCAN ("" : the text layer is whole)
    status: str = "OK"  # OK | NEEDS_REVIEW (OCR missing, failed or disagreeing: the text layer is kept)
    missing: tuple[str, ...] = ()  # numbers of the text layer that Gemini's text lacks
    added: tuple[str, ...] = ()  # numbers only Gemini read: fractions in images, measures of a figure
    # QuotaExceeded, ModelUnavailable, EMPTY, NO_OCR: why there is no reading; CONFIRMED: a second model read
    # the same added numbers; DISAGREE: it did not (``disputed``); UNCONFIRMED:<error>: no second reading.
    note: str = ""
    disputed: tuple[str, ...] = ()  # added numbers the two readings do not share: for the teacher


@dataclass(frozen=True)
class Extraction:
    text: str
    pages: int
    method: str  # pdf-text | pdf-text+ocr | docx | text | ocr-gemini
    needs_ocr: bool = False
    page_reads: tuple[PageRead, ...] = ()

    @property
    def needs_review(self) -> bool:
        return any(p.status != "OK" for p in self.page_reads)


def extension_of(filename: str) -> str:
    match = re.search(r"\.[A-Za-z0-9]+$", filename)
    return match.group(0).lower() if match else ""


def extract(data: bytes, filename: str, ocr: Ocr | None) -> Extraction:
    ext = extension_of(filename)
    if ext == ".pdf":
        return _pdf(data, ocr)
    if ext == ".docx":
        return Extraction(_docx(data), 1, "docx")
    if ext in (".txt", ".md"):
        return Extraction(data.decode("utf-8", errors="replace").strip(), 1, "text")
    if ext in (".png", ".jpg", ".jpeg", ".webp"):
        if ocr is None:
            return Extraction("", 1, "", needs_ocr=True)
        return Extraction(ocr(data, KINDS[ext], OCR_PROMPT).strip(), 1, "ocr-gemini")
    raise ValueError(f"unsupported file type: {ext or filename}")


def _pdf(data: bytes, ocr: Ocr | None) -> Extraction:
    reader = PdfReader(io.BytesIO(data))
    texts: list[str] = []
    reads: list[PageRead] = []
    for number, page in enumerate(reader.pages, 1):
        layer = (page.extract_text() or "").strip()
        reason = why_read_again(page, layer)
        text, read = layer, PageRead(number, "pdf-text")
        if reason and ocr is None:
            read = PageRead(number, "pdf-text", reason, "NEEDS_REVIEW", note="NO_OCR")
        elif reason:
            text, read = _read_again(page, number, layer, reason, ocr)  # type: ignore[arg-type]
        texts.append(text)
        reads.append(read)
    joined = "\n\n".join(f"[Trang {i}]\n{t}" for i, t in enumerate(texts, 1) if t)
    scans = sum(r.reason == "SCAN" for r in reads)
    method = "ocr-gemini" if reads and scans == len(reads) and ocr else "pdf-text"
    if any(r.method == "ocr-gemini" for r in reads) and method == "pdf-text":
        method = "pdf-text+ocr"
    needs_ocr = ocr is None and scans == len(reads) and bool(reads)
    return Extraction(joined, len(reads), method, needs_ocr=needs_ocr, page_reads=tuple(reads))


def why_read_again(page: PageObject, layer: str) -> str:
    """What the text layer of this page cannot hold: a scan, images (fractions, pictures), a figure."""
    if len(layer) < MIN_CHARS_PER_PAGE:
        return "SCAN"
    if any(p.search(layer) for p in (_FIGURE_LABELS, _FIGURE_MEASURES, _FIGURE_TICKS)):
        return "FIGURE"
    if _has_images(page):
        return "IMAGES"
    return ""


def _has_images(page: PageObject) -> bool:
    """An image XObject on the page, directly or inside a form XObject (no image library needed)."""

    def walk(resources: Any, depth: int) -> bool:
        xobjects = resources.get("/XObject") if resources else None
        if not xobjects or depth > 2:
            return False
        for ref in xobjects.get_object().values():
            obj = ref.get_object()
            subtype = obj.get("/Subtype")
            if subtype == "/Image":
                return True
            if subtype == "/Form" and walk(obj.get("/Resources"), depth + 1):
                return True
        return False

    resources = page.get("/Resources")
    return walk(resources.get_object() if resources is not None else None, 0)


def _read_again(page: PageObject, number: int, layer: str, reason: str, ocr: Ocr) -> tuple[str, PageRead]:
    single = io.BytesIO()
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(single)
    try:
        read = clean_reading(ocr(single.getvalue(), "application/pdf", OCR_PAGE_PROMPT)).strip()
    except Exception as exc:  # quota, network: the text layer stays and the teacher is told
        return layer, PageRead(number, "pdf-text", reason, "NEEDS_REVIEW", note=type(exc).__name__)
    if not read:
        return layer, PageRead(number, "pdf-text", reason, "NEEDS_REVIEW", note="EMPTY")
    missing, added = compare_numbers(layer, read)
    if missing:
        return layer, PageRead(number, "pdf-text", reason, "NEEDS_REVIEW", missing, added)
    check = getattr(ocr, "check", None)
    if not added or check is None:
        return read, PageRead(number, "ocr-gemini", reason, "OK", (), added)
    # What only this reading has (a fraction in an image) is confirmed by a second reading of another model.
    try:
        second = clean_reading(
            check(
                single.getvalue(),
                "application/pdf",
                OCR_PAGE_PROMPT,
                other_than=getattr(ocr, "last_model", ""),
            )
        )
    except Exception as exc:
        return read, PageRead(
            number, "ocr-gemini", reason, "NEEDS_REVIEW", (), added, f"UNCONFIRMED:{type(exc).__name__}"
        )
    _, added_again = compare_numbers(layer, second)
    disputed = tuple(sorted(set(added) ^ set(added_again)))
    if disputed:
        return read, PageRead(number, "ocr-gemini", reason, "NEEDS_REVIEW", (), added, "DISAGREE", disputed)
    return read, PageRead(number, "ocr-gemini", reason, "OK", (), added, "CONFIRMED")


_LATEX_POWER = re.compile(r"\$\s*(?:\\text\{|\\mathrm\{)?\s*([a-zA-Z]+)\s*\}?\s*\^\s*\{?([23])\}?\s*\$")
_LATEX_FRACTION = re.compile(r"\$\s*\\(?:d|t)?frac\{([^{}]+)\}\{([^{}]+)\}\s*\$")
_LATEX_REST = re.compile(r"\$([^$]{1,40})\$")
_POWERS = {"2": "²", "3": "³"}


def clean_reading(text: str) -> str:
    """Gemini sometimes writes units and fractions as LaTeX ("10 $\\text{m}^2$", seen on the owner's test):
    the plain forms the rest of the system reads ("10 m²", "7/10")."""
    text = _LATEX_POWER.sub(lambda m: m.group(1) + _POWERS[m.group(2)], text)
    text = _LATEX_FRACTION.sub(lambda m: f"{m.group(1).strip()}/{m.group(2).strip()}", text)
    text = _LATEX_REST.sub(lambda m: m.group(1).replace("\\times", "×").replace("\\", "").strip(), text)
    return text


def compare_numbers(layer: str, read: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """DI-43: the numbers of the text layer that a reading lacks, and the numbers only the reading has.

    Single digits are left out of "missing": the text layer cuts tables and figures into lone digits that a
    good reading writes whole ("3 0 5 , 4 7 8" is "305,478"). A number counts as kept when the reading
    has it written the same way or with the same value ("1.000" and "1000").
    """
    ours = extract_numbers(layer)
    theirs = extract_numbers(read)
    their_texts = {n.text for n in theirs}
    their_values = {n.value for n in theirs}
    missing = [
        n.text for n in ours if len(n.text) > 1 and n.text not in their_texts and n.value not in their_values
    ]
    our_texts = {n.text for n in ours}
    our_values = {n.value for n in ours}
    added = [n.text for n in theirs if n.text not in our_texts and n.value not in our_values]
    return tuple(dict.fromkeys(missing)), tuple(dict.fromkeys(added))


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx(data: bytes) -> str:
    """Paragraphs and table rows of word/document.xml, in order."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    body = root.find(f"{_W}body")
    lines: list[str] = []
    for block in list(body) if body is not None else []:
        if block.tag == f"{_W}p":
            lines.append(_paragraph(block))
        elif block.tag == f"{_W}tbl":
            for row in block.iter(f"{_W}tr"):
                cells = [
                    " ".join(_paragraph(p) for p in cell.iter(f"{_W}p")).strip()
                    for cell in row.iter(f"{_W}tc")
                ]
                lines.append(" | ".join(cells))
    return "\n".join(line for line in lines).strip()


def _paragraph(p: ElementTree.Element) -> str:
    parts = []
    for node in p.iter():
        if node.tag == f"{_W}t" and node.text:
            parts.append(node.text)
        elif node.tag in (f"{_W}tab",):
            parts.append("\t")
        elif node.tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
    return "".join(parts)
