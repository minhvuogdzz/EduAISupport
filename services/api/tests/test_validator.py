"""Output validator (T03, blueprint PART 13.4): positive and negative cases for every check."""

from pathlib import Path

import pytest
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.content.lesson_package import CompareAnswer, NumericAnswer, load_lesson_package
from cavat.modules.tutor.contracts import (
    ItemState,
    MessageValidator,
    PolicyDecision,
    RenderContext,
    ValidationCode,
)
from cavat.modules.tutor.validator import foreign_text, validate_message, wrong_address

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
        ("GP-01", "Vậy 0,25 bé hơn 0,3, đúng không con?"),  # a tag question still tells
        ("GP-01", "Vì sao 0,25 < 0,3?"),
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


def fraction_ctx(answer, stem, move=Move.HINT):
    """A copy of GP-01 whose answer is written as fractions: what a chapter built from the teacher's
    documents asks ("0,7 = ……" answers 7/10)."""
    item = PKG.item("GP-01").model_copy(update={"answer": answer, "stem": stem, "leak_patterns": []})
    state = ItemState(item_id=item.id, activity=ActivityType.GUIDED_PRACTICE)
    return RenderContext(decision=PolicyDecision(move=move), item=item, package=PKG, state=state)


FRACTION_KEY = NumericAnswer(type="numeric", value="7/10", form="fraction")
FRACTION_STEM = "Viết 0,7 dưới dạng phân số thập phân: 0,7 = ……"
FRACTION_PAIR = CompareAnswer(type="compare", left="3/7", right="7/10")
FRACTION_PAIR_STEM = "Điền dấu >, < hoặc = vào chỗ chấm: 3/7 … 7/10"


@pytest.mark.parametrize(
    "text",
    [
        "Đáp án là 7/10. Con thử viết lại nhé?",  # REFORM 4.4: a fraction is one number, not "7"
        "Kết quả bằng 7/10 đó. Con thử lại nhé?",
        "Đáp án là 7 / 10, con viết lại nhé?",  # spaces around the bar
        "Vậy x = 7/10. Con kiểm tra lại nhé?",
        "Đáp án là 70/100. Con rút gọn được không?",  # the same value, written bigger
    ],
)
def test_a_fraction_answer_is_a_leak(text):
    result = VALIDATE(text, fraction_ctx(FRACTION_KEY, FRACTION_STEM))
    assert LEAK in result.codes, text


@pytest.mark.parametrize(
    "text",
    [
        "Con viết 0,7 thành phân số có mẫu số là 10 nhé?",  # no statement of the answer
        "Đáp án là 7. Con thử lại nhé?",  # 7 is not 7/10
        "Đáp án là 3/10. Con thử lại nhé?",  # another fraction
        "Con nhớ 7/10 đọc là bảy phần mười, còn 0,7 viết thế nào?",  # says the number, not "the answer is"
    ],
)
def test_a_fraction_that_is_not_the_answer_is_no_leak(text):
    result = VALIDATE(text, fraction_ctx(FRACTION_KEY, FRACTION_STEM))
    assert LEAK not in result.codes, text


def test_a_fraction_is_not_its_numerator():
    # "Đáp án là 7/10" says 7/10, so for an item whose answer is the number 7 it is no leak (it read "7")
    key = NumericAnswer(type="numeric", value="7")
    result = VALIDATE("Đáp án là 7/10. Con thử lại nhé?", fraction_ctx(key, "Viết 7 thành số tự nhiên: ……"))
    assert LEAK not in result.codes
    result = VALIDATE("Đáp án là 7. Con thử lại nhé?", fraction_ctx(key, "Viết 7 thành số tự nhiên: ……"))
    assert LEAK in result.codes  # and the number itself is still one


@pytest.mark.parametrize(
    "text",
    [
        "Ta có 3/7 bé hơn 7/10. Con điền dấu nào?",
        "Số 7/10 > 3/7 nhé. Con điền dấu nào?",
        "Vì 3/7 < 7/10 nên con điền dấu bé nhé?",
        "Ta có 3 / 7 nhỏ hơn 7 / 10 đó. Con điền dấu nào?",
    ],
)
def test_a_relation_between_fractions_is_a_leak(text):
    result = VALIDATE(text, fraction_ctx(FRACTION_PAIR, FRACTION_PAIR_STEM))
    assert LEAK in result.codes, text


@pytest.mark.parametrize(
    "text",
    [
        "Giữa 3/7 và 7/10, phân số nào lớn hơn?",  # a question does not tell
        "Ta có 3/7 > 1/7 vì cùng mẫu số thì tử số lớn hơn lớn hơn. Con điền dấu nào?",  # another pair
        "Con quy đồng 3/7 và 7/10 trước nhé?",
    ],
)
def test_no_leak_between_fractions_that_are_not_the_pair(text):
    result = VALIDATE(text, fraction_ctx(FRACTION_PAIR, FRACTION_PAIR_STEM))
    assert LEAK not in result.codes, text


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


@pytest.mark.parametrize(
    "text",
    [
        "Nó chỉ để hai số có số chữ số thập分 like nha.",  # seen live from Qwen
        "Con thử so sánh hàng phần mười nhé, okay?",
        "Đây là fraction, con nhé.",
        "Это число.",
    ],
)
def test_a_message_that_is_not_vietnamese_is_refused(text):
    assert foreign_text(text) is not None


@pytest.mark.parametrize(
    "text",
    ["Con đổi 2 kg ra gam nhé: 2 kg = 2000 g.", "Dài 4,56 m, tức là 4 m 56 cm.", "Con nghĩ là 0,9 nhé."],
)
def test_vietnamese_with_units_is_not_foreign(text):
    assert foreign_text(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "Phân số thập phân có dấu vết trong số đếm của em.",  # seen live from Qwen (TQ-3)
        "Em thử nhìn mẫu số nhé?",
        "Cháu đọc lại đề giúp cô nhé?",
    ],
)
def test_calling_the_child_other_than_con_is_refused(text):
    assert wrong_address(text, "con") is not None


@pytest.mark.parametrize(
    "text",
    [
        "Con nhìn mẫu số nhé?",
        "Con bị bạn trêu à? Con nói ngay với thầy cô nhé.",  # "bạn" echoes the child's words
        "Em bé có 3 quả táo.",
        "Kem que dài 12 cm.",
    ],
)
def test_the_lesson_address_and_lookalikes_pass(text):
    assert wrong_address(text, "con") is None


def test_wrong_address_is_a_validation_code():
    assert ValidationCode.WRONG_ADDRESS.value in codes("Em thử so sánh hàng phần mười xem?")
