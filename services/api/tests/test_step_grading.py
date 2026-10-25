"""REFORM-2: a right step is not a wrong answer, a question is not an explanation, and "không" is not praised.

The owner's live session of 2026-10-25:
- "10 ăn 3" then "3/10" for the cake item (answer 0,3) were graded WRONG and counted as unproductive
  turns, and the third one jumped the ladder to H6/H7;
- "mẫu như nào" and "lý thuyết là gì" got a stock sentence in place of the theory;
- "không" / "ki" to "vì sao" ended with "Đúng rồi! Con đã suy nghĩ và kiểm tra rất cẩn thận".
Offline, on the real chapter."""

from __future__ import annotations

from dataclasses import replace

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, ItemResolution, Move, Outcome
from cavat.modules.assessment.math_checker import CheckResult, check_answer
from cavat.modules.assessment.student_intent import asks_question
from cavat.modules.session import chapter_service
from cavat.modules.tutor.contracts import (
    ItemState,
    PolicyDecision,
    PolicyInput,
    RenderContext,
    ValidationCode,
)
from cavat.modules.tutor.item_loop import HINT_REQUEST_TEXT, ItemTutor, Phase
from cavat.modules.tutor.policy import DEFAULT_CONFIG, ItemFacts, decide
from cavat.modules.tutor.renderer import TemplateRenderer, covering_sentence
from cavat.modules.tutor.validator import validate_message

CHAPTER = chapter_service.chapters()["math-g5-decimals"]
CAKE = CHAPTER.item("TP-TR-01")  # "Lan ăn 3 phần trong 10 phần bằng nhau. Viết số thập phân." -> 0,3
PR01 = CHAPTER.item("TP-PR-01")  # "Viết phân số 9/10 dưới dạng số thập phân."
NO_VERIFY = replace(DEFAULT_CONFIG, verify_rate=0.0)
ALWAYS_VERIFY = replace(DEFAULT_CONFIG, verify_rate=1.0)


def tutor(item, cfg=NO_VERIFY) -> ItemTutor:
    return ItemTutor(
        item,
        CHAPTER.lesson_of(item.id),
        ActivityType.GUIDED_PRACTICE,
        TemplateRenderer(),
        validate_message,
        cfg,
    )


def check(item, text: str) -> CheckResult:
    return check_answer(item, text, CHAPTER.lesson_of(item.id))


def decisions(t: ItemTutor) -> list[dict]:
    return [e.payload for e in t.events if e.type == EventType.POLICY_DECISION]


# --------------------------------------------------------------------------- 2.1 the checker


@pytest.mark.parametrize("said", ["3/10", "ba phần mười là 3/10", "con viết 3/10"])
def test_the_same_value_in_the_other_form_is_partial_not_wrong(said):
    result = check(CAKE, said)
    assert result.outcome == Outcome.PARTIAL
    assert result.detail["partial_reason"] == "EQUIVALENT_FORM"
    assert result.detail["student_value"] == "3/10"


def test_the_asked_form_is_still_correct_and_a_wrong_value_still_wrong():
    assert check(CAKE, "0,3").outcome == Outcome.CORRECT
    assert check(CAKE, "0,03").outcome == Outcome.WRONG


def test_repeating_the_fraction_of_the_stem_is_not_a_step():
    # "Viết phân số 9/10 dưới dạng số thập phân": saying 9/10 back is not progress (it stays wrong)
    assert check(PR01, "9/10").outcome == Outcome.WRONG


def test_a_pronoun_con_does_not_split_a_clause_of_an_open_answer():
    from cavat.modules.assessment.math_checker import _check_facts
    from cavat.modules.content.lesson_package import OpenAnswer

    spec = OpenAnswer.model_validate(
        {"type": "open", "rubric": "", "sample_answer": "x", "facts": {"pairs": [["nhẹ", "C"]]}}
    )
    assert _check_facts(spec, "bao C con thấy là nhẹ nhất").outcome == Outcome.CORRECT
    assert _check_facts(spec, "bao A nhẹ nhất còn bao C nặng nhất").outcome == Outcome.WRONG


# --------------------------------------------------------------------------- 2.1 the policy


def _inp(check_: CheckResult, activity=ActivityType.GUIDED_PRACTICE, **state) -> PolicyInput:
    return PolicyInput(
        item=CAKE,
        state=ItemState(item_id=CAKE.id, activity=activity, **state),
        check=check_,
        trigger="ANSWER",
    )


def test_a_right_step_moves_the_ladder_up_and_is_praised():
    step = CheckResult(Outcome.PARTIAL, detail={"partial_reason": "STEP_CORRECT"})
    d = decide(
        _inp(step, attempt_no=1, hint_levels=[HintLevel.H1], hint_targets=[HintTarget.TASK]),
        ItemFacts(top_hint_level=5),
        NO_VERIFY,
    )
    assert d is not None
    assert (d.move, d.level) == (Move.HINT, HintLevel.H2)
    assert "STEP_PRAISE" in d.reason_codes


def test_a_right_step_never_goes_past_h5():
    step = CheckResult(Outcome.PARTIAL, detail={"partial_reason": "STEP_CORRECT"})
    d = decide(
        _inp(
            step, attempt_no=2, hint_levels=[HintLevel.H4, HintLevel.H5], hint_targets=[HintTarget.STEP] * 2
        ),
        ItemFacts(top_hint_level=5),
        NO_VERIFY,
    )
    assert d is not None and d.level == HintLevel.H5


def test_the_assessment_cap_still_holds_for_a_right_step():
    step = CheckResult(Outcome.PARTIAL, detail={"partial_reason": "STEP_CORRECT"})
    d = decide(
        _inp(
            step,
            activity=ActivityType.EXIT_ASSESSMENT,
            attempt_no=1,
            hint_levels=[HintLevel.H1],
            hint_targets=[HintTarget.TASK],
        ),
        ItemFacts(top_hint_level=5),
        NO_VERIFY,
    )
    assert d is not None
    assert d.level is None or d.level <= DEFAULT_CONFIG.assessment_cap


# --------------------------------------------------------------------------- 2.1 the owner's session


def test_the_cake_session_does_not_jump_to_the_worked_solution():
    t = tutor(CAKE)
    t.start()
    t.on_student("5")  # wrong: "con làm thế nào?"
    t.on_student(HINT_REQUEST_TEXT)  # H1: "chia thành mấy phần bằng nhau, Lan ăn mấy phần?"
    after_h1 = t.state.unproductive_turns
    turn2 = t.on_student("10 ăn 3")
    assert t.state.unproductive_turns == after_h1
    assert turn2.move == Move.HINT
    d2 = decisions(t)[-1]
    assert d2["hint_level"] == 2 and "STEP_PRAISE" in d2["reason_codes"]
    reads = [e.payload for e in t.events if e.type == EventType.MESSAGE_READ]
    assert reads and reads[-1]["label"] == "STEP_ANSWER" and reads[-1]["source"] == "RULE"

    turn3 = t.on_student("3/10")
    assert t.state.unproductive_turns == after_h1
    assert turn3.move == Move.HINT
    assert decisions(t)[-1]["hint_level"] == 3
    assert t.state.max_hint_level < HintLevel.H6
    assert t.on_student("0,3").move in (Move.CONFIRM_ADVANCE, Move.VERIFY)


def test_a_wrong_number_that_is_not_in_the_task_is_still_unproductive():
    t = tutor(CAKE)
    t.start()
    t.on_student("5")
    t.on_student(HINT_REQUEST_TEXT)
    before = t.state.unproductive_turns
    t.on_student("7")
    assert t.state.unproductive_turns == before + 1


# --------------------------------------------------------------------------- 2.2 questions


@pytest.mark.parametrize(
    "said",
    ["mẫu như nào", "nhu nao", "ntn", "ra sao", "viết sao", "viết như nào", "lý thuyết là gì", "là gì"],
)
def test_short_questions_without_a_question_mark_are_questions(said):
    assert asks_question(said)


@pytest.mark.parametrize("said", ["không", "0,3", "con làm xong rồi", "bỏ số 0 ở giữa thì không"])
def test_answers_are_not_questions(said):
    assert not asks_question(said)


def test_a_sentence_with_punctuation_still_covers_the_question():
    evidence = ("Phân số thập phân là phân số có mẫu số 10, 100, 1000. Mẫu, tử số đọc như sau.",)
    assert covering_sentence("mẫu", evidence) is not None
    assert covering_sentence("1000", ("Mẫu số có thể là 10, 100 hoặc 1000. Còn lại thì khác.",)) is not None


def test_a_question_about_the_rule_in_the_why_is_answered_with_the_rule():
    t = tutor(CAKE, ALWAYS_VERIFY)
    t.start()
    t.on_student("0,3")
    assert t.phase == Phase.VERIFYING
    turn = t.on_student("lý thuyết là gì")
    assert turn.move == Move.VERIFY
    assert "10 phần" in turn.text or "ba phần mười" in turn.text.lower()  # the item's approved explanation
    assert turn.text.count("?") == 1


# --------------------------------------------------------------------------- 3.2 no praise, no explanation


@pytest.mark.parametrize("reply", ["không", "ki", "kkk", "con không biết"])
def test_a_child_who_could_not_explain_is_not_praised(reply):
    t = tutor(CAKE, ALWAYS_VERIFY)
    t.start()
    t.on_student("0,3")
    assert t.phase == Phase.VERIFYING
    t.on_student(reply)  # asked once more, or ended
    final = t.on_student(reply) if t.phase != Phase.RESOLVED else None
    last = final.text if final else t.last_tutor
    assert not last.startswith("Đúng rồi") and "suy nghĩ và kiểm tra rất cẩn thận" not in last
    assert t.phase == Phase.RESOLVED
    assert CAKE.explanation in last  # the teacher's approved explanation is said instead
    assert (
        "EXPLAIN_AND_ADVANCE" in decisions(t)[-1]["reason_codes"]
        or "NO_EXPLANATION" in decisions(t)[-1]["reason_codes"]
    )


def test_a_real_explanation_is_still_praised():
    t = tutor(CAKE, ALWAYS_VERIFY)
    t.start()
    t.on_student("0,3")
    turn = t.on_student("vì 3/10 có mẫu số 10 nên phần thập phân có một chữ số")
    assert turn.move == Move.CONFIRM_ADVANCE and turn.text.startswith("Đúng rồi")


def test_the_check_catches_praise_on_explain_and_advance():
    d = PolicyDecision(
        move=Move.CONFIRM_ADVANCE,
        resolution=ItemResolution.SUPPORTED,
        reason_codes=("EXPLAIN_AND_ADVANCE",),
        rule_ids=("R-VERIFY",),
    )
    state = ItemState(item_id=CAKE.id, activity=ActivityType.GUIDED_PRACTICE)
    ctx = RenderContext(decision=d, item=CAKE, package=CHAPTER.lesson_of(CAKE.id), state=state)
    text = "Đúng rồi! Con đã suy nghĩ rất cẩn thận. Mình sang câu tiếp theo nhé."
    assert ValidationCode.WRONG_PRAISE.value in validate_message(text, ctx).codes
