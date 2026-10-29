"""Contextual youth language must not become assent, a failed answer, or learning evidence."""

import json

import pytest
from cavat.core.events import EventType
from cavat.modules.ai_gateway.base import ModelClass, ModelUnavailable, QuotaExceeded
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.tutor.conversation import conversation_signal
from cavat.modules.tutor.reader import LiveReader, ModelReader
from test_brain2 import small_index
from test_brain4 import OK, tutor
from test_grounded import NOW, loop_at_theory


@pytest.mark.parametrize("text", ["hahaha", "hihi", "😂🤣", "😅"])
def test_plain_reaction_is_never_assent(text):
    assert conversation_signal(text, "Mình thử bài này nhé?").label == "REACTION"
    assert conversation_signal(text + " con viết 31/10", "Con viết bao nhiêu?") is None


@pytest.mark.parametrize(
    "said,label,focus",
    [
        ("kkk e khum hỉu", "REPAIR", "cần giảng lại bằng cách đơn giản"),
        ("ok nhưng e vẫn ko bít lm", "REPAIR", "chưa hiểu cách làm"),
        ("ảo ma quá cô", "REACTION", "bày tỏ ngạc nhiên, chưa là đồng ý"),
        ("chán vãi, dài quá cô", "REACTION", "con thấy bài giảng dài và chán"),
        ("haha e nghĩ 31/10", "PASS", "con đưa đáp án Toán"),
    ],
)
def test_listener_sees_raw_and_normalized_words_in_context(said, label, focus):
    p = FakeChatModel([{"label": label, "focus": focus, "answer": "31/10" if label == "PASS" else ""}])
    reader = LiveReader(ModelReader(AIRouter(chat_provider=p)), semantic=True)
    got = reader.read_dialogue(
        stem="Viết 3,1 thành phân số thập phân", last_tutor="Con thử viết nhé?", said=said, turn=1
    )
    assert got.label == label
    request = p.calls[0][1]
    context = json.loads(request.messages[1].content)
    assert context["con_vua_noi"] == said
    assert context["co_vua_noi"] == "Con thử viết nhé?"
    assert "ban_ho_tro_doc_teencode" in context
    if "ko " in said:
        assert "không" in context["ban_ho_tro_doc_teencode"]


def test_reaction_generates_contextual_reply_without_repeating_check_or_changing_progress():
    p = FakeChatModel(
        [
            {
                "message": (
                    "Mình quay lại bài nhé. "
                    "Bốn phần trong một trăm phần bằng nhau viết thành phân số nào con?"
                ),
                "safety_flag": False,
                "policy_feedback": "",
            },
            OK,
        ]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=LiveReader(None, semantic=True), speaker=speaker)
    turn = loop.on_student("hahaha", NOW)
    assert turn.messages[-1].source == "LLM" and not turn.messages[-1].text.endswith(first.prompt)
    assert (turn.awaiting, turn.node_id) == (first.awaiting, first.node_id)
    assert turn.prompt != first.prompt
    assert not any(
        e.event_type in {EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED, EventType.NODE_DECISION}
        for e in turn.events
    )
    assert json.loads(p.calls[0][1].messages[1].content)["can_quay_lai_bai"] is True


def test_item_reaction_does_not_add_a_wrong_attempt_or_a_hint():
    t = tutor(LiveReader(None, semantic=True))
    before = t.state.attempt_no, t.state.max_hint_level
    turn = t.on_student("hahaha", dialogue_version=3)
    assert (t.state.attempt_no, t.state.max_hint_level) == before
    assert not turn.resolved
    assert any("REACTION" in e.payload.get("reason_codes", ()) for e in turn.events)
    assert not any(e.type == EventType.ANSWER_SUBMITTED for e in turn.events)


@pytest.mark.parametrize("error", [QuotaExceeded("limited"), ModelUnavailable("timeout")])
def test_rate_limit_or_timeout_moves_on_and_is_remembered_across_roles(error):
    p = FakeChatModel({"bad": [error], "good": [{"message": "được"}, {"message": "lượt sau"}]})
    r = AIRouter(
        chat_provider=p,
        chains={ModelClass.TUTOR_REASONING: ("bad", "good"), ModelClass.EVAL_JUDGE: ("bad", "good")},
    )
    from cavat.modules.tutor import brain

    request = brain.build_request(brain.BrainPack(task="Nói gọn", question="Số thập phân"))
    first = r.chat(ModelClass.TUTOR_REASONING, request, calls_used=0)
    second = r.chat(ModelClass.EVAL_JUDGE, request, calls_used=first.calls_made)
    assert first.result.model == second.result.model == "good"
    assert second.attempts[0].sent is False
    assert [model for model, _ in p.calls] == ["bad", "good", "good"]


@pytest.mark.parametrize("said,label", [("kkk", "REACTION"), ("khum hỉu", "REPAIR"), ("ảo ma", "REACTION")])
def test_short_language_reaches_semantics_before_gibberish_or_wrong_answer(said, label):
    provider = FakeChatModel([{"label": label, "focus": "phản ứng theo ngữ cảnh", "answer": ""}])
    t = tutor(LiveReader(ModelReader(AIRouter(chat_provider=provider)), semantic=True))
    turn = t.on_student(said, dialogue_version=3)
    assert provider.calls[0][1].schema_name == "dialogue_listen_v6"
    assert t.state.attempt_no == 0 and not turn.resolved
    assert any(e.type == EventType.MESSAGE_READ and e.payload["label"] == label for e in turn.events)
    assert not any(e.type == EventType.ANSWER_SUBMITTED for e in turn.events)


def test_clear_numeric_submission_keeps_deterministic_grading_without_listener():
    provider = FakeChatModel([])
    t = tutor(LiveReader(ModelReader(AIRouter(chat_provider=provider)), semantic=True))
    turn = t.on_student("31/10", dialogue_version=3)
    assert not provider.calls
    assert any(e.type == EventType.ANSWER_SUBMITTED for e in turn.events)


def test_unavailable_listener_does_not_assume_help_or_grade_unknown_language():
    provider = FakeChatModel([QuotaExceeded("limited")])
    router = AIRouter(chat_provider=provider, chains={ModelClass.INTENT_AGENT: ("limited",)})
    t = tutor(LiveReader(ModelReader(router), semantic=True))
    turn = t.on_student("thui e nghỉ xíu nha", dialogue_version=3)
    assert not turn.resolved and t.state.attempt_no == 0
    assert any(
        e.type == EventType.MESSAGE_READ and e.payload["label"] == "AMBIGUOUS_REPLY" for e in turn.events
    )
    assert not any(e.type == EventType.ANSWER_SUBMITTED for e in turn.events)


def test_semantic_repair_invokes_mentor_and_asks_a_smaller_concrete_question():
    from cavat.modules.ai_gateway.router import RecordingRouter
    from cavat.modules.tutor.reader import Reading, RecordedReader

    said = (
        "Mình lấy một chiếc bánh chia thành 10 phần bằng nhau, mỗi phần là một phần mười chiếc bánh. "
        "Ba phần mười viết thành số thập phân nào?"
    )
    provider = FakeChatModel(
        {
            "main": [{"message": said, "safety_flag": False, "policy_feedback": ""}],
            "mentor": [{"message": said, "safety_flag": False, "policy_feedback": "Chỉ một ý rõ."}],
            "judge": [OK, OK],
        },
        max_prompt_tokens=5000,  # Gemini accepts the extra mentor system prompt.
    )
    router = RecordingRouter(
        AIRouter(
            chat_provider=provider,
            chains={
                ModelClass.TUTOR_REASONING: ("main",),
                ModelClass.TUTOR_MENTOR: ("mentor",),
                ModelClass.EVAL_JUDGE: ("judge",),
            },
        )
    )
    speaker = GroundedSpeaker(small_index(), router, allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=RecordedReader({1: Reading("REPAIR", focus="chưa hiểu")}), speaker=speaker)
    turn = loop.on_student("khum hỉu cô ui", NOW)
    assert provider.calls[0][0] == "mentor"
    assert turn.messages[-1].source == "LLM"
    assert not turn.messages[-1].text.endswith(first.prompt)
    assert turn.prompt == "Ba phần mười viết thành số thập phân nào?"
