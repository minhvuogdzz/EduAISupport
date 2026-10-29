"""Tutor conversation improvements must respect the configured grade-five curriculum."""

import httpx
import pytest
from cavat.core.events import EventType
from cavat.modules.ai_gateway.fake import FakeChatModel
from cavat.modules.ai_gateway.router import AIRouter
from cavat.modules.teaching.grounded import GroundedSpeaker
from cavat.modules.teaching.search_web import SearchEducation
from cavat.modules.tutor.reader import Reading, RecordedReader
from test_brain2 import small_index
from test_grounded import NOW, loop_at_theory


def test_frustrated_student_gets_explanation_without_server_repeating_question():
    provider = FakeChatModel(
        [
            {"message": "Imagine une tarte.", "safety_flag": False, "policy_feedback": ""},
        ]
    )
    # No provider needed: the fallback still must respect an explicit request to stop asking.
    speaker = GroundedSpeaker(
        small_index(), AIRouter(chat_provider=provider, max_calls_per_session=0), allow_knowledge=True
    )
    loop, first = loop_at_theory(speaker)
    loop.go_live(
        reader=RecordedReader({1: Reading("REPAIR", focus="cần giải thích trực tiếp")}), speaker=speaker
    )
    turn = loop.on_student("Con nói không hiểu rồi, sao cứ hỏi hoài vậy?", NOW)
    assert "?" not in turn.messages[-1].text
    assert (turn.awaiting, turn.prompt) == (first.awaiting, first.prompt)
    assert not provider.calls


def test_multi_turn_confusion_then_correct_reply_preserves_evidence_and_progression():
    from cavat.modules.teaching.loop import TeachingLoop
    from cavat.modules.tutor.reader import LiveReader

    provider = FakeChatModel([])
    speaker = GroundedSpeaker(
        small_index(), AIRouter(chat_provider=provider, max_calls_per_session=0), allow_knowledge=True
    )
    loop, first = loop_at_theory(speaker)
    loop.go_live(reader=LiveReader(None, semantic=True), speaker=speaker)
    for said in ("Con chưa hiểu", "Con vẫn chưa hiểu", "Giải thích trực tiếp, đừng hỏi con nữa"):
        turn = loop.on_student(said, NOW)
        assert (turn.awaiting, turn.node_id, turn.prompt) == (first.awaiting, first.node_id, first.prompt)
        assert not any(
            e.event_type in {EventType.ANSWER_SUBMITTED, EventType.RETELL_JUDGED, EventType.NODE_DECISION}
            for e in turn.events
        )
    assert "?" not in turn.messages[-1].text
    restored = TeachingLoop.resume(loop.chapter, "s1", [], loop.events)
    restored.go_live(reader=LiveReader(None, semantic=True), speaker=speaker)
    variant = next(v for v in restored.chapter.node(first.node_id).theory if v.ask == first.prompt)
    correct = restored.on_student(variant.accept[0], NOW)
    assert (correct.awaiting, correct.prompt) != (first.awaiting, first.prompt)
    assert not provider.calls


@pytest.mark.parametrize(
    "question",
    [
        "Cho con ví dụ ứng dụng AI mới nhất trong y tế năm nay.",
        "Thủ đô Việt Nam là gì?",
        "Tại sao chuyển vế lại đổi dấu?",
        "Mẫu số có ứng dụng AI y tế mới nhất không?",
    ],
)
def test_outside_curriculum_never_reaches_web_or_open_domain_answer(question):
    calls = []
    web = SearchEducation(
        api_key="test",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: calls.append(request) or httpx.Response(500))
        ),
    )
    provider = FakeChatModel([{"concept": ""}])
    speaker = GroundedSpeaker(small_index(), AIRouter(chat_provider=provider), web=web, allow_knowledge=True)
    turn = speaker.answer(question, node_id="eq", pending=None)
    assert turn.kind == "PARKED" and not calls
    assert all(request.schema_name != "grounded_turn" for _, request in provider.calls)
    assert not hasattr(web, "lookup_current")


@pytest.mark.parametrize("query", ["AI trong y tế", "thủ đô", "chuyển vế", "thể tích hình tròn"])
def test_search_service_only_accepts_canonical_lesson_concepts(query):
    calls = []
    web = SearchEducation(
        api_key="test",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: calls.append(request) or httpx.Response(500))
        ),
    )
    assert web.lookup(query) is None and not calls
