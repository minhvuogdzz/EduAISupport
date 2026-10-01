"""Content checks for lesson.yaml that the schema cannot express (lesson review, 2026-10-01).

They run in CI so a content edit cannot reintroduce answer leaks, misleading hints or blind spots in
the exit assessment.
"""

import re
import unicodedata
from pathlib import Path

import pytest
from cavat.modules.assessment.math_checker import BUG_RULES, check_answer
from cavat.modules.assessment.vi_numbers import extract_numbers, parse_literal
from cavat.modules.content.lesson_package import (
    BooleanAnswer,
    ChoiceAnswer,
    CompareAnswer,
    NumericAnswer,
    OrderAnswer,
    load_lesson_package,
)

LESSON = Path(__file__).resolve().parents[3] / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"
PKG = load_lesson_package(LESSON)
ITEMS = PKG.items


def lower(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def below_h7_texts(item):
    """Everything the tutor may say before the student has answered and before H7 is allowed.

    Verify prompts are left out: they are only asked after a correct answer.
    """
    texts = [item.stem, item.rephrase or ""]
    texts += [h.text for h in item.hints] + [h.text for h in PKG.generic_hints]
    texts += item.worked_solution[:-1]
    if isinstance(item.answer, CompareAnswer):
        for m in PKG.misconceptions:
            texts += [c.format(left=item.answer.left, right=item.answer.right) for c in m.counter_examples]
    else:
        texts += [c for m in PKG.misconceptions for c in m.counter_examples if "{" not in c]
    return [t for t in texts if t]


@pytest.mark.parametrize("item", [i for i in ITEMS if i.leak_patterns], ids=lambda i: i.id)
def test_leak_patterns_have_word_boundaries_and_never_fire_below_h7(item):
    for pattern in item.leak_patterns:
        assert pattern.startswith("\\b"), f"{item.id}: {pattern!r} needs \\b at the start"
        rx = re.compile(pattern)
        for text in below_h7_texts(item):
            assert not rx.search(lower(text)), f"{item.id}: {pattern!r} fires on {text!r}"


@pytest.mark.parametrize(
    "item", [i for i in ITEMS if i.leak_patterns and i.worked_solution], ids=lambda i: i.id
)
def test_leak_patterns_catch_the_stated_answer(item):
    """A pattern that never matches the answer as written in the lesson is useless."""
    answers = [item.worked_solution[-1], item.explanation or ""]
    assert any(re.search(p, lower(a)) for p in item.leak_patterns for a in answers), item.id


def test_common_words_do_not_trigger_name_patterns():
    sentences = ["mình cùng so sánh nhé", "năm nay con học lớp 5", "tuần sau mình học tiếp", "nhà con ở gần"]
    sentences += ["nếu con nghĩ bạn nói sai thì con giải thích nhé", "con làm khá tốt"]
    for item in ITEMS:
        for pattern in item.leak_patterns:
            for s in sentences:
                assert not re.search(pattern, s), f"{item.id}: {pattern!r} fires on {s!r}"


def _pair(item):
    return frozenset({parse_literal(item.answer.left).value, parse_literal(item.answer.right).value})


def test_hard_coded_counter_examples_do_not_reuse_an_item_pair():
    pairs = {_pair(i): i.id for i in ITEMS if isinstance(i.answer, CompareAnswer) and len(_pair(i)) == 2}
    for m in PKG.misconceptions:
        for c in m.counter_examples:
            if "{" in c:
                continue
            values = {n.value for n in extract_numbers(c) if n.form == "decimal"}
            for pair, item_id in pairs.items():
                assert not pair <= values, f"{m.id}: counter-example reuses the numbers of {item_id}: {c!r}"


def test_unit_conversion_counter_examples_stay_within_two_decimals():
    for m in PKG.misconceptions:
        for c in m.counter_examples:
            if "xăng-ti-mét" in c:
                assert all(len(n.frac_part) <= 2 for n in extract_numbers(c)), f"{m.id}: {c!r}"


def test_exit_items_do_not_reuse_a_practice_pair():
    practice = {_pair(i) for i in ITEMS if i.purpose != "EXIT" and isinstance(i.answer, CompareAnswer)}
    for item in ITEMS:
        if item.purpose == "EXIT" and isinstance(item.answer, CompareAnswer):
            assert _pair(item) not in practice, f"{item.id} reuses a practice pair"


def test_exit_covers_every_objective_kc():
    exit_kcs = {kc for i in ITEMS if i.purpose == "EXIT" for kc in i.kc_ids}
    for objective in PKG.objectives:
        assert set(objective.kc_ids) & exit_kcs, f"{objective.id} has no exit item"


def _exit_detects(mis):
    """True when some exit item gives a wrong answer that is evidence of `mis`."""
    for item in (i for i in ITEMS if i.purpose == "EXIT"):
        ans = item.answer
        if isinstance(ans, BooleanAnswer | NumericAnswer) and mis.id in ans.wrong_answers.values():
            return True
        if isinstance(ans, ChoiceAnswer) and any(mis.id in o.misconceptions for o in ans.options):
            return True
        if isinstance(ans, CompareAnswer) and mis.bug_rule in BUG_RULES:
            left, right = parse_literal(ans.left), parse_literal(ans.right)
            predicted = BUG_RULES[mis.bug_rule](left, right)
            result = check_answer(item, predicted, PKG) if predicted else None
            if result and result.misconception_id == mis.id:
                return True
    return False


@pytest.mark.parametrize(
    "mis", [m for m in PKG.misconceptions if m.severity == "CRITICAL"], ids=lambda m: m.id
)
def test_exit_detects_every_critical_misconception(mis):
    assert _exit_detects(mis), f"no exit item tells {mis.id} apart"


def test_exit_has_an_order_item():
    assert any(i.purpose == "EXIT" and isinstance(i.answer, OrderAnswer) for i in ITEMS)


def test_probe_questions_separate_their_two_causes():
    for item in ITEMS:
        if not isinstance(item.answer, ChoiceAnswer):
            continue
        for option in item.answer.options:
            if option.probe is None:
                continue
            probe = option.probe
            assert probe.if_wrong != probe.if_correct
            left, right = parse_literal(probe.left), parse_literal(probe.right)
            assert left.value != right.value
            assert probe.left in probe.prompt and probe.right in probe.prompt
            assert PKG.misconception(probe.if_correct).kc_id != "KC-DEC-CMP"


def test_every_hint_asks_at_most_one_question():
    hints = [(i.id, h.text) for i in ITEMS for h in i.hints]
    hints += [("generic", h.text) for h in PKG.generic_hints]
    for owner, text in hints:
        assert text.count("?") <= 1, f"{owner}: {text!r}"


def test_generic_hints_do_not_assume_equal_integer_parts():
    for h in PKG.generic_hints:
        assert "phần nguyên bằng nhau thì" not in lower(h.text), h.text
