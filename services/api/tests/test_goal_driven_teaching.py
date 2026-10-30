"""Teaching is authored from the objective, not a compulsory RAG/sample-question script."""

import json

import pytest
from cavat.core.events import EventType
from cavat.modules.ai_gateway.base import MODEL_WAIT_MESSAGE
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.decimal_facts import claim_errors, notation_facts
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.loop import TeachingLoop
from cavat.modules.tutor.reader import Reading, RecordedReader
from test_brain2 import small_index
from test_brain4 import OK
from test_grounded import CHAPTER, NOW

QUESTION = "Bảy phần mười viết thành số thập phân nào con?"
EXPLANATION = "Hai phần mười được viết là 0,2. "


def output(text):
    return {"message": text, "safety_flag": False, "policy_feedback": ""}


ENTRY_OK = {**OK, "recall_explains_knowledge": True, "plan_names_practice": True}


def opening_output(text):
    return {
        **output(text),
        "knowledge_recall": "Mình nhớ lại: phần mười là một trong mười phần bằng nhau.",
        "practice_plan": "Hôm nay mình ôn cách viết phần mười thành số thập phân.",
    }


def test_generated_opening_does_not_receive_the_teacher_sample_question_or_accepted_phrases():
    node = CHAPTER.nodes[0]
    provider = FakeChatModel([opening_output(EXPLANATION + QUESTION), ENTRY_OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    turn = loop.start(NOW)
    request = provider.calls[0][1]
    assert node.theory[0].ask not in request.messages[1].content
    assert "DẠY THEO MỤC TIÊU" in request.messages[1].content
    assert turn.prompt == QUESTION and turn.messages[-1].source == "LLM"
    assert loop._dynamic_theory()
    restored = TeachingLoop.resume(CHAPTER, "synthetic", [], loop.events)
    assert restored._prompt == QUESTION and restored._dynamic_theory()


def test_short_answer_is_read_against_actual_generated_question_without_sample_reply():
    provider = FakeChatModel(
        [opening_output(EXPLANATION + QUESTION), ENTRY_OK, {"answered": True, "quote": "0,7"}]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    loop.start(NOW)
    variant = CHAPTER.node(loop._node).theory[0]
    assert loop._theory_by_meaning(variant, "0,7", None) is True
    context = json.loads(provider.calls[-1][1].messages[1].content)
    assert context["cau_hoi_thuc_te"] == QUESTION
    assert "cau_mau" not in context and "accept" not in context


def test_new_concrete_question_after_repair_survives_restore_without_grades():
    followup = "Nếu có ba phần mười, con viết số thập phân nào?"
    provider = FakeChatModel(
        [opening_output(EXPLANATION + QUESTION), ENTRY_OK, output(EXPLANATION + followup), OK]
    )
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    loop = TeachingLoop(CHAPTER, "synthetic", speaker=speaker)
    first = loop.start(NOW)
    loop.go_live(reader=RecordedReader({1: Reading("REPAIR", focus="muốn ví dụ dễ hơn")}), speaker=speaker)
    turn = loop.on_student("là sao", NOW)
    assert turn.prompt == followup and turn.awaiting == first.awaiting and turn.node_id == first.node_id
    assert not any(
        e.event_type in (EventType.NODE_DECISION, EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED)
        for e in turn.events
    )
    restored = TeachingLoop.resume(CHAPTER, "synthetic", [], loop.events)
    assert restored._prompt == followup and restored._dynamic_theory()


def test_unavailable_generation_does_not_present_raw_rag_as_a_teacher_response():
    provider = FakeChatModel([])
    speaker = GroundedSpeaker(
        small_index(), AIRouter(chat_provider=provider, max_calls_per_session=0), allow_knowledge=True
    )
    turn = TeachingLoop(CHAPTER, "synthetic", speaker=speaker).start(NOW)
    assert CHAPTER.nodes[0].theory[0].ask not in turn.messages[-1].text
    assert CHAPTER.nodes[0].theory[0].text not in turn.messages[-1].text
    assert turn.messages[-1].text == MODEL_WAIT_MESSAGE


def test_opening_can_teach_examples_named_in_objective_but_not_answer_its_new_question():
    node = CHAPTER.nodes[0].model_copy(
        update={"description": "Bé nhận ra 3/10 viết thành 0,3. Bé viết được số thập phân đơn giản."}
    )
    safe = "Ba phần mười viết là 0,3. Con viết 7/10 thành số thập phân nào?"
    leaked = "Ba phần mười viết là 0,3. Con viết 3/10 thành số thập phân nào?"
    provider = FakeChatModel([opening_output(leaked), opening_output(safe), ENTRY_OK])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    result = speaker.lesson_opening(node, node.theory[0].text, session_entry=True)
    assert result.source == "LLM" and safe in result.text
    assert "ANSWER_LEAK" in result.rejected[0]


@pytest.mark.parametrize(
    "text",
    [
        "Mẫu số có mấy chữ số 0 thì phần thập phân có chính xác mấy chữ số 0 đó.",
        "Mẫu số có bao nhiêu chữ số 0 thì phần thập phân có bấy nhiêu chữ số 0.",
        "0,01 có hai chữ số 0.",
    ],
)
def test_zero_count_is_not_the_decimal_place_count(text):
    assert claim_errors(text)


def test_notation_facts_keep_written_zeroes_and_correct_statements():
    assert not claim_errors("Mẫu số có hai chữ số 0 thì phần thập phân có hai chữ số.")
    facts = notation_facts("0,01 và 0,200")
    assert [(x["so_chu_so_sau_dau_phay"], x["so_chu_so_0_trong_phan_thap_phan"]) for x in facts] == [
        (2, 1),
        (3, 2),
    ]


def test_checked_master_answer_is_delivered_without_a_weaker_compulsory_rewrite():
    from cavat.modules.ai_gateway.base import ModelClass
    from cavat.modules.teaching.author import write_lesson
    from cavat.modules.tutor.brain import BrainPack

    provider = FakeChatModel({"master": [output(EXPLANATION + QUESTION)], "review": [OK], "main": []})
    router = AIRouter(
        chat_provider=provider,
        chains={
            ModelClass.TUTOR_MENTOR: ("master",),
            ModelClass.EVAL_JUDGE: ("review",),
            ModelClass.TUTOR_REASONING: ("main",),
        },
    )
    result = write_lesson(
        router,
        BrainPack(
            task="Giảng một ví dụ theo mục tiêu", question="Số thập phân", prefer_mentor=True, max_words=80
        ),
        calls_used=0,
        questions="required",
    )
    assert result.text == EXPLANATION + QUESTION and result.model == "master"
    assert [m for m, _ in provider.calls] == ["master", "review"]


def test_understanding_rejects_an_invented_student_quote():
    provider = FakeChatModel([{"answered": True, "quote": "0,7"}])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), allow_knowledge=True)
    assert speaker.theory_understanding("con chưa biết", asked=QUESTION, node=CHAPTER.nodes[0]) is False


def test_unavailable_master_does_not_consume_one_of_the_two_actual_drafts():
    from cavat.modules.ai_gateway.base import ModelClass, QuotaExceeded
    from cavat.modules.teaching.author import write_lesson
    from cavat.modules.tutor.brain import BrainPack

    provider = FakeChatModel(
        {
            "master": [QuotaExceeded("limit")],
            "main": [output("Con thử nhé? Con biết chưa?"), output(EXPLANATION + QUESTION)],
            "review": [OK],
        }
    )
    router = AIRouter(
        chat_provider=provider,
        chains={
            ModelClass.TUTOR_MENTOR: ("master",),
            ModelClass.TUTOR_REASONING: ("main",),
            ModelClass.EVAL_JUDGE: ("review",),
        },
    )
    result = write_lesson(
        router,
        BrainPack(task="Giảng ví dụ", question="Số thập phân", prefer_mentor=True, max_words=80),
        calls_used=0,
        questions="required",
    )
    assert result.text == EXPLANATION + QUESTION
    assert [m for m, _ in provider.calls] == ["master", "main", "main", "review"]
