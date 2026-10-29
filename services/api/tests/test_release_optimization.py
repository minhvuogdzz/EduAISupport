"""Release regressions: explanatory turns and provider output integrity."""

from dataclasses import replace

import httpx
import pytest
from cavat.core.pedagogy import Move
from cavat.modules.ai_gateway.base import ChatMessage, ChatRequest, InvalidModelOutput
from cavat.modules.ai_gateway.groq import GroqClient
from cavat.modules.tutor import brain
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext, ValidationCode
from cavat.modules.tutor.validator import validate_message
from test_brain4 import ITEM, PKG, tutor


def test_explanation_can_end_without_question_but_practice_still_requires_one():
    t = tutor(None)
    t.state.dialogue_version = 3
    ctx = RenderContext(decision=PolicyDecision(Move.EXPLAIN), item=ITEM, package=PKG, state=t.state)
    text = "Mẫu số cho biết một đơn vị được chia thành bao nhiêu phần bằng nhau."
    assert ValidationCode.MISSING_QUESTION not in validate_message(text, ctx).codes
    old = replace(ctx, state=replace(t.state, dialogue_version=1))
    assert ValidationCode.MISSING_QUESTION in validate_message(text, old).codes
    practice = replace(ctx, decision=PolicyDecision(Move.HINT))
    assert ValidationCode.MISSING_QUESTION in validate_message(text, practice).codes


@pytest.mark.parametrize(
    "reason,content",
    [
        ("length", "Câu chưa xong"),
        ("tool_calls", ""),
        ("stop", "<think>private reasoning</think>Câu trả lời"),
        ("stop", 123),
    ],
)
def test_incomplete_or_reasoning_content_never_reaches_student(reason, content):
    client = GroqClient(
        "test",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200, json={"choices": [{"message": {"content": content}, "finish_reason": reason}]}
            )
        ),
    )
    try:
        with pytest.raises(InvalidModelOutput):
            client.chat(ChatRequest(messages=(ChatMessage("user", "test"),)), "openai/gpt-oss-120b")
    finally:
        client.close()


def test_recent_explanation_is_not_cut_mid_step_when_budget_allows():
    explanation = "Cô chia mỗi đơn vị thành mười phần bằng nhau. " * 7 + "Bước cuối: giữ nguyên mẫu số mười."
    request = brain.build_request(
        brain.BrainPack(
            task="Giải thích bước cuối", question="Phân số", recent=(brain.Turn("tutor", explanation),)
        )
    )
    assert "Bước cuối: giữ nguyên mẫu số mười." in request.messages[1].content
