"""An active lesson keeps eliciting KC evidence; model availability is not speech validity."""

import json
from dataclasses import replace

from cavat.core.events import EventType
from cavat.core.pedagogy import Move
from cavat.modules.ai_gateway.base import ModelClass, estimate_prompt_tokens
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.author import write_lesson
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import TeachingLoop
from cavat.modules.tutor import brain
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext, RenderedMessage
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.prompt_builder import Turn
from cavat.modules.tutor.reader import Reading, RecordedReader
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message
from test_brain2 import small_index
from test_brain4 import ITEM, OK, PKG, tutor
from test_goal_driven_teaching import ENTRY_OK, EXPLANATION, QUESTION, opening_output, output
from test_grounded import CHAPTER, NOW


def test_repeated_wrong_answers_never_advance_merely_because_coteach_happened_once():
    provider = FakeChatModel(
        [
            opening_output(EXPLANATION + QUESTION),
            ENTRY_OK,
            *[
                part
                for followup in (
                    "Hai phần mười có chữ số 2 ngay sau dấu phẩy. Ba phần mười viết thế nào?",
                    "Bốn phần mười là bốn phần khi chia một đơn vị thành mười phần bằng nhau. "
                    "Con viết số đó thế nào?",
                    "Sáu phần mười viết là 0,6. Nếu lấy bảy phần mười thì con viết được số nào?",
                )
                for part in (
                    {"answered": False, "quote": ""},
                    output(followup),
                    OK,
                )
            ],
            {"answered": True, "quote": "0,7"},
            output("Con đã viết đúng bảy phần mười là 0,7."),
            OK,
        ]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    first = loop.start(NOW)
    for _ in range(3):
        # A real command restores the loop each time; reteaching must not become an implicit pass.
        loop = TeachingLoop.resume(CHAPTER, "synthetic", [], loop.events)
        loop.go_live(reader=RecordedReader({1: Reading("PASS")}), speaker=speaker)
        turn = loop.on_student("0,9", NOW)
        assert turn.node_id == first.node_id and turn.awaiting == first.awaiting
        assert turn.messages[-1].source == "LLM" and turn.messages[-1].text.endswith("?")
        assert not any(
            e.event_type in (EventType.NODE_DECISION, EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED)
            for e in turn.events
        )
    advanced = []
    loop._advance = lambda now, messages, events: advanced.append(True)
    loop.on_student("0,7", NOW)
    assert advanced == [True]


def test_repair_that_only_explains_is_retried_with_a_concrete_followup():
    good = EXPLANATION + QUESTION
    provider = FakeChatModel([output(EXPLANATION), output(good), OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    spoken = speaker.conversation_reply(
        "con chưa hiểu",
        asked=QUESTION,
        node=CHAPTER.nodes[0],
        focus="chưa hiểu phần mười",
        label="REPAIR",
        objective_driven=True,
    )
    assert spoken.text == good and ("QUESTION_COUNT",) in spoken.rejected
    case = json.loads(provider.calls[0][1].messages[1].content)
    assert case["cau_hoi"] == "required"


def test_practice_repair_requires_a_question_and_keeps_the_pending_task():
    router = AIRouter(chat_provider=FakeChatModel([]), model_only_speech=True)
    renderer = LLMRenderer(router, TemplateRenderer(), validate_message, allow_knowledge=True)
    ctx = RenderContext(
        decision=PolicyDecision(Move.EXPLAIN, reason_codes=("CONVERSATION", "REPAIR")),
        item=ITEM,
        package=PKG,
        state=tutor(None).state,
        student_text="con chưa hiểu",
    )
    pack = renderer._pack(ctx, RenderedMessage("", "TEMPLATE"))
    assert "không thêm câu hỏi" not in pack.task
    assert "MISSING_QUESTION" in renderer._codes("Cô giải thích một ý.", ctx, pack)


def test_long_lesson_context_is_trimmed_for_both_draft_and_review_without_truncating_speech():
    provider = FakeChatModel([output(EXPLANATION + QUESTION), OK])
    router = AIRouter(chat_provider=provider)
    result = write_lesson(
        router,
        brain.BrainPack(
            task="Giảng phần mười " * 80,
            question="Số thập phân " * 30,
            grounds=("Phần mười " * 150,) * 2,
            recent=tuple(Turn("tutor", "Lịch sử " * 100) for _ in range(6)),
        ),
        calls_used=0,
        questions="required",
    )
    assert result.text == EXPLANATION + QUESTION
    assert all(estimate_prompt_tokens(req) <= 3000 for _, req in provider.calls)
    assert json.loads(provider.calls[-1][1].messages[1].content)["loi_de_xuat"] == result.text


def test_mentor_instruction_is_included_inside_the_prompt_budget():
    from test_tutor_mentor import MENTOR, check, pack, row

    provider = FakeChatModel({MENTOR: [row("Cô sẽ giúp con.")]})
    router = AIRouter(chat_provider=provider, chains={ModelClass.TUTOR_MENTOR: (MENTOR,)})
    rich = replace(
        pack(True),
        recent=tuple(Turn("tutor", "Ví dụ " * 200) for _ in range(6)),
        grounds=("Quy tắc " * 150,) * 3,
    )
    result = brain.speak(
        router, rich, check, calls_used=0, model_class=ModelClass.TUTOR_MENTOR, allow_mentor=False
    )
    assert result.text
    assert estimate_prompt_tokens(provider.calls[0][1]) <= 3000


def test_transient_model_limit_recovers_once_without_a_wait_utterance():
    from datetime import timedelta

    from cavat.modules.ai_gateway.base import QuotaExceeded
    from test_ai_gateway import _request

    now = [NOW]
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += timedelta(seconds=seconds)

    provider = FakeChatModel(
        [QuotaExceeded("TPM", reset_at=NOW + timedelta(seconds=2)), {"message": "Đã hồi hạn mức."}]
    )
    router = AIRouter(
        chat_provider=provider,
        chains={ModelClass.TUTOR_REASONING: ("m",)},
        clock=lambda: now[0],
        sleeper=sleep,
        transient_retry_s=6,
    )
    result = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert result.result and result.calls_made == 2 and len(result.attempts) == 2
    assert len(sleeps) == 1 and 2 <= sleeps[0] < 3


def test_daily_exhaustion_never_sleeps_or_retries_the_same_model():
    from datetime import timedelta

    from cavat.modules.ai_gateway.base import QuotaExceeded
    from test_ai_gateway import _request

    provider = FakeChatModel([QuotaExceeded("RPD", reset_at=NOW + timedelta(hours=10))])
    sleeps = []
    router = AIRouter(
        chat_provider=provider,
        chains={ModelClass.TUTOR_REASONING: ("m",)},
        clock=lambda: NOW,
        sleeper=sleeps.append,
        transient_retry_s=6,
    )
    result = router.chat(ModelClass.TUTOR_REASONING, _request(), calls_used=0)
    assert result.result is None and result.calls_made == 1 and not sleeps


def test_ambiguous_decimal_digit_rule_and_false_fraction_quantity_are_rejected():
    assert brain.math_errors(
        "Đổi sang số thập phân với số chữ số sau dấu phẩy tương ứng số chữ số của mẫu số."
    )
    assert brain.math_errors("3/10 tương đương với một phần mười.")
    assert not brain.math_errors("3/10 tương đương với ba phần mười.")


def test_acknowledgment_is_not_evidence_that_the_student_has_understood():
    pack = brain.BrainPack(
        task="Mời con vận dụng", question=QUESTION, student_text="à ra vậy", return_to_lesson=True
    )
    assert "UNSUPPORTED_UNDERSTANDING" in brain.speech_codes("Cô vui vì con đã nắm ý. " + QUESTION, pack)
    assert not brain.speech_codes("Mình thử một bước nhé. " + QUESTION, pack)


def test_repeated_incomplete_retells_keep_the_same_kc_and_require_another_attempt(monkeypatch):
    from cavat.modules.teaching.grounded import Spoken
    from cavat.modules.teaching.loop import Awaiting

    loop = TeachingLoop(CHAPTER, "synthetic")
    first = loop.start(NOW)
    node = CHAPTER.node(first.node_id)
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=FakeChatModel([])), allow_knowledge=True)
    monkeypatch.setattr(speaker, "judge_meaning", lambda *a, **kw: ([], []))
    monkeypatch.setattr(
        speaker,
        "conversation_reply",
        lambda *a, **kw: Spoken(
            "Mình nhớ lại cách chia một đơn vị thành các phần bằng nhau. Con nói lại ý này được không?", "LLM"
        ),
    )
    loop._wait(Awaiting.RETELL, node.id, None, node.explain.prompt, [], [])
    loop.go_live(reader=RecordedReader({1: Reading("PASS"), 2: Reading("PASS")}), speaker=speaker)
    for _ in range(2):
        turn = loop.on_student("có một điều khác", NOW)
        assert turn.awaiting == Awaiting.RETELL and turn.node_id == node.id
        assert turn.messages[-1].source == "LLM" and turn.messages[-1].text.endswith("?")
        assert not any(
            e.event_type in (EventType.NODE_DECISION, EventType.RETELL_JUDGED) for e in turn.events
        )
