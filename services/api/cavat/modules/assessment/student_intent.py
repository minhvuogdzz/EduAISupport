"""What a student message is, before any grading (ADR-019).

A child of 10 does not only answer. They say "con không biết", ask "là sao ạ?", demand the answer, say
they are bored, or talk about football. Each of these needs its own move, and none of them is a wrong
answer: counting them as one led the tutor to show the worked solution after three off-topic messages.

The reading is deterministic: the text is expanded (the short forms children type: "ko", "bít", "j"...)
and matched against phrase lists that tolerate missing diacritics, in a fixed order of priority (the
order of the Edubot intent detector the owner pointed to). The phrase lists are part of the versioned
policy; a change is a policy change (CLAUDE.md rule 7).
"""

from __future__ import annotations

import re

from cavat.core.pedagogy import Outcome
from cavat.core.vi_text import fold
from cavat.modules.assessment.vi_numbers import normalize_text, phrase_regex

INTENT_VERSION = "student-intent/0.1.0"

# Short forms as children type them, token by token. Only used to read the intent: answers are parsed
# from the raw text. DI-32: "k", "v", "r" stand alone only in this sense in a lesson about decimals.
_SHORT_FORMS: dict[str, str] = {
    "ko": "không",
    "k": "không",
    "kh": "không",
    "khg": "không",
    "khum": "không",
    "hok": "không",
    "hông": "không",
    "hem": "không",
    "bít": "biết",
    "bit": "biết",
    "bik": "biết",
    "hiu": "hiểu",
    "hỉu": "hiểu",
    "bjk": "biết",
    "j": "gì",
    "z": "vậy",
    "v": "vậy",
    "dz": "vậy",
    "dc": "được",
    "đc": "được",
    "r": "rồi",
    "ns": "nói",
    "lm": "làm",
    "hc": "học",
    "cx": "cũng",
    "ntn": "như thế nào",
    "mk": "mình",
    "mik": "mình",
}
_TOKEN_RE = re.compile(r"\w+|\W+")

_SILENT_RE = re.compile(r"[\s.…?!]*")

# DI-32: the phrase lists. A phrase is listed before a shorter one it starts with.
_ANSWER_DEMAND_RE = phrase_regex(
    [
        "đáp án là gì",
        "cho con biết đáp án",
        "cho con xin đáp án",
        "cho em xin đáp án",
        "cho con đáp án",
        "cho em đáp án",
        "xin đáp án",
        "nói đáp án",
        "đáp án đi",
        "cho đáp án",
        "in ra đáp án",
        "kết quả là gì",
        "cho con kết quả",
        "nói kết quả",
        "đáp số là gì",
        "nói luôn",
        "nói đi mà",
        "giải hộ",
        "giải giùm",
        "giải giúp",
        "làm hộ",
        "làm giùm",
        "làm giúp con",
        "làm giúp em",
        "bỏ qua luật",
        "bỏ qua mọi",
        "cho con chép",
    ]
)
_AFFECT_RE = phrase_regex(
    [
        "chán",
        "mệt",
        "buồn ngủ",
        "buồn",
        "con ngu",
        "em ngu",
        "ngu quá",
        "dốt",
        "không muốn học",
        "không học nữa",
        "không làm nữa",
        "muốn nghỉ",
        "bỏ cuộc",
        "sợ sai",
        "sợ lắm",
        "sợ bị",
        "ghét toán",
        "ghét học",
        "khó quá",
        "khó lắm",
        "khóc",
        "bực",
        "cáu",
    ]
)
_CLARIFY_RE = phrase_regex(
    [
        "nghĩa là gì",
        "nghĩa là sao",
        "tức là sao",
        "tức là gì",
        "là sao",
        "là gì",
        "là thế nào",
        "sao vậy",
        "sao ạ",
        "sao cơ",
        "ý cô là",
        "ý là sao",
        "thế nào ạ",
        "nói lại",
        "nhắc lại",
        "hỏi lại",
        "giải thích lại",
        "giải thích đi",
        "không hiểu",
        "chưa hiểu",
        "đề hỏi gì",
        "hỏi gì",
        "gì cơ",
        "gì ạ",
        "cái gì",
        "hả",
    ]
)
_HELP_RE = phrase_regex(
    [
        "không biết",
        "chưa biết",
        "không nhớ",
        "chưa nhớ",
        "quên",
        "chịu",
        "bó tay",
        "gợi ý",
        "giúp con",
        "giúp em",
        "giúp với",
        "bỏ qua",
        "làm sao",
        "làm thế nào",
        "như thế nào",
        "khó",
    ]
)
_OFF_TOPIC_RE = phrase_regex(
    [
        "game",
        "chơi",
        "bóng đá",
        "đá bóng",
        "youtube",
        "tiktok",
        "phim",
        "hoạt hình",
        "minecraft",
        "roblox",
        "liên quân",
        "free fire",
        "đói",
        "ăn cơm",
        "ăn kem",
        "đi ngủ",
        "mấy tuổi",
        "tên gì",
        "nhà cô",
        "chuyện cười",
        "kể chuyện",
        "đi chơi",
        "con mèo",
        "con chó",
        "thời tiết",
        "trời mưa",
        "trời nắng",
        "điện thoại",
        "ipad",
    ]
)
# Words of the lesson: a long unreadable reply without any of them is off-topic (DI-32).
_LESSON_WORDS_RE = phrase_regex(
    [
        "số",
        "phân",
        "phẩy",
        "thập",
        "mẫu",
        "tử",
        "chục",
        "trăm",
        "nghìn",
        "mười",
        "hàng",
        "bằng",
        "lớn",
        "bé",
        "nhỏ",
        "hơn",
        "đúng",
        "sai",
        "vì",
        "nên",
        "cộng",
        "trừ",
        "nhân",
        "chia",
        "mét",
        "chọn",
        "câu",
        "bài",
        "đáp",
        "phần",
        "đơn vị",
    ]
)
_OFF_TOPIC_MIN_WORDS = 4  # DI-32


def expand_short_forms(text: str) -> str:
    """`normalize_text` with the short forms children type written out: "ko bít" -> "không biết"."""
    parts = _TOKEN_RE.findall(normalize_text(text))
    return "".join(_SHORT_FORMS.get(p, p) for p in parts)


def read_intent(text: str, has_answer: bool = False) -> Outcome | None:
    """The intent of a message that is not an attempt, or None for an attempt (an answer, a retell).

    ``has_answer``: the message also carries something the checker can grade (a number, a relation). An
    answer with a doubt ("0,25 < 0,3 nhưng con không biết vì sao") is an attempt; a demand for the answer
    ("cho con đáp án câu 2") is not.
    """
    t = expand_short_forms(text)
    if _SILENT_RE.fullmatch(t):
        return Outcome.NO_RESPONSE
    if _ANSWER_DEMAND_RE.search(t):
        return Outcome.ANSWER_DEMAND
    if has_answer:
        return None
    if _AFFECT_RE.search(t):
        return Outcome.NEGATIVE_AFFECT
    if _CLARIFY_RE.search(t):
        return Outcome.CLARIFY_REQUEST
    if _HELP_RE.search(t):
        return Outcome.HELP_REQUEST
    if _OFF_TOPIC_RE.search(t):
        return Outcome.OFF_TOPIC
    return None


def looks_off_topic(text: str) -> bool:
    """An unreadable reply of several words that says nothing about the lesson (DI-32)."""
    t = expand_short_forms(text)
    if any(ch.isdigit() for ch in t):
        return False  # numbers are about the lesson, even when they cannot be read as an answer
    return len(t.split()) >= _OFF_TOPIC_MIN_WORDS and not _LESSON_WORDS_RE.search(t)


# DI-39: the form of a question (RAG-2). A question word inside a statement is not one: a retell says
# "bao nhiêu chữ số 0 thì..." and an answer says "tức là". A message asks when it has a question mark, opens
# with a question word, or ends with a question particle. Whether it is about the lesson, and new, is decided
# by the grounded speech (content words, the question the tutor waits on), not here. Matched on the folded
# text (children type without diacritics), except the particles that fold onto other words ("à" is "ạ").
_LEAD = r"^\W*(?:(?:co|thay)\s+oi\W+)?(?:(?:cho\s+con\s+hoi|con\s+hoi|the|vay)\W+)?"
_OPENING_RE = re.compile(
    _LEAD
    + r"(?:tai sao|vi sao|sao|lam sao|lam the nao|nhu the nao|nhu nao|the nao|co phai|bao nhieu|cai gi)\b"
)
_TAIL = r"(?:\s+(?:a|vay|the|ha|nhi|co|oi))*\W*$"
_ENDING_RE = re.compile(
    r"\b(?:la sao|the nao|nhu nao|ra sao|bao nhieu|duoc khong|dung khong|phai khong|khong|chua|gi)" + _TAIL
)
_PARTICLE_RE = re.compile(r"\s(?:à|hả|nhỉ)(?:\s+(?:cô|ạ))*\W*$")


def asks_question(text: str) -> bool:
    """The child asks something (DI-39): "?", an opening question word, or a closing question particle."""
    t = expand_short_forms(text)
    if "?" in t or _PARTICLE_RE.search(t):
        return True
    folded = fold(t)
    if _OPENING_RE.match(folded):
        return True
    # "không", "chưa" alone answer a question; a closing particle asks only after a few words
    return len(folded.split()) >= 3 and bool(_ENDING_RE.search(folded))


# DI-41 (drafted for the owner's review): words of a child in danger or in distress. Whatever else the message
# is, the tutor answers with care and flags it for the teacher; it is never parked or treated as off-topic.
_DISTRESS_RE = phrase_regex(
    [
        "bắt nạt",
        "bị đánh",
        "đánh con",
        "đánh em",
        "bị chửi",
        "chửi con",
        "muốn chết",
        "không muốn sống",
        "tự tử",
        "tự làm đau",
        "làm đau bản thân",
        "làm đau mình",
        "cắt tay",
        "rạch tay",
        "bị sờ",
        "sờ vào người",
        "sợ về nhà",
        "bỏ nhà",
        "bị nhốt",
        "bị bỏ đói",
        "bị dọa",
        "đe dọa",
    ]
)


# "bị bạn đánh", "bị anh ấy dọa": who did it comes between "bị" and the act (with or without diacritics).
_HARMED_RE = re.compile(r"\bbị(?:\s+\w+){0,2}\s+(?:đánh|chửi|tát|dọa|đe dọa|nhốt|bắt nạt|sờ)\b")
_HARMED_FOLDED_RE = re.compile(r"\bbi(?:\s+\w+){0,2}\s+(?:danh|chui|tat|doa|nhot|bat nat)\b")


def signals_distress(text: str) -> bool:
    """The child says something worrying (DI-41): for the teacher, whatever the lesson is doing."""
    t = expand_short_forms(text)
    return bool(_DISTRESS_RE.search(t) or _HARMED_RE.search(t) or _HARMED_FOLDED_RE.search(fold(t)))


_ASK_HINT_RE = phrase_regex(["gợi ý", "giúp con", "giúp em", "giúp với"])


def asks_for_hint(text: str) -> bool:
    """The student names the help they want ("gợi ý", "giúp con"), unlike a bare "con không biết"."""
    return bool(_ASK_HINT_RE.search(expand_short_forms(text)))
