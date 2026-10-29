"""Stronger authors still obey the same question and assistance boundaries."""

import json
from dataclasses import replace

import pytest
from cavat.core.pedagogy import HintLevel, HintTarget, Move
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.author import write_lesson
from cavat.modules.tutor.brain import BrainPack
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext, RenderedMessage
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.socratic import conversion_answer_leaked, readiness_only
from cavat.modules.tutor.validator import validate_message
from test_brain4 import ITEM, OK, PKG, tutor


def output(text):
    return {"message": text, "safety_flag": False, "policy_feedback": ""}


@pytest.mark.parametrize("value", ["0,7", "0,70", "0.7"])
def test_pending_conversion_cannot_be_answered_in_the_explanation(value):
    assert conversion_answer_leaked(
        f"7/10 viết là {value}. Con thử viết 2/10 thành số thập phân nào?",
        "Con viết 7/10 thành số thập phân nào?",
    )


def test_different_worked_example_and_its_unanswered_followup_are_allowed():
    assert not conversion_answer_leaked(
        "Hai phần mười viết là 0,2. Con viết 7/10 thành số thập phân nào?",
        "Con viết 7/10 thành số thập phân nào?",
    )


@pytest.mark.parametrize(
    "question",
    [
        "Con hiểu chưa?",
        "Con có thể thử viết ra chưa?",
        "Con thử được không?",
        "Con còn nhớ một phần mười thì viết thế nào không?",
    ],
)
def test_readiness_question_is_not_a_learning_step(question):
    assert readiness_only("Cô vừa giảng một ý. " + question)


def test_readiness_is_retried_with_a_concrete_step():
    safe = "Phần mười đứng ngay sau dấu phẩy. Con đặt chữ số nào vào hàng phần mười để viết 3/10?"
    provider = FakeChatModel(
        [output("Phần mười đứng ngay sau dấu phẩy. Con có thể thử viết ra chưa?"), output(safe), OK]
    )
    out = write_lesson(
        AIRouter(chat_provider=provider),
        BrainPack(task="Giảng một ý rồi hỏi bước nhỏ", question="3/10"),
        calls_used=0,
        questions="required",
    )
    assert out.text == safe and "MISSING_LEARNING_STEP" in out.rejected[0]
    assert not readiness_only(safe)


def test_standard_short_definition_is_not_mistaken_for_reading_a_script():
    rule = "Một đơn vị chia thành mười phần bằng nhau, mỗi phần là một phần mười."
    speech = rule + " Con đặt chữ số nào ở hàng phần mười để viết 3/10?"
    provider = FakeChatModel([output(speech), OK])
    out = write_lesson(
        AIRouter(chat_provider=provider),
        BrainPack(task="Giảng định nghĩa rồi hỏi một bước", question="3/10", grounds=(rule,)),
        calls_used=0,
        questions="required",
    )
    assert out.text == speech and not out.rejected


def test_deterministic_leak_guard_retries_even_when_a_reviewer_would_accept():
    safe = "Hai phần mười viết là 0,2. Con viết 7/10 thành số thập phân nào?"
    provider = FakeChatModel(
        [
            output("7/10 viết là 0,7. Con thử viết 2/10 thành số thập phân nào?"),
            output(safe),
            OK,
        ]
    )
    out = write_lesson(
        AIRouter(chat_provider=provider),
        BrainPack(task="Giảng rồi hỏi một bước", question="Con viết 7/10 thành số thập phân nào?"),
        calls_used=0,
        questions="required",
    )
    assert out.text == safe and "ANSWER_LEAK" in out.rejected[0]
    assert len(provider.calls) == 3


@pytest.mark.parametrize("move", [Move.EXPLAIN, Move.HINT, Move.WORKED_GUIDANCE])
def test_repair_cannot_end_in_a_statement_even_when_legacy_validator_allows_it(move):
    renderer = LLMRenderer(
        AIRouter(chat_provider=FakeChatModel([]), model_only_speech=True),
        TemplateRenderer(),
        validate_message,
        allow_knowledge=True,
    )
    ctx = RenderContext(
        decision=PolicyDecision(move, reason_codes=("REPAIR",)),
        item=ITEM,
        package=PKG,
        state=tutor(None).state,
        student_text="con chưa hiểu",
    )
    pack = renderer._pack(ctx, RenderedMessage("Một ý tham khảo.", "TEMPLATE"))
    assert "MISSING_QUESTION" in renderer._codes("Phần mười đứng ngay sau dấu phẩy.", ctx, pack)
    resting = replace(ctx, decision=PolicyDecision(move, reason_codes=("DECLINE",)))
    assert "MISSING_QUESTION" not in renderer._codes("Mình nghỉ một lát nhé.", resting, pack)


def test_semantic_reviewer_receives_actual_item_and_server_hint_limit():
    provider = FakeChatModel([OK])
    renderer = LLMRenderer(
        AIRouter(chat_provider=provider, model_only_speech=True),
        TemplateRenderer(),
        validate_message,
        allow_knowledge=True,
    )
    ctx = RenderContext(
        decision=PolicyDecision(Move.HINT, HintLevel.H1, HintTarget.CONCEPT),
        item=ITEM,
        package=PKG,
        state=tutor(None).state,
        student_text="con chưa hiểu",
    )
    pack = renderer._pack(ctx, RenderedMessage("Một ý tham khảo.", "TEMPLATE"))
    assert not renderer._codes("Phần mười là những phần bằng nhau. Con tìm hàng phần mười nào?", ctx, pack)
    case = json.loads(provider.calls[-1][1].messages[1].content)
    assert case["cau_dang_lam"] == ITEM.stem
    assert case["gioi_han_goi_y"] == {"move": "HINT", "hint_level": 1, "may_reveal": False}
    assert ITEM.answer.value not in provider.calls[-1][1].messages[1].content
