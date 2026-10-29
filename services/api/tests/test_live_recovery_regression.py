"""Regressions from a retell conversation: prompt overflow, leaked scaffold and spoken arithmetic."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from cavat.modules.ai_gateway.base import MAX_PROMPT_TOKENS, ModelClass, estimate_prompt_tokens
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.curriculum import verification
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import Awaiting, MessageKind, TeachMessage
from cavat.modules.tutor import brain
from cavat.modules.tutor.prompt_builder import Turn, _prompt_file
from cavat.modules.tutor.reader import Reading, RecordedReader
from cavat.modules.tutor.socratic import acknowledges_correction, conversion_answer_leaked, readiness_only
from test_brain2 import small_index
from test_brain4 import OK
from test_grounded import NOW, loop_at_theory

ASKED = "Con thử giải thích cách chuyển 5/10 sang số thập phân nhé?"
BAD_MATH = "Không sao, 5/10 chia cho 10 cho kết quả 0,5. Con thử viết lại 5/10 thành số thập phân đúng nhé?"
LEAK = (
    "Không sao, mình cùng viết lại 5/10 thành số thập phân nhé: 5/10 = 0,5. "
    "Con thử viết ra kết quả này được không?"
)
SAFE = "Mỗi phần mười ứng với một chữ số sau dấu phẩy. Để viết 5/10, con đặt chữ số nào ở hàng phần mười?"


def row(text):
    return {"message": text, "safety_flag": False, "policy_feedback": ""}


@pytest.mark.parametrize("text", [BAD_MATH, LEAK, "Vậy 5/10 bằng 0,5 đúng không?"])
def test_actual_scaffold_answer_is_protected_even_in_a_confirmation_question(text):
    assert conversion_answer_leaked(text, ASKED)


@pytest.mark.parametrize(
    "text",
    [
        "5/10 chia cho 10 cho kết quả 0,5.",
        "3/100 nhân với 100 được kết quả 0,03.",
        "7 cộng với 2 bằng 8.",
        "8 trừ đi 3 ra kết quả 6.",
    ],
)
def test_false_spoken_operations_are_rejected(text):
    assert brain.math_errors(text)


@pytest.mark.parametrize(
    "text",
    [
        "5/10 chia cho 10 cho kết quả 0,05.",
        "5 chia cho 10 bằng 0,5.",
        "7 cộng với 2 bằng 9.",
        "8 trừ đi 3 ra kết quả 5.",
    ],
)
def test_true_spoken_operations_are_allowed(text):
    assert not brain.math_errors(text)


def test_asking_to_copy_a_given_answer_is_not_a_learning_step():
    assert readiness_only(LEAK)


def test_retell_uses_the_last_spoken_scaffold_without_awarding_retell_evidence():
    provider = FakeChatModel([row(BAD_MATH), row(SAFE), OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop, first = loop_at_theory(None)
    loop.awaiting = Awaiting.RETELL
    loop._ref = None
    loop._prompt = "Từ một phân số thập phân, con chuyển thành số thập phân bằng cách nào?"
    loop._say(NOW, [], [], TeachMessage(MessageKind.FEEDBACK, ASKED, first.node_id, source="LLM"))
    loop._say(NOW, [], [], TeachMessage(MessageKind.FEEDBACK, LEAK, first.node_id, source="LLM"))
    loop._say(
        NOW,
        [],
        [],
        TeachMessage(MessageKind.FEEDBACK, "Cô mừng con quay trở lại!", first.node_id, ref="GREETING_ONLY"),
    )
    loop.go_live(reader=RecordedReader({1: Reading("REPAIR", focus="chưa hiểu")}), speaker=speaker)
    assert loop._pending_question(loop._prompt) == ASKED
    turn = loop.on_student("88", NOW)
    assert turn.messages[-1].text == SAFE and turn.awaiting == Awaiting.RETELL
    assert "WRONG_MATH" in turn.messages[-1].rejected[0]
    assert not any(e.event_type == "RETELL_JUDGED" for e in turn.events)
    assert ASKED in provider.calls[0][1].messages[1].content
    review = next(request for _, request in provider.calls if request.schema_name == "curriculum_check_v2")
    assert json.loads(review.messages[1].content)["duoc_giai_cau_dang_lam"] is False
    assert json.loads(review.messages[1].content)["cau_dang_lam"] == ASKED
    assert all(estimate_prompt_tokens(request) <= MAX_PROMPT_TOKENS for _, request in provider.calls)


def test_mentor_budget_includes_its_full_system_prompt_before_context_is_trimmed():
    pack = brain.BrainPack(
        task="Giảng đúng chỗ vướng bằng một ví dụ, hỏi một bước cụ thể. " * 18,
        question=ASKED,
        student_text="??",
        lesson="Chuyển phân số thập phân thành số thập phân",
        recent=tuple(Turn("tutor" if i % 2 else "student", "Hội thoại gần đây. " * 45) for i in range(6)),
        grounds=("Phần mười có một chữ số sau dấu phẩy. " * 30,) * 3,
        prefer_mentor=True,
    )
    for codes in ((), ("UNSUPPORTED_MEANING", "CHECK: " + "Cần sửa cách giảng. " * 8)):
        request = brain.build_request(
            replace(pack, retry_codes=codes),
            system_suffix=_prompt_file("mentor.v4.md"),
            schema_name="tutor_mentor_turn",
        )
        assert estimate_prompt_tokens(request) <= MAX_PROMPT_TOKENS
        assert ASKED in request.messages[1].content and "??" in request.messages[1].content


def test_reviewer_budget_preserves_the_complete_speech_and_target():
    speech = "Cô giải thích một bước bằng một ví dụ khác. " * 30 + "Sau đó có phát biểu 5/10 ÷ 10 = 0,5."
    request = verification(
        speech,
        question=ASKED,
        scope="Số thập phân",
        references=("Ý tham khảo. " * 50,) * 3,
        recent=("Lời cô trước. " * 50,) * 2,
        student="??",
        task="Hỗ trợ nói lại. " * 60,
    )
    assert estimate_prompt_tokens(request) <= MAX_PROMPT_TOKENS
    data = json.loads(request.messages[1].content)
    assert data["loi_co"] == speech and data["cau_dang_lam"] == ASKED


def test_unavailable_reviewer_does_not_trigger_another_generation_draft():
    provider = FakeChatModel({"writer": [row(SAFE)], "judge": []})
    router = AIRouter(
        chat_provider=provider, chains={ModelClass.TUTOR_REASONING: ("writer",), ModelClass.EVAL_JUDGE: ()}
    )
    speaker = GroundedSpeaker(small_index(), router, allow_knowledge=True)
    spoken = speaker._teacher_say(
        brain.BrainPack(task="Giúp một bước, hỏi ở cuối.", question=ASKED), questions=True
    )
    assert not spoken.text and len(provider.calls) == 1
    assert any(code.startswith("SERVICE_UNAVAILABLE:") for group in spoken.rejected for code in group)
    assert not any(code == "UNSUPPORTED_MEANING" for group in spoken.rejected for code in group)


def test_recovery_feedback_reaches_the_mentor_and_stays_inside_its_budget():
    provider = FakeChatModel([row(SAFE), OK])
    router = AIRouter(
        chat_provider=provider,
        chains={
            ModelClass.TUTOR_MENTOR: ("mentor",),
            ModelClass.TUTOR_REASONING: ("main",),
            ModelClass.EVAL_JUDGE: ("judge",),
        },
    )
    speaker = GroundedSpeaker(small_index(), router, allow_knowledge=True, recovery_codes=("ANSWER_LEAK",))
    spoken = speaker.conversation_reply(
        "??",
        asked=ASKED,
        node=loop_at_theory(None)[0].chapter.nodes[0],
        label="REPAIR",
        focus="chưa hiểu",
        ground="Hàng phần mười đứng sau dấu phẩy.",
        objective_driven=False,
    )
    assert spoken.text == SAFE
    model, request = provider.calls[0]
    assert model == "mentor" and "ANSWER_LEAK" in request.messages[1].content
    assert estimate_prompt_tokens(request) <= MAX_PROMPT_TOKENS


def test_known_wrong_teacher_claim_must_be_corrected_before_another_question():
    corrected = (
        "Cô nói nhầm: mình lấy tử số chia cho mẫu số, không chia cả phân số thêm lần nữa. "
        "Với 5/10, mẫu số là số nào?"
    )
    provider = FakeChatModel([row("Mẫu số của 5/10 là gì?"), row(corrected), OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    spoken = speaker._teacher_say(
        brain.BrainPack(
            task="Giảng một bước rồi hỏi lại.",
            question=ASKED,
            recent=(Turn("tutor", BAD_MATH), Turn("student", "??")),
        ),
        questions=True,
    )
    assert spoken.text == corrected
    assert "MISSING_CORRECTION" in spoken.rejected[0]
    assert "correction" in provider.calls[0][1].json_schema["required"]
    prompt = provider.calls[0][1].messages[1].content
    assert BAD_MATH not in prompt and ASKED in prompt
    assert "chỉ lấy tử số chia cho mẫu số" in prompt


def test_explicit_admission_of_an_arithmetic_mistake_is_a_correction_cue():
    assert acknowledges_correction("Cô xin lỗi, đã tính sai trước. Mình chỉ lấy tử số chia cho mẫu số.")


def test_correction_has_a_small_extra_word_budget_without_removing_mathematical_checks():
    correction = (
        "Cô nói nhầm: không phải lấy tử số chia mẫu số rồi chia lại. "
        "Chỉ chia tử số cho mẫu số một lần để được số thập phân."
    )
    message = (
        "Con, để chuyển 5/10 thành số thập phân, hãy nhớ chia 5 cho 10 rồi viết kết quả. "
        "Thử làm một lần và cho cô biết kết quả phần nguyên và phần thập phân nhé?"
    )
    provider = FakeChatModel([{**row(message), "correction": correction}, OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    spoken = speaker._teacher_say(
        brain.BrainPack(
            task="Giúp một bước rồi hỏi.",
            question=ASKED,
            max_words=40,
            recent=(Turn("tutor", BAD_MATH), Turn("student", "??")),
        ),
        questions=True,
    )
    assert spoken.text == correction + " " + message
    assert 40 < len(spoken.text.split()) <= 65


@pytest.mark.parametrize(
    "available,wait,delay,status",
    [
        (False, 12, 13_000, "retrying"),
        (False, 3600, 2000, "stopped"),
        (True, 3600, 2000, "retrying"),
    ],
)
def test_recovery_follows_provider_capacity_without_blocking_a_working_fallback(
    available, wait, delay, status
):
    from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE
    from cavat.modules.session.api import _track_recovery
    from cavat.modules.session.repository import LifecycleState, NewEvent, SessionState
    from cavat.modules.session.service import Step

    before = SessionState(lifecycle=LifecycleState.ACTIVE, activity={"prompt": ASKED})
    session = SimpleNamespace(state=before, state_version=1, student_id="synthetic", events=[])
    step = Step(
        before,
        [
            NewEvent(
                event_type="TEACH_MESSAGE_SENT",
                payload={
                    "kind": "FEEDBACK",
                    "ref": "MODEL_WAIT",
                    "text": MODEL_WAIT_MESSAGE,
                    "source": "TEMPLATE",
                },
            )
        ],
        {},
    )
    recording = SimpleNamespace(
        has_available_chat=lambda: available,
        calls=[SimpleNamespace(outcome=SimpleNamespace(attempts=[SimpleNamespace(retry_after_s=wait)]))],
    )
    tracked = _track_recovery(session, step, "ANSWER", {"text": "??"}, recording=recording)
    recovery = tracked.state.activity["tutor_recovery"]
    assert (recovery["retry_after_ms"], recovery["status"]) == (delay, status)
    assert tracked.state.activity["prompt"] == ASKED and "tutor_recovery" not in before.activity
