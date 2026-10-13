"""MISC-1 (DI-54): the misconceptions a published plan names, recognised in wrong answers. Offline: the
sample chapter's lessons stand in for a published plan, with the teacher's kind of misconceptions."""

from fractions import Fraction

import pytest
from cavat.core.pedagogy import Outcome
from cavat.modules.assessment.math_checker import check_answer
from cavat.modules.assessment.misconception_rules import enrich_lesson, families, wrong_answers
from cavat.modules.assessment.vi_numbers import parse_literal
from cavat.modules.content.lesson_package import Item, Misconception, validate_package
from test_teaching_loop import CHAPTER


def mis(mid, kc, name, description="", severity="NORMAL"):
    return Misconception(id=mid, kc_id=kc, name=name, description=description, severity=severity)


def item(iid, kc, stem, value, answer_type="numeric"):
    return Item.model_validate(
        {
            "id": iid,
            "purpose": "PRACTICE",
            "kc_ids": [kc],
            "cognitive_level": "B",
            "difficulty": 0.4,
            "stem": stem,
            "answer": {"type": answer_type, "value": value},
        }
    )


@pytest.mark.parametrize(
    ("name", "description", "family"),
    [
        ("Bé bỏ số 0 ở giữa (4,05 → 4,5)", "", "ZERO_PLACEHOLDER"),
        ("Bé viết 8/1000 = 0,8", "", "ZERO_PLACEHOLDER"),
        ("Quên chia 2 khi tính diện tích tam giác", "Đáy 8 cm, cao 5 cm: S = 8 × 5 = 40", "FORGOT_HALF"),
        ("Hình thang: nhân hai đáy thay vì cộng", "", "BASES_MULTIPLIED"),
        ("Bé làm tròn “dây chuyền” (3,449 → 3,45 → 3,5)", "", "ROUND_CHAIN"),
        ("Cho rằng “dài hơn thì lớn hơn”", "Chọn 0,125 > 0,5 vì 125 lớn hơn 5", "LONGER_IS_LARGER"),
        ("Bé viết 750 g = 7,5 kg", "", "UNIT_STEP"),
    ],
)
def test_a_misconception_is_read_into_its_family(name, description, family):
    assert family in families(mis("M", "KC-DEC-FRAC", name, description))


def test_a_misconception_without_a_computable_mistake_has_no_family():
    assert families(mis("M", "KC-DEC-FRAC", "Bé không vẽ được đường cao tam giác tù")) == set()
    assert families(mis("M", "KC-DEC-FRAC", "Nhầm tên hàng", "nói 0,03 là “phần ba”")) == set()


def wrongs(stem, value, topic=""):
    found = wrong_answers(item("X", "KC-DEC-FRAC", stem, value), parse_literal(value), topic)
    return {(w.value, w.family) for w in found}


def test_the_wrong_answers_come_from_the_item_numbers():
    assert (Fraction(40), "FORGOT_HALF") in wrongs("Tam giác đáy 8 cm, cao 5 cm: S = …… cm²", "20")
    assert (Fraction(40), "FORGOT_HALF") in wrongs(
        "Đáy 8 cm, cao 5 cm: S = ……", "20", topic="diện tích tam giác"
    )
    trapezoid = wrongs("Hình thang đáy 8 cm và 4 cm, cao 5 cm: S = …… cm²", "30")
    assert {
        (Fraction(60), "FORGOT_HALF"),
        (Fraction(80), "BASES_MULTIPLIED"),
        (Fraction(18), "MISSING_PARENS"),
    } <= (trapezoid)
    assert (Fraction(5), "FORGOT_DOUBLE") in wrongs(
        "Tam giác có diện tích 60 cm², đáy 12 cm. Tính chiều cao.", "10"
    )
    assert (parse_literal("3,5").value, "UNIT_STEP") in wrongs("3 m 5 cm = …… m", "3,05")
    assert (parse_literal("7,5").value, "UNIT_STEP") in wrongs("750 g = …… kg", "0,75")
    assert (parse_literal("9,3").value, "AREA_AS_LENGTH") in wrongs("9 dm² 3 cm² = …… dm²", "9,03")
    assert (parse_literal("3,5").value, "ROUND_CHAIN") in wrongs("3,449 ≈ …… (hàng phần mười)", "3,4")
    assert (parse_literal("9,1").value, "ROUND_CARRY") in wrongs("9,96 ≈ …… (hàng phần mười)", "10,0")
    assert (parse_literal("5,2").value, "ROUND_LOOK") in wrongs("5,261 ≈ …… (hàng phần mười)", "5,3")


def test_a_compound_measure_is_not_multiplied_by_ten():
    assert all(
        f != "UNIT_STEP" or v == parse_literal("27,67").value
        for v, f in wrongs("27 km 67 m = …… km", "27,067")
    )


def published_lesson():
    """The concept lesson as a published plan has it: the teacher's misconceptions, no wrong answers."""
    pkg = CHAPTER.lessons["math-g5-dec-concept"]
    teacher = [
        mis("T01-M1", "KC-DEC-FRAC", "Bé viết 8/1000 = 0,8"),
        mis("T02-M1", "KC-DEC-CONCEPT", "Bé đọc 3,05 thành “ba phẩy năm”"),
        mis("L1", "KC-DEC-CONCEPT", "Đọc/viết sai chữ số 0 ngay sau dấu phẩy", severity="CRITICAL"),
        mis("T03-M1", "KC-DEC-PLACE-LATER", "Bé bỏ số 0 ở giữa (4,05 → 4,5)"),
    ]
    teacher = [m for m in teacher if m.kc_id in {k.id for k in pkg.kcs}]
    items = [
        item("P1", "KC-DEC-FRAC", "Viết thành số thập phân: 8/1000 = ……", "0,008"),
        item("P2", "KC-DEC-CONCEPT", "Gồm 12 đơn vị và 5 phần trăm: ……", "12,05"),
        item("P3", "KC-DEC-CONCEPT", "Gồm 3 đơn vị và 7 phần mười: ……", "3,7"),
    ]
    return pkg.model_copy(update={"misconceptions": teacher, "items": items})


def test_each_wrong_answer_names_a_misconception_of_its_period_a_critical_one_first():
    enriched = enrich_lesson(published_lesson(), CHAPTER)
    assert [p for p in validate_package(enriched) if "misconception" in p] == []
    assert {it.id: it.answer.wrong_answers for it in enriched.items} == {
        "P1": {"0,8": "T01-M1"},
        "P2": {"12,5": "L1"},  # its own period, the critical one
        "P3": {},  # no zero after the comma, and no "quên dấu phẩy" in this lesson
    }


def test_the_checker_now_recognises_the_teacher_s_misconception():
    enriched = enrich_lesson(published_lesson(), CHAPTER)
    p2 = next(it for it in enriched.items if it.id == "P2")
    got = check_answer(p2, "12,5", enriched)
    assert got.outcome == Outcome.WRONG and got.misconception_id == "L1"
    assert check_answer(p2, "12,05", enriched).outcome == Outcome.CORRECT


def test_teacher_written_wrong_answers_are_kept():
    pkg = published_lesson()
    own = pkg.items[1].model_copy(
        update={"answer": pkg.items[1].answer.model_copy(update={"wrong_answers": {"1205": "T02-M1"}})}
    )
    pkg = pkg.model_copy(update={"items": [pkg.items[0], own, pkg.items[2]]})
    enriched = enrich_lesson(pkg, CHAPTER)
    assert enriched.items[1].answer.wrong_answers == {"1205": "T02-M1"}


def test_a_misconception_of_a_later_period_is_never_given_to_an_earlier_item():
    pkg = published_lesson().model_copy(
        update={"misconceptions": [mis("T02-M1", "KC-DEC-CONCEPT", "Bé đọc 3,05 thành “ba phẩy năm”")]}
    )
    enriched = enrich_lesson(pkg, CHAPTER)
    assert enriched.items[0].answer.wrong_answers == {}  # P1 is on KC-DEC-FRAC, before KC-DEC-CONCEPT


def test_compare_items_get_the_bug_rule_of_the_teacher_s_misconception():
    pkg = CHAPTER.lessons["math-g5-dec-compare"]
    teacher = [
        mis("T04-M1", "KC-DEC-CMP", "Bé nói “0,125 > 0,5 vì 125 > 5”"),
        mis("T04-M2", "KC-DEC-CMP", "Bé so sánh sai phần nguyên"),
    ]
    items = [it for it in pkg.items if it.answer.type in ("compare", "order")]
    enriched = enrich_lesson(pkg.model_copy(update={"misconceptions": teacher, "items": items}), CHAPTER)
    assert {m.id: m.bug_rule for m in enriched.misconceptions} == {
        "T04-M1": "longer_is_larger",
        "T04-M2": "ignore_integer_part",
    }
