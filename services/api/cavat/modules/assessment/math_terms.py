"""The words a mathematical claim is made of (DI-40): grade 5, both chapters of the demo.

Shared by the checks on what a model writes (``teaching/grounded.py``, ``tutor/llm_renderer.py``): a claim
needs its terms, so a term the sources do not use is a new idea ("nhân với 10"), and a term the approved
sentence uses is part of the idea a rewording must keep. Matched with their diacritics in the model's
message (folded, "nhân" would match "nhận"); looked up folded in the sources.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from cavat.core.vi_text import fold, normalize
from cavat.modules.assessment.vi_numbers import normalize_text

MATH_TERMS = (
    "số thập phân", "phân số", "tử số", "mẫu số", "phần nguyên", "phần thập phân", "chữ số", "hàng", "đơn vị",
    "chục", "trăm", "nghìn", "triệu", "phần mười", "phần trăm", "phần nghìn", "dấu phẩy", "tia số",
    "số tự nhiên", "lớn hơn", "bé hơn", "nhỏ hơn", "bằng nhau", "so sánh", "sắp xếp", "cộng", "trừ", "nhân",
    "chia", "tổng", "hiệu", "tích", "thương", "gấp", "làm tròn", "mét", "ki-lô-mét", "đề-xi-mét",
    "xăng-ti-mét", "mi-li-mét", "km", "dm", "cm", "mm", "kg", "ki-lô-gam", "gam", "lít", "giây", "phút",
    "độ dài", "khối lượng", "dung tích", "thời gian", "quãng đường", "vận tốc", "chu vi", "diện tích",
    "tam giác", "hình thang", "hình vuông", "hình chữ nhật", "hình tròn", "đáy", "chiều cao", "cạnh", "góc",
)  # fmt: skip
_TERM_RE = re.compile(
    r"(?<!\w)(" + "|".join(sorted(map(re.escape, MATH_TERMS), key=len, reverse=True)) + r")(?!\w)"
)


def _folded(text: str) -> str:
    return f" {fold(normalize(text))} "


def terms_in(text: str) -> list[str]:
    """The mathematical terms of a text, in order, once each."""
    return list(dict.fromkeys(_TERM_RE.findall(normalize_text(text))))


def terms_missing(terms: Iterable[str], sources: Iterable[str]) -> list[str]:
    """The terms that none of the sources uses."""
    have = _folded(" ".join(sources))
    return [t for t in terms if _folded(t) not in have]
