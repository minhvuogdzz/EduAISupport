"""The tutor owns the next question; acknowledgements cannot become another lecture or a grade."""

from datetime import timedelta

import pytest
from cavat.core.events import EventType, PolicyDecisionMade
from cavat.core.pedagogy import Move, Outcome
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.grounded import GroundedSpeaker, QuestionTurn, Spoken
from cavat.modules.teaching.loop import Awaiting
from cavat.modules.tutor.item_loop import Phase, TutorEvent
from cavat.modules.tutor.reader import LiveReader, ModelReader, Reading, RecordedReader
from test_brain2 import small_index
from test_brain4 import OK, tutor
from test_grounded import NOW, loop_at_theory

ACKS = ["ok", "okok", "à", "ra là vậy à", "làm tiếp", "à ok", "hiểu rồi", "tiếp tục"]


def at_theory():
    provider = FakeChatModel([])
    router = AIRouter(chat_provider=provider, max_calls_per_session=0)
    speaker = GroundedSpeaker(small_index(), router, allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=LiveReader(ModelReader(router), semantic=True), speaker=speaker)
    return loop, first, provider


def test_ack_sequence_asks_the_pending_question_without_model_calls_or_grades():
    loop, first, provider = at_theory()
    before = first.awaiting, first.node_id, first.prompt
    for raw in ACKS:
        turn = loop.on_student(raw, NOW + timedelta(seconds=1))
        assert (turn.awaiting, turn.node_id, turn.prompt) == before
        assert turn.messages[-1].text.endswith(first.prompt)
        assert turn.messages[-1].text.count("?") == 1
        assert turn.messages[-1].source == "TEMPLATE"
        assert not any(
            e.event_type in {EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED, EventType.NODE_DECISION}
            for e in turn.events
        )
    assert provider.calls == []
    # The API rebuilds a session between requests: CONTINUE must survive that boundary too.
    from cavat.modules.teaching.loop import TeachingLoop

    restored = TeachingLoop.resume(loop.chapter, "s1", [], loop.events)
    assert restored.awaiting == first.awaiting and restored._prompt == first.prompt
    restored.go_live(reader=loop.item_reader, speaker=loop.speaker)
    loop = restored
    variant = next(v for v in loop.chapter.node(first.node_id).theory if v.ask == first.prompt)
    # Actual knowledge after the ack sequence advances the existing lesson, not another "do you understand?".
    turn = loop.on_student(variant.accept[0], NOW + timedelta(seconds=2))
    assert (turn.awaiting, turn.prompt) != (first.awaiting, first.prompt)


def test_repair_preserves_pending_question_without_forcing_it_into_the_explanation_at_quota():
    loop, first, provider = at_theory()
    turn = loop.on_student("hả", NOW)
    assert not turn.messages[-1].text.endswith(first.prompt) and "?" not in turn.messages[-1].text
    assert turn.prompt == first.prompt and turn.awaiting == first.awaiting and provider.calls == []


def test_retell_acknowledgement_does_not_repeat_the_lesson_or_award_comprehension():
    loop, first, provider = at_theory()
    loop.awaiting = Awaiting.RETELL
    loop._prompt = loop.chapter.node(first.node_id).explain.prompt
    loop._ref = None
    turn = loop.on_student("hiểu rồi", NOW)
    assert turn.awaiting == Awaiting.RETELL and turn.messages[-1].text.endswith(loop._prompt)
    assert not any(e.event_type == EventType.RETELL_JUDGED for e in turn.events)
    assert len(turn.messages[-1].text.split()) <= len(loop._prompt.split()) + 5
    assert not provider.calls


def test_a_theory_lookup_returns_to_the_waiting_check_instead_of_leaving_the_child_to_prompt_the_tutor():
    loop, first, _ = at_theory()
    loop.speaker.answer = lambda *a, **kw: QuestionTurn(
        "ANSWERED", Spoken("Mẫu số là số viết dưới gạch ngang.", "LLM")
    )
    turn = loop._on_question("mẫu số là gì", NOW, first.node_id, [], [])
    assert turn.messages[-1].text.endswith(first.prompt) and turn.messages[-1].text.count("?") == 1
    assert turn.prompt == first.prompt


@pytest.mark.parametrize("phase", [Phase.AWAITING, Phase.VERIFYING, Phase.TEACH_BACK, Phase.AWAITING_REASON])
def test_item_continuation_preserves_the_kind_of_evidence_waited_for(phase):
    t = tutor(LiveReader(None, semantic=True))
    t.phase = phase
    turn = t.on_student("okok", dialogue_version=3)
    assert turn.phase == phase and not turn.resolved and turn.text.count("?") == 1
    assert t.state.attempt_no == 0 and t.state.max_hint_level == 0
    assert not any(e.type == EventType.ANSWER_SUBMITTED for e in turn.events)
    if phase in (Phase.VERIFYING, Phase.TEACH_BACK):
        assert "cách con làm" in turn.text


def test_ack_then_an_actual_correct_answer_moves_on():
    t = tutor(LiveReader(None, semantic=True))
    assert not t.on_student("ok", dialogue_version=3).resolved
    turn = t.on_student("31/10 vì có một chữ số sau dấu phẩy", dialogue_version=3)
    assert turn.resolved and t._last_graded.outcome == Outcome.CORRECT


def test_continuing_a_supported_small_question_keeps_its_numeric_answer_contract():
    t = tutor(LiveReader(None, semantic=True))
    question = "Phần thập phân của số trên đề có mấy chữ số?"
    t.last_tutor = question
    t._helper_context = True
    t.events.append(
        TutorEvent(
            type=EventType.POLICY_DECISION,
            payload=PolicyDecisionMade(
                item_id=t.item.id, move=Move.EXPLAIN, reason_codes=["CONVERSATION", "REPAIR"]
            ).model_dump(mode="json"),
        )
    )
    turn = t.on_student("ok", dialogue_version=3)
    assert turn.text.endswith(question)
    t.on_student("1", dialogue_version=3)
    assert t._last_graded.outcome == Outcome.PARTIAL and t.state.unproductive_turns == 0


def test_explicit_rest_does_not_gain_a_forced_question():
    provider = FakeChatModel(
        [{"message": "Mình nghỉ một chút nhé, cô chờ con.", "safety_flag": False, "policy_feedback": ""}, OK]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop, _ = loop_at_theory(speaker)
    loop.go_live(reader=RecordedReader({1: Reading("DECLINE", focus="muốn nghỉ")}), speaker=speaker)
    turn = loop.on_student("con muốn nghỉ một chút", NOW)
    assert "?" not in turn.messages[-1].text


def test_math_letters_are_not_mistaken_for_vietnamese_acknowledgements():
    from cavat.modules.tutor.conversation import conversation_signal

    assert conversation_signal("A", "Con chọn A hay B?") is None
    assert conversation_signal("U", "Đỉnh nào con?") is None
    assert conversation_signal("à", "Cô giải thích như trên.").label == "CONTINUE"


def test_continuation_of_a_real_probe_keeps_the_original_probe_and_grader():
    from test_item_loop import tutor as original_tutor

    t = original_tutor("GP-08")
    t.start()
    t.on_student("Lan")
    assert t.phase == Phase.AWAITING_PROBE
    original = t._probe_option
    before = t.state.attempt_no
    t.reader = LiveReader(None, semantic=True)
    turn = t.on_student("ok", dialogue_version=3)
    assert turn.phase == Phase.AWAITING_PROBE and t._probe_option == original
    assert turn.text.endswith(original.probe.prompt) and t.state.attempt_no == before
    assert not any(e.type == EventType.OUTPUT_REJECTED for e in turn.events)


def test_resuming_the_question_does_not_depend_on_permission_to_use_outside_knowledge():
    loop, first, provider = at_theory()
    loop.speaker.allow_knowledge = False
    turn = loop.on_student("ok", NOW)
    assert turn.messages[-1].text.endswith(first.prompt)
    assert provider.calls == [] and turn.awaiting == first.awaiting


def test_ready_theory_ack_is_generated_when_available_and_item_probe_contract_is_preserved():
    from cavat.modules.tutor.llm_renderer import LLMRenderer
    from cavat.modules.tutor.renderer import TemplateRenderer
    from cavat.modules.tutor.validator import validate_message

    actual = "Bốn phần trong một trăm phần bằng nhau viết thành phân số nào con?"
    provider = FakeChatModel([{"message": actual, "safety_flag": False, "policy_feedback": ""}, OK])
    router = AIRouter(chat_provider=provider, max_calls_per_session=160)
    reader = LiveReader(ModelReader(router), semantic=True)
    speaker = GroundedSpeaker(small_index(), router, allow_knowledge=True)
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=reader, speaker=speaker)
    turn = loop.on_student("okok", NOW)
    assert turn.messages[-1].source == "LLM" and turn.prompt == actual
    assert len(provider.calls) == 2
    provider.calls.clear()
    renderer = LLMRenderer(router, TemplateRenderer(), validate_message, allow_knowledge=True)
    item = tutor(reader, renderer=renderer)
    turn = item.on_student("ok", dialogue_version=3)
    assert turn.move == Move.REDIRECT and turn.text.endswith("?")
    assert provider.calls == []
