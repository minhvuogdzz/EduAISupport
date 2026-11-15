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


# ENG-5g (L-5, DI-160, ``reason-rubric-en/0.1.0``, drafted for the owner's review): the words of an English
# lesson's "vì sao" in Vietnamese. A Mathematics package never reads them.
REASON_VERSION_EN = "reason-rubric-en/0.1.0"
ENGLISH_PHRASES = (
    "quá khứ", "đã qua", "đã xảy ra", "chuyện cũ", "hiện tại", "hôm qua", "tuần trước", "năm ngoái",
    "động từ", "nguyên mẫu", "giữ nguyên", "không đổi", "bất quy tắc", "có quy tắc", "dạng riêng", "thêm ed",
    "thêm -ed", "câu hỏi", "câu trả lời", "trả lời ngắn", "từ để hỏi", "chủ ngữ", "nơi chốn", "thời gian",
    "trọng âm", "nhấn mạnh", "đọc nhấn", "đọc nhẹ", "từ chính", "đoạn văn", "câu đầu", "trong tranh",
    "trong bài đọc", "nghĩa là", "quà lưu niệm", "số nhiều",
)  # fmt: skip
_EN_STOP = frozenset(
    "the and you did not was were yes she her his they their our your with for there this that".split()
)


def _english_words(text: str) -> set[str]:
    """The English words of a text (ASCII words of three letters or more, not grammar words)."""
    return {
        w for w in re.findall(r"[a-z]+", text.lower()) if len(w) >= 3 and w not in _EN_STOP and w.isascii()
    }


_QUOTED = re.compile(r"['‘\"“]([^'’\"”]{2,})['’\"”]")
_NAME_RUN = re.compile(r"(?<!^)(?<![.!?:] )\b[A-Z][a-z]+(?: [A-Z][a-z]+)*")


def _english_parts(item: Item) -> list[str]:
    """The English of an item, never its Vietnamese ("con", "nha" are ASCII too): the accepted answers and
    options, the quoted sentences of its stem and explanation, and the names in them ("Ha Long Bay")."""
    answer = item.answer
    parts = [*(getattr(answer, "accept", ()) or ()), *(o.text for o in getattr(answer, "options", ()) or ())]
    for text in (item.stem, item.explanation or "", *item.worked_solution):
        parts += _QUOTED.findall(text) + _NAME_RUN.findall(text)
    return [p for p in parts if isinstance(p, str)]


def _judge_english(item: Item, text: str, pkg: LessonPackage) -> ReasonJudged:
    """DI-160: an English item's "vì sao". Cues: TERM, a Vietnamese word of the grammar of the lesson ("quá
    khứ", "giữ nguyên", "trọng âm") or of its knowledge components; QUOTE, an English word of the item the
    child points to ("took", "last weekend", "Ha Long Bay"); SOLUTION, as for Mathematics. Never numbers."""
    tokens = re.findall(r"\w+", normalize_text(text).lower())
    plain = f" {' '.join(tokens)} "
    folded = fold(plain)
    cues = []
    phrases = list(ENGLISH_PHRASES) + [kc.name.lower() for kc in pkg.kcs]
    if any(f" {fold(p)} " in folded for p in phrases if len(p.split()) >= 2) or any(
        f" {p} " in plain for p in phrases
    ):
        cues.append("TERM")
    if _english_words(text) & _english_words(" ".join(_english_parts(item))):
        cues.append("QUOTE")
    solution = _words(" ".join([item.explanation or "", *item.worked_solution]))
    if len(_words(text) & solution) >= 2:
        cues.append("SOLUTION")
    quality = VAGUE if not cues else ONE_CUE if len(cues) == 1 else TWO_CUES
    return ReasonJudged(quality, tuple(cues))


def judge_reason(item: Item, text: str, pkg: LessonPackage | None = None) -> ReasonJudged:
    if pkg is not None and getattr(pkg, "subject", "math") == "english":
        return _judge_english(item, text, pkg)
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
