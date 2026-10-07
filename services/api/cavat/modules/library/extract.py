"""Read the text of a teacher's document (DOC-1). Self-written on low-level libraries (ADR-018, D-T11):
pypdf for the text layer of a PDF, the standard library for DOCX (a zip of XML), Gemini only for what
has no text layer (photos, scans: ADR-017 gives Gemini the images and OCR).

Pages are marked "[Trang n]" so a passage found later by the RAG can say where it comes from.
"""

from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from xml.etree import ElementTree

from pypdf import PdfReader

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

Ocr = Callable[[bytes, str], str]  # (file bytes, mime type) -> text


@dataclass(frozen=True)
class Extraction:
    text: str
    pages: int
    method: str  # pdf-text | docx | text | ocr-gemini
    needs_ocr: bool = False


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
        return Extraction(ocr(data, KINDS[ext]).strip(), 1, "ocr-gemini")
    raise ValueError(f"unsupported file type: {ext or filename}")


def _pdf(data: bytes, ocr: Ocr | None) -> Extraction:
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    text = "\n\n".join(f"[Trang {i}]\n{t}" for i, t in enumerate(pages, 1) if t)
    if sum(len(t) for t in pages) >= MIN_CHARS_PER_PAGE * max(len(pages), 1):
        return Extraction(text, len(pages), "pdf-text")
    if ocr is None:
        return Extraction(text, len(pages), "pdf-text", needs_ocr=True)
    return Extraction(ocr(data, "application/pdf").strip(), len(pages), "ocr-gemini")


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
