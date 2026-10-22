"""FIX-5 (DI-63): the validator rejects a turn that repeats the child's words as the tutor's own.

Seen in the hard roles of 2026-10-22: to "cô ơi con chơi game được không", Qwen answered "cô ơi con chơi
game được không, nhưng bây giờ mình quay lại bài nhé…". A short quote, a number the child wrote, words in
quotation marks and words the lesson itself has stay allowed. Offline, on the chapter of the repo."""

from __future__ import annotations

import pytest
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.session import chapter_service
from cavat.modules.tutor.contracts import ItemState, PolicyDecision, RenderContext, ValidationCode
from cavat.modules.tutor.validator import echoes_child, validate_message

CHAPTER = chapter_service.chapters()["math-g5-decimals"]
ITEM = CHAPTER.item("TP-PR-01")  # "Viết phân số 9/10 dưới dạng số thập phân."
PACKAGE = CHAPTER.lesson_of(ITEM.id)
REDIRECT = PolicyDecision(move=Move.REDIRECT, reason_codes=("OFF_TOPIC",), rule_ids=("R-REDIRECT",))


def ctx(said: str, last_tutor: str = "") -> RenderContext:
    state = ItemState(item_id=ITEM.id, activity=ActivityType.GUIDED_PRACTICE, attempt_no=1)
    return RenderContext(
        decision=REDIRECT, item=ITEM, package=PACKAGE, state=state, student_text=said, last_tutor=last_tutor
    )


def test_the_turn_seen_live_is_rejected():
    said = "cô ơi con chơi game được không"
    text = (
        "cô ơi con chơi game được không, nhưng bây giờ mình quay lại bài nhé. "
        "Con có thể thử viết phân số 9/10 dưới dạng số thập phân được không?"
    )
    codes = [i.code for i in validate_message(text, ctx(said)).issues]
    assert codes == [ValidationCode.ECHOES_CHILD]


def test_the_childs_words_without_diacritics_are_caught_too():
    said = "co oi con choi game duoc khong"
    assert echoes_child("Cô ơi con chơi game được không, mình quay lại bài nhé?", ctx(said))


def test_a_long_copied_run_is_caught_anywhere_in_the_turn():
    said = "hôm qua con đi đá bóng với các bạn ở sân trường"
    text = "Cô nghe rồi, hôm qua con đi đá bóng với các bạn ở sân trường. Mình làm bài tiếp nhé?"
    assert echoes_child(text, ctx(said))


@pytest.mark.parametrize(
    ("said", "text"),
    [
        ("C", "Con chọn C. Con nhìn mẫu số của từng phân số nhé?"),  # a short quote
        ("0,09", "Con đã viết ra 0,09 rồi, con làm thế nào vậy?"),  # a number the child wrote
        ("con không biết", "Không sao, con không biết thì mình cùng nghĩ nhé?"),  # under 4 words
        (  # the child's words in quotation marks
            "cô ơi con chơi game được không",
            "Con hỏi “cô ơi con chơi game được không”, để lúc nghỉ nhé. Mình làm bài tiếp nhé?",
        ),
        (  # the child read the task back; the tutor may say it too
            "viết phân số 9/10 dưới dạng số thập phân",
            "Viết phân số 9/10 dưới dạng số thập phân. Mẫu số 10 cho biết điều gì?",
        ),
        (  # an answer that only repeats words the tutor said just before
            "mẫu số cho biết phần thập phân có mấy chữ số",
            "Đúng rồi, mẫu số cho biết phần thập phân có mấy chữ số. Vậy 9/10 viết thế nào?",
        ),
    ],
)
def test_what_stays_allowed(said, text):
    last = "Mẫu số cho biết phần thập phân có mấy chữ số?"
    assert echoes_child(text, ctx(said, last_tutor=last)) is None
