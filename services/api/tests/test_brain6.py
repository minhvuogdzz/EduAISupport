"""Warm acknowledgement must not trigger another lecture or misrepresent a wrong result."""

from cavat.core.pedagogy import Move, Outcome
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext, ValidationCode
from cavat.modules.tutor.validator import validate_message
from test_brain2 import small_index
from test_brain4 import ITEM, OK, PKG, tutor


def test_correct_theory_reply_receives_brief_warm_acknowledgement_without_appended_lecture():
    reply = "Đúng rồi, con phân biệt được hai phần rồi đấy!"
    provider = FakeChatModel([{"message": reply, "safety_flag": False, "policy_feedback": ""}, OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    explanation = "Phần nguyên ở trước dấu phẩy, phần thập phân ở sau dấu phẩy."
    spoken = speaker.bridge(
        "phần nguyên trước dấu phẩy, phần thập phân sau dấu phẩy",
        asked="Hai phần nằm ở đâu?",
        explanation=explanation,
        judged="đúng",
        lead="Đúng ý rồi, con ạ.",
    )
    assert spoken.source == "LLM" and spoken.text == reply
    assert explanation not in spoken.text


def test_correct_theory_reply_without_model_does_not_fall_back_to_repeating_the_whole_lesson():
    speaker = GroundedSpeaker(small_index(), allow_knowledge=True)
    spoken = speaker.bridge(
        "phần nguyên trước dấu phẩy",
        asked="Phần nguyên ở đâu?",
        explanation="Phần nguyên nằm trước dấu phẩy. Phần thập phân nằm sau dấu phẩy.",
        judged="đúng",
        lead="Đúng ý rồi, con ạ.",
    )
    assert spoken.text == "Đúng ý rồi, con ạ." and spoken.source == "TEMPLATE"


def test_encouraging_a_real_attempt_is_allowed_but_false_correctness_and_intelligence_flattery_stay_blocked():
    t = tutor(None)
    ctx = RenderContext(
        decision=PolicyDecision(Move.PROBE),
        item=ITEM,
        package=PKG,
        state=t.state,
        check=CheckResult(Outcome.WRONG),
        student_text="7",
    )
    warm = "Con đã thử rồi, mình xem từng chút nhé. Con đã chọn mẫu số như thế nào?"
    assert validate_message(warm, ctx).ok
    assert (
        ValidationCode.WRONG_PRAISE in validate_message("Đúng rồi! Con chọn mẫu số như thế nào?", ctx).codes
    )
    assert (
        ValidationCode.INTELLIGENCE_PRAISE
        in validate_message("Con thông minh quá! Con chọn mẫu số như thế nào?", ctx).codes
    )
    assert (
        ValidationCode.ANSWER_LEAK
        in validate_message("Không sao đâu, kết quả là 31/10. Con viết lại được không?", ctx).codes
    )


def test_feedback_to_shorten_explanation_is_respected_even_without_a_model():
    from cavat.modules.tutor.reader import Reading, RecordedReader

    t = tutor(RecordedReader({1: Reading("REPAIR", focus="giảng ngắn hơn")}))
    turn = t.on_student("cô nói nhiều quá, nói ngắn thôi", dialogue_version=3)
    assert turn.text.startswith("Ừ, cô nói gọn nhé.")
    assert len(turn.text.split()) <= 45 and "27/10" in turn.text
    assert t.state.attempt_no == 0 and not turn.resolved
