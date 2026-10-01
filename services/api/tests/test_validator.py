"""Output validator (T03, blueprint PART 13.4): positive and negative cases for every check."""

from pathlib import Path

import pytest
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.content.lesson_package import load_lesson_package
from cavat.modules.tutor.contracts import (
    ItemState,
    MessageValidator,
    PolicyDecision,
    RenderContext,
    ValidationCode,
)
from cavat.modules.tutor.validator import validate_message

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"
PKG = load_lesson_package(LESSON)
VALIDATE: MessageValidator = validate_message


def ctx_for(item_id, move=Move.HINT, **kw):
    item = PKG.item(item_id)
    state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
    return RenderContext(decision=PolicyDecision(move=move), item=item, package=PKG, state=state, **kw)


def codes(text, item_id="GP-01", move=Move.HINT, **kw):
    return set(VALIDATE(text, ctx_for(item_id, move, **kw)).codes)


LEAK = ValidationCode.ANSWER_LEAK.value


@pytest.mark.parametrize(
    ("item_id", "text"),
    [
        ("GP-01", "Vì 2 < 3 nên 0,25 < 0,3. Con thấy đúng không?"),
        ("GP-01", "Số 0,3 > 0,25 nhé. Con điền dấu nào?"),
        ("GP-01", "0,25 bé hơn 0,3 đó. Con điền dấu nào?"),
        ("GP-01", "Mình có 0,250 < 0,30. Con điền dấu nào?"),  # equivalent forms of the same pair
        ("GP-01", "Ta có 0,25 m nhỏ hơn 0,3 m. Con điền dấu nào?"),
        ("GP-07", "Con thử với x = 6 xem sao?"),  # "x = answer", even inside a question
        ("GP-07", "Chữ số x bé nhất là 6 đấy. Con kiểm tra lại nhé?"),  # leak_patterns
        ("GP-08", "Vậy Hoa chạy nhanh hơn. Con đồng ý không?"),
        ("GP-08b", "Bạn MINH chạy chậm hơn. Con đồng ý không?"),  # case-insensitive
        ("GP-09", "Bạn An nói sai rồi. Con giải thích được không?"),
        ("GP-10", "Gói kẹo A nặng hơn. Con đồng ý không?"),
        ("GP-06", "Thứ tự là 0,2; 0,25; 0,3; 0,305. Con kiểm tra lại được không?"),
        ("GP-06", "Ta thấy 0,2 < 0,25. Số nào bé tiếp theo?"),  # part of the order
    ],
)
def test_answer_leak_detected(item_id, text):
    assert LEAK in codes(text, item_id)


@pytest.mark.parametrize(
    ("item_id", "text"),
    [
        ("GP-01", "Giữa 0,25 và 0,3, số nào lớn hơn?"),  # a question does not tell
        ("GP-01", "0,25 lớn hơn hay bé hơn 0,3?"),
        ("GP-01", "Có bạn nghĩ 0,25 > 0,3 vì 25 > 3. Con thấy bạn ấy đúng không?"),  # false statement
        ("GP-01", "Mình viết 0,3 thành 0,30. Con so sánh 0,25 và 0,30 được không?"),
        ("GP-02", "Ta có 0,4 = 0,40. Vậy mình so sánh tiếp hàng nào?"),  # not the answer pair
        ("GP-07", "Nếu x = 5 thì 0,55 so với 0,60 thế nào?"),
        ("GP-08b", "Nếu mình chạy chậm hơn thì về đích sau, đúng không?"),  # "mình" is not "Minh"
        ("GP-09", "Nếu con nghĩ bạn nói sai thì con giải thích nhé?"),  # "bạn nói sai" is not "an nói sai"
        ("GP-06", "Viết lại: 0,300; 0,250; 0,305; 0,200. Số nào bé nhất?"),
    ],
)
def test_no_answer_leak(item_id, text):
    assert LEAK not in codes(text, item_id)


def test_full_explanation_may_state_the_answer():
    explanation = PKG.item("GP-01").explanation
    text = f"{explanation} Con nói lại cách làm cho cô nghe được không?"
    assert LEAK in codes(text, "GP-01", Move.HINT)
    assert codes(text, "GP-01", Move.FULL_EXPLANATION) == set()


def test_verify_after_a_correct_answer_is_not_a_leak():
    # GP-09's approved verify prompt says "bạn An nhầm", which matches its leak pattern.
    assert codes(PKG.item("GP-09").verify_prompt, "GP-09", Move.VERIFY) == set()


def test_empty():
    for text in ("", "   \n"):
        assert codes(text) == {ValidationCode.EMPTY.value}


def test_multiple_questions():
    assert ValidationCode.MULTIPLE_QUESTIONS.value in codes("Con thấy sao? Số nào lớn hơn?")
    assert ValidationCode.MULTIPLE_QUESTIONS.value not in codes("Số nào lớn hơn?")


def test_missing_question_for_moves_that_require_one():
    assert ValidationCode.MISSING_QUESTION.value in codes("Con so sánh hàng phần mười nhé.")
    assert ValidationCode.MISSING_QUESTION.value in codes("Số nào lớn hơn? Con so sánh hàng phần mười nhé.")
    assert ValidationCode.MISSING_QUESTION.value not in codes("Con so sánh hàng phần mười nhé?")
    # PRESENT and CONFIRM_ADVANCE do not need a question.
    assert codes(PKG.item("GP-01").stem, "GP-01", Move.PRESENT) == set()
    assert ValidationCode.MISSING_QUESTION.value not in codes("Mình sang câu tiếp nhé.", move=Move.CLOSE_ITEM)


def test_too_long():
    text = " ".join(["con"] * 60) + "?"
    assert ValidationCode.TOO_LONG.value not in codes(text)
    assert ValidationCode.TOO_LONG.value in codes("thử " + text)
    assert ValidationCode.TOO_LONG.value in codes("Con đọc lại đề bài nhé?", max_words=4)


@pytest.mark.parametrize(
    "text",
    [
        "Nhà con ở đâu?",
        "Con cho cô xin số điện thoại của bố mẹ nhé?",
        "Con học trường nào?",
        "Con gửi cô địa chỉ nhà được không?",
        "Con có Zalo không?",
    ],
)
def test_pii_request(text):
    assert ValidationCode.PII_REQUEST.value in codes(text)


@pytest.mark.parametrize("text", ["Con thông minh quá! Mình làm tiếp nhé?", "Con giỏi quá!", "Con rất giỏi."])
def test_intelligence_praise(text):
    assert ValidationCode.INTELLIGENCE_PRAISE.value in codes(text, move=Move.CONFIRM_ADVANCE)


def test_process_praise_is_fine():
    text = "Đúng rồi! Con kiểm tra lại từng hàng rất cẩn thận. Mình sang câu tiếp theo nhé."
    assert codes(text, move=Move.CONFIRM_ADVANCE) == set()


def test_ungrounded_number():
    assert ValidationCode.UNGROUNDED_NUMBER.value in codes("Con so sánh 0,81 và 0,92 xem?")
    issue = VALIDATE("Con so sánh 0,81 và 0,92 xem?", ctx_for("GP-01")).issues[0]
    assert issue.detail == "0,81, 0,92"


def test_grounded_numbers():
    # Item numbers in an equivalent form, lesson counter-examples and the student's own words are grounded.
    assert codes("Con viết 0,3 thành 0,30 rồi so sánh với 0,25 được không?") == set()
    assert codes("0,9 mét là 90 xăng-ti-mét, đúng không?") == set()
    assert codes("Con vừa viết 0,52 đúng không?", student_text="0,52") == set()
    assert ValidationCode.UNGROUNDED_NUMBER.value in codes("Con vừa viết 0,52 đúng không?")
