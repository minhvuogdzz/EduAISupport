"""The conductor (conductor/0.1.0): the text the loop reads, and what the intent lists make of teen code
and keyword heaps (student-intent/0.2.0)."""

import pytest
from cavat.core.pedagogy import Outcome
from cavat.modules.assessment.student_intent import keyword_dump, read_intent
from cavat.modules.teaching.conductor import clean, repeats


@pytest.mark.parametrize(
    ("raw", "text", "signals"),
    [
        ("😭😭 ko bít lm j hết", "ko bít lm j hết", {"EMOJI", "TEENCODE"}),
        ("đúnggggg!!!!", "đúng!", {"STRETCHED"}),
        ("o,5 > o,49", "0,5 > 0,49", {"O_AS_ZERO"}),
        ("0,5 < 0,75", "0,5 < 0,75", set()),  # an answer is left as typed
        ("S = 12 × 7 : 2 = 42 cm²", "S = 12 × 7 : 2 = 42 cm²", set()),  # math signs stay
        (
            "phân số thập phân mẫu số tử số hàng phần mười",
            "phân số thập phân mẫu số tử số hàng phần mười",
            {"KEYWORD_DUMP"},
        ),
    ],
)
def test_the_text_the_loop_reads(raw, text, signals):
    cleaned = clean(raw)
    assert cleaned.text == text and set(cleaned.signals) == signals


def test_a_long_message_keeps_its_end():
    cleaned = clean("con nghĩ " * 60 + "nên đáp án là 0,7")
    assert "LONG" in cleaned.signals and cleaned.text.endswith("đáp án là 0,7") and len(cleaned.text) <= 302


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("ko bít lm j hết", Outcome.HELP_REQUEST),
        ("kbt", Outcome.HELP_REQUEST),
        ("khó wá chán wá", Outcome.NEGATIVE_AFFECT),
        ("hk hiu cô ơi", Outcome.CLARIFY_REQUEST),
        ("phần nguyên phần thập phân dấu phẩy hàng phần mười", Outcome.CLARIFY_REQUEST),
    ],
)
def test_teen_code_and_keyword_heaps_are_read(text, intent):
    assert read_intent(text) == intent


@pytest.mark.parametrize(
    "text",
    [
        "so sánh phần nguyên trước rồi so sánh phần thập phân hàng phần mười",  # a sentence, not a heap
        "đáy nhân chiều cao chia hai",
        "mẫu số và tử số khác nhau thế nào?",  # a question: the RAG answers it
        "phần mười phần trăm 0,5",  # a number: an answer
    ],
)
def test_an_explanation_or_a_question_is_not_a_heap(text):
    assert not keyword_dump(text)


def test_a_repeat_is_the_same_words_as_a_moment_ago():
    assert repeats(
        ["Mình quay lại câu đang làm nhé.  7/10 = ……"], ["Mình quay lại câu đang làm nhé. 7/10 = ……"]
    )
    assert not repeats(["Cô gợi ý nhé."], ["Mình quay lại câu đang làm nhé."])


def test_a_closing_negation_is_a_statement_not_a_question():
    """The retell "bỏ số 0 ở giữa thì không" was parked as a question 200 times in a simulated session."""
    from cavat.modules.assessment.student_intent import asks_question

    assert not asks_question("Bỏ số 0 ở cuối được. bỏ số 0 ở giữa thì không")
    assert not asks_question("con cũng chưa")
    assert asks_question("0,5 có lớn hơn 0,49 không")
    assert asks_question("cái này đúng không")
