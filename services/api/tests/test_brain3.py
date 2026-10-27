"""BRAIN-3: regressions of the owner's conversation, synthetic items, no stored learner data."""

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, Move, Outcome
from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, ModelClass
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter, FallbackReason, RecordingRouter
from cavat.modules.content.lesson_package import BooleanAnswer, KeyFacts, NumericAnswer, OpenAnswer
from cavat.modules.tutor.dialogue import parts_read, relation_step, verbal_verdict
from cavat.modules.tutor.item_loop import ItemTutor, Phase
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message
from test_item_loop import NO_VERIFY, PKG

BASE = PKG.item("GP-01")
RULE = "Đường cao vuông góc với đáy. Tam giác tù có đường cao nằm ngoài tam giác."
PARTS = BASE.model_copy(
    update={
        "id": "SYNTH-PARTS",
        "hints": [],
        "rephrase": None,
        "verify_prompt": None,
        "worked_solution": [],
        "stem": "Phân loại hình 1, 2, 3 và cho biết hình nào có đường cao nằm ngoài tam giác?",
        "answer": OpenAnswer(
            type="open",
            rubric="Hai phần",
            sample_answer="nhọn, vuông, tù; ngoài hình 3",
            facts=KeyFacts(order=["nhọn", "vuông", "tù"], pairs=[("ngoài", "3")]),
        ),
    }
)
FALSE = BASE.model_copy(
    update={
        "id": "SYNTH-BOOLEAN",
        "hints": [],
        "rephrase": None,
        "verify_prompt": None,
        "worked_solution": [],
        "stem": "Đường cao của tam giác luôn nằm bên trong tam giác.",
        "answer": BooleanAnswer(type="boolean", value=False, requires_explanation=False),
        "explanation": RULE,
    }
)


def tutor(item, **kw):
    t = ItemTutor(
        item,
        PKG,
        ActivityType.GUIDED_PRACTICE,
        TemplateRenderer(),
        validate_message,
        NO_VERIFY,
        knowledge=(RULE,),
        **kw,
    )
    t.start()
    return t


@pytest.mark.parametrize(
    ("said", "verdict"),
    [
        ("đường cao của tam giác nằm bên trong", True),
        ("tam giác tù có đường cao nằm ngoài tam giác", False),
        ("à nó nằm ngoài ạ", False),
        ("đường cao không nằm ngoài", True),
        ("đường cao ở trong hay ngoài?", None),
        ("hình như đường cao ở ngoài", None),
        ("con đang ở ngoài sân", None),
        ("đường cao ở trong và ngoài", None),
    ],
)
def test_explicit_counterexample_is_read_without_requiring_the_word_sai(said, verdict):
    assert verbal_verdict(FALSE.stem, said) is verdict


@pytest.mark.parametrize(
    ("stem", "said"),
    [
        ("1,2 lớn hơn 1,1.", "1,1 lớn hơn 1,2"),
        ("Đường cao của tam giác nhọn nằm trong tam giác.", "tam giác tù có đường cao nằm ngoài"),
        ("Đường cao không luôn nằm trong tam giác.", "đường cao nằm ngoài"),
    ],
)
def test_another_condition_or_operand_order_is_never_inferred_as_a_verdict(stem, said):
    assert verbal_verdict(stem, said) is None


def test_correct_counterexample_resolves_without_arguing_or_another_why():
    t = tutor(FALSE, first_on_kc=True)
    t.on_student("Đúng")
    t.on_student("đường cao của tam giác nằm bên trong")
    turn = t.on_student("tam giác tù có đường cao nằm ngoài tam giác")
    assert turn.resolved and turn.move == Move.CONFIRM_ADVANCE
    answers = [e.payload for e in t.events if e.type == EventType.ANSWER_SUBMITTED]
    assert answers[-1]["outcome"] == "CORRECT"
    reasons = [e.payload for e in t.events if e.type == EventType.EXPLANATION_SUBMITTED]
    assert reasons[-1]["reasoning_quality"] >= 0.6


def test_legacy_reading_and_assessment_do_not_use_contextual_inference():
    t = tutor(FALSE)
    t.on_student("tam giác tù có đường cao nằm ngoài tam giác", dialogue_version=1)
    assert t.phase != Phase.RESOLVED
    exam = tutor(FALSE.model_copy(update={"purpose": "EXIT"}))
    assert exam._check("tam giác tù có đường cao nằm ngoài tam giác").outcome != Outcome.CORRECT


def test_parts_accumulate_without_a_wrong_attempt_or_hint_jump():
    t = tutor(PARTS)
    t.last_tutor = "Hình nào có đường cao nằm ngoài tam giác?"
    turn = t.on_student("à vậy thì nó là hình số 3")
    assert turn.move == Move.EXPLAIN and "lần lượt" in turn.text
    assert t.state.unproductive_turns == 0 and not t.state.hint_levels
    final = t.on_student("nhọn, vuông, tù")
    assert final.resolved
    answers = [e.payload["outcome"] for e in t.events if e.type == EventType.ANSWER_SUBMITTED]
    assert answers == ["PARTIAL", "CORRECT"]


def test_retracting_a_part_does_not_glue_it_to_a_later_answer():
    progress = {}
    assert parts_read(PARTS, "hình 3", "hình nào nằm ngoài?", progress).outcome == Outcome.PARTIAL
    assert parts_read(PARTS, "ngoài hình 2", "", progress) is None
    result = parts_read(PARTS, "nhọn, vuông, tù", "", progress)
    assert result.outcome == Outcome.PARTIAL and result.detail["remaining_parts"] == ["pairs:0"]


@pytest.mark.parametrize("said", ["không phải hình 3", "hình như hình 3", "hình 3 à?"])
def test_negated_or_uncertain_parts_are_not_accepted(said):
    assert parts_read(PARTS, said, "hình nào nằm ngoài?", {}) is None


@pytest.mark.parametrize(
    ("question", "said", "knowledge"),
    [
        ("Đường cao vuông góc với cạnh nào?", "vuông góc với đáy", (RULE,)),
        ("Phần nguyên ở bên nào của dấu phẩy?", "bên trái", ("Phần nguyên ở bên trái dấu phẩy.",)),
        ("Mẫu số ở đâu?", "ở dưới gạch ngang", ("Mẫu số ở dưới gạch ngang.",)),
    ],
)
def test_helper_question_is_a_correct_step_in_both_chapters(question, said, knowledge):
    check = relation_step(PARTS, said, question, knowledge)
    assert check.outcome == Outcome.PARTIAL
    assert check.detail["partial_reason"] == "VERBAL_STEP"


def test_helper_step_needs_an_approved_ground_and_cannot_accept_opposite_positions():
    assert relation_step(PARTS, "đáy", "Đường cao vuông góc với cạnh nào?", ()) is None
    assert (
        relation_step(PARTS, "bên phải", "Phần nguyên ở bên nào?", ("Phần nguyên ở bên trái dấu phẩy.",))
        is None
    )


def test_demonstrated_reason_on_same_kc_does_not_prompt_it_again():
    item = BASE.model_copy(update={"answer": NumericAnswer(type="numeric", value="5")})
    t = tutor(item, reason_seen=True, first_on_kc=True, kc_mastery=0.1)
    assert t.on_student("5").resolved
    required = tutor(
        FALSE.model_copy(update={"answer": BooleanAnswer(type="boolean", value=False)}),
        reason_seen=True,
        first_on_kc=True,
    )
    assert required.on_student("Sai").move == Move.VERIFY


def test_overlapping_components_cannot_spend_the_same_remaining_call_twice():
    provider = FakeChatModel([{"ok": True}, {"ok": True}])
    shared = AIRouter(chat_provider=provider, max_calls_per_session=40)
    scoped = shared.with_session_cap(2)
    assert scoped.quota is shared.quota and shared.max_calls_per_session == 40
    router = RecordingRouter(scoped)
    req = ChatRequest(messages=(ChatMessage("user", "test"),))
    assert router.chat(ModelClass.TUTOR_REASONING, req, calls_used=1).calls_made == 1
    second = router.chat(ModelClass.TUTOR_REASONING, req, calls_used=1)
    assert second.fallback_reason == FallbackReason.SESSION_CAP and len(provider.calls) == 1


@pytest.mark.parametrize(
    "text",
    [
        "Trong tam giác tù, đường cao từ đỉnh có góc tù nằm ngoài tam giác.",
        "Nếu có một góc lớn hơn 90°, đường cao từ đỉnh đó sẽ kéo ra ngoài tam giác.",
    ],
)
def test_false_altitude_claim_seen_in_live_eval_is_refused(text):
    from cavat.modules.tutor.brain import math_errors

    assert math_errors(text)


def test_altitude_rule_has_a_coordinate_counterexample_not_a_model_vote():
    # A=(-1,1), B=(0,0), C=(2,0): B is obtuse (BA dot BC = -2).
    # Its opposite side AC has direction (3,-1); perpendicular foot parameter t=4/10 is on AC.
    from fractions import Fraction

    t = Fraction(4, 10)
    assert 0 < t < 1
    foot = (-1 + 3 * t, 1 - t)
    assert foot[0] * 3 - foot[1] == 0  # B-foot perpendicular AC
    from cavat.modules.tutor.brain import math_errors

    assert not math_errors("Trong tam giác tù, đường cao từ đỉnh có góc tù nằm trong tam giác.")


def test_semantic_guard_rejects_false_theory_and_checks_the_rewrite():
    from cavat.modules.tutor.llm_renderer import LLMRenderer

    wrong = "Tam giác tù có cả ba đường cao nằm trong hình. Con thử nghĩ lại nhé?"
    good = "Con hãy thử với tam giác tù: đường cao có thể nằm ngoài hình. Con thấy nhận định còn đúng không?"
    provider = FakeChatModel(
        [
            {"message": wrong, "safety_flag": False, "policy_feedback": ""},
            {"supported": False, "quotes": []},
            {"message": good, "safety_flag": False, "policy_feedback": ""},
            {"supported": True, "quotes": [RULE]},
        ]
    )
    renderer = LLMRenderer(AIRouter(chat_provider=provider), TemplateRenderer(), validate_message)
    t = ItemTutor(
        FALSE, PKG, ActivityType.GUIDED_PRACTICE, renderer, validate_message, NO_VERIFY, knowledge=(RULE,)
    )
    t.start()
    turn = t.on_student("Đúng")
    assert turn.text == good and renderer.last_trace.rejected == (("UNSUPPORTED_MEANING",),)
    assert renderer.calls_used == 4


def test_assessment_key_never_enters_a_prompt_even_with_the_new_guard():
    from cavat.modules.tutor.llm_renderer import LLMRenderer

    provider = FakeChatModel([])
    renderer = LLMRenderer(AIRouter(chat_provider=provider), TemplateRenderer(), validate_message)
    t = ItemTutor(
        FALSE.model_copy(update={"purpose": "EXIT"}),
        PKG,
        ActivityType.EXIT_ASSESSMENT,
        renderer,
        validate_message,
        NO_VERIFY,
    )
    t.start()
    t.on_student("Đúng")
    assert not provider.calls


def test_a_false_universal_cannot_count_as_a_correct_reason():
    assert verbal_verdict(FALSE.stem, "mọi đường cao của tam giác đều nằm ngoài") is None


def test_a_short_position_reply_only_answers_a_position_question():
    from cavat.modules.tutor.dialogue import boolean_read

    assert boolean_read(FALSE, "nó nằm ngoài", PKG, "Đường cao vuông góc với cạnh nào?") is None
    assert boolean_read(FALSE, "nó nằm ngoài", PKG, "Đường cao nằm ở vị trí nào?").outcome == Outcome.CORRECT
