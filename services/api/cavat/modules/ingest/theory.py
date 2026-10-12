"""Read the teaching documents into their parts (INGEST-3): the theory, the lesson plan, the mistakes.

Deterministic, like ``parse``: what is taught is the teacher's text, cut where the document cuts it, each
part with its page. The owner's documents write

- the theory as "Bài N · <title>", numbered sections "1. <title>" or short subheadings, and boxes
  "GHI NHỚ · …" (a rule), "VÍ DỤ · …" (a worked example, its solution, "Đáp số: …"), "LƯU Ý · …",
  "MẸO · …", figures "[Hình: …]";
- each period of the lesson plan with "Mục tiêu", "Chuẩn bị", "Tiến trình" (Khởi động, Khám phá, Thực
  hành, Củng cố), "Câu hỏi gợi mở" and "Khi bé sai";
- each common mistake as "Lỗi k · <name>" with "Biểu hiện", "Vì sao bé hay sai", "Cho bé tự thấy (phản ví
  dụ)", "Cách sửa", "Luyện nhanh (kèm đáp án)".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cavat.modules.ingest.parse import clean_lines

_SEP = r"\s*[·.\-–]\s*"
_LESSON = re.compile(rf"^Bài\s+(\d{{1,2}}){_SEP}(?![\d])(.+?)\s*[①-⑩]?$")
_SECTION = re.compile(r"^(\d)\s*\.\s+(\S.+)$")
_BOX = re.compile(r"^(GHI NHỚ|VÍ DỤ|LƯU Ý|MẸO|CÂU HỎI GỢI MỞ)\b\s*[·.\-–]?\s*(.*)$")
_BOX_KIND = {
    "GHI NHỚ": "RULE",
    "VÍ DỤ": "EXAMPLE",
    "LƯU Ý": "NOTE",
    "MẸO": "TIP",
    "CÂU HỎI GỢI MỞ": "QUESTIONS",
}
_BULLET = re.compile(r"^[\x7f\uf000-\uf8ff•●▪\-–]\s*")
_INNER_BULLET = re.compile(r"\s*[\x7f\uf000-\uf8ff•●▪]\s*")


@dataclass
class Box:
    kind: str  # TEXT | RULE | EXAMPLE | NOTE | TIP | QUESTIONS | FIGURE
    title: str
    lines: list[str] = field(default_factory=list)
    page: int = 1

    @property
    def text(self) -> str:
        return _join(self.lines)


@dataclass
class Section:
    lesson: str  # "Bài 10"
    lesson_title: str
    title: str  # the numbered section or subheading ("" for the lesson's opening text)
    page: int
    boxes: list[Box] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(b.text for b in self.boxes)


def _join(lines: list[str]) -> str:
    """Lines of a paragraph as one text: a word cut at a line end is not glued to the next."""
    return re.sub(r"\s+", " ", " ".join(line.strip() for line in lines)).strip()


def _is_subheading(line: str, previous: str) -> bool:
    """A short title line ("Sắp xếp thứ tự") after a finished sentence or a heading."""
    if len(line) > 50 or re.search(r"[\d|]", line) or line[-1] in ".,:;" or not line[0].isupper():
        return False
    # Not after a figure: the line under "[Hình: …]" is its caption.
    return not previous or previous[-1] in ".!?)”" or bool(_BOX.match(previous))


def parse_theory(text: str) -> list[Section]:
    sections: list[Section] = []
    lesson = lesson_title = ""
    box: Box | None = None
    figure: Box | None = None  # a figure described over several lines, until its "]"
    previous = ""
    for page, raw in clean_lines(text):
        line = raw.strip()
        if m := _LESSON.match(line):
            lesson, lesson_title = f"Bài {m.group(1)}", m.group(2).strip()
            sections.append(Section(lesson, lesson_title, "", page))
            box, figure, previous = None, None, line
            continue
        if not lesson:
            continue  # the cover and the note for the teacher before the first lesson
        current = sections[-1]
        if figure is not None:
            figure.lines.append(line)
            figure = None if line.endswith("]") else figure
            previous = line
            continue
        if line.startswith("[Hình"):
            current.boxes.append(Box("FIGURE", "", [line], page))
            figure = None if line.endswith("]") else current.boxes[-1]
            box, previous = None, line
            continue
        if m := _BOX.match(line):
            box = Box(_BOX_KIND[m.group(1)], m.group(2).strip(), [], page)
            current.boxes.append(box)
            previous = line
            continue
        if (m := _SECTION.match(line)) or _is_subheading(line, previous):
            title = m.group(2).strip() if m else line
            sections.append(Section(lesson, lesson_title, title, page))
            box, previous = None, line
            continue
        if box is None:
            box = Box("TEXT", "", [], page)
            current.boxes.append(box)
        box.lines.append(line)
        previous = line
    return [s for s in sections if s.boxes or s.title]


# --- the lesson plan, period by period ------------------------------------------------------------------


@dataclass
class PeriodPlan:
    number: int
    lesson: str
    title: str
    objectives: list[str] = field(default_factory=list)
    preparation: list[str] = field(default_factory=list)
    steps: dict[str, str] = field(default_factory=dict)  # Khởi động, Khám phá, Thực hành, Củng cố, Ôn tập
    questions: list[str] = field(default_factory=list)  # Câu hỏi gợi mở
    mistakes: list[str] = field(default_factory=list)  # Khi bé sai
    page: int = 1


_PERIOD = re.compile(r"^Tiết\s+(\d{1,2})(?:\s*\(thêm\))?\s*[·.\-–]\s*(?:(Bài\s+\d+)\s*:\s*)?(.+?)\s*$")
_STEP = re.compile(r"^(Khởi động|Khám phá|Thực hành|Củng cố|Ôn tập|Vận dụng)\s*\([^)]*\)\s*[—–-]\s*(.*)$")
_PART = {
    "Mục tiêu": "objectives",
    "Chuẩn bị": "preparation",
    "Tiến trình": "steps",
    "Câu hỏi gợi": "questions",
    "Khi bé sai": "mistakes",
}


def parse_lesson_plan(text: str) -> list[PeriodPlan]:
    periods: list[PeriodPlan] = []
    part = ""
    step = ""
    for page, raw in clean_lines(text):
        line = raw.strip()
        if m := _PERIOD.match(line):
            periods.append(PeriodPlan(int(m.group(1)), m.group(2) or "", m.group(3), page=page))
            part = step = ""
            continue
        if not periods or re.fullmatch(r"\d+–\d+′", line):
            continue
        period = periods[-1]
        heading = next((name for prefix, name in _PART.items() if line.startswith(prefix)), None)
        if heading:
            part, step = heading, ""
            continue
        if part == "questions" and line == "mở":  # "Câu hỏi gợi" / "mở": a heading cut in two
            continue
        if part == "steps":
            if m := _STEP.match(line):
                step = m.group(1)
                period.steps[step] = m.group(2).strip()
            elif step:
                period.steps[step] = f"{period.steps[step]} {line}".strip()
            continue
        if part in ("objectives", "preparation", "questions", "mistakes"):
            items: list[str] = getattr(period, part)
            pieces = [p for p in _INNER_BULLET.split(line)]
            if pieces and pieces[0] and items and not _BULLET.match(line):
                items[-1] = f"{items[-1]} {pieces[0]}".strip()  # a bullet that goes on to this line
                pieces = pieces[1:]
            items += [p.strip() for p in pieces if p.strip()]
    return periods


# --- the common mistakes ---------------------------------------------------------------------------------


@dataclass
class Mistake:
    number: int
    name: str
    signs: str = ""  # Biểu hiện
    cause: str = ""  # Vì sao bé hay sai
    counter_example: str = ""  # Cho bé tự thấy (phản ví dụ)
    remedy: str = ""  # Cách sửa
    drill: str = ""  # Luyện nhanh (kèm đáp án)
    page: int = 1


_MISTAKE = re.compile(r"^Lỗi\s+(\d{1,2})\s*[·.\-–]\s*(.+)$")
_MISTAKE_PART = (
    ("Biểu hiện", "signs"),
    ("Vì sao", "cause"),
    ("Cho bé tự", "counter_example"),
    ("Cách sửa", "remedy"),
    ("Luyện nhanh", "drill"),
)
_FRAGMENTS = {"sai", "thấy", "(phản ví dụ)", "(kèm đáp án)", "hay sai", "bé hay sai"}


def parse_mistakes(text: str) -> list[Mistake]:
    mistakes: list[Mistake] = []
    part = ""
    for page, raw in clean_lines(text):
        line = raw.strip()
        if m := _MISTAKE.match(line):
            mistakes.append(Mistake(int(m.group(1)), m.group(2).strip(), page=page))
            part = ""
            continue
        if not mistakes:
            continue
        found = next((name for prefix, name in _MISTAKE_PART if line.startswith(prefix)), None)
        if found:
            part = found
            continue
        if line in _FRAGMENTS or not part:
            continue
        mistake = mistakes[-1]
        line = _INNER_BULLET.sub(" • ", _BULLET.sub("", line)).strip(" •")
        setattr(mistake, part, f"{getattr(mistake, part)} {line}".strip())
    return mistakes
