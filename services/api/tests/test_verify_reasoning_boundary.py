"""A correct answer does not authorize the teacher to supply the student's reasoning."""

import json
from dataclasses import replace

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, Move
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.content.lesson_package import NumericAnswer
from cavat.modules.tutor.item_loop import ItemTutor, Phase
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.policy import DEFAULT_CONFIG
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.socratic import verification_reason_leaked
from cavat.modules.tutor.validator import validate_message
from test_brain4 import OK
from test_llm_renderer import PKG, turn

BAD = (
    "Con làm rất tốt, viết 7/10 thành 0,7 vì mẫu 10 cho biết một phần mười là 0,1, "
    "nên 7 phần mười là 0,7. Vì sao con lại nhớ cách này?"
)
GOOD = "Đúng rồi, con viết 0,7. Con giải thích cho cô vì sao con viết như vậy được không?"


@pytest.mark.parametrize(
    "message",
    [
        BAD,
        "Có phải con chia 7 cho 10 để được 0,7 không?",
        "Mẫu số là 10 nên con viết một chữ số sau dấu phẩy. Vì sao con viết 0,7?",
    ],
)
def test_causal_explanation_cannot_be_disguised_as_a_why_question(message):
    assert verification_reason_leaked(message)


@pytest.mark.parametrize(
    "message",
    [GOOD, "Con làm thế nào để ra kết quả đó?", "Vì sao con chọn cách đó?", "Kết quả này do đâu mà con có?"],
)
def test_open_questions_do_not_supply_the_reason(message):
    assert not verification_reason_leaked(message)


@pytest.mark.parametrize("semantic_leak", [False, True])
def test_live_verify_retries_leaked_reason_and_reviews_the_safe_question(semantic_leak):
    item = PKG.item("GP-01").model_copy(
        update={
            "stem": "Viết thành số thập phân: 7/10 = …",
            "answer": NumericAnswer(type="numeric", value="0,7"),
            "explanation": "SECRET-REASON",
            "worked_solution": ["SECRET-WORKED-STEP"],
            "verify_prompt": "Vì sao con viết được số đó?",
        }
    )
    subtle = "Một chữ số sau dấu phẩy ứng với phần mười. Vì sao con viết 0,7?"
    script = (
        [turn(subtle), {**OK, "solution_leaked": True}, turn(GOOD), OK]
        if semantic_leak
        else [turn(BAD), turn(GOOD), OK]
    )
    provider = FakeChatModel(script)
    renderer = LLMRenderer(
        AIRouter(chat_provider=provider, model_only_speech=True),
        TemplateRenderer(),
        validate_message,
        allow_knowledge=True,
    )
    tutor = ItemTutor(
        item,
        PKG,
        ActivityType.GUIDED_PRACTICE,
        renderer,
        validate_message,
        replace(DEFAULT_CONFIG, verify_rate=1.0),
    )
    tutor.start()
    result = tutor.on_student("0,7")
    assert result.text == GOOD and renderer.last_trace.source == "LLM"
    assert result.move == Move.VERIFY and result.phase == Phase.VERIFYING
    assert not any(
        e.type in (EventType.EXPLANATION_SUBMITTED, EventType.ITEM_RESOLVED) for e in result.events
    )
    assert ("UNSUPPORTED_MEANING" if semantic_leak else "REASONING_LEAK") in renderer.last_trace.rejected[0]
    for _, request in provider.calls:
        assert "SECRET-REASON" not in request.messages[1].content
        assert "SECRET-WORKED-STEP" not in request.messages[1].content
    review = json.loads(provider.calls[-1][1].messages[1].content)
    assert review["duoc_giai_cau_dang_lam"] is False
    assert review["gioi_han_goi_y"]["awaiting_student_reasoning"] is True
