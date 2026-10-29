"""A bounded Gemini teaching intervention, using the real gateway and validators with fake providers."""

from cavat.modules.ai_gateway.base import ModelClass, QuotaExceeded
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter, RecordingRouter
from cavat.modules.tutor import brain
from cavat.modules.tutor.prompt_builder import Turn

MAIN = "qwen/qwen3.8-27b"
MENTOR = "gemini-4-argon"
ANSWER = "Ba phần mười và ba mươi phần trăm biểu thị cùng một lượng: 3/10 = 30/100."


def row(text, feedback=""):
    return {"message": text, "safety_flag": False, "policy_feedback": feedback}


def router(steps, cap=20):
    provider = FakeChatModel(steps)
    return RecordingRouter(
        AIRouter(
            chat_provider=provider,
            max_calls_per_session=cap,
            chains={ModelClass.TUTOR_REASONING: (MAIN,), ModelClass.TUTOR_MENTOR: (MENTOR,)},
        )
    ), provider


def pack(stalled=False):
    return brain.BrainPack(
        task="Giải thích một ví dụ, không hỏi.",
        question="Vì sao 0,3 bằng 0,30?",
        student_text="Con vẫn chưa hiểu" if stalled else "Vì sao vậy?",
        recent=(Turn("student", "Con chưa hiểu"),) if stalled else (),
    )


def check(text):
    return ("COPIES_GROUND",) if text == "Đọc nguyên nguồn" else ("WRONG_MATH",) if "sai" in text else ()


def test_failed_main_delivers_the_verified_mentor_without_an_extra_rewrite():
    r, p = router(
        {
            MAIN: [row("Đọc nguyên nguồn"), row("Đọc nguyên nguồn"), row(ANSWER)],
            MENTOR: [row(ANSWER, "Dùng cùng một lượng rồi đổi cách chia phần.")],
        }
    )
    result = brain.speak(r, pack(), check, calls_used=0)
    assert result.text == ANSWER and result.model == MENTOR and result.calls == 3
    assert [model for model, _ in p.calls] == [MAIN, MAIN, MENTOR]
    prompt = p.calls[-1][1].messages[1].content
    assert "Hỗ trợ sư phạm" in prompt
    assert len([c for c in r.calls if c.model_class == ModelClass.TUTOR_MENTOR]) == 1


def test_mentor_first_answer_does_not_spend_a_main_rewrite():
    r, _ = router({MAIN: [row("sai")], MENTOR: [row(ANSWER)]})
    result = brain.speak(r, pack(True), check, calls_used=0)
    assert result.text == ANSWER and result.model == MENTOR and result.calls == 1


def test_gemini_failure_does_not_suppress_a_working_main_model():
    r, p = router({MAIN: [row(ANSWER)], MENTOR: [QuotaExceeded("quota", model=MENTOR)]})
    result = brain.speak(r, pack(True), check, calls_used=0)
    assert result.text == ANSWER and result.model == MAIN
    assert [model for model, _ in p.calls] == [MENTOR, MAIN]


def test_good_turn_does_not_call_mentor():
    r, p = router({MAIN: [row(ANSWER)], MENTOR: []})
    assert brain.speak(r, pack(), check, calls_used=0).text == ANSWER
    assert [model for model, _ in p.calls] == [MAIN]


def test_mentor_cannot_bypass_answer_guard_or_session_cap():
    r, p = router({MAIN: [row("sai"), row("sai")], MENTOR: [row("sai")]}, cap=3)
    result = brain.speak(r, pack(), check, calls_used=0)
    assert result.text is None and len(p.calls) == 3
    assert all(c in ("COPIES_GROUND", "WRONG_MATH") for codes in result.rejected for c in codes)


def test_disabled_mentor_keeps_old_chain_and_no_extra_calls():
    p = FakeChatModel([row("sai"), row("sai")])
    r = AIRouter(chat_provider=p, chains={ModelClass.TUTOR_REASONING: (MAIN,)})
    assert brain.speak(r, pack(), check, calls_used=0).text is None
    assert len(p.calls) == 2


def test_rag_is_synthesized_and_keeps_attribution_instead_of_extracting_verbatim():
    from cavat.modules.teaching.grounded import GroundedSpeaker
    from test_brain2 import small_index

    source = "Phân số thập phân là phân số có mẫu số là 10, 100, 1000 và các lũy thừa của 10."
    answer = "Con nhìn vào mẫu số nhé: mẫu 10, 100 hay 1000 cho biết đây là phân số thập phân."
    p = FakeChatModel([row(answer), {"supported": True, "quotes": [source]}])
    speaker = GroundedSpeaker(
        small_index(source, "Phân số thập phân"), AIRouter(chat_provider=p), allow_knowledge=True
    )
    turn = speaker.answer("Phân số thập phân là gì?", node_id="eq", pending=None)
    assert turn.kind == "ANSWERED" and turn.spoken.source == "LLM"
    assert turn.spoken.text == answer and source not in turn.spoken.text
    assert turn.spoken.sources and source in p.calls[0][1].messages[1].content


def test_rag_rejects_a_generalization_not_supported_by_the_source():
    from cavat.modules.teaching.grounded import GroundedSpeaker
    from test_brain2 import small_index

    source = (
        "Viết thêm chữ số 0 vào tận cùng bên phải phần thập phân thì giá trị không đổi. Ví dụ 0,3 = 0,30."
    )
    bad = "Phần thập phân chỉ xét các chữ số khác 0."
    good = "Chữ số 0 được thêm ở cuối bên phải nên 0,3 và 0,30 vẫn có cùng giá trị."
    p = FakeChatModel(
        [row(bad), {"supported": False, "quotes": []}, row(good), {"supported": True, "quotes": [source]}]
    )
    speaker = GroundedSpeaker(small_index(source), AIRouter(chat_provider=p), allow_knowledge=True)
    turn = speaker.answer(
        "Vì sao viết thêm chữ số 0 bên phải phần thập phân không đổi giá trị?", node_id="eq", pending=None
    )
    assert turn.kind == "ANSWERED" and turn.spoken.text == good
    assert "UNSUPPORTED_MEANING" in turn.spoken.rejected[0]


def test_gemini_four_uses_compatible_thinking_and_a_reasoning_budget():
    from cavat.modules.ai_gateway.gemini import GeminiChat
    from test_ai_gateway import _FakeGenaiClient, _gemini_answer

    fake = _FakeGenaiClient(_gemini_answer('{"message":"Lời giảng"}'))
    GeminiChat("key", client=fake).chat_with(brain.build_request(pack()), MENTOR)
    config = fake.models.kwargs["config"]
    assert config.thinking_config.thinking_level.value == "LOW"
    assert config.max_output_tokens >= 2048
