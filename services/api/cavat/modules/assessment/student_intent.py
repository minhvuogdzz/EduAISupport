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
from collections.abc import Collection

from cavat.core.pedagogy import Outcome
from cavat.core.vi_text import fold
from cavat.modules.assessment.vi_numbers import normalize_text, phrase_regex, tolerant_pattern

# 0.3.0: REFORM-5 (DI-75, DI-76), a bare "không"/"chưa" is "con không biết", a bare "gì" asks, and the few
#        letters nothing reads ("ki", "kk", "ể") are told apart (``is_gibberish_or_ambiguous_short``)
# 0.2.1: REFORM-2, "là gì", "ra sao", "viết sao" ask; 0.2.0: more teen code, keyword dumps (conductor)
INTENT_VERSION = "student-intent/0.3.0"

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
    # student-intent/0.2.0 (conductor): what the owner's students type. Not "kg", "m", "s", "t": units, "Sai".
    "hk": "không",
    "hong": "không",
    "hum": "không",
    "kô": "không",
    "khong": "không",
    "kbt": "không biết",
    "kb": "không biết",
    "pít": "biết",
    "bíc": "biết",
    "biet": "biết",
    "hieu": "hiểu",
    "chx": "chưa",
    "đag": "đang",
    "dag": "đang",
    "ròi": "rồi",
    "zậy": "vậy",
    "zị": "vậy",
    "lun": "luôn",
    "wá": "quá",
    "qá": "quá",
    "bùn": "buồn",
    "chời": "trời",
    "vs": "với",
    "ms": "mới",
    "nx": "nữa",
    "trc": "trước",
    "nma": "nhưng mà",
    "lsao": "làm sao",
    "ntnao": "như thế nào",
    "ok": "được",
    "oke": "được",
    "okie": "được",
    "okela": "được",
    "uk": "ừ",
    "uh": "ừ",
    "ừm": "ừ",
    "đk": "được",
    "dk": "được",
    "đuợc": "được",
    "jo": "giờ",
    "h": "giờ",
    "bh": "bao giờ",
    "nhìu": "nhiều",
    "iu": "yêu",
    "thik": "thích",
    "thíc": "thích",
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


_TERM_PIECES = frozenset("số phân thập phần hàng mười trăm nghìn đơn vị chục dấu phẩy và với của".split())
_FILLER = frozenset("ạ à ơi cô con dạ thì là".split())


def keyword_dump(text: str) -> bool:
    """A heap of lesson keywords with no question and no answer in it ("phân số thập phân mẫu số tử số hàng
    phần mười"): at least three distinct terms, no digit, no question, and nothing left once the terms (and
    their pieces, fillers) are taken out. The tutor says the task again rather than guess (R-CLARIFY).
    Linking words ("trước", "rồi", "vì", "bằng") make a sentence of it: an explanation is not a heap."""
    from cavat.modules.assessment.math_terms import _TERM_RE, terms_in

    t = expand_short_forms(text)
    if re.search(r"\d", t) or asks_question(text) or len(terms_in(t)) < 3:
        return False
    left = [w for w in re.findall(r"\w+", _TERM_RE.sub(" ", t)) if w not in _TERM_PIECES | _FILLER]
    return not left


# REFORM-5 (DI-75): "không", "ko", "k", "chưa", "không ạ", "không mà" and nothing else. Alone, it answers a
# question that a no can answer (a true/false item, a yes/no question, the number 0); asked "vì sao" or a
# question with a number to give, it is "con không biết". Seen live: it was praised as an explanation.
_NO_FILLERS = ("ạ", "à", "mà", "cô", "ơi", "nhé", "nha")
_BARE_NO_RE = re.compile(
    rf"^(?:{tolerant_pattern('không')}|{tolerant_pattern('chưa')})"
    rf"(?:\s+(?:{'|'.join(tolerant_pattern(f) for f in _NO_FILLERS)}))*[\s.!…]*$"
)
# "j" is "gì": alone, it asks what (a child who did not catch the question), as "hả" does.
_BARE_WH_RE = re.compile(rf"^(?:{tolerant_pattern('gì')}|{tolerant_pattern('sao')})[\s.!?…]*$")


def is_bare_negation(text: str) -> bool:
    """The whole message is "không" or "chưa" (``ko``, ``k``, ``hông`` too), with at most a polite word."""
    return bool(_BARE_NO_RE.match(expand_short_forms(text).strip()))


def read_intent(text: str, has_answer: bool = False, *, verdict: bool = False) -> Outcome | None:
    """The intent of a message that is not an attempt, or None for an attempt (an answer, a retell).

    ``has_answer``: the message also carries something the checker can grade (a number, a relation). An
    answer with a doubt ("0,25 < 0,3 nhưng con không biết vì sao") is an attempt; a demand for the answer
    ("cho con đáp án câu 2") is not.
    ``verdict``: the question can be answered by a bare "không" or "chưa" (true or false, yes or no, the
    number
    0): then it is an answer, not "con không biết" (REFORM-5, DI-75).
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
    if _CLARIFY_RE.search(t) or keyword_dump(text) or _BARE_WH_RE.match(t.strip()):
        return Outcome.CLARIFY_REQUEST
    if _HELP_RE.search(t):
        return Outcome.HELP_REQUEST
    if not verdict and _BARE_NO_RE.match(t.strip()):
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


# --------------------------------------------------------------------------- the few letters nothing reads
# REFORM-5 (DI-76, drafted for the owner's review). A child stuck on a question types "ki" (the i sits next
# to the o: "ko"), "kt", "ể" or "êr" (a Telex slip), "tt", "kk", "kkk" (a key held down, laughter). The
# lists above read "ko bít", "hả", "chán"; these are what is left when none of them reads the message. They
# are neither an answer nor an explanation, so the tutor asks what the child meant (ASK_CONFIRM) instead of
# grading them or praising them. The words below are what a child of grade 5 may type alone in a maths
# lesson, without diacritics (the match is folded): a short message made only of other letters is
# "unreadable".
SHORT_MAX_LETTERS = 6  # DI-76: a longer message is read by the lists, the checker and the context reader
SHORT_MAX_WORDS = 2
_KNOWN_WORDS = """
có không chưa rồi phải đúng sai dạ vâng ừ ừm ờ ạ à ơi ôi ui ồ ok oke yes no hay thôi nhé nha nhỉ nhá
cô con em mẹ bố ba anh chị bạn mình tớ cậu thầy cháu ông bà
là và của với cho để do vì nên nhưng mà thì sẽ đã đang bị rất quá lắm hơn nhất cũng vẫn còn chỉ mới lại nữa
luôn
ngay xong hết đủ nào đâu gì sao thế vậy đây kia này đó ấy nhiều ít mỗi từng mọi các những một hai bốn năm sáu
bảy tám
chín mười trăm nghìn ngàn chục linh lẻ
số tử mẫu phẩy phân thập hàng bằng lớn bé nhỏ kém cộng trừ nhân chia bớt thêm dư gấp đôi nửa tròn đơn vị cm dm
mm km
m kg g l ml diện tích dài rộng cao đáy cạnh góc hình tam giác thang vuông
biết hiểu nhớ quên làm viết đọc tính đếm xem thử chọn tìm bỏ giữ đổi ghi nói hỏi đặt lấy ra vào lên xuống được
khó dễ nhanh chậm ngắn nặng nhẹ to chán mệt buồn sợ ghét thích vui khóc bực cáu câu bài đáp đề ý game chơi
phim đói ăn ngủ
"""
_KNOWN_SHORT = (
    {fold(w) for w in _KNOWN_WORDS.split()}
    | {fold(k) for k in _SHORT_FORMS}
    | {fold(w) for v in _SHORT_FORMS.values() for w in v.split()}
)
# One letter typed over and over ("kk", "kkk"), or one chunk of two or three ("hihi", "haha"): a key held
# down or laughter, whatever the letters. (A message of several words is never one: "ba ba".)
_MASH_RE = re.compile(r"([a-z])\1+|([a-z]{2,3})\2+")


def is_keyboard_mash(text: str) -> bool:
    """One letter or one short chunk typed over and over, nothing else ("kk", "kkk", "tt", "haha")."""
    one = text.strip().lower()
    return bool(one) and not re.search(r"[\s\d]", one) and bool(_MASH_RE.fullmatch(fold(one)))


def is_gibberish_or_ambiguous_short(text: str, known: Collection[str] = frozenset()) -> bool:
    """A message of at most 6 letters and two words, no digit, in which no word is one a child types alone in
    this lesson (``_KNOWN_WORDS``, the short forms, ``known``): "ki", "kt", "kk", "kkk", "tt", "ể", "êr".

    ``known``: folded words of the item the child may quote (a name in the task, a letter of an option). What
    another reader gives a meaning to is never here: "hả" and "j" ask, "ko" is "không" (``read_intent``).
    """
    one = text.strip()
    if not one or any(ch.isdigit() for ch in one):
        return False
    words = re.findall(r"[^\W\d_]+", one.lower())
    if not words or len(words) > SHORT_MAX_WORDS or sum(map(len, words)) > SHORT_MAX_LETTERS:
        return False
    if is_keyboard_mash(one):
        return True
    if read_intent(one) is not None:
        return False
    return not any(fold(w) in _KNOWN_SHORT or fold(w) in known for w in words)


# "ừ", "dạ", "đúng rồi": the reply to "cô đoán con muốn nói là con chưa biết làm, đúng không?". Alone it means
# nothing; after that question it confirms the guess (``intent_of_guess``).
_AFFIRM = ("ừ", "dạ", "vâng", "đúng", "đúng rồi", "đúng vậy", "phải", "phải rồi", "được", "có", "ờ")
_AFFIRM_RE = re.compile(
    rf"^(?:{'|'.join(tolerant_pattern(w) for w in _AFFIRM)})"
    rf"(?:\s+(?:{'|'.join(tolerant_pattern(f) for f in ('ạ', 'cô', 'ơi', 'nhé', 'đó', 'ạ'))}))*[\s.!…]*$"
)


def is_affirmation(text: str) -> bool:
    """The whole message says yes ("ừ", "dạ", "đúng rồi ạ", "ok")."""
    return bool(_AFFIRM_RE.match(expand_short_forms(text).strip()))


def intent_of_guess(meaning: str) -> Outcome | None:
    """What a guessed meaning ("chưa biết làm", "muốn nghỉ", "chưa hiểu đề") asks of the tutor: the same
    lists that read the child's own words read it. Only a request the tutor answers without grading
    (help, a feeling, a question) counts; anything else is None."""
    intent = read_intent(f"con {meaning}") if meaning.strip() else None
    return (
        intent if intent in (Outcome.HELP_REQUEST, Outcome.NEGATIVE_AFFECT, Outcome.CLARIFY_REQUEST) else None
    )


def without_subject(meaning: str) -> str:
    """A guessed meaning as a phrase with no subject, which the question adds: "con chưa biết làm" and
    "chưa biết làm." are both "chưa biết làm"."""
    return re.sub(r"^(?:con|em|cô)(?:\s+|$)", "", meaning.strip(" .?!"), flags=re.IGNORECASE)


def known_words(*texts: str) -> frozenset[str]:
    """The folded words of texts a child may quote back (the task, the options): for ``known`` above. A word
    with hyphens ("ki-lô-gam") stays one word, so its first syllable does not make "ki" a word of the task."""
    return frozenset(fold(w) for t in texts for w in re.findall(r"[^\W\d_]+(?:-[^\W\d_]+)*", t.lower()))


# QWERTY, each row shifted as on a keyboard: the keys a finger lands on by mistake are the near ones.
_KEYBOARD = ("qwertyuiop", "asdfghjkl", "zxcvbnm")
_ROW_SHIFT = (0.0, 0.25, 0.75)
_NEAR = 1.3
_NO_FORMS = frozenset({"ko", "kh", "khg", "hok", "hem", "hum", "hong", "hk"})


def _near_keys(ch: str) -> list[str]:
    here = next(((row.index(ch) + _ROW_SHIFT[r], r) for r, row in enumerate(_KEYBOARD) if ch in row), None)
    if here is None:
        return []
    return [
        c
        for r, row in enumerate(_KEYBOARD)
        for i, c in enumerate(row)
        if c != ch and ((i + _ROW_SHIFT[r] - here[0]) ** 2 + (r - here[1]) ** 2) ** 0.5 <= _NEAR
    ]


def guess_typo(text: str) -> str | None:
    """What a child most likely meant by a word one key away from "ko" or "khg" ("ki": the i is next to the
    o), without a model: "chưa biết làm". None when no such word is one slip away (then a model may guess)."""
    word = fold(text.strip().lower())
    if not re.fullmatch(r"[a-z]{2,4}", word):
        return None
    slips = [word[:i] + near + word[i + 1 :] for i, ch in enumerate(word) for near in _near_keys(ch)]
    swaps = [word[:i] + word[i + 1] + word[i] + word[i + 2 :] for i in range(len(word) - 1)]
    return "chưa biết làm" if _NO_FORMS.intersection(slips + swaps) else None


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
# REFORM-2 (DI-69): two words are enough when they are the question itself ("là gì", "ra sao", "viết sao").
_SHORT_QUESTION_RE = re.compile(r"^(?:\w+\s+)?(?:la gi|ra sao|viet sao|nhu nao|the nao)" + _TAIL)
_NEGATION_END_RE = re.compile(r"\b(?:thi|cung|van|deu|lai)\s+(?:khong|chua)\W*$")
_PARTICLE_RE = re.compile(r"\s(?:à|hả|nhỉ)(?:\s+(?:cô|ạ))*\W*$")


def asks_question(text: str) -> bool:
    """The child asks something (DI-39): "?", an opening question word, or a closing question particle."""
    t = expand_short_forms(text)
    if "?" in t or _PARTICLE_RE.search(t):
        return True
    folded = fold(t)
    if _OPENING_RE.match(folded):
        return True
    # "không", "chưa" alone answer a question; a closing particle asks only after a few words, and a
    # negation ("bỏ số 0 ở giữa thì không", "con cũng chưa") says something: it asks nothing (0.2.0).
    if _NEGATION_END_RE.search(folded):
        return False
    if len(folded.split()) <= 3 and _SHORT_QUESTION_RE.match(folded):
        return True
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
