"""FIX-2: no praise of a wrong answer, and the counterexamples of the teacher's documents reach the child.

Found while looking for the generic phrases ("câu dự phòng") of the simulated sessions:
- R-STRONG-PRIOR asks "vì sao" in place of a light hint after a WRONG answer, and every "vì sao" prompt
  opened with "Đúng rồi!" (294/294 items of the published plans), unseen by the validator;
- no counterexample of the published plans ended with a question (0/848 passed the check), so every
  COGNITIVE_CONFLICT fell back to "đọc lại đề bài thật chậm…".
Offline, on the chapter whose content is in the repo."""

from __future__ import annotations

from dataclasses import replace

from cavat.core.pedagogy import ActivityType, ErrorClass, HintLevel, HintTarget, Move, Outcome
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.session import chapter_service
from cavat.modules.tutor.contracts import (
    ItemState,
    PolicyDecision,
    PolicyInput,
    RenderContext,
    StudentSnapshot,
    ValidationCode,
)
from cavat.modules.tutor.policy import ItemFacts, decide
from cavat.modules.tutor.renderer import TemplateRenderer, counter_example
from cavat.modules.tutor.validator import validate_message

CHAPTER = chapter_service.chapters()["math-g5-decimals"]
ITEM = CHAPTER.item("TP-PR-01")  # "Viết phân số 9/10 dưới dạng số thập phân."
PACKAGE = CHAPTER.lesson_of(ITEM.id)
STRONG = StudentSnapshot(
    kc_mastery={k: 0.9 for k in ITEM.kc_ids}, kc_confidence={k: 0.8 for k in ITEM.kc_ids}
)


def ctx(decision: PolicyDecision, package=PACKAGE, said: str = "0,8") -> RenderContext:
    state = ItemState(item_id=ITEM.id, activity=ActivityType.GUIDED_PRACTICE, attempt_no=1)
    return RenderContext(decision=decision, item=ITEM, package=package, state=state, student_text=said)


def test_a_strong_student_who_slips_is_asked_how_not_praised():
    state = ItemState(item_id=ITEM.id, activity=ActivityType.GUIDED_PRACTICE, attempt_no=1)
    slip = CheckResult(Outcome.WRONG, error_class=ErrorClass.CALCULATION)
    inp = PolicyInput(item=ITEM, state=state, check=slip, trigger="ANSWER", snapshot=STRONG)
    d = decide(inp, ItemFacts(kc_ids=tuple(ITEM.kc_ids)))
    assert d.move == Move.VERIFY and "VERIFY_BEFORE_HINT" in d.reason_codes
    msg = TemplateRenderer().render(ctx(d))
    assert not msg.text.startswith("Đúng rồi") and "làm thế nào" in msg.text
    assert msg.source == "TEMPLATE" and validate_message(msg.text, ctx(d)).ok


def test_the_check_refuses_praise_on_a_turn_after_a_wrong_answer():
    hint = PolicyDecision(move=Move.HINT, level=HintLevel.H1, target=HintTarget.STEP)
    text = "Đúng rồi! Con nhìn lại mẫu số của phân số nhé?"
    assert ValidationCode.WRONG_PRAISE.value in validate_message(text, ctx(hint)).codes
    before_hint = PolicyDecision(move=Move.VERIFY, reason_codes=("SLIP", "VERIFY_BEFORE_HINT"))
    assert ValidationCode.WRONG_PRAISE.value in validate_message(text, ctx(before_hint)).codes
    # after a right answer the praise is the point; a step right after a hint may be told so (R-DEESCALATE)
    verify = PolicyDecision(move=Move.VERIFY, reason_codes=("CORRECT", "VERIFY_SAMPLED"))
    fading = replace(hint, reason_codes=("STEP_CORRECT_AFTER_HINT", "FADING"))
    for d in (verify, fading):
        assert ValidationCode.WRONG_PRAISE.value not in validate_message(text, ctx(d)).codes


def test_a_counterexample_without_a_question_gets_the_approved_invitation():
    [mis] = [m for m in PACKAGE.misconceptions if m.id == "FRAC-M01"]
    stated = ["Nếu 7/100 viết thành 0,7 thì 7/10 cũng viết thành 0,7."]  # states the case, asks nothing
    package = PACKAGE.model_copy(
        update={
            "misconceptions": [
                m.model_copy(update={"counter_examples": stated}) if m.id == mis.id else m
                for m in PACKAGE.misconceptions
            ]
        }
    )
    assert counter_example(ITEM, package, mis.id) is not None
    d = PolicyDecision(
        move=Move.COGNITIVE_CONFLICT, level=HintLevel.H2, target=HintTarget.CONCEPT, misconception_id=mis.id
    )
    msg = TemplateRenderer().render(ctx(d, package))
    assert msg.text.endswith("Con làm thử giúp cô được không?") and msg.source == "TEMPLATE"
    assert validate_message(msg.text, ctx(d, package)).ok
    # a counterexample that already asks is left as it is
    asked = TemplateRenderer().render(ctx(d)).text
    assert asked == counter_example(ITEM, PACKAGE, mis.id)[0]
