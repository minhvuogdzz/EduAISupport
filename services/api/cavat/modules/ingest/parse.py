"""Cut the teacher's exercise documents into questions, and their answer keys into answers (INGEST-2).

Deterministic, no model: the documents follow a few layouts, and what a model would invent here is exactly
what must not reach the item bank. Three layouts, for the questions and their answer keys alike:

- ``BAI_TAP``: parts "Phần k · Kiểm tra hiểu | Cùng làm | Luyện tập | Vận dụng", questions numbered 1..N
  across the whole document;
- ``PHIEU``: sheets "Phiếu k · Tiết k · <title>", questions 1..8 in each, printed in two columns (so read in
  the order 1, 3, 5, 7, 2, 4, 6, 8);
- ``DE_KIEM_TRA``: tests "Đề số k", part I multiple choice (1..6), part II essay (B1..B6); the answer key
  labels sub-questions "B1a" and adds a score column.

A page read by Gemini writes a table row as "2 | a) 9/10 | b) 6/100"; the text layer puts the label alone on
a line and the answer on the next ones. Both are read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STAGES = {
    "kiểm tra hiểu": "KIEM_TRA_HIEU",
    "cùng làm": "CUNG_LAM",
    "luyện tập": "LUYEN_TAP",
    "vận dụng": "VAN_DUNG",
}

_SEP = r"\s*[·.\-–|]\s*"
_PART = re.compile(rf"^Phần\s+(\d){_SEP}(Kiểm tra hiểu|Cùng làm|Luyện tập|Vận dụng)\b", re.IGNORECASE)
_SHEET = re.compile(rf"^Phiếu\s+(\d{{1,2}}){_SEP}Tiết\s+(\d{{1,2}}){_SEP}(.+?)\s*$")
_TEST = re.compile(r"^Đề số\s+(\d)\b")
_TEST_PART = re.compile(r"^Phần\s+(I{1,2})\b\.?\s*(Trắc nghiệm|Tự luận)?", re.IGNORECASE)
_PAGE = re.compile(r"^\[Trang (\d+)\]$")
# A label at the start of a line: "12", "B3", "B1a", then a pipe, a dot, a space or nothing.
_LABEL = re.compile(r"^(B\d{1,2}[a-e]?|\d{1,2})(?:\s*\|\s*|\.\s+|\s+|$)(.*)$")
# Lines that are not content: running headers and footers, the form to fill in, the stars of a part.
_NOISE = re.compile(
    r"^(TOÁN 5\b|CAVAT AI Tutor|Trang \d+$|TÀI LIỆU\b|Họ và tên|Điểm$|Nhận xét|Câu$|Câu\s*\|"
    r"|Đáp án và lời giải|★+$|△$|Thời gian|\d+ điểm$|\d,?\d* điểm\s*·|Khoanh tròn|Lớp:|Ngày:)",
    re.IGNORECASE,
)
# Lines that close the block being read: advice for the teacher, tips, notes after the last answer.
_STOP = re.compile(
    r"^(DÀNH CHO NGƯỜI DẠY|MẸO|LƯU Ý|Học sinh làm cách khác|Dành cho người dạy)", re.IGNORECASE
)
# The running title of a page ("Bài tập · Số thập phân", "Đáp án phiếu luyện tập. Số thập phân").
_RUNNING = re.compile(
    r"^(Bài tập|Đáp án.*|Phiếu luyện tập.*|Đề kiểm tra.*|Lý thuyết|Giáo án.*|Ghi chú lỗi sai.*)"
    r"\s*[·.]\s*(Số thập phân|Diện tích.*)$",
    re.IGNORECASE,
)
_SCORE_LINE = re.compile(r"^(?:0,25|0,5|0,75|1,0|1,5|2,0)(?:\s*\(mỗi ý)?$|^0,25\)$")
_SCORE_CELL = re.compile(r"\s*\|\s*\d,\d{1,2}(\s*\(mỗi ý\s*\d,\d{1,2}\))?\s*$")
_PART_LETTER = re.compile(r"(?:(?<=\s)|(?<=^)|(?<=\|))([a-e])\)\s*")


@dataclass
class Block:
    """One question or one answer as the document writes it."""

    section: str  # "Phần 1" | "Phiếu 3" | "Đề 1 · I" | ""
    label: str  # "12", "B1", "B1a"
    lines: list[str] = field(default_factory=list)
    page: int = 1
    stage: str = ""  # KIEM_TRA_HIEU, CUNG_LAM, LUYEN_TAP, VAN_DUNG, TIET, TRAC_NGHIEM, TU_LUAN
    period: int | None = None  # the lesson period (tiết) of a sheet
    title: str = ""  # the title of the sheet or part

    @property
    def text(self) -> str:
        return "\n".join(line for line in self.lines if line).strip()

    @property
    def key(self) -> tuple[str, str]:
        return self.section, self.label


def clean_lines(text: str) -> list[tuple[int, str]]:
    """(page, line) of the content: markers, headers, footers and the form removed, separators unified."""
    out: list[tuple[int, str]] = []
    page = 1
    for raw in text.splitlines():
        line = raw.strip()
        marker = _PAGE.match(line)
        if marker:
            page = int(marker.group(1))
            continue
        if not line or _NOISE.match(line) or _RUNNING.match(line):
            continue
        out.append((page, line))
    return out


def parse_blocks(text: str, layout: str, *, answers: bool = False) -> list[Block]:
    """The questions (or answers) of a document of this layout, in the order they are printed."""
    blocks: list[Block] = []
    section, stage, period, title = "", "", None, ""
    test = ""
    current: Block | None = None
    seen: set[tuple[str, str]] = set()
    expected = 1  # BAI_TAP and the text layer: the next number in sequence

    def close() -> None:
        nonlocal current
        current = None

    for page, line in clean_lines(text):
        if _STOP.match(line):
            close()
            continue
        if layout == "BAI_TAP" and (m := _PART.match(line)):
            section, stage, title = f"Phần {m.group(1)}", STAGES[m.group(2).lower()], m.group(2)
            close()
            continue
        if layout == "PHIEU" and (m := _SHEET.match(line)):
            section, stage, period, title = f"Phiếu {m.group(1)}", "TIET", int(m.group(2)), m.group(3)
            close()
            continue
        if layout == "DE_KIEM_TRA":
            if m := _TEST.match(line):
                test = m.group(1)
                close()
                continue
            if m := _TEST_PART.match(line):
                part = m.group(1).upper()
                section = f"Đề {test or '1'} · {part}"
                stage = "TRAC_NGHIEM" if part == "I" else "TU_LUAN"
                close()
                continue
        if not section:
            continue  # the cover and the instructions before the first part
        label = _start_of_block(line, layout, section, seen, expected, current, answers)
        if label is not None:
            number, rest = label
            current = Block(section, number, [], page, stage, period, title)
            blocks.append(current)
            seen.add((section, number))
            if number.isdigit():
                expected = int(number) + 1
            line = rest
        if current is None or not line:
            continue
        if answers and layout == "DE_KIEM_TRA":
            line = _SCORE_CELL.sub("", line)
        current.lines.append(line.strip(" |"))
    if answers and layout == "DE_KIEM_TRA":
        # The text layer puts the score on its own line after the answer: only a last line is a score
        # (an answer may itself be "0,06").
        for block in blocks:
            while len(block.lines) > 1 and _SCORE_LINE.match(block.lines[-1]):
                block.lines.pop()
    if layout in ("PHIEU", "DE_KIEM_TRA"):
        order = {key: i for i, key in enumerate(_natural_order(blocks))}
        blocks.sort(key=lambda b: order[b.key])
    return blocks


def _start_of_block(
    line: str,
    layout: str,
    section: str,
    seen: set[tuple[str, str]],
    expected: int,
    current: Block | None,
    answers: bool,
) -> tuple[str, str] | None:
    m = _LABEL.match(line)
    if not m:
        return None
    label, rest = m.group(1), m.group(2).strip()
    if (section, label) in seen:
        return None
    marked = bool(re.match(rf"^{re.escape(label)}(\s*\||\.\s)", line))  # "2 | …", "3. …": a table cell
    alone = rest == ""
    if label.startswith("B"):
        return label, rest  # B1, B2a: only essay questions are labelled this way
    number = int(label)
    if layout == "BAI_TAP" or (layout == "DE_KIEM_TRA" and section.endswith("I")):
        # Numbered in sequence: a line that starts with another number is content ("1 m 8 cm < 1,09 m").
        if number != expected and not (number == 1 and current is None):
            return None
        # A question may open on a measure ("5 5 kg 25 g = … kg"); in an answer key that is an answer line.
        if not (marked or alone or _looks_like_question(rest) or (not answers and rest[:1].isdigit())):
            return None
        return label, rest
    if layout == "PHIEU":
        if number > 8:
            return None
        if marked:
            return label, rest
        if alone and current is not None and current.lines and number == expected:
            return label, rest  # the text layer: "5" alone, the answer on the next line
        if alone and current is None and number == 1:
            return label, rest
        return None
    return None


def _looks_like_question(rest: str) -> bool:
    """After a number, the start of a sentence rather than a measure ("12 Sắp xếp…" not "12 cm")."""
    word = rest.split(maxsplit=1)[0] if rest else ""
    return bool(word) and word[0].isupper()


def _natural_order(blocks: list[Block]) -> list[tuple[str, str]]:
    """Sections in the order they come, labels in their natural order (1, 2, …, B1, B1a, B1b, B2…)."""

    def label_key(label: str) -> tuple[int, int, str]:
        m = re.match(r"^(B?)(\d+)([a-e]?)$", label)
        assert m
        return (1 if m.group(1) else 0, int(m.group(2)), m.group(3))

    sections: list[str] = []
    for b in blocks:
        if b.section not in sections:
            sections.append(b.section)
    return [
        key
        for section in sections
        for key in sorted({b.key for b in blocks if b.section == section}, key=lambda k: label_key(k[1]))
    ]


def split_parts(text: str) -> tuple[str, list[tuple[str, str]]]:
    """The shared stem and the sub-questions "a) …", "b) …" of a question (or of an answer)."""
    matches = list(_PART_LETTER.finditer(text))
    # Only a run a, b, c… counts: "a)" alone inside a sentence is not a list. A second run after it (an
    # answer key repeating "a) 8,30 > 8,29; b) …" as an explanation) ends the list.
    run = 0
    while run < len(matches) and matches[run].group(1) == chr(ord("a") + run):
        run += 1
    if run < 2:
        return text.strip(), []
    tail = matches[run].start() if run < len(matches) else len(text)
    matches = matches[:run]
    stem = text[: matches[0].start()].strip()
    parts = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else tail
        parts.append((m.group(1), text[m.end() : end].strip(" |;\n")))
    return stem, parts


def options_of(text: str) -> tuple[str, dict[str, str]]:
    """The stem and the options "A. …", "B. …" of a multiple-choice question."""
    found = list(re.finditer(r"(?:(?<=\s)|^)([A-D])\.\s+", text))
    letters = [m.group(1) for m in found]
    if len(found) < 2 or letters != ["A", "B", "C", "D"][: len(found)]:
        return text.strip(), {}
    stem = text[: found[0].start()].strip()
    options = {}
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        options[m.group(1)] = text[m.end() : end].strip()
    return stem, options
