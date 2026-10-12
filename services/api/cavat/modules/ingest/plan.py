"""The periods of a lesson plan (giáo án) and the exercises each one uses (INGEST-2).

The owner's lesson plans write every period as "Tiết k · Bài N: <title>" and, in its practice step,
"Bài tập câu 1, 2, 6 … Phiếu luyện tập số 1": the plan itself says which question is practised when.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from cavat.modules.ingest.parse import clean_lines

_PERIOD = re.compile(r"^Tiết\s+(\d{1,2})(?:\s*\(thêm\))?\s*[·.\-–]\s*(?:(Bài\s+\d+)\s*:\s*)?(.+?)\s*$")
_EXERCISES = re.compile(r"Bài tập câu\s+((?:\d{1,2}(?:\s*\([^)]*\))?\s*(?:,|và)\s*)*\d{1,2})")
_SHEET = re.compile(r"Phiếu luyện tập số\s+(\d{1,2})")


@dataclass
class Period:
    number: int
    lesson: str  # "Bài 10", "" for the review period
    title: str
    exercises: list[int] = field(default_factory=list)  # question numbers of the exercise document
    sheet: int | None = None  # the worksheet of the period


def parse_periods(text: str) -> list[Period]:
    periods: list[Period] = []
    current: Period | None = None
    buffer = ""
    for _, line in clean_lines(text):
        if m := _PERIOD.match(line):
            if current is not None:
                _read_refs(current, buffer)
            current = Period(int(m.group(1)), m.group(2) or "", m.group(3))
            periods.append(current)
            buffer = ""
            continue
        if current is not None:
            buffer += " " + line
    if current is not None:
        _read_refs(current, buffer)
    return periods


def _read_refs(period: Period, text: str) -> None:
    text = re.sub(r"\s+", " ", text)
    for m in _EXERCISES.finditer(text):
        for n in re.findall(r"\d{1,2}(?!\s*′)", re.sub(r"\([^)]*\)", "", m.group(1))):
            if int(n) not in period.exercises:
                period.exercises.append(int(n))
    if m := _SHEET.search(text):
        period.sheet = int(m.group(1))
