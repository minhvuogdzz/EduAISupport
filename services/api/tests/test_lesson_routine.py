"""The teaching routine: orient first, recall the relevant theory after errors, stay in the lesson."""

import json

from cavat.core.events import EventType
from cavat.core.pedagogy import HintLevel, HintTarget, Move, Outcome
from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.assessment.math_checker import CheckResult
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import TeachingLoop
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext, RenderedMessage
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.reader import LiveReader, Reading, RecordedReader
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message
from test_brain2 import small_index
from test_brain4 import ITEM, OK, PKG, tutor
from test_goal_driven_teaching import ENTRY_OK, opening_output
from test_grounded import CHAPTER, NOW, loop_at_theory

QUESTION = "Bảy phần mười viết thành số thập phân nào?"
OPENING = "Ví dụ ba phần mười viết là 0,3. " + QUESTION


def row(text):
    return {"message": text, "safety_flag": False, "policy_feedback": ""}


def test_opening_greets_orients_then_examples_without_claiming_unrecorded_learning():
    p = FakeChatModel([opening_output(OPENING), ENTRY_OK])
    speaker = GroundedSpeaker(
        small_index(), AIRouter(chat_provider=p), allow_knowledge=True, student_name="Hải"
    )
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    turn = loop.start(NOW)
    assert turn.messages[0].text.startswith("Cô chào Hải!")
    body = turn.messages[-1].text
    assert body.index("nhớ lại") < body.index("Hôm nay") < body.index("Ví dụ")
    case = json.loads(p.calls[0][1].messages[1].content)
    assert "MỞ BUỔI" in case["muc_tieu_va_viec_can_lam"]
    assert "không có dữ liệu" in case["muc_tieu_va_viec_can_lam"]
    restored = TeachingLoop.resume(CHAPTER, "synthetic", [], loop.events)
    assert restored._prompt == QUESTION
    assert sum("Cô chào Hải!" in e.payload.get("text", "") for e in restored.events) == 1


def test_wrong_theory_answer_gets_relevant_recall_before_help_without_a_grade():
    reminder = (
        "Hàng phần mười là hàng đầu tiên sau dấu phẩy. Bảy phần mười đặt chữ số 7 ở hàng này, viết là 0,7. "
        "Con thử viết sáu phần mười thành số thập phân nào?"
    )
    p = FakeChatModel(
        [opening_output(OPENING), ENTRY_OK, {"answered": False, "quote": ""}, row(reminder), OK]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    first = loop.start(NOW)
    loop.go_live(reader=RecordedReader({1: Reading("PASS")}), speaker=speaker)
    turn = loop.on_student("0,9", NOW)
    assert reminder in turn.messages[-1].text and turn.messages[-1].source == "LLM"
    case = json.loads(p.calls[-2][1].messages[1].content)
    assert "nhắc MỘT ý lý thuyết liên quan trước" in case["muc_tieu_va_viec_can_lam"]
    assert turn.node_id == first.node_id and turn.awaiting == first.awaiting
    assert not any(e.event_type in (EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED) for e in turn.events)


def test_wrong_practice_reply_requests_relevant_theory_without_giving_the_answer():
    renderer = LLMRenderer(
        AIRouter(chat_provider=FakeChatModel([])), TemplateRenderer(), validate_message, allow_knowledge=True
    )
    ctx = RenderContext(
        decision=PolicyDecision(Move.HINT, HintLevel.H1, HintTarget.CONCEPT),
        item=ITEM,
        package=PKG,
        state=tutor(None).state,
        student_text="3/10",
        check=CheckResult(Outcome.WRONG),
    )
    pack = renderer._pack(ctx, RenderedMessage("Mình xem lại phần mười nhé.", "TEMPLATE"))
    assert "trước hết nhắc MỘT ý lý thuyết" in pack.task
    assert not pack.answer


def test_gossip_invitation_is_rejected_and_replaced_by_a_learning_action():
    question = "Ba phần mười viết thành số thập phân nào con?"
    p = FakeChatModel(
        [
            row("Haha, con có gì vui thế? Mình cứ trao đổi thoải mái nhé."),
            row("Mình quay lại bài nhé. " + question),
            OK,
        ]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=LiveReader(None, semantic=True), speaker=speaker)
    turn = loop.on_student("hahaha", NOW)
    assert turn.messages[-1].source == "LLM" and turn.prompt == question
    assert (turn.awaiting, turn.node_id) == (first.awaiting, first.node_id)
    assert "OFF_LESSON_CHAT" in turn.messages[-1].rejected[0]
    assert "chia sẻ" not in turn.messages[-1].text and "thoải mái" not in turn.messages[-1].text
    assert not any(e.event_type in (EventType.ANSWER_SUBMITTED, EventType.NODE_DECISION) for e in turn.events)


def test_explicit_return_to_lesson_is_understood_even_when_models_are_down():
    p = FakeChatModel([])
    speaker = GroundedSpeaker(
        small_index(), AIRouter(chat_provider=p, max_calls_per_session=0), allow_knowledge=True
    )
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=LiveReader(None, semantic=True), speaker=speaker)
    for text in ("đang học mà chia sẻ gì", "đang học mà nói chuyện chia sẻ gì, tao mách mẹ"):
        turn = loop.on_student(text, NOW)
        assert "quay lại bài" in turn.messages[-1].text
        assert "lạc đề" in turn.messages[-1].text
        assert "nói thêm" not in turn.messages[-1].text
        assert (turn.awaiting, turn.node_id) == (first.awaiting, first.node_id)
    assert not p.calls


def test_topic_title_alone_does_not_satisfy_required_knowledge_recall():
    bad = {**opening_output(OPENING), "knowledge_recall": "Hôm nay ôn số thập phân."}
    p = FakeChatModel(
        [
            bad,
            {
                **ENTRY_OK,
                "recall_explains_knowledge": False,
                "reason": "Chỉ tên chủ đề, chưa nhắc kiến thức.",
            },
            opening_output(OPENING),
            ENTRY_OK,
        ]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    turn = TeachingLoop(CHAPTER, "synthetic", speaker=speaker).start(NOW)
    assert turn.messages[-1].source == "LLM"
    assert turn.messages[-1].text.startswith("Mình nhớ lại:")
    assert turn.messages[-1].rejected


def test_fraction_explanation_cannot_confuse_number_of_parts_and_decimal_places():
    from cavat.modules.tutor.brain import math_errors

    assert math_errors("3/10 = 0,3 vì có một phần mười.")
    assert math_errors("27/100 tức là hai phần trăm.")
    assert not math_errors("3/10 = 0,3 vì có ba phần mười.")
    assert not math_errors("3/10 viết 0,3 vì có một chữ số sau dấu phẩy.")
    assert not math_errors("3/10 = 0,3 vì có một phần mười và hai phần mười nữa.")


def test_failed_opening_retries_after_restore_without_grading_or_sample_question():
    offline = AIRouter(chat_provider=None)
    speaker = GroundedSpeaker(small_index(), offline, allow_knowledge=True, student_name="Hải")
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    first = loop.start(NOW)
    assert not first.prompt
    assert first.messages[-1].text == MODEL_WAIT_MESSAGE
    assert first.messages[-1].rejected
    restored = TeachingLoop.resume(CHAPTER, "synthetic", [], loop.events)
    assert not restored.current_turn().prompt
    provider = FakeChatModel([opening_output(OPENING), ENTRY_OK])
    live = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    restored.go_live(reader=RecordedReader({}), speaker=live)
    turn = restored.on_student("cô ơi", NOW)
    assert turn.messages[-1].source == "LLM" and turn.prompt == QUESTION
    assert "knowledge_recall" in provider.calls[0][1].json_schema["required"]
    assert not any(
        e.event_type in (EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED, EventType.NODE_DECISION)
        for e in turn.events
    )
    replay = TeachingLoop.resume(CHAPTER, "synthetic", [], restored.events)
    assert replay.current_turn().prompt == QUESTION


def test_missing_reviewer_does_not_burn_another_draft():
    from cavat.modules.ai_gateway.base import ModelClass

    provider = FakeChatModel([opening_output(OPENING)])
    router = AIRouter(
        chat_provider=provider,
        chains={
            ModelClass.TUTOR_REASONING: ("qwen-test",),
            ModelClass.TUTOR_MENTOR: (),
            ModelClass.EVAL_JUDGE: (),
        },
    )
    speaker = GroundedSpeaker(small_index(), router, allow_knowledge=True)
    turn = TeachingLoop(CHAPTER, "synthetic", speaker=speaker).start(NOW)
    assert len(provider.calls) == 1
    assert turn.messages[-1].source == "TEMPLATE"
    assert any(
        code.startswith("SERVICE_UNAVAILABLE:") for group in turn.messages[-1].rejected for code in group
    )


def test_unavailable_dialogue_does_not_blame_student_for_unclear_words():
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=None), allow_knowledge=True)
    spoken = speaker.conversation_reply(
        "cô oi",
        label="AMBIGUOUS_REPLY",
        asked=QUESTION,
        node=CHAPTER.nodes[0],
        focus="gọi cô",
        objective_driven=True,
    )
    assert spoken.text == MODEL_WAIT_MESSAGE
    assert "chưa rõ" not in spoken.text
