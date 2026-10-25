"""Tests for the deterministic Math checker (T01), run on the items of lesson 1 (lesson.yaml)."""

from pathlib import Path

import pytest
from cavat.core.pedagogy import ErrorClass, Outcome
from cavat.modules.assessment.math_checker import (
    bug_ignore_integer_part,
    bug_ignore_zero_placeholder,
    bug_longer_is_larger,
    bug_shorter_is_larger,
    bug_trailing_zero_larger,
    check_answer,
    classify_intent,
    parse_relation,
    parse_verdict,
    rule_family,
)
from cavat.modules.assessment.vi_numbers import parse_literal
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    CompareAnswer,
    Item,
    NumericAnswer,
    OpenAnswer,
    OrderAnswer,
    load_lesson_package,
)

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"
PKG = load_lesson_package(LESSON)

CORRECT, WRONG, UNPARSEABLE = Outcome.CORRECT, Outcome.WRONG, Outcome.UNPARSEABLE


def check(item_id: str, text: str):
    return check_answer(PKG.item(item_id), text, PKG)


def assert_result(result, outcome, misconception=None):
    assert (result.outcome, result.misconception_id) == (outcome, misconception)


# --------------------------------------------------------------------------- compare


@pytest.mark.parametrize(
    ("item_id", "text", "outcome", "misconception"),
    [
        ("GP-01", "<", CORRECT, None),
        ("GP-01", ">", WRONG, "DEC-M01"),
        ("GP-01", "0,3 > 0,25", CORRECT, None),  # numbers written the other way round
        ("GP-01", "0,25 lớn hơn 0,3", WRONG, "DEC-M01"),
        ("GP-01", "be hon", CORRECT, None),  # typed without diacritics
        ("GP-02", ">", WRONG, "DEC-M02"),
        ("GP-03", "=", WRONG, "DEC-M03"),
        ("GP-04", "<", WRONG, "DEC-M04"),
        ("GP-05", ">", WRONG, None),  # M01 and M05 both predict ">": not distinguishable
    ],
)
def test_compare(item_id, text, outcome, misconception):
    assert_result(check(item_id, text), outcome, misconception)


def test_compare_normalizes_the_relation_to_left_vs_right():
    result = check("GP-01", "0,3 > 0,25")
    assert (result.normalized, result.correct_answer) == ("<", "<")


def test_specific_bug_rule_hides_the_general_one():
    # Reading 0,05 as 0,5 is the same step as comparing "05" with "5": M03 hides M01.
    assert check("GP-03", "=").candidates == [("DEC-M03", 0.8)]


def test_overlapping_predictions_are_not_attributed():
    # 0,50 > 0,5 fits M01 (50 > 5) and M05 (trailing zero) equally: record both, attribute neither.
    result = check("GP-05", ">")
    assert result.misconception_id is None and result.error_class is ErrorClass.CONCEPTUAL
    assert result.candidates == [("DEC-M05", 0.5), ("DEC-M01", 0.5)]
    assert result.detail["ambiguous_misconceptions"] == ["DEC-M05", "DEC-M01"]


@pytest.mark.parametrize(
    ("item_id", "text", "outcome", "misconception"),
    [
        # "bảng hàng" (place-value table) must not be read as "bằng" (=)
        ("GP-01", "Con kẻ bảng hàng thì thấy 0,25 bé hơn 0,3", CORRECT, None),
        ("GP-01", "con ke bang hang thi thay 0,25 be hon 0,3", CORRECT, None),
        # a relation between other numbers is an explanation, not the answer
        ("GP-01", "vì 30 > 25 nên 0,3 > 0,25", CORRECT, None),
        ("GP-01", "0,25 > 0,3 vì 25 > 3", WRONG, "DEC-M01"),
        ("GP-01", "vì 2 < 3", UNPARSEABLE, None),
        # "dấu bé hơn" names the sign to write, whatever number stands before it
        ("GP-01", "con làm bằng cách viết 0,3 thành 0,30, dấu bé hơn", CORRECT, None),
        ("GP-01", "dấu bé", CORRECT, None),
        ("GP-01", "0.25 < 0.3", CORRECT, None),
        ("GP-01", "0,3 lớn hơn", CORRECT, None),
        ("GP-01", "0,3 con nghĩ là lớn hơn", CORRECT, None),
        ("GP-01", "< hay >", UNPARSEABLE, None),  # undecided: ask again
        ("GP-01", "0,25 > 0,3, à không, 0,25 < 0,3", UNPARSEABLE, None),
        ("GP-05", "0.50 > 0.5", WRONG, None),  # "0.50" is the left number; M01/M05 not distinguishable
    ],
)
def test_compare_reads_explanations_and_other_phrasings(item_id, text, outcome, misconception):
    assert_result(check(item_id, text), outcome, misconception)


@pytest.mark.parametrize(
    ("text", "ask", "relation"),
    [
        ("0,3", "larger", "<"),
        ("0,25", "larger", ">"),
        ("0,25", "smaller", "<"),
        ("0,3", "sign", None),  # naming a number does not answer "điền dấu"
        ("lớn hơn 0,25", "sign", "<"),
    ],
)
def test_parse_relation(text, ask, relation):
    assert parse_relation(text, parse_literal("0,25"), parse_literal("0,3"), ask) == relation


# --------------------------------------------------------------------------- bug rules M01–M05


@pytest.mark.parametrize(
    ("rule", "left", "right", "prediction"),
    [
        (bug_longer_is_larger, "0,25", "0,3", ">"),  # applies: 25 > 3
        (bug_longer_is_larger, "2,1", "1,99", ">"),  # integer parts differ: same as the correct answer
        (bug_shorter_is_larger, "0,4", "0,45", ">"),  # applies: fewer digits looks larger
        (bug_shorter_is_larger, "0,25", "0,3", "<"),  # same as the correct answer
        (bug_ignore_zero_placeholder, "0,05", "0,5", "="),  # applies: 0,05 read as 0,5
        (bug_ignore_zero_placeholder, "0,25", "0,3", None),  # no zero right after the comma
        (bug_ignore_integer_part, "2,1", "1,99", "<"),  # applies: 1 < 99
        (bug_ignore_integer_part, "0,25", "0,3", None),  # integer parts are equal
        (bug_trailing_zero_larger, "0,50", "0,5", ">"),  # applies: the extra zero looks larger
        (bug_trailing_zero_larger, "0,25", "0,3", None),  # different values
    ],
)
def test_bug_rule_prediction(rule, left, right, prediction):
    assert rule(parse_literal(left), parse_literal(right)) == prediction


@pytest.mark.parametrize(
    ("item_id", "text", "misconception", "not_diagnosed"),
    [
        ("GP-02", ">", "DEC-M02", "DEC-M01"),  # M01 predicts 0,4 < 0,45 (4 < 45): the correct answer
        ("GP-04", "<", "DEC-M04", "DEC-M01"),  # M01 compares the integer parts first
        ("GP-01", ">", "DEC-M01", "DEC-M02"),  # M02 predicts 0,25 < 0,3: the correct answer
        ("GP-01", "=", None, "DEC-M03"),  # no zero placeholder in 0,25 or 0,3
        ("GP-03", ">", None, "DEC-M03"),  # M03 predicts "=", not ">"
        ("GP-04", "=", None, "DEC-M04"),  # M04 predicts "<", not "="
        ("GP-01", "=", None, "DEC-M05"),  # M05 only concerns equal values
        ("GP-05", "<", "DEC-M02", "DEC-M05"),  # M05 predicts ">", not "<"
    ],
)
def test_bug_rule_does_not_apply(item_id, text, misconception, not_diagnosed):
    result = check(item_id, text)
    assert result.outcome is WRONG
    assert result.misconception_id == misconception
    assert not_diagnosed not in {mid for mid, _ in result.candidates}
    assert result.error_class is (ErrorClass.CONCEPTUAL if misconception else ErrorClass.UNKNOWN)


@pytest.mark.parametrize(
    ("misconception", "family"),
    [
        ("DEC-M01", "longer_is_larger"),
        ("DEC-M02", "shorter_is_larger"),
        ("DEC-M03", "longer_is_larger"),  # a specialization maps to its parent rule
        ("DEC-M04", "ignore_integer_part"),
        ("DEC-M05", "longer_is_larger"),
        ("CALC-SLIP", "CALC-SLIP"),  # not in the package: returned as is
        (None, None),
    ],
)
def test_rule_family(misconception, family):
    assert rule_family(PKG, misconception) == family


# --------------------------------------------------------------------------- order (GP-06)


@pytest.mark.parametrize(
    ("text", "outcome", "misconception"),
    [
        ("0,2; 0,25; 0,3; 0,305", CORRECT, None),
        ("0,2 < 0,25 < 0,3 < 0,305", CORRECT, None),
        ("0,305 > 0,3 > 0,25 > 0,2", CORRECT, None),  # a descending ">" chain states the same order
        ("0,200 < 0,250 < 0,300 < 0,305", CORRECT, None),
        ("0,2; 0,3; 0,25; 0,305", WRONG, "DEC-M01"),  # sorted as 2 < 3 < 25 < 305
        ("0,305; 0,25; 0,2; 0,3", WRONG, "DEC-M02"),  # more decimal digits sorted as smaller
        ("0,3; 0,2; 0,25; 0,305", WRONG, None),
        ("0,2; 0,25; 0,3", UNPARSEABLE, None),  # a number is missing
        ("0,2; 0,25; 0,3; 0,305; 0,4", UNPARSEABLE, None),  # a number not in the list
        ("0,2; 0,2; 0,3; 0,305", UNPARSEABLE, None),
    ],
)
def test_order(text, outcome, misconception):
    assert_result(check("GP-06", text), outcome, misconception)


def test_order_normalizes_to_the_asked_direction():
    assert check("GP-06", "0,305 > 0,3 > 0,25 > 0,2").normalized == "0,2; 0,25; 0,3; 0,305"


def test_order_descending_item():
    item = Item.model_validate(
        {
            "id": "T-DESC",
            "purpose": "PRACTICE",
            "kc_ids": ["KC-DEC-ORDER"],
            "cognitive_level": "B",
            "difficulty": 0.6,
            "stem": "Sắp xếp các số sau theo thứ tự từ lớn đến bé: 0,3; 0,25; 0,305; 0,2",
            "answer": {"type": "order", "numbers": ["0,3", "0,25", "0,305", "0,2"], "direction": "desc"},
        }
    )
    assert check_answer(item, "0,305; 0,3; 0,25; 0,2", PKG).outcome is CORRECT
    assert check_answer(item, "0,2 < 0,25 < 0,3 < 0,305", PKG).outcome is CORRECT
    assert_result(check_answer(item, "0,305; 0,25; 0,3; 0,2", PKG), WRONG, "DEC-M01")


# --------------------------------------------------------------------------- numeric (GP-07)


@pytest.mark.parametrize(
    ("text", "outcome", "misconception"),
    [
        ("6", CORRECT, None),
        ("1", WRONG, "DEC-M01"),  # 0,15 > 0,6 because 15 > 6
        ("x = 6", CORRECT, None),
        ("x bằng 1", WRONG, "DEC-M01"),
        ("vì 0,65 > 0,6 nên x = 6", CORRECT, None),  # the value given to x, not the first number
        ("0,x5 > 0,6 khi x = 6", CORRECT, None),
        ("6 vì 0,65 > 0,6", CORRECT, None),
        ("5", WRONG, None),
        ("x = 5 thì 0,55 < 0,6, x = 6 thì 0,65 > 0,6", UNPARSEABLE, None),  # two values for x
        ("sáu", CORRECT, None),  # GRADE-1: a number in words, said alone
    ],
)
def test_numeric(text, outcome, misconception):
    assert_result(check("GP-07", text), outcome, misconception)


def test_numeric_ambiguous_separator_needs_confirmation():
    result = check("GP-07", "1.250")
    assert result.outcome is Outcome.NEEDS_CONFIRMATION
    assert result.detail == {"interpretation": "1,25"}


def test_numeric_reports_the_values_given_to_the_unknown():
    result = check("GP-07", "x = 5 thì 0,55 < 0,6, x = 6 thì 0,65 > 0,6")
    assert result.detail == {"assigned": ["5", "6"]}


def test_numeric_isomorphic_item():
    assert check("GP-07b", "7").outcome is CORRECT
    assert_result(check("GP-07b", "1"), WRONG, "DEC-M01")


def test_a_decimal_fraction_is_written_as_asked():
    """ "0,475 = ……" asks 475/1000: the same value as 0,475 or reduced to 19/40 is not the answer asked
    for, but it is no wrong answer either: a step (PARTIAL, EQUIVALENT_FORM; REFORM-2, DI-67)."""
    item = PKG.item("GP-07b").model_copy(
        update={"answer": NumericAnswer(type="numeric", value="475/1000", form="fraction")}
    )
    assert check_answer(item, "475/1000", PKG).outcome is CORRECT
    assert check_answer(item, "dạ là 475 / 1000 ạ", PKG).outcome is CORRECT
    for text in ("0,475", "19/40"):
        result = check_answer(item, text, PKG)
        assert result.outcome is Outcome.PARTIAL and result.correct_answer == "475/1000"
        assert result.detail["partial_reason"] == "EQUIVALENT_FORM"
    assert check_answer(item, "47/100", PKG).outcome is WRONG
    item = item.model_copy(update={"answer": NumericAnswer(type="numeric", value="0,49", form="decimal")})
    assert check_answer(item, "0,49", PKG).outcome is CORRECT
    assert check_answer(item, "49/100", PKG).outcome is Outcome.PARTIAL


# --------------------------------------------------------------------------- choice (GP-08, GP-10)


@pytest.mark.parametrize(
    ("item_id", "text", "outcome", "misconception"),
    [
        ("GP-08", "Hoa ạ", CORRECT, None),  # "ạ" is a polite particle, not option A
        ("GP-08", "Lan", WRONG, None),  # two possible causes: the probe decides
        ("GP-08", "Hoa", CORRECT, None),
        ("GP-08", "B ạ", CORRECT, None),
        ("GP-08", "Dạ, B ạ", CORRECT, None),
        ("GP-08", "Con chọn đáp án B", CORRECT, None),
        ("GP-08", "a", WRONG, None),  # a bare "a" is option A
        ("GP-08", "ạ", UNPARSEABLE, None),
        ("GP-10", "gói kẹo A", CORRECT, None),
        ("GP-10", "goi keo a", CORRECT, None),
        ("GP-10", "kẹo B", WRONG, "DEC-M01"),
        ("CC-01", "phần mười", CORRECT, None),
        ("CC-01", "hàng phần trăm", WRONG, None),  # a place-name slip, not M03
        ("CC-01", "hàng đơn vị", WRONG, None),
    ],
)
def test_choice(item_id, text, outcome, misconception):
    assert_result(check(item_id, text), outcome, misconception)


def test_choice_normalizes_to_the_option_id():
    result = check("GP-08", "Hoa ạ")
    assert (result.normalized, result.correct_answer) == ("B", "B")


@pytest.mark.parametrize(
    ("item_id", "text", "outcome"),
    [
        # The comparative the question asks about ("nhanh hơn") tells which named option is the answer.
        ("GP-08", "Hoa chạy nhanh hơn Lan", CORRECT),
        ("GP-10", "Gói kẹo A nặng hơn", CORRECT),
        ("GP-10b", "Chai A nhiều hơn chai B", CORRECT),
        ("EX-03", "Minh cao hơn Nam", CORRECT),
        ("GP-08", "Hoa ạ, vì 9,75 bé hơn 9,8", CORRECT),  # this comparative is about numbers
        # Another comparative ("chậm hơn") or two options without one: ask again, never grade a guess.
        ("GP-08", "Lan chạy chậm hơn Hoa", UNPARSEABLE),
        ("GP-08", "Lan chạy chậm hơn", UNPARSEABLE),
        ("EX-03", "Nam thấp hơn", UNPARSEABLE),
        ("GP-08", "Lan hay Hoa", UNPARSEABLE),
        ("CC-01", "hàng phần mười hay hàng phần trăm", UNPARSEABLE),
    ],
)
def test_choice_with_several_options_named(item_id, text, outcome):
    result = check(item_id, text)
    assert result.outcome is outcome
    assert result.misconception_id is None


# --------------------------------------------------------------------------- boolean (GP-09)


@pytest.mark.parametrize(
    ("item_id", "text", "outcome", "misconception"),
    [
        ("GP-09", "sai", CORRECT, None),
        ("GP-09", "không đúng", CORRECT, None),
        ("GP-09", "đúng", WRONG, "DEC-M01"),
        ("GP-09", "Sai ạ, vì 0,25 < 0,3", CORRECT, None),
        ("GP-09", "bạn An nói chưa chính xác", CORRECT, None),
        ("GP-09", "ko đúng", CORRECT, None),
        ("GP-09", "không sai", WRONG, "DEC-M01"),  # "not wrong" agrees with An
        ("GP-09", "đúng hay sai", UNPARSEABLE, None),
        ("GP-09", "Dạ", UNPARSEABLE, None),  # acknowledges the question, gives no verdict
        ("GP-09", "con dùng bảng hàng", UNPARSEABLE, None),  # "dùng" is not "đúng"
        ("EX-04", "đúng", WRONG, "DEC-M03"),
    ],
)
def test_boolean(item_id, text, outcome, misconception):
    assert_result(check(item_id, text), outcome, misconception)


@pytest.mark.parametrize(
    ("text", "verdict"),
    [
        ("đúng rồi", True),
        ("sai", False),
        ("không đúng", False),
        ("không sai", True),
        ("k đúng", False),
        ("không phải", False),
        ("dạ", True),  # a yes, e.g. to "Có phải con muốn viết 1,25 không?"
        ("có", True),
        ("đúng hay sai", None),
        ("con dùng cách khác", None),
        ("phải so sánh hàng phần mười trước", None),  # an explanation, not a yes
    ],
)
def test_parse_verdict(text, verdict):
    assert parse_verdict(text) is verdict


# --------------------------------------------------------------------------- intents


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("", Outcome.NO_RESPONSE),
        ("   ", Outcome.NO_RESPONSE),
        ("...", Outcome.NO_RESPONSE),
        ("?", Outcome.NO_RESPONSE),
        ("con không biết", Outcome.HELP_REQUEST),
        ("ko biết", Outcome.HELP_REQUEST),
        ("cô gợi ý cho con với", Outcome.HELP_REQUEST),
        ("con không biết là < hay >", Outcome.HELP_REQUEST),
        ("cho con đáp án đi", Outcome.ANSWER_DEMAND),
        ("đáp án là gì vậy cô", Outcome.ANSWER_DEMAND),
        ("0,25 < 0,3 nhưng con không biết vì sao", None),  # an answer, with a doubt
        ("đáp án là 0,25 < 0,3", None),
    ],
)
def test_classify_intent(text, intent):
    assert classify_intent(text) == intent


@pytest.mark.parametrize(
    ("item_id", "text", "intent"),
    [
        ("GP-01", "", Outcome.NO_RESPONSE),
        ("GP-09", "không biết", Outcome.HELP_REQUEST),  # not the verdict "không" (false)
        ("GP-08", "con không biết", Outcome.HELP_REQUEST),
        ("GP-07", "cho con đáp án đi", Outcome.ANSWER_DEMAND),
        ("CC-03", "con không biết", Outcome.HELP_REQUEST),
    ],
)
def test_intent_comes_before_grading(item_id, text, intent):
    result = check(item_id, text)
    assert result.outcome is intent
    assert result.misconception_id is None


# --------------------------------------------------------------------------- every item of the lesson


def canonical_answer(item: Item) -> str:
    """The expected answer as a student would write it, computed without the checker."""
    ans = item.answer
    if isinstance(ans, CompareAnswer):
        left, right = parse_literal(ans.left).value, parse_literal(ans.right).value
        return "<" if left < right else ">" if left > right else "="
    if isinstance(ans, OrderAnswer):
        ordered = sorted(ans.numbers, key=lambda s: parse_literal(s).value, reverse=ans.direction == "desc")
        return "; ".join(ordered)
    if isinstance(ans, NumericAnswer):
        return ans.value
    if isinstance(ans, ChoiceAnswer):
        return next(o.text for o in ans.options if o.correct)
    if isinstance(ans, BooleanAnswer):
        return "đúng" if ans.value else "sai"
    raise TypeError(type(ans).__name__)


def by_id(item: Item) -> str:
    return item.id


GRADABLE = [it for it in PKG.items if not isinstance(it.answer, OpenAnswer)]


@pytest.mark.parametrize("item", GRADABLE, ids=by_id)
def test_every_item_accepts_its_answer(item):
    result = check_answer(item, canonical_answer(item), PKG)
    assert result.outcome is CORRECT
    assert result.error_class is None


@pytest.mark.parametrize("item", [it for it in GRADABLE if isinstance(it.answer, CompareAnswer)], ids=by_id)
def test_every_compare_item_rejects_the_other_signs(item):
    correct = canonical_answer(item)
    for sign in "<>=".replace(correct, ""):
        assert check_answer(item, sign, PKG).outcome is WRONG


@pytest.mark.parametrize("item", [it for it in GRADABLE if isinstance(it.answer, ChoiceAnswer)], ids=by_id)
def test_every_choice_item_accepts_the_option_letter(item):
    correct = next(o for o in item.answer.options if o.correct)
    assert check_answer(item, correct.id, PKG).outcome is CORRECT


@pytest.mark.parametrize("item", [it for it in PKG.items if isinstance(it.answer, OpenAnswer)], ids=by_id)
def test_open_items_go_to_the_llm(item):
    result = check_answer(item, "Vì ở hàng phần mười 6 lớn hơn 5.", PKG)
    assert result.outcome is Outcome.NEEDS_LLM


@pytest.mark.parametrize(
    "text",
    ["😅", "<<<>>>", "0,,5", "1/0", "x =", "9" * 300, "ạạạ", "́", "(B)", "k k k", "dấu", "hơn?", "１２"],
)
def test_unexpected_input_never_raises(text):
    for item in PKG.items:
        assert isinstance(check_answer(item, text, PKG).outcome, Outcome)


def test_wrong_choice_with_probe_waits_for_the_probe():
    result = check("GP-08", "Lan")
    assert result.detail["probe_option"] == "A"
    assert result.misconception_id is None and result.error_class is ErrorClass.UNKNOWN


# --------------------------------------------------------------------------- open answers with facts (DI-48)


def _open(text: str, **facts) -> Outcome:
    from cavat.modules.content.lesson_package import KeyFacts

    spec = OpenAnswer(type="open", rubric="", sample_answer="mẫu", facts=KeyFacts(**facts))
    item = PKG.item("GP-07b").model_copy(update={"answer": spec})
    return check_answer(item, text, PKG).outcome


@pytest.mark.parametrize(
    ("facts", "text", "outcome"),
    [
        ({"phrases": [["đơn vị"]], "numbers": [["4"]]}, "hàng đơn vị, giá trị là 4 ạ", CORRECT),
        ({"phrases": [["đơn vị"]], "numbers": [["4"]]}, "hàng chục, giá trị 40", WRONG),
        ({"reading": "14,205"}, "mười bốn phẩy hai trăm linh năm", CORRECT),
        ({"reading": "5,7"}, "5,7", WRONG),  # the number written back is not read
        ({"reading": "5,7"}, "năm phẩy tám", WRONG),
        ({"numbers": [["2"], ["3"], ["4"], ["5"]], "only_numbers": True}, "x = 2; 3; 4; 5", CORRECT),
        ({"numbers": [["2"], ["3"], ["4"], ["5"]], "only_numbers": True}, "2, 3, 4", WRONG),
        ({"numbers": [["2"], ["3"], ["4"], ["5"]], "only_numbers": True}, "2 3 4 5 6", WRONG),
        ({"relations": ["<", "=", "<", ">"]}, "<, =, <, >", CORRECT),
        ({"relations": [">"]}, "0,8 kg bé hơn 750 g", WRONG),
        ({"order": ["Chi", "An", "Bình"]}, "Chi, An, Bình. Bình cao nhất", CORRECT),
        ({"order": ["Chi", "An", "Bình"]}, "Bình, An, Chi", WRONG),
        ({"pairs": [["nhẹ", "C"], ["nặng", "A"]]}, "nặng nhất là bao A còn nhẹ nhất là bao C", CORRECT),
        ({"pairs": [["nhẹ", "C"], ["nặng", "A"]]}, "bao A nhẹ nhất, bao C nặng nhất", WRONG),
        ({"numbers": [["375", "3,75"]]}, "3,75 dm2", CORRECT),
        ({"phrases": [["đơn vị"]]}, "con nghĩ mãi", UNPARSEABLE),  # nothing the facts can read: asked again
    ],
)
def test_an_open_answer_is_read_against_the_facts_of_its_key(facts, text, outcome):
    assert _open(text, **facts) is outcome


def test_an_open_answer_without_facts_still_needs_a_reader():
    item = PKG.item("GP-07b").model_copy(
        update={"answer": OpenAnswer(type="open", rubric="", sample_answer="x")}
    )
    assert check_answer(item, "gì đó", PKG).outcome is Outcome.NEEDS_LLM


def test_a_pair_may_be_said_with_a_colon():
    assert _open("Nhẹ nhất: bao C. Nặng nhất: bao A.", pairs=[["nhẹ", "C"], ["nặng", "A"]]) is CORRECT


def test_a_pair_said_the_wrong_way_round_is_wrong():
    assert _open("bao A nhẹ nhất còn bao C nặng nhất", pairs=[["nhẹ", "C"], ["nặng", "A"]]) is WRONG


# --------------------------------------------------------------------------- GRADE-1: numbers in words


@pytest.mark.parametrize(
    ("text", "digits"),
    [
        ("không phẩy chín", "0,9"),
        ("0 phẩy 9 ạ", "0,9 ạ"),
        ("ba phẩy không sáu", "3,06"),
        ("hai phẩy bảy mươi lăm", "2,75"),
        ("mười hai", "12"),
        ("con không biết", "con không biết"),  # "không" is "no" here, never 0
        ("năm nay con lớp năm", "năm nay con lớp năm"),  # words around: not a number said alone
    ],
)
def test_a_number_said_in_words_is_read(text, digits):
    from cavat.modules.assessment.vi_words import spoken_to_digits

    assert spoken_to_digits(text) == digits


def test_an_item_asking_for_a_decimal_does_not_take_the_fraction_back():
    from cavat.modules.content.lesson_package import Item

    item = Item.model_validate(
        {
            "id": "X",
            "purpose": "PRACTICE",
            "kc_ids": ["KC"],
            "cognitive_level": "B",
            "difficulty": 0.3,
            "stem": "Viết phân số 9/10 dưới dạng số thập phân.",
            "answer": {"type": "numeric", "value": "0,9"},
        }
    )
    pkg = PKG
    assert check_answer(item, "0,9", pkg).outcome == CORRECT
    assert check_answer(item, "không phẩy chín", pkg).outcome == CORRECT
    assert check_answer(item, "9/10", pkg).outcome == WRONG
