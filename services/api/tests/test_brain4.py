"""Semantic listening, open teaching within the curriculum, and immutable student grading."""

import json
from dataclasses import replace

import pytest
from cavat.core.events import EventType
from cavat.core.pedagogy import ActivityType, HintLevel, HintTarget, Move
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.content.lesson_package import NumericAnswer
from cavat.modules.teaching.curriculum import verified
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.tutor.contracts import PolicyDecision, RenderContext
from cavat.modules.tutor.item_loop import ItemTutor, Phase
from cavat.modules.tutor.llm_renderer import LLMRenderer
from cavat.modules.tutor.reader import LiveReader, ModelReader, Reading, RecordedReader
from cavat.modules.tutor.renderer import TemplateRenderer
from cavat.modules.tutor.validator import validate_message
from test_brain2 import small_index
from test_brain3 import BASE, NO_VERIFY, PKG, RULE

ITEM = BASE.model_copy(
    update={
        "id": "SYNTH-FRACTION",
        "stem": "Viết thành phân số thập phân: 3,1 = …",
        "rephrase": "Viết số này thành phân số rút gọn.",
        "verify_prompt": None,
        "answer": NumericAnswer(type="numeric", value="31/10", form="fraction"),
        "worked_solution": [],
        "explanation": "Một chữ số ở phần thập phân tương ứng mẫu số 10.",
    }
)
OK = {
    "mathematically_correct": True,
    "within_scope": True,
    "task_preserved": True,
    "addresses_student": True,
    "solution_leaked": False,
    "reason": "",
}


def tutor(reader, item=ITEM, renderer=None):
    t = ItemTutor(
        item,
        PKG,
        ActivityType.GUIDED_PRACTICE,
        renderer or TemplateRenderer(),
        validate_message,
        NO_VERIFY,
        reader=reader,
        knowledge=(RULE,),
    )
    t.start()
    return t


def test_bare_no_after_worked_help_is_not_another_failure_or_an_automatic_close():
    r = RecordedReader(
        {
            1: Reading("AMBIGUOUS_REPLY", source="RULE"),
            2: Reading("REPAIR", focus="cần giảng một bước khác", source="RULE"),
        }
    )
    t = tutor(r)
    t.phase = Phase.TEACH_BACK
    t.state.worked_shown = True
    t.state.hint_levels = [HintLevel.H6]
    t.state.hint_targets = [HintTarget.STEP]
    before = replace(t.state)
    first = t.on_student("không", seconds=900, dialogue_version=3)
    second = t.on_student("không", seconds=5, dialogue_version=3)
    assert first.move == Move.ASK_CONFIRM and second.move == Move.EXPLAIN
    assert second.phase == Phase.TEACH_BACK and not second.resolved
    assert t.state.attempt_no == before.attempt_no and t.state.hint_levels == before.hint_levels
    assert t.state.seconds_since_shown == before.seconds_since_shown
    assert not any(e.type in (EventType.ANSWER_SUBMITTED, EventType.ITEM_RESOLVED) for e in t.events)


def test_listener_sees_raw_words_and_real_context_not_a_fabricated_dont_know():
    provider = FakeChatModel([{"label": "AMBIGUOUS_REPLY", "focus": "chưa rõ có muốn làm tiếp không"}])
    router = AIRouter(chat_provider=provider)
    t = tutor(LiveReader(ModelReader(router), semantic=True))
    t.last_tutor = "Con muốn tự thử hay muốn cô giảng trước?"
    turn = t.on_student("không", dialogue_version=3)
    request = provider.calls[0][1]
    assert request.schema_name == "dialogue_listen_v6"
    assert json.loads(request.messages[1].content)["con_vua_noi"] == "không"
    assert "Con muốn tự thử" in request.messages[1].content
    assert "con không biết" not in request.messages[1].content
    assert turn.move == Move.ASK_CONFIRM and t.state.unproductive_turns == 0


def test_no_provider_still_asks_what_no_means_without_charging_a_wrong_answer():
    t = tutor(LiveReader(None, semantic=True))
    turn = t.on_student("không", dialogue_version=3)
    assert turn.move == Move.ASK_CONFIRM and "nói thêm" in turn.text
    assert t.state.attempt_no == 0 and t.state.max_hint_level == 0


def test_old_inputs_keep_old_reading_on_replay():
    t = tutor(LiveReader(None, semantic=True))
    turn = t.on_student("không", dialogue_version=2)
    assert turn.move != Move.ASK_CONFIRM


def test_assessment_does_not_call_the_listener_or_get_its_key_into_a_prompt():
    p = FakeChatModel([])
    t = tutor(
        LiveReader(ModelReader(AIRouter(chat_provider=p)), semantic=True),
        item=ITEM.model_copy(update={"purpose": "EXIT"}),
    )
    t.on_student("không", dialogue_version=3)
    assert not p.calls


def test_explicit_refusal_is_respected_without_a_compulsory_question_or_fake_resolution():
    t = tutor(RecordedReader({1: Reading("DECLINE", focus="muốn nghỉ", source="RULE")}))
    turn = t.on_student("con muốn nghỉ một chút", dialogue_version=3)
    assert "?" not in turn.text and not turn.resolved and t.state.attempt_no == 0


def test_canonical_task_overrides_an_unfaithful_rephrase_and_reduction_request_is_blocked():
    provider = FakeChatModel([])
    renderer = LLMRenderer(
        AIRouter(chat_provider=provider), TemplateRenderer(), validate_message, allow_knowledge=True
    )
    t = tutor(None, renderer=renderer)
    ctx = RenderContext(
        decision=PolicyDecision(Move.HINT, HintLevel.H1, HintTarget.CONCEPT),
        item=ITEM,
        package=PKG,
        state=t.state,
        evidence=(RULE,),
    )
    pack = renderer._pack(ctx, TemplateRenderer().render(ctx))
    assert pack.question == ITEM.stem and "không yêu cầu rút gọn" in pack.task
    assert "CHANGES_TASK" in renderer._codes("Bây giờ con thử rút gọn phân số nhé?", ctx, pack)
    assert not provider.calls


@pytest.mark.parametrize(
    "field",
    ["mathematically_correct", "within_scope", "task_preserved", "addresses_student"],
)
def test_independent_verifier_requires_every_condition(field):
    assert verified(OK)
    assert not verified({**OK, field: False})
    assert not verified({**OK, field: "true"})
    assert not verified({**OK, "solution_leaked": True})


def test_theory_missing_in_retrieval_can_use_verified_standard_knowledge_without_fake_web_citation():
    answer = "Mẫu số cho biết một đơn vị được chia thành bao nhiêu phần bằng nhau."
    p = FakeChatModel([{"message": answer, "safety_flag": False, "policy_feedback": ""}, OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    # Exercise the selected-topic lane with a deliberately empty source result: no source was fabricated.
    found = speaker.index.question("mẫu số là gì", "eq", speaker.order)[1]
    turn = speaker._background("mẫu số là gì", found, "mẫu số")
    assert turn.kind == "ANSWERED" and turn.spoken.text == answer
    assert turn.spoken.source == "LLM" and not turn.spoken.sources and turn.web is None
    assert [r.schema_name for _, r in p.calls] == ["tutor_turn", "curriculum_check_v2"]


def test_invalid_theory_is_never_spoken_even_when_a_draft_sounds_fluent():
    draft = {
        "message": "Mẫu số là số phần đã lấy từ cả cái bánh.",
        "safety_flag": False,
        "policy_feedback": "",
    }
    p = FakeChatModel(
        [draft, {**OK, "mathematically_correct": False}, draft, {**OK, "mathematically_correct": False}]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=p), allow_knowledge=True)
    found = speaker.index.question("mẫu số là gì", "eq", speaker.order)[1]
    assert speaker._background("mẫu số là gì", found, "mẫu số").kind == "PARKED"


def test_scope_uses_normalized_node_titles_and_does_not_drop_fraction_prerequisites():
    p = FakeChatModel([{"concept": "mẫu số"}])
    speaker = GroundedSpeaker(
        small_index(title="Phân số thập phân"), AIRouter(chat_provider=p), allow_knowledge=True
    )
    assert speaker._theory_topic("mẫu số có ý nghĩa gì", "eq") == "mẫu số"
    assert "mẫu số" in p.calls[0][1].messages[1].content


def test_fluid_teaching_must_not_give_the_unsolved_numerical_answer():
    p = FakeChatModel([])
    renderer = LLMRenderer(
        AIRouter(chat_provider=p), TemplateRenderer(), validate_message, allow_knowledge=True
    )
    t = tutor(None, renderer=renderer)
    ctx = RenderContext(
        decision=PolicyDecision(Move.EXPLAIN), item=ITEM, package=PKG, state=t.state, evidence=(RULE,)
    )
    pack = renderer._pack(ctx, TemplateRenderer().render(ctx))
    assert "ANSWER_LEAK" in renderer._codes("Ta viết 3,1 thành 31/10 nhé con.", ctx, pack)
    assert not p.calls


def test_semantic_scope_cannot_choose_an_arbitrary_future_topic_or_url():
    p = FakeChatModel([{"concept": "https://untrusted.example/"}])
    speaker = GroundedSpeaker(
        small_index(title="Phân số thập phân"), AIRouter(chat_provider=p), allow_knowledge=True
    )
    assert speaker._theory_topic("giải thích mẫu số", "eq") == ""


def test_published_numeric_items_without_form_still_get_the_right_teaching_contract():
    published = ITEM.model_copy(update={"answer": NumericAnswer(type="numeric", value="31/10")})
    renderer = LLMRenderer(
        AIRouter(chat_provider=FakeChatModel([])), TemplateRenderer(), validate_message, allow_knowledge=True
    )
    t = tutor(None, item=published, renderer=renderer)
    ctx = RenderContext(
        decision=PolicyDecision(Move.EXPLAIN, reason_codes=("CONVERSATION", "REPAIR")),
        item=published,
        package=PKG,
        state=t.state,
        student_text="con chưa hiểu cách đổi",
        evidence=(RULE,),
    )
    pack = renderer._pack(ctx, TemplateRenderer().render(ctx))
    assert "3,1" not in pack.question and any("2,7" in g for g in pack.grounds)
    assert "NEW_TASK_QUESTION" in renderer._codes("Con thử viết 7,203 thành phân số nhé?", ctx, pack)


@pytest.mark.parametrize(
    ("asked", "answer"),
    [
        ("Mẫu số của phân số cần là bao nhiêu?", "10"),
        ("Phần thập phân có mấy chữ số?", "1"),
        ("Mẫu số cần có bao nhiêu chữ số 0?", "1"),
    ],
)
def test_correct_answer_to_teachers_small_question_is_not_graded_as_the_whole_exercise(asked, answer):
    from cavat.core.pedagogy import Outcome
    from cavat.modules.tutor.dialogue import numeric_helper

    assert numeric_helper(ITEM, answer, asked, PKG).outcome == Outcome.PARTIAL
    assert numeric_helper(ITEM, "999", asked, PKG) is None


def test_replay_uses_the_actual_small_question_the_child_heard():
    from datetime import UTC, datetime

    from cavat.core.events import MessageRead, NodeDecisionMade, StudentMessage, TutorMessageSent
    from cavat.core.pedagogy import Outcome, TeachAction
    from cavat.modules.teaching.loop import LoopEvent, TeachingLoop
    from test_teaching_loop import CHAPTER

    now = datetime(2026, 10, 28, tzinfo=UTC)

    def event(kind, payload):
        return LoopEvent(kind.value, payload.model_dump(mode="json"), "s1", now)

    item = "TP-PR-01"
    events = [
        event(
            EventType.NODE_DECISION,
            NodeDecisionMade(
                action=TeachAction.ENTER_NODE, node_id="KC-DEC-FRAC", policy_version="node-policy/0.5.0"
            ),
        ),
        event(
            EventType.NODE_DECISION,
            NodeDecisionMade(
                action=TeachAction.PRACTICE_ITEM,
                node_id="KC-DEC-FRAC",
                ref=item,
                policy_version="node-policy/0.5.0",
            ),
        ),
        event(
            EventType.STUDENT_MESSAGE,
            StudentMessage(item_id=item, kind="ANSWER", text="con chưa hiểu đổi thế nào", dialogue_version=3),
        ),
        event(
            EventType.MESSAGE_READ,
            MessageRead(item_id=item, turn=1, label="REPAIR", focus="cách đổi", source="RULE"),
        ),
        event(
            EventType.TUTOR_MESSAGE_SENT,
            TutorMessageSent(
                item_id=item,
                move=Move.EXPLAIN,
                text="Phần thập phân của số trên đề có mấy chữ số?",
                source="LLM",
                words=13,
                attempts_to_pass_validator=1,
            ),
        ),
        event(
            EventType.STUDENT_MESSAGE,
            StudentMessage(item_id=item, kind="ANSWER", text="1", dialogue_version=3),
        ),
    ]
    revised = CHAPTER.item(item).model_copy(update={"stem": ITEM.stem, "answer": ITEM.answer})
    chapter = replace(CHAPTER, _items={**CHAPTER._items, item: (revised, CHAPTER.lesson_of(item))})
    restored = TeachingLoop.resume(chapter, "s1", [], events)
    assert restored.tutor._last_graded.outcome == Outcome.PARTIAL
    assert restored.tutor.state.unproductive_turns == 0


def test_a_correct_answer_after_a_verbal_reason_is_extracted_not_misgraded_from_the_first_number():
    from cavat.core.pedagogy import Outcome

    raw = "Con làm bước 1: vì có một chữ số sau dấu phẩy nên con viết 31/10 ạ"
    r = RecordedReader({1: Reading("PASS", answer="31/10", source="LLM")})
    t = tutor(r)
    turn = t.on_student(raw, dialogue_version=3)
    assert t._last_graded.outcome == Outcome.CORRECT and turn.resolved
    assert any(e.type == EventType.EXPLANATION_SUBMITTED for e in t.events)


def test_listener_cannot_invent_a_correct_answer_the_child_never_gave():
    r = RecordedReader({1: Reading("PASS", answer="31/10", source="LLM")})
    t = tutor(r)
    turn = t.on_student("con viết 99/10 cô ạ", dialogue_version=3)
    assert not turn.resolved and t._last_graded.outcome.value != "CORRECT"


def test_repeated_ambiguous_no_without_provider_teaches_instead_of_asking_forever():
    t = tutor(LiveReader(None, semantic=True))
    assert t.on_student("không", dialogue_version=3).move == Move.ASK_CONFIRM
    second = t.on_student("không", dialogue_version=3)
    assert second.move == Move.EXPLAIN and not second.resolved
    assert t.state.unproductive_turns == 0
    assert (
        t.state.max_hint_level == 2
    )  # conceptual help is recorded, never independent credit for helped work


def test_a_correct_theoretical_point_can_be_acknowledged_without_reusing_a_stale_wrong_grade():
    from cavat.core.pedagogy import Outcome
    from cavat.modules.assessment.math_checker import CheckResult
    from cavat.modules.tutor.validator import wrong_praise

    t = tutor(None)
    ctx = RenderContext(
        decision=PolicyDecision(Move.EXPLAIN, reason_codes=("CONVERSATION", "REPAIR")),
        item=ITEM,
        package=PKG,
        state=t.state,
        check=CheckResult(Outcome.WRONG),
    )
    assert wrong_praise("Đúng rồi, mẫu số cho biết số phần bằng nhau.", ctx) is None


@pytest.mark.parametrize(
    "wrong",
    [
        "Trong tam giác vuông có một đường cao nằm ngoài tam giác.",
        "Tam giác nhọn có đường cao nằm ngoài tam giác.",
        "Mọi đường cao của tam giác tù đều nằm ngoài tam giác.",
    ],
)
def test_shape_conditions_cannot_be_swapped_by_a_fluent_confirmation(wrong):
    from cavat.modules.tutor.brain import math_errors

    assert math_errors(wrong)


@pytest.mark.parametrize(
    "correct",
    [
        "Đường cao từ đỉnh góc tù luôn nằm trong tam giác.",
        "Trong tam giác tù, đường cao từ đỉnh có góc tù ở trong, còn hai đường cao khác ở ngoài.",
        "Mọi đường cao của tam giác nhọn nằm trong, còn tam giác tù có hai đường cao ở ngoài.",
    ],
)
def test_geometry_guard_keeps_vertex_conditions_and_contrasting_clauses(correct):
    from cavat.modules.tutor.brain import math_errors

    assert not math_errors(correct)
