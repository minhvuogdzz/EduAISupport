"""Conversation regressions: hear agreement in context and let a new explanation through."""

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import Move
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.content.lesson_package import NumericAnswer
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.tutor import brain
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext
from cavat.modules.tutor.dialogue import conversion_ground
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.prompt_builder import Turn
from cavat.modules.tutor.reader import LiveReader, Reading, RecordedReader
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message
from test_brain2 import small_index
from test_brain4 import ITEM, OK, PKG, tutor


def test_ok_without_provider_is_not_a_typo_or_an_incorrect_math_answer():
    t = tutor(LiveReader(None, semantic=True))
    turn = t.on_student("ok", dialogue_version=3)
    assert turn.move == Move.EXPLAIN and not turn.resolved
    assert t.state.attempt_no == 0 and t.state.unproductive_turns == 0
    reads = [e.payload for e in turn.events if e.type == EventType.MESSAGE_READ]
    assert [p["label"] for p in reads] == ["REPAIR"]
    assert not any(p.get("guessed_meaning") for p in reads)


def test_shared_opening_does_not_discard_a_different_explanation_but_exact_repeat_is_still_blocked():
    first = "Cô giảng lại nhé: mẫu số 10 cho biết đơn vị chia thành mười phần."
    second = "Cô giảng lại nhé: tưởng tượng một thanh chia mười ô bằng nhau, mỗi ô là một phần mười."
    pack = brain.BrainPack(task="Giảng lại", question="", recent=(Turn("tutor", first),))
    assert brain.REPEATS_PREVIOUS in brain.speech_codes(second, pack)
    assert brain.REPEATS_PREVIOUS not in brain.speech_codes(second, pack, flexible=True)
    assert brain.REPEATS_PREVIOUS in brain.speech_codes(first, pack, flexible=True)


@pytest.mark.parametrize("denominator", [10, 100, 1000])
def test_fraction_to_decimal_repair_uses_another_verified_example_and_survives_final_validator(denominator):
    item = ITEM.model_copy(
        update={
            "stem": f"Viết thành số thập phân: 7/{denominator} = …",
            "answer": NumericAnswer(
                type="numeric", value="0," + "7".zfill(len(str(denominator)) - 1), form="decimal"
            ),
        }
    )
    t = tutor(RecordedReader({1: Reading("REPAIR", focus="cách viết")}), item=item)
    turn = t.on_student("cô giảng cách viết giúp con", dialogue_version=3)
    assert turn.move == Move.EXPLAIN
    assert not any(e.type == EventType.OUTPUT_REJECTED for e in turn.events)
    assert f"3/{denominator}" in turn.text
    assert not brain.math_errors(conversion_ground(item))
    assert not turn.resolved and t.state.attempt_no == 0


def test_repair_model_can_explain_reverse_conversion_without_a_question():
    item = ITEM.model_copy(
        update={
            "stem": "Viết thành số thập phân: 7/10 = …",
            "answer": NumericAnswer(type="numeric", value="0,7", form="decimal"),
        }
    )
    r = LLMRenderer(
        AIRouter(chat_provider=FakeChatModel([OK])),
        TemplateRenderer(),
        validate_message,
        allow_knowledge=True,
    )
    t = tutor(None, item=item)
    ctx = RenderContext(
        decision=PolicyDecision(Move.EXPLAIN, reason_codes=("CONVERSATION", "REPAIR")),
        item=item,
        package=PKG,
        state=t.state,
        student_text="viết như nào nhỉ",
    )
    pack = r._pack(ctx, TemplateRenderer().render(ctx))
    answer = "Ví dụ 3/10 là ba phần mười: viết 0 ở phần nguyên, rồi dấu phẩy và 3, được 0,3."
    assert "NEW_TASK_QUESTION" not in r._codes(answer, ctx, pack)
    assert not validate_message(answer, ctx).codes


def test_ambiguous_clarification_allows_exactly_one_question_and_keeps_context():
    text = "Con muốn cô giải thích lại chỗ nào?"
    p = FakeChatModel([{"message": text, "safety_flag": False, "policy_feedback": ""}, OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    from test_teaching_loop import CHAPTER

    spoken = speaker.conversation_reply(
        "ý gì",
        asked="Câu đang chờ?",
        node=CHAPTER.nodes[0],
        focus="chỗ con chưa rõ",
        label="AMBIGUOUS_REPLY",
        recent=[("tutor", "Lời cô vừa giải thích")],
    )
    assert spoken.text == text and spoken.source == "LLM"
    assert "Lời cô vừa giải thích" in p.calls[0][1].messages[1].content


def test_token_minute_backoff_does_not_use_an_unexhausted_daily_request_reset():
    from datetime import UTC, datetime, timedelta

    from cavat.modules.ai_gateway.base import QuotaTracker
    from cavat.modules.ai_gateway.groq import _reset_at

    now = datetime(2026, 10, 28, tzinfo=UTC)
    headers = {
        "x-ratelimit-reset-tokens": "8s",
        "x-ratelimit-reset-requests": "12m",
        "x-ratelimit-remaining-requests": "990",
        "x-ratelimit-remaining-tokens": "1000",
    }
    until = _reset_at(headers, now, "TPM")
    assert until == now + timedelta(seconds=8)
    quota = QuotaTracker()
    quota.update("model", headers, now)
    quota.mark_exhausted("model", until, now)
    assert quota.reset_at("model") == until
    assert quota.is_exhausted("model", now + timedelta(seconds=7))
    assert not quota.is_exhausted("model", now + timedelta(seconds=9))
    assert _reset_at({**headers, "retry-after": "20"}, now, "TPM") == now + timedelta(seconds=20)
    assert _reset_at(headers, now, "RPD") == now + timedelta(minutes=12)
    # If the daily bucket really is empty too, its longer reset must remain visible.
    quota.update("both", {**headers, "x-ratelimit-remaining-requests": "0"}, now)
    quota.mark_exhausted("both", until, now)
    assert quota.reset_at("both") == now + timedelta(minutes=12)
    assert quota.is_exhausted("both", now + timedelta(seconds=9))


@pytest.mark.parametrize("raw", ["phải", "đúng", "vâng"])
def test_agreeing_with_need_for_help_is_not_clarified_again(raw):
    r = LiveReader(None, semantic=True)
    reading = r.read_dialogue(
        stem="Bài Toán", last_tutor="Con chưa hiểu cách viết, phải không?", said=raw, turn=1
    )
    assert reading.label == "REPAIR" and reading.answer == ""
    # The same word may answer a mathematical location question; leave it to the grader/model.
    if raw == "phải":
        assert (
            r.read_dialogue(stem="Bài Toán", last_tutor="Phần thập phân nằm bên nào?", said=raw, turn=1)
            is None
        )


def test_huh_when_provider_is_unavailable_is_help_without_mistake_or_hint_escalation():
    t = tutor(LiveReader(None, semantic=True))
    for text in ["hả", "?", "con chưa hiểu"]:
        turn = t.on_student(text, dialogue_version=3)
        assert turn.move == Move.EXPLAIN and not turn.resolved
        assert t.state.max_hint_level == 2 and t.state.attempt_no == 0
        assert not any(e.type == EventType.ANSWER_SUBMITTED for e in turn.events)


def test_before_recording_student_input_history_keeps_the_actual_last_teacher_message():
    from types import SimpleNamespace

    from cavat.modules.teaching.loop import TeachingLoop

    loop = object.__new__(TeachingLoop)
    loop.events = [
        SimpleNamespace(
            event_type=EventType.TEACH_MESSAGE_SENT, payload={"text": "Con chưa hiểu cách viết, phải không?"}
        )
    ]
    assert loop._recent(6, include_last=True) == [("tutor", "Con chưa hiểu cách viết, phải không?")]
    assert loop._recent(6) == []  # the existing post-input convention remains


@pytest.mark.parametrize("denominator", [10, 100, 1000])
def test_analogous_fraction_example_never_reuses_the_original_value(denominator):
    item = ITEM.model_copy(
        update={
            "stem": f"Viết thành số thập phân: 3/{denominator} = …",
            "answer": NumericAnswer(
                type="numeric", value="0," + "3".zfill(len(str(denominator)) - 1), form="decimal"
            ),
        }
    )
    ground = conversion_ground(item)
    assert f"6/{denominator}" in ground and f"Ví dụ 3/{denominator}" not in ground
