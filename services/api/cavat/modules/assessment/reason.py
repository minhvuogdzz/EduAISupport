"""The child's "vì sao", judged by a deterministic rubric (WHY-1, DI-55, ``reason-rubric/0.1.0``).

"Vì con làm theo quy tắc cô dạy" used to count as an explanation like any other reply. Here a reply is an
explanation when it says something about this item, by three cues:

- NUMBER: a number of the item (its stem, key, worked solution or explanation);
- TERM: a word of Grade 5 Math or of the lesson's knowledge components ("phần nguyên", "chiều cao"...);
- SOLUTION: two content words shared with the item's own explanation or worked solution.

No cue: vague (quality 0.2), the tutor asks once more what was done with which numbers. One cue: 0.6.
Two or more: 1.0. The quality is evidence on R with a rubric weight (``MasteryPolicy``); never a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from cavat.core.vi_text import fold
from cavat.modules.assessment.vi_numbers import extract_numbers, normalize_text
from cavat.modules.content.lesson_package import Item, LessonPackage

REASON_VERSION = "reason-rubric/0.1.0"
VAGUE, ONE_CUE, TWO_CUES = 0.2, 0.6, 1.0  # DI-55

# Words of Grade 5 Math that carry meaning in an explanation (DI-55). Phrases of two words or more are
# matched without diacritics too (children type "phan nguyen"); one-word terms only with their diacritics,
# since folded they are everyday words ("nhân" / "nhận", "tạ" / "ta", "đổi" / "đợi").
MATH_PHRASES = (
    "phần nguyên", "phần thập phân", "hàng đơn vị", "hàng phần mười", "hàng phần trăm", "hàng phần nghìn",
    "dấu phẩy", "chữ số", "số 0", "mẫu số", "tử số", "phân số", "số thập phân", "so sánh", "lớn hơn",
    "bé hơn", "nhỏ hơn", "bằng nhau", "đáy lớn", "đáy bé", "chiều cao", "đường cao", "diện tích",
    "hình thang", "tam giác", "vuông góc", "song song", "đơn vị", "làm tròn", "giữ nguyên", "phần mười",
    "phần trăm", "phần nghìn", "bên phải", "bên trái", "tận cùng", "hai đáy", "chia đôi", "gấp đôi",
)  # fmt: skip
MATH_WORDS = (
    "nhân", "chia", "cộng", "trừ", "gấp", "lần", "tổng", "hiệu", "tích", "thương", "đáy", "cạnh", "hàng",
    "đổi", "thêm", "bớt", "bỏ", "cm", "dm", "mm", "km", "kg", "tấn", "tạ", "yến", "gam", "mét",
)  # fmt: skip
_STOP = frozenset(
    "vi con co thi la va cua cho nen nay do da duoc lam theo nhu the nao gi mot hai ba cac nhung voi "
    "roi khi neu ma de tu den o tren duoi trong ngoai vao ra len xuong ay a nhe day ah u minh ban em".split()
)


@dataclass(frozen=True)
class ReasonJudged:
    quality: float
    cues: tuple[str, ...]

    @property
    def vague(self) -> bool:
        return not self.cues


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", fold(normalize_text(text))) if len(w) >= 3 and w not in _STOP}


def judge_reason(item: Item, text: str, pkg: LessonPackage | None = None) -> ReasonJudged:
    answer = item.answer
    sources = [item.stem, item.explanation or "", *item.worked_solution, str(getattr(answer, "value", ""))]
    known = {n.value for s in sources for n in extract_numbers(s)}
    said = extract_numbers(text)
    tokens = re.findall(r"\w+", normalize_text(text).lower())
    plain = f" {' '.join(tokens)} "
    folded = fold(plain)
    cues = []
    if any(n.value in known for n in said):
        cues.append("NUMBER")
    phrases = list(MATH_PHRASES) + ([kc.name.lower() for kc in pkg.kcs] if pkg is not None else [])
    if any(f" {fold(p)} " in folded for p in phrases) or any(f" {w} " in plain for w in MATH_WORDS):
        cues.append("TERM")
    solution = _words(" ".join([item.explanation or "", *item.worked_solution]))
    if len(_words(text) & solution) >= 2:
        cues.append("SOLUTION")
    quality = VAGUE if not cues else ONE_CUE if len(cues) == 1 else TWO_CUES
    return ReasonJudged(quality, tuple(cues))
